import asyncio
import importlib.util
import io
import logging
from pathlib import Path
from typing import Any

import numpy as np

from ...config import optional_dependency_install_hint
from .base import AudioFormat, TTSAdapter, TTSCapabilities, TTSResult, Voice, VoiceCloneRequest

logger = logging.getLogger(__name__)

VOXCPM_AVAILABLE = importlib.util.find_spec("voxcpm") is not None
VOXCPM_MODEL_ID = "openbmb/VoxCPM2"


class VoxCPMTTSAdapter(TTSAdapter):
    def __init__(self) -> None:
        self.model: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self.sample_rate: int = 48000

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not VOXCPM_AVAILABLE:
            raise ImportError(optional_dependency_install_hint("voxcpm", "voxcpm"))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch
        from voxcpm import VoxCPM

        if device == "auto":
            resolved = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            resolved = device
        self.device = resolved
        self.model_path = model_path
        local_ready = (model_path / "config.json").is_file()
        source = str(model_path) if local_ready else VOXCPM_MODEL_ID
        logger.info("Loading VoxCPM2 from %s on %s", source, resolved)
        self.model = VoxCPM.from_pretrained(
            source,
            load_denoiser=False,
            local_files_only=local_ready,
            optimize=resolved != "cpu",
            device=resolved,
        )
        self.sample_rate = int(self.model.tts_model.sample_rate)
        logger.info("VoxCPM2 loaded on %s (sr=%d)", resolved, self.sample_rate)

    async def unload_model(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
            self.model_path = None
            if self.device == "cuda":
                try:
                    import torch

                    torch.cuda.empty_cache()
                except Exception as exc:
                    logger.warning("Failed to clear CUDA cache during unload: %s", exc)

    def is_loaded(self) -> bool:
        return self.model is not None

    def get_model_info(self) -> dict:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "sample_rate": self.sample_rate,
            "loaded": self.is_loaded(),
            "backend": "voxcpm",
        }

    def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_streaming=False,
            supports_voice_list=False,
            supports_voice_clone=True,
            supports_voice_design=True,
            requires_gpu=True,
            clone_mode="reference_audio",
            voice_mode="instruction",
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
        **kwargs,
    ) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")
        if output_format != AudioFormat.WAV:
            raise ValueError(f"VoxCPM2 only supports WAV output. Requested: '{output_format}'. Convert the result yourself if another format is needed.")

        loop = asyncio.get_running_loop()
        audio_bytes, duration = await loop.run_in_executor(None, self._generate_sync, _with_instruction(text, voice), None, None)
        return TTSResult(audio_data=audio_bytes, sample_rate=self.sample_rate, duration=duration, format=AudioFormat.WAV)

    async def clone_synthesize(self, request: VoiceCloneRequest) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")
        output_format = request.output_format if request.output_format else AudioFormat.WAV
        if output_format != AudioFormat.WAV:
            raise ValueError(f"VoxCPM2 only supports WAV output. Requested: '{output_format}'. Convert the result yourself if another format is needed.")

        loop = asyncio.get_running_loop()
        audio_bytes, duration = await loop.run_in_executor(
            None,
            self._generate_sync,
            request.text,
            request.reference_audio_path,
            request.reference_text,
        )
        return TTSResult(audio_data=audio_bytes, sample_rate=self.sample_rate, duration=duration, format=AudioFormat.WAV)

    def _generate_sync(self, text: str, reference_wav_path: str | None, reference_text: str | None) -> tuple[bytes, float]:
        import soundfile as sf

        kwargs: dict[str, Any] = {"text": text, "cfg_value": 2.0, "inference_timesteps": 10}
        if reference_wav_path:
            kwargs["reference_wav_path"] = reference_wav_path
            if reference_text:
                kwargs["prompt_wav_path"] = reference_wav_path
                kwargs["prompt_text"] = reference_text
        wav = self.model.generate(**kwargs)
        audio = np.asarray(wav).squeeze()
        duration = float(audio.shape[-1]) / self.sample_rate
        buf = io.BytesIO()
        sf.write(buf, audio, self.sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue(), duration

    async def get_voices(self) -> list[Voice]:
        return []


def _with_instruction(text: str, voice: str | None) -> str:
    if voice and not text.lstrip().startswith("("):
        return f"({voice}){text}"
    return text
