from typing import BinaryIO
from pathlib import Path
import tempfile
from fastapi import UploadFile

from vocal_core import ModelRegistry, FasterWhisperAdapter, TranscriptionResult
from vocal_core.adapters.stt import TranscriptionSegment as CoreSegment, TranscriptionWord as CoreWord

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
    
    async def transcribe(
        self,
        file: UploadFile,
        request: TranscriptionRequest
    ) -> TranscriptionResponse:
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
            raise ValueError(
                f"Model {model_id} not downloaded. "
                f"Download it first: POST /v1/models/{model_id}/download"
            )
        
        adapter = await self._get_or_create_adapter(model_id, model_path)
        
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
            content = await file.read()
            temp_file.write(content)
            temp_file.close()
            
            word_timestamps = "word" in request.timestamp_granularities
            
            result = await adapter.transcribe(
                audio=temp_file.name,
                language=request.language,
                task="transcribe",
                temperature=request.temperature,
                word_timestamps=word_timestamps,
            )
            
            return self._convert_result(result)
            
        finally:
            if temp_file and Path(temp_file.name).exists():
                Path(temp_file.name).unlink()
    
    async def translate(
        self,
        file: UploadFile,
        model_id: str
    ) -> TranscriptionResponse:
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
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
            content = await file.read()
            temp_file.write(content)
            temp_file.close()
            
            result = await adapter.transcribe(
                audio=temp_file.name,
                task="translate",
            )
            
            return self._convert_result(result)
            
        finally:
            if temp_file and Path(temp_file.name).exists():
                Path(temp_file.name).unlink()
    
    async def _get_or_create_adapter(
        self,
        model_id: str,
        model_path: Path
    ) -> FasterWhisperAdapter:
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
