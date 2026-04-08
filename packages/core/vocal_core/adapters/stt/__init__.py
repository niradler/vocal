from .base import (
    STTAdapter,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)
from .faster_whisper import FasterWhisperAdapter
from .nemo_adapter import NEMO_AVAILABLE, NemoSTTAdapter
from .transformers_adapter import TRANSFORMERS_AVAILABLE, TransformersSTTAdapter
from .qwen3_omni import QWEN3_OMNI_STT_AVAILABLE, Qwen3OmniSTTAdapter
from .voxtral import VOXTRAL_STT_AVAILABLE, VoxtralSTTAdapter
from .whisperx_adapter import WHISPERX_AVAILABLE, WhisperXSTTAdapter

__all__ = [
    "STTAdapter",
    "TranscriptionResult",
    "TranscriptionSegment",
    "TranscriptionWord",
    "FasterWhisperAdapter",
    "TransformersSTTAdapter",
    "TRANSFORMERS_AVAILABLE",
    "NemoSTTAdapter",
    "NEMO_AVAILABLE",
    "WhisperXSTTAdapter",
    "WHISPERX_AVAILABLE",
    "VoxtralSTTAdapter",
    "VOXTRAL_STT_AVAILABLE",
    "Qwen3OmniSTTAdapter",
    "QWEN3_OMNI_STT_AVAILABLE",
]
