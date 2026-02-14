from abc import abstractmethod

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
        output_format: str = "wav",
        **kwargs,
    ) -> TTSResult:
        """
        Synthesize text to speech

        Args:
            text: Text to convert to speech
            voice: Voice ID to use (None for default)
            speed: Speech speed multiplier (1.0 = normal)
            pitch: Voice pitch multiplier (1.0 = normal)
            output_format: Output audio format (wav, mp3, etc.)
            **kwargs: Additional backend-specific parameters

        Returns:
            TTSResult with audio data and metadata
        """
        pass

    @abstractmethod
    async def get_voices(self) -> list[Voice]:
        """
        Get list of available voices

        Returns:
            List of Voice objects
        """
        pass
