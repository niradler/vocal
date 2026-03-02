from .models import router as models_router
from .realtime import router as realtime_router
from .stream import router as stream_router
from .system import router as system_router
from .transcription import router as transcription_router
from .tts import tts_router

__all__ = [
    "transcription_router",
    "models_router",
    "tts_router",
    "system_router",
    "stream_router",
    "realtime_router",
]
