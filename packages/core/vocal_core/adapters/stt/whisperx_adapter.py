import asyncio
import importlib.util
import logging
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from ...config import optional_dependency_install_hint, vocal_settings
from ...utils import get_optimal_compute_type
from .base import STTAdapter, TranscriptionResult, TranscriptionSegment, TranscriptionWord

logger = logging.getLogger(__name__)

WHISPERX_AVAILABLE = importlib.util.find_spec("whisperx") is not None


class WhisperXSTTAdapter(STTAdapter):
    """
    WhisperX STT adapter — faster-whisper + forced word alignment via wav2vec2.

    Provides accurate word-level timestamps on top of any Whisper model.
    Speaker diarization is available but requires a HuggingFace token and pyannote.

    Requires: pip install whisperx
    """

    def __init__(self) -> None:
        self.model: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self.compute_type: str = "float32"

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not WHISPERX_AVAILABLE:
            raise ImportError(optional_dependency_install_hint("whisperx", "whisperx"))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch
        import whisperx

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        self.device = resolved
        self.compute_type = get_optimal_compute_type(resolved)

        # whisperx.load_model expects a CTranslate2 dir (with model.bin), a short Whisper
        # model name (e.g. "distil-large-v3"), or a HF repo ID ("Systran/faster-...").
        # If model_path has model.bin, use it directly; otherwise derive a model ref.
        model_bin = model_path / "model.bin"
        if model_bin.exists():
            model_ref = str(model_path)
        else:
            dir_name = model_path.name
            # vocal stores whisperx models as "whisperx--<model-name>"; the part
            # after "whisperx--" is the short name that faster-whisper can resolve
            # (e.g. "distil-large-v3" → "Systran/faster-distil-whisper-large-v3").
            if dir_name.startswith("whisperx--"):
                model_ref = dir_name.removeprefix("whisperx--")
            elif "--" in dir_name:
                model_ref = dir_name.replace("--", "/", 1)
            else:
                model_ref = str(model_path)
            logger.info("model.bin not in %s — loading via model ref: %s", model_path, model_ref)

        logger.info("Loading WhisperX model from %s on %s", model_ref, resolved)
        # PyTorch 2.6+ defaults weights_only=True which breaks CTranslate2/whisperx
        # (many omegaconf classes not in safe globals). Temporarily patch torch.load.
        _orig_load = torch.load
        torch.load = lambda *a, **kw: _orig_load(*a, **{**kw, "weights_only": False})
        try:
            self.model = whisperx.load_model(model_ref, resolved, compute_type=self.compute_type)
        finally:
            torch.load = _orig_load
        self.model_path = model_path
        logger.info("WhisperX model loaded on %s", resolved)

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
            "compute_type": self.compute_type,
            "loaded": self.is_loaded(),
            "backend": "whisperx",
        }

    async def transcribe(
        self,
        audio: str | Path | BinaryIO,
        language: str | None = None,
        task: str = "transcribe",
        temperature: float = 0.0,
        word_timestamps: bool = False,
        batch_size: int | None = None,
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

            resolved_batch = batch_size if batch_size is not None else vocal_settings.WHISPERX_BATCH_SIZE
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._run_transcribe, audio_path, language, resolved_batch, word_timestamps)
            return result
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    def _run_transcribe(
        self,
        audio_path: str,
        language: str | None,
        batch_size: int,
        word_timestamps: bool,
    ) -> TranscriptionResult:
        import whisperx

        audio = whisperx.load_audio(audio_path)

        transcribe_kwargs: dict[str, Any] = {"batch_size": batch_size}
        if language:
            transcribe_kwargs["language"] = language

        result = self.model.transcribe(audio, **transcribe_kwargs)
        detected_language = result.get("language", language or "unknown")

        if word_timestamps:
            try:
                align_model, metadata = whisperx.load_align_model(language_code=detected_language, device=self.device)
                result = whisperx.align(result["segments"], align_model, metadata, audio, self.device)
            except Exception as e:
                logger.warning("WhisperX alignment failed, falling back to segment timestamps: %s", e)

        return self._build_result(result, detected_language)

    def _build_result(self, result: dict, language: str) -> TranscriptionResult:
        raw_segments = result.get("segments", [])
        segments: list[TranscriptionSegment] = []
        words: list[TranscriptionWord] = []
        full_text: list[str] = []
        last_end: float = 0.0

        for i, seg in enumerate(raw_segments):
            text = seg.get("text", "").strip()
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", 0.0))
            full_text.append(text)
            last_end = max(last_end, end)
            segments.append(TranscriptionSegment(id=i, start=start, end=end, text=text))
            for w in seg.get("words", []):
                words.append(
                    TranscriptionWord(
                        word=w.get("word", ""),
                        start=float(w.get("start", start)),
                        end=float(w.get("end", end)),
                        probability=w.get("score"),
                    )
                )

        return TranscriptionResult(
            text=" ".join(full_text).strip(),
            language=language,
            duration=last_end,
            segments=segments or None,
            words=words or None,
        )
