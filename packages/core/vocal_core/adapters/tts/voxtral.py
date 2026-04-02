import logging
import os
from pathlib import Path
from typing import Any

import httpx

from .base import TTSAdapter, TTSCapabilities, TTSResult, Voice

logger = logging.getLogger(__name__)

VOXTRAL_TTS_AVAILABLE = True

# 20 preset voices from mistralai/Voxtral-4B-TTS-2603
_VOXTRAL_VOICES: list[Voice] = [
    Voice(id="casual_male", name="Casual Male", language="en", gender="male"),
    Voice(id="intense_male", name="Intense Male", language="en", gender="male"),
    Voice(id="mature_male", name="Mature Male", language="en", gender="male"),
    Voice(id="calm_male", name="Calm Male", language="en", gender="male"),
    Voice(id="military_male", name="Military Male", language="en", gender="male"),
    Voice(id="deep_male", name="Deep Male", language="en", gender="male"),
    Voice(id="pleasant_male", name="Pleasant Male", language="en", gender="male"),
    Voice(id="excited_male", name="Excited Male", language="en", gender="male"),
    Voice(id="articulate_male", name="Articulate Male", language="en", gender="male"),
    Voice(id="casual_female", name="Casual Female", language="en", gender="female"),
    Voice(id="intense_female", name="Intense Female", language="en", gender="female"),
    Voice(id="mature_female", name="Mature Female", language="en", gender="female"),
    Voice(id="calm_female", name="Calm Female", language="en", gender="female"),
    Voice(id="pleasant_female", name="Pleasant Female", language="en", gender="female"),
    Voice(id="excited_female", name="Excited Female", language="en", gender="female"),
    Voice(id="articulate_female", name="Articulate Female", language="en", gender="female"),
    Voice(id="engaging_female", name="Engaging Female", language="en", gender="female"),
    Voice(id="serene_female", name="Serene Female", language="en", gender="female"),
    Voice(id="confident_female", name="Confident Female", language="en", gender="female"),
    Voice(id="natural_female", name="Natural Female", language="en", gender="female"),
]

_DEFAULT_VOICE = "casual_male"
_VOXTRAL_TTS_MODEL_ID = "mistralai/Voxtral-4B-TTS-2603"


class VoxtralTTSAdapter(TTSAdapter):
    """
    Voxtral-4B-TTS adapter.

    Connects to a locally-running vLLM server serving Voxtral-4B-TTS-2603
    with the --omni flag:
        vllm serve mistralai/Voxtral-4B-TTS-2603 --omni

    The server URL is read from the VOXTRAL_TTS_URL environment variable
    (default: http://localhost:8080).

    License: CC BY-NC 4.0 (non-commercial use only).
    """

    def __init__(self) -> None:
        self.base_url: str = ""
        self._loaded: bool = False

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        self.base_url = os.environ.get("VOXTRAL_TTS_URL", "http://localhost:8080").rstrip("/")
        self._loaded = True
        logger.info("VoxtralTTSAdapter ready — connecting to vLLM at %s", self.base_url)

    async def unload_model(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def get_model_info(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "loaded": self._loaded,
            "backend": "voxtral_tts",
        }

    def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_voice_list=True,
            voice_mode="voice_id",
            requires_gpu=True,
        )

    async def get_voices(self) -> list[Voice]:
        return list(_VOXTRAL_VOICES)

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
            raise RuntimeError("Adapter not loaded. Call load_model() first.")

        selected_voice = voice or _DEFAULT_VOICE
        payload = {
            "model": _VOXTRAL_TTS_MODEL_ID,
            "input": text,
            "voice": selected_voice,
            "response_format": output_format,
            "speed": speed,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/audio/speech", json=payload)
            response.raise_for_status()
            audio_data = response.content

        return TTSResult(
            audio_data=audio_data,
            sample_rate=24000,
            duration=0.0,
            format=output_format,
        )
