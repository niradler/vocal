import logging

from .base import VADAdapter
from .rms import RMSVADAdapter
from .silero import SILERO_AVAILABLE, SileroVADAdapter

logger = logging.getLogger(__name__)

__all__ = [
    "VADAdapter",
    "RMSVADAdapter",
    "SileroVADAdapter",
    "SILERO_AVAILABLE",
    "create_vad_adapter",
]


def create_vad_adapter(rms_threshold: float | None = None) -> VADAdapter:
    """
    Factory that returns the best available VAD adapter.

    Prefers Silero VAD (neural, accurate) and falls back to RMS energy
    detection when silero-vad is not installed.

    Args:
        rms_threshold: Energy threshold for the RMS fallback adapter.
                       Ignored when Silero is available.
                       Defaults to vocal_settings.VAD_THRESHOLD.
    """
    from vocal_core.config import vocal_settings

    if SILERO_AVAILABLE:
        logger.debug("VAD: using Silero VAD")
        return SileroVADAdapter()

    threshold = rms_threshold if rms_threshold is not None else vocal_settings.VAD_THRESHOLD
    logger.debug("VAD: silero-vad not installed, falling back to RMS (threshold=%.1f)", threshold)
    return RMSVADAdapter(rms_threshold=threshold)
