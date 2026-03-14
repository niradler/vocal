"""Unit tests for STT adapters — import, capabilities, unloaded guards, AVAILABLE flags."""

import pytest

from vocal_core.adapters.stt import (
    NEMO_AVAILABLE,
    TRANSFORMERS_AVAILABLE,
    WHISPERX_AVAILABLE,
    FasterWhisperAdapter,
    NemoSTTAdapter,
    TransformersSTTAdapter,
    WhisperXSTTAdapter,
)


def test_faster_whisper_not_loaded_initially():
    adapter = FasterWhisperAdapter()
    assert adapter.is_loaded() is False


def test_transformers_availability_flag_is_bool():
    assert isinstance(TRANSFORMERS_AVAILABLE, bool)


def test_transformers_adapter_not_loaded_initially():
    adapter = TransformersSTTAdapter()
    assert adapter.is_loaded() is False
    assert adapter._is_ctc is False


def test_nemo_availability_flag_is_bool():
    assert isinstance(NEMO_AVAILABLE, bool)


def test_nemo_adapter_not_loaded_initially():
    adapter = NemoSTTAdapter()
    assert adapter.is_loaded() is False


def test_nemo_get_model_info_when_not_loaded():
    adapter = NemoSTTAdapter()
    info = adapter.get_model_info()
    assert info["loaded"] is False
    assert info["backend"] == "nemo"
    assert info["model_path"] is None


def test_whisperx_availability_flag_is_bool():
    assert isinstance(WHISPERX_AVAILABLE, bool)


def test_whisperx_adapter_not_loaded_initially():
    adapter = WhisperXSTTAdapter()
    assert adapter.is_loaded() is False


def test_whisperx_get_model_info_when_not_loaded():
    adapter = WhisperXSTTAdapter()
    info = adapter.get_model_info()
    assert info["loaded"] is False
    assert info["backend"] == "whisperx"
    assert info["model_path"] is None


@pytest.mark.asyncio
async def test_nemo_transcribe_raises_when_not_loaded():
    adapter = NemoSTTAdapter()
    with pytest.raises(RuntimeError, match="not loaded"):
        await adapter.transcribe("audio.wav")


@pytest.mark.asyncio
async def test_whisperx_transcribe_raises_when_not_loaded():
    adapter = WhisperXSTTAdapter()
    with pytest.raises(RuntimeError, match="not loaded"):
        await adapter.transcribe("audio.wav")


def test_nemo_load_raises_import_error_when_not_available(monkeypatch):
    import vocal_core.adapters.stt.nemo_adapter as mod

    monkeypatch.setattr(mod, "NEMO_AVAILABLE", False)
    adapter = NemoSTTAdapter()

    import asyncio

    with pytest.raises(ImportError, match="nemo_toolkit"):
        asyncio.run(adapter.load_model(__import__("pathlib").Path(".")))


def test_whisperx_load_raises_import_error_when_not_available(monkeypatch):
    import vocal_core.adapters.stt.whisperx_adapter as mod

    monkeypatch.setattr(mod, "WHISPERX_AVAILABLE", False)
    adapter = WhisperXSTTAdapter()

    import asyncio

    with pytest.raises(ImportError, match="whisperx"):
        asyncio.run(adapter.load_model(__import__("pathlib").Path(".")))
