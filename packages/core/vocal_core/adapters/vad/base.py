from abc import ABC, abstractmethod


class VADAdapter(ABC):
    """
    Base interface for Voice Activity Detection adapters.

    VAD adapters are lightweight and stateful — create one per WebSocket session
    so internal buffers and state are isolated between concurrent connections.
    """

    @abstractmethod
    def get_probability(self, pcm_bytes: bytes, sample_rate: int) -> float:
        """
        Return the speech probability for a PCM audio chunk.

        Args:
            pcm_bytes: Raw 16-bit signed little-endian PCM audio bytes.
            sample_rate: Sample rate in Hz (typically 16000 or 8000).

        Returns:
            Float in [0.0, 1.0] — 0 = silence, 1 = confident speech.
        """

    def is_speech(self, pcm_bytes: bytes, sample_rate: int, threshold: float) -> bool:
        """Returns True if speech probability >= threshold."""
        return self.get_probability(pcm_bytes, sample_rate) >= threshold

    def reset(self) -> None:
        """Reset internal state. Call between utterances if the adapter is stateful."""
