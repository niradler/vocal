import asyncio
import importlib.util
import io
import logging
from pathlib import Path
from typing import Any

from ...config import optional_dependency_install_hint, vocal_settings
from .base import AudioFormat, TTSAdapter, TTSCapabilities, TTSResult, Voice, VoiceCloneRequest

logger = logging.getLogger(__name__)

OMNIVOICE_AVAILABLE = importlib.util.find_spec("omnivoice") is not None


class OmniVoiceTTSAdapter(TTSAdapter):
    """
    OmniVoice TTS adapter — zero-shot voice cloning and voice design for 600+ languages.

    Supports standard synthesis, reference-audio voice cloning, and instruction-based
    voice design (gender, age, pitch, accent, etc.).
    Requires: pip install omnivoice
    """

    def __init__(self) -> None:
        self.model: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self.sample_rate: int = 24000

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not OMNIVOICE_AVAILABLE:
            raise ImportError(optional_dependency_install_hint("omnivoice"))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        from .._compat import apply_transformers_shims

        apply_transformers_shims()

        import torch
        from omnivoice import OmniVoice

        if device == "auto":
            resolved = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            resolved = device
        self.device = resolved

        dtype = torch.float16 if "cuda" in resolved else torch.float32

        logger.info("Loading OmniVoice model from %s on %s (dtype=%s)", model_path, resolved, dtype)
        self.model = OmniVoice.from_pretrained(
            str(model_path),
            device_map=resolved,
            torch_dtype=dtype,
        )
        self.model_path = model_path
        logger.info("OmniVoice model loaded on %s (sr=%d)", resolved, self.sample_rate)

    async def unload_model(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
            self.model_path = None
            if "cuda" in self.device:
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
            "backend": "omnivoice",
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
            raise ValueError(f"OmniVoice only supports WAV output. Requested: '{output_format}'. Convert the result yourself if another format is needed.")

        loop = asyncio.get_running_loop()
        audio_bytes, duration = await loop.run_in_executor(
            None,
            self._synthesize_sync,
            text,
            voice,
            speed,
        )
        return TTSResult(
            audio_data=audio_bytes,
            sample_rate=self.sample_rate,
            duration=duration,
            format=AudioFormat.WAV,
        )

    async def clone_synthesize(self, request: VoiceCloneRequest) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        output_format = request.output_format if request.output_format else AudioFormat.WAV
        if output_format != AudioFormat.WAV:
            raise ValueError(f"OmniVoice only supports WAV output. Requested: '{output_format}'. Convert the result yourself if another format is needed.")

        loop = asyncio.get_running_loop()
        audio_bytes, duration = await loop.run_in_executor(
            None,
            self._clone_sync,
            request.text,
            request.reference_audio_path,
            request.reference_text,
            request.speed,
        )
        return TTSResult(
            audio_data=audio_bytes,
            sample_rate=self.sample_rate,
            duration=duration,
            format=AudioFormat.WAV,
        )

    def _synthesize_sync(
        self,
        text: str,
        instruct: str | None,
        speed: float,
    ) -> tuple[bytes, float]:
        import soundfile as sf
        from omnivoice.models.omnivoice import OmniVoiceGenerationConfig

        gen_config = OmniVoiceGenerationConfig()
        gen_kwargs: dict[str, Any] = {
            "text": text,
            "speed": speed,
            "generation_config": gen_config,
        }
        if instruct and instruct != "default":
            gen_kwargs["instruct"] = instruct

        audio = self.model.generate(**gen_kwargs)
        wav = audio[0].squeeze(0).cpu()
        duration = wav.shape[-1] / self.sample_rate

        buf = io.BytesIO()
        sf.write(buf, wav.numpy(), self.sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue(), duration

    def _clone_sync(
        self,
        text: str,
        ref_audio_path: str,
        ref_text: str | None,
        speed: float,
    ) -> tuple[bytes, float]:
        import soundfile as sf
        import torch
        from omnivoice.models.omnivoice import OmniVoiceGenerationConfig

        # Load reference audio via soundfile to avoid torchaudio/torchcodec
        # issues on Windows. OmniVoice accepts (Tensor, sample_rate) tuples.
        ref_data, ref_sr = sf.read(ref_audio_path, dtype="float32")
        ref_tensor = torch.from_numpy(ref_data)
        if ref_tensor.ndim == 1:
            ref_tensor = ref_tensor.unsqueeze(0)
        else:
            ref_tensor = ref_tensor.T  # (samples, channels) -> (channels, samples)

        gen_config = OmniVoiceGenerationConfig()
        gen_kwargs: dict[str, Any] = {
            "text": text,
            "ref_audio": (ref_tensor, ref_sr),
            "speed": speed,
            "generation_config": gen_config,
        }
        if ref_text:
            gen_kwargs["ref_text"] = ref_text

        audio = self.model.generate(**gen_kwargs)
        wav = audio[0].squeeze(0).cpu()
        duration = wav.shape[-1] / self.sample_rate

        buf = io.BytesIO()
        sf.write(buf, wav.numpy(), self.sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue(), duration

    async def get_voices(self) -> list[Voice]:
        return [Voice(id="default", name="Default", language=vocal_settings.DEFAULT_LANGUAGE)]
