import asyncio
import tempfile
import time
from collections.abc import AsyncGenerator
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from vocal_core import ModelRegistry, TranscriptionResult
from vocal_core.adapters.stt import (
    NEMO_AVAILABLE,
    TRANSFORMERS_AVAILABLE,
    WHISPERX_AVAILABLE,
    FasterWhisperAdapter,
    NemoSTTAdapter,
    STTAdapter,
    TransformersSTTAdapter,
    WhisperXSTTAdapter,
)
from vocal_core.adapters.stt import (
    TranscriptionSegment as CoreTranscriptionSegment,
)
from vocal_core.config import optional_dependency_install_hint

from ..models.transcription import (
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionSegment,
    TranscriptionWord,
)


class TranscriptionService:
    """Service for handling transcription requests with Ollama-style keep-alive"""

    def __init__(self, registry: ModelRegistry, keep_alive_seconds: int = 300):
        self.registry = registry
        self.adapters: dict[str, STTAdapter] = {}
        self.last_used: dict[str, float] = {}
        self.keep_alive_seconds = keep_alive_seconds
        self._cleanup_task = None

    async def start_cleanup_task(self):
        """Start background task to cleanup unused models"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """Background task to unload models after keep_alive expires"""
        while True:
            try:
                await asyncio.sleep(60)
                current_time = time.time()
                models_to_unload = [m for m, t in self.last_used.items() if current_time - t > self.keep_alive_seconds]
                for model_id in models_to_unload:
                    if model_id in self.adapters:
                        await self.adapters[model_id].unload_model()
                        del self.adapters[model_id]
                        del self.last_used[model_id]
            except Exception:
                pass

    async def transcribe(self, file: UploadFile, request: TranscriptionRequest) -> TranscriptionResponse:
        model_id = request.model
        model_info = await self.registry.get_model(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found in registry")

        model_path = self.registry.get_model_path(model_id)
        if not model_path:
            raise ValueError(f"Model {model_id} not downloaded. Download it first: POST /v1/models/{model_id}/download")

        adapter = await self._get_or_create_adapter(model_id, model_path, model_info.backend.value)
        self.last_used[model_id] = time.time()

        temp_path: str | None = None
        try:
            # Preserve original extension so audio libraries (lhotse, soundfile)
            # can detect the format correctly.
            ext = Path(file.filename).suffix if file.filename else ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext or ".wav") as tmp:
                temp_path = tmp.name
            content = await file.read()
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(content)

            word_timestamps = "word" in request.timestamp_granularities
            result = await adapter.transcribe(
                audio=temp_path,
                language=request.language,
                task="transcribe",
                temperature=request.temperature,
                word_timestamps=word_timestamps,
            )
            return self._convert_result(result)
        finally:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()

    async def translate(self, file: UploadFile, model_id: str) -> TranscriptionResponse:
        model_info = await self.registry.get_model(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found in registry")

        model_path = self.registry.get_model_path(model_id)
        if not model_path:
            raise ValueError(f"Model {model_id} not downloaded")

        adapter = await self._get_or_create_adapter(model_id, model_path, model_info.backend.value)
        self.last_used[model_id] = time.time()

        temp_path: str | None = None
        try:
            ext = Path(file.filename).suffix if file.filename else ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext or ".wav") as tmp:
                temp_path = tmp.name
            content = await file.read()
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(content)

            result = await adapter.transcribe(audio=temp_path, task="translate")
            return self._convert_result(result)
        finally:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()

    async def transcribe_stream_path(
        self,
        audio_path: str,
        model_id: str,
        language: str | None = None,
        task: str = "transcribe",
    ) -> AsyncGenerator[CoreTranscriptionSegment, None]:
        model_info = await self.registry.get_model(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found in registry")

        model_path = self.registry.get_model_path(model_id)
        if not model_path:
            raise ValueError(f"Model {model_id} not downloaded. Download it first: POST /v1/models/{model_id}/download")

        adapter = await self._get_or_create_adapter(model_id, model_path, model_info.backend.value)
        self.last_used[model_id] = time.time()

        async for seg in adapter.transcribe_stream(audio_path, language=language, task=task):
            yield seg

    def _create_adapter(self, backend: str) -> STTAdapter:
        """Instantiate the correct STT adapter for a given backend."""
        if backend == "faster_whisper":
            return FasterWhisperAdapter()
        if backend == "transformers":
            if not TRANSFORMERS_AVAILABLE:
                raise ImportError("transformers and torch are required. Install with: pip install transformers torch")
            return TransformersSTTAdapter()
        if backend == "nemo":
            if not NEMO_AVAILABLE:
                raise ImportError(optional_dependency_install_hint("nemo", "nemo_toolkit[asr]"))
            return NemoSTTAdapter()
        if backend == "whisperx":
            if not WHISPERX_AVAILABLE:
                raise ImportError(optional_dependency_install_hint("whisperx", "whisperx"))
            return WhisperXSTTAdapter()
        raise ValueError(f"Unsupported STT backend: '{backend}'. Supported backends: faster_whisper, transformers, nemo, whisperx")

    async def _get_or_create_adapter(self, model_id: str, model_path: Path, backend: str) -> STTAdapter:
        """Get or create adapter for model, dispatching by backend."""
        if model_id not in self.adapters:
            adapter = self._create_adapter(backend)
            await adapter.load_model(model_path)
            self.adapters[model_id] = adapter
        return self.adapters[model_id]

    def _convert_result(self, result: TranscriptionResult) -> TranscriptionResponse:
        """Convert core TranscriptionResult to API TranscriptionResponse"""
        segments = None
        if result.segments:
            segments = [
                TranscriptionSegment(
                    id=seg.id,
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                    tokens=seg.tokens,
                    temperature=seg.temperature,
                    avg_logprob=seg.avg_logprob,
                    compression_ratio=seg.compression_ratio,
                    no_speech_prob=seg.no_speech_prob,
                )
                for seg in result.segments
            ]

        words = None
        if result.words:
            words = [
                TranscriptionWord(
                    word=w.word,
                    start=w.start,
                    end=w.end,
                    probability=w.probability,
                )
                for w in result.words
            ]

        return TranscriptionResponse(
            text=result.text,
            language=result.language,
            duration=result.duration,
            segments=segments,
            words=words,
        )
