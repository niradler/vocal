from abc import abstractmethod
from collections.abc import AsyncGenerator

from pydantic import BaseModel

from ..base import BaseAdapter


class Voice(BaseModel):
    """Voice configuration for TTS"""

    id: str
    name: str
    language: str
    gender: str | None = None


class TTSResult(BaseModel):
    """Text-to-Speech result"""

    audio_data: bytes
    sample_rate: int
    duration: float
    format: str


class TTSAdapter(BaseAdapter):
    """Base interface for Text-to-Speech adapters"""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "mp3",
        **kwargs,
    ) -> TTSResult:
        """
        Synthesize text to speech

        Args:
            text: Text to convert to speech
            voice: Voice ID to use (None for default)
            speed: Speech speed multiplier (1.0 = normal)
            pitch: Voice pitch multiplier (1.0 = normal)
            output_format: Output audio format (mp3, opus, aac, flac, wav, pcm)
            **kwargs: Additional backend-specific parameters

        Returns:
            TTSResult with audio data and metadata
        """
        pass

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "mp3",
        **kwargs,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream audio bytes as they are generated.

        Default implementation batches via synthesize() and yields the full result
        as a single chunk. Adapters that support true streaming should override this.

        Args:
            text: Text to convert to speech
            voice: Voice ID to use (None for default)
            speed: Speech speed multiplier (1.0 = normal)
            pitch: Voice pitch multiplier (1.0 = normal)
            output_format: Output audio format (mp3, opus, aac, flac, wav, pcm)
            **kwargs: Additional backend-specific parameters

        Yields:
            bytes chunks of audio data
        """
        result = await self.synthesize(text=text, voice=voice, speed=speed, pitch=pitch, output_format=output_format, **kwargs)
        yield result.audio_data

    @abstractmethod
    async def get_voices(self) -> list[Voice]:
        """
        Get list of available voices

        Returns:
            List of Voice objects
        """
        pass
