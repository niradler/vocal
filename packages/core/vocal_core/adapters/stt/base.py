from abc import abstractmethod
from typing import Optional, BinaryIO, Union
from pathlib import Path
from pydantic import BaseModel

from ..base import BaseAdapter


class TranscriptionSegment(BaseModel):
    """A segment of transcribed text with timing"""

    id: int
    start: float
    end: float
    text: str
    tokens: Optional[list[int]] = None
    temperature: Optional[float] = None
    avg_logprob: Optional[float] = None
    compression_ratio: Optional[float] = None
    no_speech_prob: Optional[float] = None


class TranscriptionWord(BaseModel):
    """Word-level timestamp"""

    word: str
    start: float
    end: float
    probability: Optional[float] = None


class TranscriptionResult(BaseModel):
    """Transcription result"""

    text: str
    language: str
    duration: float
    segments: Optional[list[TranscriptionSegment]] = None
    words: Optional[list[TranscriptionWord]] = None


class STTAdapter(BaseAdapter):
    """Base interface for Speech-to-Text adapters"""

    @abstractmethod
    async def transcribe(
        self,
        audio: Union[str, Path, BinaryIO],
        language: Optional[str] = None,
        task: str = "transcribe",
        temperature: float = 0.0,
        word_timestamps: bool = False,
        **kwargs,
    ) -> TranscriptionResult:
        """
        Transcribe audio to text

        Args:
            audio: Audio file path or file-like object
            language: Language code (ISO 639-1) or None for auto-detect
            task: Task type ('transcribe' or 'translate')
            temperature: Sampling temperature (0.0 = greedy)
            word_timestamps: Whether to include word-level timestamps
            **kwargs: Additional backend-specific parameters

        Returns:
            TranscriptionResult with text and metadata
        """
        pass
