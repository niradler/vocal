import asyncio
import importlib.util
import io
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np

from ...config import optional_dependency_install_hint, vocal_settings
from .base import AudioFormat, TTSAdapter, TTSCapabilities, TTSResult, Voice

logger = logging.getLogger(__name__)

SUPERTONIC_AVAILABLE = importlib.util.find_spec("supertonic") is not None

SUPERTONIC_VOICES = tuple(f"{gender}{index}" for gender in ("M", "F") for index in range(1, 6))
_VOICE_NAME = re.compile(r"^[MF][1-5]$")
SUPERTONIC_LANGUAGES = (
    "en",
    "ko",
    "ja",
    "ar",
    "bg",
    "cs",
    "da",
    "de",
    "el",
    "es",
    "et",
    "fi",
    "fr",
    "hi",
    "hr",
    "hu",
    "id",
    "it",
    "lt",
    "lv",
    "nl",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "sv",
    "tr",
    "uk",
    "vi",
)


def _has_onnx_weights(model_path: Path) -> bool:
    return (model_path / "onnx" / "vocoder.onnx").is_file()


class SupertonicTTSAdapter(TTSAdapter):
    def __init__(self) -> None:
        self.model: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self.sample_rate: int = 44100

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not SUPERTONIC_AVAILABLE:
            raise ImportError(optional_dependency_install_hint("supertonic", "supertonic==1.3.1"))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path)

    def _load_sync(self, model_path: Path) -> None:
        from supertonic import TTS

        self.model_path = model_path
        self.device = "cpu"
        if _has_onnx_weights(model_path):
            logger.info("Loading Supertonic 3 from %s", model_path)
            self.model = TTS(model="supertonic-3", model_dir=model_path, auto_download=False)
        else:
            logger.info("Supertonic weights not in %s; downloading supertonic-3", model_path)
            self.model = TTS(model="supertonic-3", auto_download=True)
        self.sample_rate = int(self.model.sample_rate)
        logger.info("Supertonic 3 loaded (sr=%d)", self.sample_rate)

    async def unload_model(self) -> None:
        self.model = None
        self.model_path = None

    def is_loaded(self) -> bool:
        return self.model is not None

    def get_model_info(self) -> dict:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "sample_rate": self.sample_rate,
            "loaded": self.is_loaded(),
            "backend": "supertonic",
        }

    def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_streaming=False,
            supports_voice_list=True,
            supports_voice_clone=False,
            supports_voice_design=False,
            requires_gpu=False,
            voice_mode="voice_id",
        )

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = AudioFormat.WAV,
        language: str | None = None,
        **kwargs,
    ) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")
        if output_format != AudioFormat.WAV:
            raise ValueError(f"Supertonic only supports WAV output. Requested: '{output_format}'. Convert the result yourself if another format is needed.")

        voice_name = voice or "M1"
        if not _VOICE_NAME.fullmatch(voice_name):
            raise ValueError(f"Unknown Supertonic voice '{voice_name}'. Available voices: {', '.join(SUPERTONIC_VOICES)}")

        language_id = (language or "en").lower().split("-")[0]
        if language_id not in SUPERTONIC_LANGUAGES:
            raise ValueError(f"Unsupported Supertonic language '{language_id}'. Supported languages: {', '.join(SUPERTONIC_LANGUAGES)}")

        loop = asyncio.get_running_loop()
        audio_bytes, duration = await loop.run_in_executor(None, self._synthesize_sync, text, voice_name, speed, language_id)
        return TTSResult(audio_data=audio_bytes, sample_rate=self.sample_rate, duration=duration, format=AudioFormat.WAV)

    def _synthesize_sync(self, text: str, voice_name: str, speed: float, language_id: str) -> tuple[bytes, float]:
        import soundfile as sf

        style = self.model.get_voice_style(voice_name)
        wav, duration = self.model.synthesize(text, voice_style=style, speed=speed, lang=language_id)
        audio = np.asarray(wav).squeeze()
        seconds = float(np.asarray(duration).reshape(-1)[0])
        buf = io.BytesIO()
        sf.write(buf, audio, self.sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue(), seconds

    async def get_voices(self) -> list[Voice]:
        language = vocal_settings.DEFAULT_LANGUAGE
        return [Voice(id=name, name=name, language=language) for name in SUPERTONIC_VOICES]
