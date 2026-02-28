import asyncio
import logging
import os
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from .base import TTSAdapter, TTSResult, Voice
from .piper import SUPPORTED_FORMATS, _convert_audio

logger = logging.getLogger(__name__)

try:
    import faster_qwen3_tts as _fqt_module
    import torch

    FASTER_QWEN3_TTS_AVAILABLE = True
except ImportError:
    FASTER_QWEN3_TTS_AVAILABLE = False

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
            raise ImportError("faster-qwen3-tts is required. Install with: uv add faster-qwen3-tts")
        if not torch.cuda.is_available():
            raise RuntimeError("faster-qwen3-tts requires NVIDIA CUDA. No CUDA device detected. Use a Kokoro or Piper model for CPU-only inference.")

        self.model_path = model_path
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self._load_sync)

    def _load_sync(self) -> None:
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

        vram_gb = torch.cuda.memory_allocated(0) / (1024**3)
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"Qwen3-TTS loaded | variant={self._variant} | GPU={gpu_name} | VRAM={vram_gb:.2f}GB")

    async def unload_model(self) -> None:
        self._model = None
        self._executor.shutdown(wait=True)
        self._executor = ThreadPoolExecutor(max_workers=1)
        try:
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
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["vram_allocated_gb"] = torch.cuda.memory_allocated(0) / (1024**3)
        except Exception:
            pass
        return info

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
        loop = asyncio.get_event_loop()
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
            if not voice or not Path(voice).is_file():
                raise ValueError("Base Qwen3-TTS models require a reference audio file path as the 'voice' parameter. Use a CustomVoice variant (e.g. 'qwen3-tts-1.7b-custom') for predefined speakers.")
            audio_list, sr = self._model.generate_voice_clone(
                text=text,
                language=language,
                ref_audio=voice,
                ref_text="",
                xvec_only=True,
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
