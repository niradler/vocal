"""Unit tests for VocalSettings config and env loading."""

from vocal_core.config import VocalSettings, optional_dependency_install_hint


def test_defaults():
    s = VocalSettings()
    assert s.STT_DEFAULT_MODEL == "Systran/faster-whisper-tiny"
    assert s.TTS_DEFAULT_MODEL == "pyttsx3"
    assert s.TTS_DEFAULT_VOICE is None
    assert s.STT_SAMPLE_RATE == 16000
    assert s.LOG_LEVEL == "INFO"


def test_env_override(monkeypatch):
    monkeypatch.setenv("STT_DEFAULT_MODEL", "Systran/faster-whisper-small")
    monkeypatch.setenv("TTS_DEFAULT_MODEL", "hexgrad/Kokoro-82M")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = VocalSettings()
    assert s.STT_DEFAULT_MODEL == "Systran/faster-whisper-small"
    assert s.TTS_DEFAULT_MODEL == "hexgrad/Kokoro-82M"
    assert s.LOG_LEVEL == "DEBUG"


def test_optional_dependency_hint():
    hint = optional_dependency_install_hint("kokoro")
    assert "kokoro" in hint
    assert "pip install" in hint or "uv add" in hint

    hint2 = optional_dependency_install_hint("qwen3-tts", "faster-qwen3-tts")
    assert "faster-qwen3-tts" in hint2


def test_vad_defaults():
    s = VocalSettings()
    assert s.VAD_THRESHOLD > 0
    assert s.VAD_SILENCE_FRAMES > 0
    assert s.VAD_SILENCE_DURATION_S > 0
