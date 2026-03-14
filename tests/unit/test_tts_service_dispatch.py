"""Unit tests for TTSService backend dispatch and install-hint errors."""

import pytest

from vocal_core.adapters.tts import CHATTERBOX_AVAILABLE, ChatterboxTTSAdapter


def _make_service():
    from unittest.mock import MagicMock

    from vocal_api.services.tts_service import TTSService

    registry = MagicMock()
    return TTSService(registry=registry)


def test_create_adapter_kokoro_returns_kokoro_adapter():
    from vocal_core.adapters.tts import KOKORO_AVAILABLE, KokoroTTSAdapter

    svc = _make_service()
    if KOKORO_AVAILABLE:
        adapter = svc._create_adapter("kokoro")
        assert isinstance(adapter, KokoroTTSAdapter)
    else:
        with pytest.raises(ImportError, match="kokoro"):
            svc._create_adapter("kokoro")


def test_create_adapter_chatterbox_returns_chatterbox_or_import_error():
    svc = _make_service()
    if CHATTERBOX_AVAILABLE:
        adapter = svc._create_adapter("chatterbox")
        assert isinstance(adapter, ChatterboxTTSAdapter)
    else:
        with pytest.raises(ImportError, match="chatterbox-tts"):
            svc._create_adapter("chatterbox")


@pytest.mark.parametrize(
    "backend",
    ["xtts", "fish_speech", "orpheus", "dia", "unknown_backend"],
)
def test_unsupported_backend_raises_value_error(backend):
    """Backends with no runtime implementation must raise ValueError (not a fake install hint)."""
    svc = _make_service()
    with pytest.raises(ValueError, match="Unsupported TTS backend"):
        svc._create_adapter(backend)
