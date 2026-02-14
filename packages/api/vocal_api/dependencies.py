from vocal_core import ModelRegistry

from .services import ModelService, TranscriptionService, TTSService

_registry: ModelRegistry | None = None
_transcription_service: TranscriptionService | None = None
_model_service: ModelService | None = None
_tts_service: TTSService | None = None


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
        _transcription_service = TranscriptionService(registry, keep_alive_seconds=300)
    return _transcription_service


def get_model_service() -> ModelService:
    """Get or create ModelService singleton"""
    global _model_service
    if _model_service is None:
        registry = get_registry()
        _model_service = ModelService(registry)
    return _model_service


def get_tts_service() -> TTSService:
    """Get or create TTSService singleton"""
    global _tts_service
    if _tts_service is None:
        registry = get_registry()
        _tts_service = TTSService(registry, keep_alive_seconds=300)
    return _tts_service
