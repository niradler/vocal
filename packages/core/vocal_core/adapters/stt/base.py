from abc import abstractmethod
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, BinaryIO

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

    async def transcribe_stream(
        self,
        audio: str | Path | BinaryIO,
        language: str | None = None,
        task: str = "transcribe",
        **kwargs,
    ) -> AsyncGenerator["TranscriptionSegment", None]:
        """Default: run full transcribe() and yield a single segment.
        Override for adapters that can produce progressive segments."""
        result = await self.transcribe(audio, language=language, task=task, **kwargs)
        yield TranscriptionSegment(
            id=0,
            start=0.0,
            end=result.duration,
            text=result.text,
            avg_logprob=0.0,
            no_speech_prob=0.0,
        )

    async def transcribe_live(
        self,
        audio_chunks: AsyncGenerator[bytes, Any],
        sample_rate: int = 16000,
        language: str | None = None,
        **kwargs,
    ) -> AsyncGenerator["TranscriptionSegment", None]:
        """Stream raw PCM16 audio chunks → progressive TranscriptionSegments.

        Default: buffer all chunks into an in-memory WAV, then delegate to
        transcribe_stream. Override for adapters with native chunk-by-chunk support.
        """
        import io
        import wave

        pcm = bytearray()
        async for chunk in audio_chunks:
            pcm.extend(chunk)
        if not pcm:
            return
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(bytes(pcm))
        wav_buf.seek(0)
        async for seg in self.transcribe_stream(wav_buf, language=language, **kwargs):
            yield seg
