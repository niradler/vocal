from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from .routes import transcription_router, models_router
from .config import settings

app = FastAPI(
    title="Vocal API",
    description="Generic Speech AI Platform (STT + TTS)",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
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


@app.get("/", tags=["health"])
async def root():
    """API health check"""
    return {
        "status": "ok",
        "message": "Vocal API - Ollama-style voice model management",
        "version": settings.VERSION
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
