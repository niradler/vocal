from .transcription import router as transcription_router
from .models import router as models_router
from .tts import tts_router
from .system import router as system_router

__all__ = [
    "transcription_router",
    "models_router",
    "tts_router",
    "system_router",
]
