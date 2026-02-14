import tempfile
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from vocal_core import FasterWhisperAdapter, ModelRegistry, TranscriptionResult

from ..models.transcription import (
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionSegment,
    TranscriptionWord,
)


class TranscriptionService:
    """Service for handling transcription requests"""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self.adapters: dict[str, FasterWhisperAdapter] = {}

    async def transcribe(self, file: UploadFile, request: TranscriptionRequest) -> TranscriptionResponse:
        """
        Transcribe audio file

        Args:
            file: Uploaded audio file
            request: Transcription parameters

        Returns:
            TranscriptionResponse with text and metadata
        """
        model_id = request.model

        model_info = await self.registry.get_model(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found in registry")

        model_path = self.registry.get_model_path(model_id)

        if not model_path:
            raise ValueError(f"Model {model_id} not downloaded. Download it first: POST /v1/models/{model_id}/download")

        adapter = await self._get_or_create_adapter(model_id, model_path)

        temp_file = None
        temp_path = None
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
            temp_path = temp_file.name
            temp_file.close()

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
        """
        Translate audio to English

        Args:
            file: Uploaded audio file
            model_id: Model to use

        Returns:
            TranscriptionResponse with translated text
        """
        model_path = self.registry.get_model_path(model_id)
        if not model_path:
            raise ValueError(f"Model {model_id} not downloaded")

        adapter = await self._get_or_create_adapter(model_id, model_path)

        temp_file = None
        temp_path = None
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
            temp_path = temp_file.name
            temp_file.close()

            content = await file.read()

            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(content)

            result = await adapter.transcribe(
                audio=temp_path,
                task="translate",
            )

            return self._convert_result(result)

        finally:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()

    async def _get_or_create_adapter(self, model_id: str, model_path: Path) -> FasterWhisperAdapter:
        """Get or create adapter for model"""
        if model_id not in self.adapters:
            adapter = FasterWhisperAdapter()
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
