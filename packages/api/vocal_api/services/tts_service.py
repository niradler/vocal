from typing import Optional
from pathlib import Path

from vocal_core.adapters.tts import SimpleTTSAdapter, TTSResult, Voice


class TTSService:
    """Service for handling TTS operations"""

    def __init__(self):
        self.adapter = SimpleTTSAdapter()
        self._initialized = False

    async def initialize(self):
        """Initialize TTS adapter"""
        if not self._initialized:
            await self.adapter.load_model(Path("."))
            self._initialized = True

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        output_format: str = "wav",
    ) -> TTSResult:
        """
        Synthesize text to speech

        Args:
            text: Text to convert to speech
            voice: Voice ID to use
            speed: Speech speed multiplier
            output_format: Output audio format

        Returns:
            TTSResult with audio data
        """
        if not self._initialized:
            await self.initialize()

        return await self.adapter.synthesize(
            text=text, voice=voice, speed=speed, output_format=output_format
        )

    async def get_voices(self) -> list[Voice]:
        """Get list of available voices"""
        if not self._initialized:
            await self.initialize()

        return await self.adapter.get_voices()
