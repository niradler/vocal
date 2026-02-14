"""
Vocal - Ollama-style Voice Model Management

Self-hosted, OpenAI-compatible Speech AI Platform.

Quick Start:
    >>> from vocal_sdk import VocalSDK
    >>> client = VocalSDK()
    >>> result = client.audio.transcribe(file="audio.mp3", model="Systran/faster-whisper-tiny")

CLI:
    $ vocal serve
    $ vocal models list
    $ vocal run audio.mp3
"""

__version__ = "0.3.0"

try:
    from vocal_core import FasterWhisperAdapter, ModelRegistry
    from vocal_sdk import VocalSDK
except ImportError:
    pass

__all__ = ["VocalSDK", "ModelRegistry", "FasterWhisperAdapter", "__version__"]
