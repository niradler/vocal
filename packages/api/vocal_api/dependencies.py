from functools import lru_cache
from vocal_core import ModelRegistry
from .services import TranscriptionService


_registry: ModelRegistry | None = None
_transcription_service: TranscriptionService | None = None


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
