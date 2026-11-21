from .adapters import (
    BaseAdapter,
    FasterWhisperAdapter,
    STTAdapter,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)
from .config import VocalSettings, vocal_settings
from .logging import get_logger, setup_logging
from .registry import (
    ModelBackend,
    ModelInfo,
    ModelMaintenanceStatus,
    ModelProvider,
    ModelRegistry,
    ModelRuntime,
    ModelStatus,
    ModelTask,
    assert_in_process_runtime,
    format_bytes,
)

__version__ = "0.4.1"

__all__ = [
    "ModelRegistry",
    "ModelInfo",
    "ModelStatus",
    "ModelBackend",
    "ModelProvider",
    "ModelTask",
    "ModelRuntime",
    "ModelMaintenanceStatus",
    "assert_in_process_runtime",
    "format_bytes",
    "BaseAdapter",
    "STTAdapter",
    "TranscriptionResult",
    "TranscriptionSegment",
    "TranscriptionWord",
    "FasterWhisperAdapter",
    "VocalSettings",
    "vocal_settings",
    "get_logger",
    "setup_logging",
]
