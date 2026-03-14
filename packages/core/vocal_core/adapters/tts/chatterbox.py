import asyncio
import importlib.util
import io
import logging
from pathlib import Path
from typing import Any

from ...config import optional_dependency_install_hint, vocal_settings
from .base import AudioFormat, TTSAdapter, TTSCapabilities, TTSResult, Voice, VoiceCloneRequest

logger = logging.getLogger(__name__)

CHATTERBOX_AVAILABLE = importlib.util.find_spec("chatterbox") is not None


class ChatterboxTTSAdapter(TTSAdapter):
    """
    Chatterbox TTS adapter — zero-shot voice cloning, emotion exaggeration control.

    Supports both standard synthesis and reference-audio voice cloning.
    Requires: pip install chatterbox-tts torchaudio
    """

    def __init__(self) -> None:
        self.model: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self.sample_rate: int = 24000

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not CHATTERBOX_AVAILABLE:
            raise ImportError(optional_dependency_install_hint("chatterbox", "chatterbox-tts"))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch
        from chatterbox.tts import ChatterboxTTS

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        self.device = resolved

        logger.info("Loading Chatterbox TTS model from %s on %s", model_path, resolved)
        path_str = str(model_path)
        self.model = ChatterboxTTS.from_pretrained(path_str, device=resolved)
        self.sample_rate = self.model.sr
        self.model_path = model_path
        logger.info("Chatterbox TTS model loaded on %s (sr=%d)", resolved, self.sample_rate)

    async def unload_model(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
            self.model_path = None
            if self.device == "cuda":
                try:
                    import torch

                    torch.cuda.empty_cache()
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return self.model is not None

    def get_model_info(self) -> dict:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "sample_rate": self.sample_rate,
            "loaded": self.is_loaded(),
            "backend": "chatterbox",
        }

    def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_streaming=False,
            supports_voice_list=False,
            supports_voice_clone=True,
            supports_voice_design=False,
            requires_gpu=False,
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
        output_format: str = AudioFormat.WAV,
        exaggeration: float | None = None,
        cfg_weight: float | None = None,
        **kwargs,
    ) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if output_format != AudioFormat.WAV:
            raise ValueError(f"Chatterbox only supports WAV output. Requested: '{output_format}'. Convert the result yourself if another format is needed.")

        exaggeration = exaggeration if exaggeration is not None else vocal_settings.CHATTERBOX_EXAGGERATION
        cfg_weight = cfg_weight if cfg_weight is not None else vocal_settings.CHATTERBOX_CFG_WEIGHT
        loop = asyncio.get_running_loop()
        audio_bytes, duration = await loop.run_in_executor(None, self._synthesize_sync, text, None, exaggeration, cfg_weight)
        return TTSResult(audio_data=audio_bytes, sample_rate=self.sample_rate, duration=duration, format=AudioFormat.WAV)

    async def clone_synthesize(self, request: VoiceCloneRequest) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        output_format = request.output_format if request.output_format else AudioFormat.WAV
        if output_format != AudioFormat.WAV:
            raise ValueError(f"Chatterbox only supports WAV output. Requested: '{output_format}'. Convert the result yourself if another format is needed.")

        exaggeration = vocal_settings.CHATTERBOX_EXAGGERATION
        cfg_weight = vocal_settings.CHATTERBOX_CFG_WEIGHT
        loop = asyncio.get_running_loop()
        audio_bytes, duration = await loop.run_in_executor(None, self._synthesize_sync, request.text, request.reference_audio_path, exaggeration, cfg_weight)
        return TTSResult(audio_data=audio_bytes, sample_rate=self.sample_rate, duration=duration, format=AudioFormat.WAV)

    def _synthesize_sync(
        self,
        text: str,
        audio_prompt_path: str | None,
        exaggeration: float,
        cfg_weight: float,
    ) -> tuple[bytes, float]:
        import torchaudio

        kwargs: dict = {"exaggeration": exaggeration, "cfg_weight": cfg_weight}
        if audio_prompt_path:
            kwargs["audio_prompt_path"] = audio_prompt_path

        wav = self.model.generate(text, **kwargs)
        duration = wav.shape[-1] / self.sample_rate

        buf = io.BytesIO()
        torchaudio.save(buf, wav, self.sample_rate, format=AudioFormat.WAV)
        return buf.getvalue(), duration

    async def get_voices(self) -> list[Voice]:
        return [Voice(id="default", name="Default", language=vocal_settings.DEFAULT_LANGUAGE)]
