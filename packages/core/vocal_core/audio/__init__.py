"""Audio stream helpers shared by the API and adapters."""

from .resample import PCM16Resampler, resample_pcm16
from .sentences import SentenceChunker
from .vad_gate import (
    DEFAULT_FRAME_MS,
    DEFAULT_SAMPLE_RATE,
    StreamingVADGate,
    SyntheticVAD,
    VADEvent,
    rms_probability,
)

__all__ = [
    "DEFAULT_FRAME_MS",
    "DEFAULT_SAMPLE_RATE",
    "PCM16Resampler",
    "SentenceChunker",
    "StreamingVADGate",
    "SyntheticVAD",
    "VADEvent",
    "resample_pcm16",
    "rms_probability",
]
