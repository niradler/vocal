import numpy as np

from .base import VADAdapter


class RMSVADAdapter(VADAdapter):
    """
    Fallback VAD using Root Mean Square energy.

    Returns a probability normalized against a configurable RMS threshold —
    values at or above the threshold map to 1.0.
    """

    def __init__(self, rms_threshold: float) -> None:
        self._threshold = rms_threshold

    def get_probability(self, pcm_bytes: bytes, sample_rate: int) -> float:
        if not pcm_bytes:
            return 0.0
        arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(arr**2))) if arr.size > 0 else 0.0
        return min(1.0, rms / self._threshold)

    def is_speech(self, pcm_bytes: bytes, sample_rate: int, threshold: float) -> bool:
        return self.get_probability(pcm_bytes, sample_rate) >= threshold
