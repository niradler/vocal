import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from ...config import optional_dependency_install_hint, vocal_settings
from .base import STTAdapter, TranscriptionResult, TranscriptionSegment

logger = logging.getLogger(__name__)

try:
    from nemo.collections.asr.models import ASRModel as _ASRModel  # noqa: F401

    NEMO_AVAILABLE = True
except Exception:
    NEMO_AVAILABLE = False


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
            raise ImportError(optional_dependency_install_hint("nemo", "nemo_toolkit[asr]"))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch
        from nemo.collections.asr.models import ASRModel

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        self.device = resolved

        # NeMo models are loaded via from_pretrained() with a HuggingFace model name.
        # The model_path directory name follows "org--repo" convention from vocal's registry.
        # If a .nemo checkpoint exists locally, use restore_from; otherwise derive the HF
        # model name and let NeMo download/cache it via from_pretrained.
        nemo_file = next(model_path.glob("*.nemo"), None)
        if nemo_file is not None:
            logger.info("Loading NeMo STT model from %s on %s", nemo_file, resolved)
            self.model = ASRModel.restore_from(str(nemo_file), map_location=resolved)
        else:
            dir_name = model_path.name
            if "--" in dir_name:
                model_name = dir_name.replace("--", "/", 1)
            else:
                model_name = str(model_path)
            logger.info("Loading NeMo STT model %s via from_pretrained on %s", model_name, resolved)
            self.model = ASRModel.from_pretrained(model_name=model_name, map_location=resolved)

        self.model.eval()
        self.model_path = model_path
        logger.info("NeMo STT model loaded on %s", resolved)

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

    _LHOTSE_UNSUPPORTED = {".m4a", ".aac", ".wma", ".amr"}

    @staticmethod
    def _to_wav(src: str) -> str:
        dst = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-ar", "16000", "-ac", "1", dst],
            check=True,
            capture_output=True,
        )
        return dst

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
        converted_path: str | None = None
        try:
            if isinstance(audio, (str, Path)):
                audio_path = str(audio)
                if Path(audio_path).suffix.lower() in self._LHOTSE_UNSUPPORTED:
                    converted_path = self._to_wav(audio_path)
                    audio_path = converted_path
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
            if converted_path:
                Path(converted_path).unlink(missing_ok=True)

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
            logger.debug("NeMo transcribe output type=%s len=%s", type(output).__name__, len(output) if hasattr(output, "__len__") else "?")
            if isinstance(output, tuple):
                hypotheses = output[0]
                text = str(hypotheses[0]) if hypotheses else ""
            elif output:
                item = output[0]
                # NeMo Hypothesis objects expose .text directly
                text = getattr(item, "text", None) or str(item)
            else:
                text = ""
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
