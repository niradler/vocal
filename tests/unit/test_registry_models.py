"""Unit tests for ModelInfo, ModelBackend, ModelTask, and format_bytes."""

from vocal_core.registry import ModelBackend, ModelInfo, ModelProvider, ModelStatus, ModelTask, format_bytes


def test_model_backend_values():
    assert ModelBackend.FASTER_WHISPER == "faster_whisper"
    assert ModelBackend.KOKORO == "kokoro"
    assert ModelBackend.FASTER_QWEN3_TTS == "faster_qwen3_tts"
    assert ModelBackend.TRANSFORMERS == "transformers"
    assert ModelBackend.PIPER == "piper"


def test_model_task_values():
    assert ModelTask.STT == "stt"
    assert ModelTask.TTS == "tts"


def test_model_status_values():
    assert ModelStatus.AVAILABLE == "available"
    assert ModelStatus.NOT_DOWNLOADED == "not_downloaded"
    assert ModelStatus.DOWNLOADING == "downloading"
    assert ModelStatus.ERROR == "error"


def test_format_bytes():
    assert format_bytes(0) == "0.0B"
    assert "KB" in format_bytes(2048)
    assert "MB" in format_bytes(5 * 1024 * 1024)
    assert "GB" in format_bytes(2 * 1024 * 1024 * 1024)


def test_model_info_construction():
    m = ModelInfo(
        id="Systran/faster-whisper-tiny",
        name="Faster Whisper Tiny",
        provider=ModelProvider.HUGGINGFACE,
        backend=ModelBackend.FASTER_WHISPER,
        task=ModelTask.STT,
        status=ModelStatus.NOT_DOWNLOADED,
    )
    assert m.id == "Systran/faster-whisper-tiny"
    assert m.backend == ModelBackend.FASTER_WHISPER
    assert m.task == ModelTask.STT
    assert m.status == ModelStatus.NOT_DOWNLOADED


def test_model_info_serialization():
    m = ModelInfo(
        id="hexgrad/Kokoro-82M",
        name="Kokoro 82M",
        provider=ModelProvider.HUGGINGFACE,
        backend=ModelBackend.KOKORO,
        task=ModelTask.TTS,
    )
    d = m.model_dump()
    assert d["backend"] == "kokoro"
    assert d["task"] == "tts"
