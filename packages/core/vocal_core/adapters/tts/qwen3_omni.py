import importlib.util
import logging
from pathlib import Path
from typing import Any

import httpx

from ...config import vocal_settings
from .._qwen_omni import OMNI_SPEAKERS, SPEAKER_GENDERS, detect_omni_generation
from .base import TTSAdapter, TTSCapabilities, TTSResult, Voice

logger = logging.getLogger(__name__)

# The proxy only needs httpx (a base dependency); the model itself runs in the
# external vLLM-Omni / SGLang-Omni engine, not in this process.
QWEN3_OMNI_TTS_AVAILABLE: bool = importlib.util.find_spec("httpx") is not None

# Qwen-Omni's talker emits 24 kHz mono audio.
_OMNI_SAMPLE_RATE = 24000


class Qwen3OmniTTSAdapter(TTSAdapter):
    """Qwen-Omni TTS served by vLLM-Omni / SGLang-Omni.

    The transformers in-process talker path is broken on transformers 5.18+
    (``GenerationMixin.generate`` drops the all-1s attention mask the talker
    needs for its codec/embedding prefill), so — like the other omni TTS models
    in the catalog (Higgs, Drama-3) — Qwen-Omni speech is produced by the
    vLLM-Omni / SGLang-Omni engine and Vocal proxies ``/v1/audio/speech`` to it.

    Run the engine against the same checkpoint, e.g.::

        vllm serve Qwen/Qwen2.5-Omni-3B --omni

    The engine URL is read from ``QWEN_OMNI_TTS_URL`` (default
    ``http://localhost:8080``). Built-in speakers: Qwen2.5-Omni -> Ethan,
    Chelsie; Qwen3-Omni -> Ethan, Chelsie, Aiden.
    """

    def __init__(self) -> None:
        self.base_url: str = ""
        self._loaded: bool = False
        self._model_id: str = ""
        self._generation: str = "3"

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        self.base_url = vocal_settings.QWEN_OMNI_TTS_URL.rstrip("/")
        self._model_id = self._resolve_model_id(model_path)
        self._generation = detect_omni_generation(model_path)
        self._loaded = True
        logger.info(
            "Qwen3OmniTTSAdapter ready — proxying Qwen%s-Omni (%s) to vLLM-Omni at %s",
            self._generation,
            self._model_id,
            self.base_url,
        )

    @staticmethod
    def _resolve_model_id(model_path: Path) -> str:
        name = Path(model_path).name
        return name.replace("--", "/", 1) if "--" in name else name

    async def unload_model(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def get_model_info(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "loaded": self._loaded,
            "backend": "qwen3_omni_tts",
            "model_id": self._model_id,
            "generation": self._generation,
            "sample_rate": _OMNI_SAMPLE_RATE,
        }

    def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_voice_list=True,
            requires_gpu=True,
            voice_mode="voice_id",
        )

    def validate_voice(self, voice: str | None) -> None:
        """Reject speakers this checkpoint's talker does not know."""
        if not voice:
            return
        speakers = OMNI_SPEAKERS[self._generation]
        if voice not in speakers:
            raise ValueError(f"Unknown speaker '{voice}' for Qwen{self._generation}-Omni. Available speakers: {', '.join(speakers)}")

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "mp3",
        **kwargs,
    ) -> TTSResult:
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        speaker = voice or OMNI_SPEAKERS[self._generation][0]
        self.validate_voice(speaker)
        payload = {
            "model": self._model_id,
            "input": text,
            "voice": speaker,
            "response_format": output_format,
            "speed": speed,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/v1/audio/speech", json=payload)
            response.raise_for_status()
            audio_data = response.content

        return TTSResult(
            audio_data=audio_data,
            sample_rate=_OMNI_SAMPLE_RATE,
            duration=0.0,
            format=output_format,
        )

    async def get_voices(self) -> list[Voice]:
        return [Voice(id=name, name=name, language="en", gender=SPEAKER_GENDERS.get(name)) for name in OMNI_SPEAKERS[self._generation]]


__all__ = ["Qwen3OmniTTSAdapter", "QWEN3_OMNI_TTS_AVAILABLE"]
