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

    if not KOKORO_AVAILABLE:
        pytest.skip("kokoro not installed")
    svc = _make_service()
    adapter = svc._create_adapter("kokoro")
    assert isinstance(adapter, KokoroTTSAdapter)


def test_create_adapter_chatterbox_returns_chatterbox_or_import_error():
    svc = _make_service()
    if CHATTERBOX_AVAILABLE:
        adapter = svc._create_adapter("chatterbox")
        assert isinstance(adapter, ChatterboxTTSAdapter)
    else:
        with pytest.raises(ImportError, match="chatterbox-tts"):
            svc._create_adapter("chatterbox")


@pytest.mark.parametrize(
    "backend,expected_hint",
    [
        ("xtts", "pip install TTS"),
        ("fish_speech", "pip install fish-speech"),
        ("orpheus", "Orpheus-TTS"),
        ("dia", "pip install dia-tts"),
    ],
)
def test_unimplemented_backends_raise_import_error_with_hint(backend, expected_hint):
    svc = _make_service()
    with pytest.raises(ImportError, match=expected_hint):
        svc._create_adapter(backend)


def test_unknown_backend_raises_value_error():
    svc = _make_service()
    with pytest.raises(ValueError, match="Unsupported TTS backend"):
        svc._create_adapter("totally_unknown_backend")
