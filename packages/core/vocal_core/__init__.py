from .adapters import (
    BaseAdapter,
    FasterWhisperAdapter,
    STTAdapter,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)
from .config import VocalSettings, vocal_settings
from .registry import (
    ModelBackend,
    ModelInfo,
    ModelProvider,
    ModelRegistry,
    ModelStatus,
    ModelTask,
    format_bytes,
)

__version__ = "0.3.4"

__all__ = [
    "ModelRegistry",
    "ModelInfo",
    "ModelStatus",
    "ModelBackend",
    "ModelProvider",
    "ModelTask",
    "format_bytes",
    "BaseAdapter",
    "STTAdapter",
    "TranscriptionResult",
    "TranscriptionSegment",
    "TranscriptionWord",
    "FasterWhisperAdapter",
    "VocalSettings",
    "vocal_settings",
]
