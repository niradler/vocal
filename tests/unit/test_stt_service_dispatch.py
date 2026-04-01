"""Unit tests for TranscriptionService backend dispatch and error messages."""

import pytest

from vocal_core.adapters.stt import (
    NEMO_AVAILABLE,
    WHISPERX_AVAILABLE,
    FasterWhisperAdapter,
    NemoSTTAdapter,
    TransformersSTTAdapter,
    WhisperXSTTAdapter,
)


def _make_service():
    from unittest.mock import MagicMock

    from vocal_api.services.transcription_service import TranscriptionService

    registry = MagicMock()
    return TranscriptionService(registry=registry)


def test_faster_whisper_dispatch():
    svc = _make_service()
    adapter = svc._create_adapter("faster_whisper")
    assert isinstance(adapter, FasterWhisperAdapter)


def test_transformers_dispatch():
    from vocal_core.adapters.stt import TRANSFORMERS_AVAILABLE

    if not TRANSFORMERS_AVAILABLE:
        pytest.skip("transformers not installed")
    svc = _make_service()
    adapter = svc._create_adapter("transformers")
    assert isinstance(adapter, TransformersSTTAdapter)


def test_nemo_dispatch_returns_nemo_or_import_error():
    svc = _make_service()
    if NEMO_AVAILABLE:
        adapter = svc._create_adapter("nemo")
        assert isinstance(adapter, NemoSTTAdapter)
    else:
        with pytest.raises(ImportError, match="nemo_toolkit"):
            svc._create_adapter("nemo")


def test_whisperx_dispatch_returns_whisperx_or_import_error():
    svc = _make_service()
    if WHISPERX_AVAILABLE:
        adapter = svc._create_adapter("whisperx")
        assert isinstance(adapter, WhisperXSTTAdapter)
    else:
        with pytest.raises(ImportError, match="whisperx"):
            svc._create_adapter("whisperx")


def test_unknown_backend_raises_value_error():
    svc = _make_service()
    with pytest.raises(ValueError, match="Unsupported STT backend"):
        svc._create_adapter("totally_unknown_backend")


def test_voxtral_stt_dispatch_returns_voxtral_or_import_error():
    from vocal_core.adapters.stt import VOXTRAL_STT_AVAILABLE, VoxtralSTTAdapter

    svc = _make_service()
    if VOXTRAL_STT_AVAILABLE:
        adapter = svc._create_adapter("voxtral_stt")
        assert isinstance(adapter, VoxtralSTTAdapter)
    else:
        with pytest.raises(ImportError, match="mistral-common"):
            svc._create_adapter("voxtral_stt")
