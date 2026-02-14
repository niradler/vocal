from abc import abstractmethod
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel

from ..base import BaseAdapter


class TranscriptionSegment(BaseModel):
    """A segment of transcribed text with timing"""

    id: int
    start: float
    end: float
    text: str
    tokens: list[int] | None = None
    temperature: float | None = None
    avg_logprob: float | None = None
    compression_ratio: float | None = None
    no_speech_prob: float | None = None


class TranscriptionWord(BaseModel):
    """Word-level timestamp"""

    word: str
    start: float
    end: float
    probability: float | None = None


class TranscriptionResult(BaseModel):
    """Transcription result"""

    text: str
    language: str
    duration: float
    segments: list[TranscriptionSegment] | None = None
    words: list[TranscriptionWord] | None = None


class STTAdapter(BaseAdapter):
    """Base interface for Speech-to-Text adapters"""

    @abstractmethod
    async def transcribe(
        self,
        audio: str | Path | BinaryIO,
        language: str | None = None,
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
