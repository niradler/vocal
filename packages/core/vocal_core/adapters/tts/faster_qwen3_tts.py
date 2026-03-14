import asyncio
import importlib.util
import logging
import os
import tempfile
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from ...config import optional_dependency_install_hint
from .base import TTSAdapter, TTSCapabilities, TTSResult, Voice, VoiceCloneRequest
from .piper import SUPPORTED_FORMATS, _convert_audio

logger = logging.getLogger(__name__)

FASTER_QWEN3_TTS_AVAILABLE: bool = importlib.util.find_spec("faster_qwen3_tts") is not None and importlib.util.find_spec("torch") is not None

_QWEN3_PATCHES_APPLIED = False


def _patch_talker_config() -> None:
    try:
        from qwen_tts.core.models.configuration_qwen3_tts import Qwen3TTSTalkerConfig as _TalkerConfig

        if not hasattr(_TalkerConfig, "pad_token_id"):
            _TalkerConfig.pad_token_id = None
    except (ImportError, AttributeError):
        pass


def _patch_tokenizers_backend() -> None:
    try:
        from transformers.tokenization_utils_tokenizers import TokenizersBackend as _TBK

        _orig_init = _TBK.__init__

        def _patched_init(self, *args, **kwargs):
            kwargs.pop("fix_mistral_regex", None)
            _orig_init(self, *args, **kwargs)

        _TBK.__init__ = _patched_init
    except (ImportError, AttributeError):
        pass


def _patch_static_layer() -> None:
    try:
        from transformers.cache_utils import StaticLayer as _SL

        _orig_lazy_init = _SL.lazy_initialization

        def _patched_lazy_init(self, key_states, value_states=None):
            if value_states is None:
                value_states = key_states
            return _orig_lazy_init(self, key_states, value_states)

        _SL.lazy_initialization = _patched_lazy_init
    except (ImportError, AttributeError):
        pass


def _patch_dynamic_cache() -> None:
    try:
        from transformers.cache_utils import DynamicCache as _DC

        if not hasattr(_DC, "__getitem__"):

            def _dc_getitem(self, layer_idx):
                layer = self.layers[layer_idx]
                return layer.keys, layer.values

            _DC.__getitem__ = _dc_getitem
    except (ImportError, AttributeError):
        pass


def _apply_qwen3_patches() -> None:
    global _QWEN3_PATCHES_APPLIED
    if _QWEN3_PATCHES_APPLIED:
        return

    from vocal_core.adapters._compat import apply_transformers_shims

    apply_transformers_shims()

    _patch_talker_config()
    _patch_tokenizers_backend()
    _patch_static_layer()
    _patch_dynamic_cache()

    _QWEN3_PATCHES_APPLIED = True


LANGUAGE_MAP: dict[str, str] = {
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "ru": "Russian",
    "pt": "Portuguese",
    "es": "Spanish",
    "it": "Italian",
}


def _to_full_language(lang: str) -> str:
    return LANGUAGE_MAP.get(lang.lower(), lang.title())


def _concat_audio_arrays(audio_list: list) -> np.ndarray:
    arrays = []
    for a in audio_list:
        if hasattr(a, "cpu"):
            arrays.append(a.flatten().cpu().numpy())
        else:
            arrays.append(np.asarray(a).flatten())
    return np.concatenate(arrays) if arrays else np.zeros(0, dtype=np.float32)


class FasterQwen3TTSAdapter(TTSAdapter):
    def __init__(self):
        self._model: Any = None
        self.model_path: Path | None = None
        self._variant: str = "base"
        self._sample_rate: int = 24000
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not FASTER_QWEN3_TTS_AVAILABLE:
            raise ImportError(optional_dependency_install_hint("qwen3-tts", "faster-qwen3-tts"))
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("faster-qwen3-tts requires NVIDIA CUDA. No CUDA device detected. Use a Kokoro or Piper model for CPU-only inference.")

        self.model_path = model_path
        # CUDA graph capture during warmup requires a larger thread stack than the
        # Windows default (1 MB). Set 64 MB before the executor spawns its thread,
        # then restore the OS default so other parts of the program are unaffected.
        prev_stack = threading.stack_size(64 * 1024 * 1024)
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(self._executor, self._load_sync)
        finally:
            threading.stack_size(prev_stack)

    def _load_sync(self) -> None:
        _apply_qwen3_patches()
        import faster_qwen3_tts as _fqt_module

        logger.info(f"Loading Qwen3-TTS from {self.model_path} ...")
        self._model = _fqt_module.FasterQwen3TTS.from_pretrained(str(self.model_path))

        try:
            self._variant = self._model.model.model.tts_model_type or "base"
        except AttributeError:
            path_lower = str(self.model_path).lower()
            if "customvoice" in path_lower or "custom" in path_lower:
                self._variant = "custom_voice"
            elif "voicedesign" in path_lower or "design" in path_lower:
                self._variant = "voice_design"
            else:
                self._variant = "base"

        import torch

        vram_gb = torch.cuda.memory_allocated(0) / (1024**3)
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"Qwen3-TTS loaded | variant={self._variant} | GPU={gpu_name} | VRAM={vram_gb:.2f}GB")

    async def unload_model(self) -> None:
        self._model = None
        self._executor.shutdown(wait=True)
        self._executor = ThreadPoolExecutor(max_workers=1)
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:
            pass

    def is_loaded(self) -> bool:
        return self._model is not None

    def get_model_info(self) -> dict:
        if not self.is_loaded():
            return {"status": "not_loaded"}
        info: dict = {
            "status": "loaded",
            "variant": self._variant,
            "model_path": str(self.model_path),
            "sample_rate": self._sample_rate,
            "device": "cuda",
        }
        try:
            import torch

            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["vram_allocated_gb"] = torch.cuda.memory_allocated(0) / (1024**3)
        except Exception:
            pass
        return info

    def get_capabilities(self) -> TTSCapabilities:
        if self._variant == "custom_voice":
            return TTSCapabilities(
                supports_voice_list=True,
                requires_gpu=True,
                voice_mode="voice_id",
            )
        if self._variant == "voice_design":
            return TTSCapabilities(
                supports_voice_design=True,
                requires_gpu=True,
                voice_mode="instruction",
            )
        return TTSCapabilities(
            supports_voice_clone=True,
            requires_gpu=True,
            clone_mode="reference_audio",
            reference_audio_min_seconds=3.0,
            reference_audio_max_seconds=30.0,
        )

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "mp3",
        language: str | None = None,
        **kwargs,
    ) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if output_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{output_format}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}")

        lang = _to_full_language(language or "en")
        loop = asyncio.get_running_loop()
        audio_array, sr = await loop.run_in_executor(self._executor, self._synthesize_sync, text, voice, lang)
        self._sample_rate = sr

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            _write_wav(temp_path, audio_array, sr)
            with ThreadPoolExecutor(max_workers=1) as ex:
                audio_bytes, out_sr, duration = await loop.run_in_executor(ex, _convert_audio, temp_path, output_format)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        return TTSResult(audio_data=audio_bytes, sample_rate=out_sr, duration=duration, format=output_format)

    def _synthesize_sync(self, text: str, voice: str | None, language: str) -> tuple[np.ndarray, int]:
        assert self._model is not None

        if self._variant == "custom_voice":
            speaker = voice or self._default_speaker()
            audio_list, sr = self._model.generate_custom_voice(text=text, speaker=speaker, language=language)
        elif self._variant == "voice_design":
            instruct = voice or "Warm, clear narrator with neutral accent"
            audio_list, sr = self._model.generate_voice_design(text=text, instruct=instruct, language=language)
        else:
            raise ValueError("Base Qwen3-TTS models do not support /v1/audio/speech voice selection. Use /v1/audio/clone with reference_audio.")

        return _concat_audio_arrays(audio_list), sr

    async def clone_synthesize(self, request: VoiceCloneRequest) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")
        if self._variant != "base":
            raise ValueError("This Qwen3-TTS variant does not support reference-audio voice cloning.")
        if request.output_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{request.output_format}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}")

        language = _to_full_language(request.language or "en")
        loop = asyncio.get_running_loop()
        audio_array, sr = await loop.run_in_executor(self._executor, self._clone_sync, request, language)
        self._sample_rate = sr

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            _write_wav(temp_path, audio_array, sr)
            with ThreadPoolExecutor(max_workers=1) as ex:
                audio_bytes, out_sr, duration = await loop.run_in_executor(ex, _convert_audio, temp_path, request.output_format)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        return TTSResult(audio_data=audio_bytes, sample_rate=out_sr, duration=duration, format=request.output_format)

    def _clone_sync(self, request: VoiceCloneRequest, language: str) -> tuple[np.ndarray, int]:
        assert self._model is not None
        if not Path(request.reference_audio_path).is_file():
            raise ValueError("reference_audio must be a readable audio file.")

        reference_text = (request.reference_text or "").strip()
        audio_list, sr = self._model.generate_voice_clone(
            text=request.text,
            language=language,
            ref_audio=request.reference_audio_path,
            ref_text=reference_text,
            xvec_only=not bool(reference_text),
        )
        return _concat_audio_arrays(audio_list), sr

    def _default_speaker(self) -> str:
        try:
            spk_ids = self._model.model.model.config.talker_config.spk_id
            if spk_ids:
                return next(iter(spk_ids))
        except AttributeError:
            pass
        return "aiden"

    async def get_voices(self) -> list[Voice]:
        if not self.is_loaded():
            return []

        if self._variant == "custom_voice":
            try:
                spk_ids = self._model.model.model.config.talker_config.spk_id
                return [Voice(id=name, name=name.title(), language="en", gender=None) for name in spk_ids]
            except AttributeError:
                pass
            return [Voice(id="aiden", name="Aiden", language="en", gender=None)]

        if self._variant == "voice_design":
            return [
                Voice(
                    id="Warm, clear narrator with neutral accent",
                    name="Custom (pass instruct as voice)",
                    language="en",
                    gender=None,
                )
            ]

        return []


def _write_wav(path: str, audio: np.ndarray, sample_rate: int) -> None:
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes((audio * 32767).astype(np.int16).tobytes())


__all__ = ["FasterQwen3TTSAdapter", "FASTER_QWEN3_TTS_AVAILABLE"]
