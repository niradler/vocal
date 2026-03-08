import asyncio
import importlib.util
import logging
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from .base import STTAdapter, TranscriptionResult, TranscriptionSegment

logger = logging.getLogger(__name__)

TRANSFORMERS_AVAILABLE = importlib.util.find_spec("transformers") is not None and importlib.util.find_spec("torch") is not None


class TransformersSTTAdapter(STTAdapter):
    """
    HuggingFace Transformers STT adapter.

    Supports any encoder-decoder ASR model loadable via AutoModelForSpeechSeq2Seq,
    including Whisper variants and Qwen3-ASR.
    """

    def __init__(self) -> None:
        self.pipe: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers and torch are required. Install with: pip install transformers torch")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        dtype = torch.float16 if resolved == "cuda" else torch.float32

        logger.info("Loading transformers STT model from %s on %s", model_path, resolved)
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            str(model_path),
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        )
        model.to(resolved)
        processor = AutoProcessor.from_pretrained(str(model_path))

        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=dtype,
            device=resolved,
        )
        self.model_path = model_path
        self.device = resolved
        logger.info("Transformers STT model loaded on %s", resolved)

    async def unload_model(self) -> None:
        self.pipe = None
        self.model_path = None
        if self.device == "cuda":
            try:
                import torch

                torch.cuda.empty_cache()
            except Exception:
                pass

    def is_loaded(self) -> bool:
        return self.pipe is not None

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "loaded": self.is_loaded(),
            "backend": "transformers",
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
                with tempfile.NamedTemporaryFile(delete=False, suffix=".audio") as tmp:
                    tmp.write(audio.read())
                    temp_path = tmp.name
                audio_path = temp_path

            generate_kwargs: dict[str, Any] = {}
            if language:
                generate_kwargs["language"] = language
            if task == "translate":
                generate_kwargs["task"] = "translate"

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._run_pipeline, audio_path, generate_kwargs)

            text = result.get("text", "").strip()
            chunks = result.get("chunks", [])
            last_ts: float | None = None
            if chunks:
                try:
                    last_ts = chunks[-1].get("timestamp", (None, None))[1]
                except (IndexError, TypeError):
                    last_ts = None
            duration = float(last_ts) if last_ts else 0.0

            segments = None
            if chunks:
                segments = [
                    TranscriptionSegment(
                        id=i,
                        start=c["timestamp"][0] or 0.0,
                        end=c["timestamp"][1] or 0.0,
                        text=c["text"],
                    )
                    for i, c in enumerate(chunks)
                ]

            return TranscriptionResult(
                text=text,
                language=language or "unknown",
                duration=duration,
                segments=segments,
            )
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    def _run_pipeline(self, audio_path: str, generate_kwargs: dict) -> dict:
        return self.pipe(
            audio_path,
            return_timestamps=True,
            generate_kwargs=generate_kwargs if generate_kwargs else None,
        )
