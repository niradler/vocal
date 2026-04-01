import asyncio
import importlib.util
import logging
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from .base import STTAdapter, TranscriptionResult

logger = logging.getLogger(__name__)

VOXTRAL_STT_AVAILABLE = (
    importlib.util.find_spec("mistral_common") is not None
    and importlib.util.find_spec("transformers") is not None
    and importlib.util.find_spec("torch") is not None
)


class VoxtralSTTAdapter(STTAdapter):
    """
    Voxtral-Mini-4B-Realtime STT adapter.

    Uses mistralai/Voxtral-Mini-4B-Realtime-2602 via the
    VoxtralRealtimeForConditionalGeneration class from transformers>=5.2.0
    and mistral_common>=1.9.0.
    """

    def __init__(self) -> None:
        self.model: Any = None
        self.processor: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self._dtype: Any = None
        self._audio_cls: Any = None

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not VOXTRAL_STT_AVAILABLE:
            raise ImportError(
                "mistral_common, transformers, and torch are required for Voxtral STT. "
                "Install with: uv pip install mistral-common"
            )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        from .._compat import apply_transformers_shims

        apply_transformers_shims()

        import torch
        from transformers import AutoProcessor, VoxtralRealtimeForConditionalGeneration

        from mistral_common.tokens.tokenizers.audio import Audio

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        dtype = torch.bfloat16 if resolved == "cuda" else torch.float32

        logger.info("Loading Voxtral STT model from %s on %s", model_path, resolved)

        self.processor = AutoProcessor.from_pretrained(str(model_path))
        self.model = VoxtralRealtimeForConditionalGeneration.from_pretrained(
            str(model_path),
            device_map=resolved,
            torch_dtype=dtype,
        )
        self._audio_cls = Audio
        self.model_path = model_path
        self.device = resolved
        self._dtype = dtype

        logger.info("Voxtral STT model loaded on %s", resolved)

    async def unload_model(self) -> None:
        self.model = None
        self.processor = None
        self._audio_cls = None
        self.model_path = None
        if self.device == "cuda":
            try:
                import gc

                import torch

                gc.collect()
                torch.cuda.empty_cache()
            except Exception:
                pass

    def is_loaded(self) -> bool:
        return self.model is not None and self.processor is not None

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "loaded": self.is_loaded(),
            "backend": "voxtral_stt",
        }

    async def transcribe(
        self,
        audio: str | Path | BinaryIO,
        language: str | None = None,
        task: str = "transcribe",
        temperature: float = 0.0,
        word_timestamps: bool = False,
        **kwargs,
    ) -> TranscriptionResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        temp_path: str | None = None
        try:
            if isinstance(audio, (str, Path)):
                audio_path = str(audio)
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio.read())
                    temp_path = tmp.name
                audio_path = temp_path

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._run_inference, audio_path, language)
            return result
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    @staticmethod
    def _ensure_wav(audio_path: str) -> tuple[str, bool]:
        """Convert audio to WAV if needed. Returns (path, created_temp)."""
        suffix = Path(audio_path).suffix.lower()
        if suffix in {".wav", ".flac", ".ogg", ".aiff", ".aif"}:
            return audio_path, False
        import subprocess
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.close()
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", tmp.name],
            check=True,
            capture_output=True,
        )
        return tmp.name, True

    def _run_inference(self, audio_path: str, language: str | None) -> TranscriptionResult:
        import torch

        wav_path, is_temp = self._ensure_wav(audio_path)
        try:
            audio = self._audio_cls.from_file(wav_path, strict=False)
        finally:
            if is_temp:
                Path(wav_path).unlink(missing_ok=True)
        audio.resample(self.processor.feature_extractor.sampling_rate)

        inputs = self.processor(audio.audio_array, return_tensors="pt")
        inputs = {k: v.to(device=self.device, dtype=self._dtype if v.is_floating_point() else None) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.generate(**inputs)

        text = self.processor.decode(outputs[0], skip_special_tokens=True).strip()

        return TranscriptionResult(
            text=text,
            language=language or "unknown",
            duration=0.0,
        )
