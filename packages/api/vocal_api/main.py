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
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from vocal_core.config import vocal_settings
from vocal_core.logging import setup_logging

from .config import settings
from .dependencies import get_transcription_service, get_tts_service
from .routes import (
    models_router,
    realtime_router,
    settings_router,
    stream_router,
    system_router,
    transcription_router,
    tts_router,
)
from .routes.settings import load_persisted_settings

WEBUI_DIR = Path(__file__).parent / "webui"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services and start background tasks"""
    load_persisted_settings()
    setup_logging(level=vocal_settings.LOG_LEVEL, fmt=vocal_settings.LOG_FORMAT)

    try:
        from vocal_core.adapters._compat import apply_transformers_shims

        apply_transformers_shims()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Failed to apply transformers shims: %s", exc)

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
    # Lets a publicly hosted console (GitHub Pages) reach this local server
    # from the browser (Chrome Private Network Access preflight).
    allow_private_network=settings.CORS_ALLOW_PRIVATE_NETWORK,
)

app.include_router(transcription_router)
app.include_router(models_router)
app.include_router(tts_router)
app.include_router(system_router)
app.include_router(settings_router)
app.include_router(stream_router)
app.include_router(realtime_router)

# Web UI static assets (landing page + console). Served under /static so the
# HTML entry points below can reference shared CSS/JS without a build step.
app.mount("/static", StaticFiles(directory=WEBUI_DIR), name="static")


@app.get("/", tags=["health"])
async def root(request: Request):
    """API health check for clients; landing page for browsers.

    Browsers send ``Accept: text/html`` and get the landing page. API clients
    (SDK, curl, health checks) send ``*/*`` or ``application/json`` and keep the
    original JSON contract.
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return FileResponse(WEBUI_DIR / "index.html", media_type="text/html", headers={"Vary": "Accept"})
    return JSONResponse(
        {
            "status": "ok",
            "message": "Vocal API - Ollama-style voice model management",
            "version": settings.VERSION,
        }
    )


@app.get("/welcome", include_in_schema=False)
async def welcome():
    """Landing page (explicit route)."""
    return FileResponse(WEBUI_DIR / "index.html", media_type="text/html")


@app.get("/ui", include_in_schema=False)
async def console():
    """Web console — manage models, run speech pipelines, configure Vocal."""
    return FileResponse(WEBUI_DIR / "app.html", media_type="text/html")


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

# Fallback static mount: serves webui assets at root-level paths (/theme.css,
# /js/app.js, ...) so the HTML entry points can use relative URLs. The same
# files then also work under a GitHub Pages subpath. Mounted LAST so every API
# route above always wins.
app.mount("/", StaticFiles(directory=WEBUI_DIR), name="webui")
