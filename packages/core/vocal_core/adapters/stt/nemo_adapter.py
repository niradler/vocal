import asyncio
import importlib.util
import logging
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from ...config import vocal_settings
from .base import STTAdapter, TranscriptionResult, TranscriptionSegment

logger = logging.getLogger(__name__)

NEMO_AVAILABLE = importlib.util.find_spec("nemo") is not None


class NemoSTTAdapter(STTAdapter):
    """
    NVIDIA NeMo STT adapter for Parakeet-TDT, Canary, and other NeMo ASR models.

    Models are distributed as .nemo checkpoint files on HuggingFace.
    Requires: pip install nemo_toolkit[asr]
    """

    def __init__(self) -> None:
        self.model: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not NEMO_AVAILABLE:
            raise ImportError("nemo_toolkit is required for NeMo models. Install with: pip install nemo_toolkit[asr]")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch
        from nemo.collections.asr.models import ASRModel

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        self.device = resolved

        nemo_file = self._find_nemo_file(model_path)
        if nemo_file is None:
            raise FileNotFoundError(f"No .nemo file found in {model_path}. Ensure the model was downloaded with 'vocal models pull'.")

        logger.info("Loading NeMo STT model from %s on %s", nemo_file, resolved)
        self.model = ASRModel.restore_from(str(nemo_file), map_location=resolved)
        self.model.eval()
        self.model_path = model_path
        logger.info("NeMo STT model loaded on %s", resolved)

    def _find_nemo_file(self, model_path: Path) -> Path | None:
        for candidate in model_path.glob("*.nemo"):
            return candidate
        return None

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

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "loaded": self.is_loaded(),
            "backend": "nemo",
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
            result = await loop.run_in_executor(None, self._run_transcribe, audio_path, language, word_timestamps)
            return result
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    def _run_transcribe(self, audio_path: str, language: str | None, word_timestamps: bool) -> TranscriptionResult:
        resolved_language = language or vocal_settings.STT_DEFAULT_LANGUAGE or vocal_settings.NEMO_DEFAULT_LANGUAGE or vocal_settings.DEFAULT_LANGUAGE

        if word_timestamps:
            output = self.model.transcribe([audio_path], timestamps=True)
            if isinstance(output, tuple):
                hypotheses, ts_list = output
                text = hypotheses[0] if hypotheses else ""
                segments = self._build_segments(ts_list[0] if ts_list else None)
            else:
                text = str(output[0]) if output else ""
                segments = None
        else:
            output = self.model.transcribe([audio_path])
            text = str(output[0]) if output else ""
            segments = None

        return TranscriptionResult(
            text=text.strip(),
            language=resolved_language,
            duration=0.0,
            segments=segments,
        )

    def _build_segments(self, ts_data: Any) -> list[TranscriptionSegment] | None:
        if ts_data is None:
            return None
        try:
            words = getattr(ts_data, "word", None) or []
            if not words:
                return None
            return [
                TranscriptionSegment(
                    id=i,
                    start=float(getattr(w, "start_offset", 0.0)),
                    end=float(getattr(w, "end_offset", 0.0)),
                    text=str(getattr(w, "word", w)),
                )
                for i, w in enumerate(words)
            ]
        except Exception:
            return None
