import os
import sys

if sys.platform == "win32":
    import ctypes

    try:
        import torch as _torch

        _torch_lib = os.path.join(os.path.dirname(_torch.__file__), "lib")
        _cudnn_stub = os.path.join(_torch_lib, "cudnn64_9.dll")
        if os.path.exists(_cudnn_stub):
            ctypes.WinDLL(_cudnn_stub)
        del _torch, _torch_lib, _cudnn_stub
    except Exception:
        pass
    del ctypes

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from vocal_core.config import vocal_settings
from vocal_core.logging import setup_logging

from .config import settings
from .dependencies import get_transcription_service, get_tts_service
from .routes import models_router, realtime_router, stream_router, system_router, transcription_router, tts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services and start background tasks"""
    setup_logging(level=vocal_settings.LOG_LEVEL, fmt=vocal_settings.LOG_FORMAT)

    transcription_service = get_transcription_service()
    await transcription_service.start_cleanup_task()

    tts_service = get_tts_service()
    await tts_service.start_cleanup_task()

    yield


app = FastAPI(
    title="Vocal API",
    description="Generic Speech AI Platform (STT + TTS)",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transcription_router)
app.include_router(models_router)
app.include_router(tts_router)
app.include_router(system_router)
app.include_router(stream_router)
app.include_router(realtime_router)



@app.get("/", tags=["health"])
async def root():
    """API health check"""
    return {
        "status": "ok",
        "message": "Vocal API - Ollama-style voice model management",
        "version": settings.VERSION,
    }


@app.get("/health", tags=["health"])
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "api_version": settings.VERSION,
    }


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Vocal API",
        version=settings.VERSION,
        description="Generic Speech AI Platform (STT + TTS)",
        routes=app.routes,
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
