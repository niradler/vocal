from functools import lru_cache
from vocal_core import ModelRegistry
from .services import TranscriptionService, ModelService


_registry: ModelRegistry | None = None
_transcription_service: TranscriptionService | None = None
_model_service: ModelService | None = None


def get_registry() -> ModelRegistry:
    """Get or create ModelRegistry singleton"""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def get_transcription_service() -> TranscriptionService:
    """Get or create TranscriptionService singleton"""
    global _transcription_service
    if _transcription_service is None:
        registry = get_registry()
        _transcription_service = TranscriptionService(registry)
    return _transcription_service


def get_model_service() -> ModelService:
    """Get or create ModelService singleton"""
    global _model_service
    if _model_service is None:
        registry = get_registry()
        _model_service = ModelService(registry)
    return _model_service
