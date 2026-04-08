import asyncio
import importlib.util
import json
import logging
import os
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from ...config import optional_dependency_install_hint
from .base import TTSAdapter, TTSCapabilities, TTSResult, Voice
from .piper import SUPPORTED_FORMATS, _convert_audio

logger = logging.getLogger(__name__)

QWEN3_OMNI_TTS_AVAILABLE: bool = (
    importlib.util.find_spec("transformers") is not None
    and importlib.util.find_spec("torch") is not None
    and importlib.util.find_spec("qwen_omni_utils") is not None
)

_SPEAKERS = ["Ethan", "Chelsie"]


def _detect_omni_generation(model_path: Path) -> str:
    """Detect whether this is a Qwen2.5-Omni or Qwen3-Omni model."""
    cfg_file = model_path / "config.json"
    if cfg_file.exists():
        with open(cfg_file) as f:
            model_type = json.load(f).get("model_type", "")
        if "qwen2_5_omni" in model_type or "qwen2.5" in model_type.lower():
            return "2.5"
    dir_lower = str(model_path).lower()
    if "qwen2.5" in dir_lower or "qwen2_5" in dir_lower:
        return "2.5"
    return "3"


class Qwen3OmniTTSAdapter(TTSAdapter):
    """Qwen-Omni TTS adapter using transformers.

    Supports both Qwen2.5-Omni and Qwen3-Omni models, auto-detecting
    the correct model class from config.json.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._processor: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self._sample_rate: int = 24000
        self._generation: str = "3"
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not QWEN3_OMNI_TTS_AVAILABLE:
            raise ImportError(
                optional_dependency_install_hint("qwen3-omni", "qwen-omni-utils")
            )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch

        from vocal_core.adapters._compat import apply_transformers_shims

        apply_transformers_shims()

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        dtype = torch.bfloat16 if resolved == "cuda" else torch.float32
        model_name = self._resolve_model_name(model_path)
        self._generation = _detect_omni_generation(model_path)

        logger.info("Loading Qwen%s-Omni TTS from %s on %s", self._generation, model_path, resolved)

        if self._generation == "2.5":
            from transformers import Qwen2_5OmniForConditionalGeneration, Qwen2_5OmniProcessor

            self._processor = Qwen2_5OmniProcessor.from_pretrained(model_name)
            self._model = Qwen2_5OmniForConditionalGeneration.from_pretrained(
                model_name,
                torch_dtype=dtype,
                device_map="auto",
            )
        else:
            from transformers import Qwen3OmniMoeForConditionalGeneration, Qwen3OmniMoeProcessor

            self._processor = Qwen3OmniMoeProcessor.from_pretrained(model_name)
            self._model = Qwen3OmniMoeForConditionalGeneration.from_pretrained(
                model_name,
                torch_dtype=dtype,
                device_map="auto",
            )

        self.model_path = model_path
        self.device = resolved
        logger.info("Qwen%s-Omni TTS loaded on %s", self._generation, resolved)

    @staticmethod
    def _resolve_model_name(model_path: Path) -> str:
        dir_name = model_path.name
        if "--" in dir_name:
            return dir_name.replace("--", "/", 1)
        return str(model_path)

    async def unload_model(self) -> None:
        self._model = None
        self._processor = None
        self.model_path = None
        self._executor.shutdown(wait=True)
        self._executor = ThreadPoolExecutor(max_workers=1)
        if self.device == "cuda":
            try:
                import torch

                torch.cuda.empty_cache()
            except Exception:
                pass

    def is_loaded(self) -> bool:
        return self._model is not None

    def get_model_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "loaded": self.is_loaded(),
            "backend": "qwen3_omni_tts",
            "sample_rate": self._sample_rate,
            "generation": self._generation,
        }
        if self.device == "cuda":
            try:
                import torch

                info["gpu_name"] = torch.cuda.get_device_name(0)
                info["vram_allocated_gb"] = torch.cuda.memory_allocated(0) / (1024**3)
            except Exception:
                pass
        return info

    def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_voice_list=True,
            requires_gpu=True,
            voice_mode="speaker_name",
        )

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "mp3",
        **kwargs,
    ) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if output_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{output_format}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}")

        speaker = voice or _SPEAKERS[0]
        loop = asyncio.get_running_loop()
        audio_array, sr = await loop.run_in_executor(self._executor, self._synthesize_sync, text, speaker)
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

    def _synthesize_sync(self, text: str, speaker: str) -> tuple[np.ndarray, int]:
        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                ],
            }
        ]

        text_input = self._processor.apply_chat_template(conversation, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(
            text=text_input,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to(self._model.device)

        text_ids, audio = self._model.generate(
            **inputs,
            max_new_tokens=512,
            speaker=speaker,
            return_audio=True,
        )

        audio_np = audio.reshape(-1).detach().cpu().numpy().astype(np.float32)
        max_val = np.abs(audio_np).max()
        if max_val > 1.0:
            audio_np = audio_np / max_val

        return audio_np, 24000

    async def get_voices(self) -> list[Voice]:
        return [
            Voice(id=name, name=name, language="en", gender=None)
            for name in _SPEAKERS
        ]


def _write_wav(path: str, audio: np.ndarray, sample_rate: int) -> None:
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes((audio * 32767).astype(np.int16).tobytes())


__all__ = ["Qwen3OmniTTSAdapter", "QWEN3_OMNI_TTS_AVAILABLE"]
