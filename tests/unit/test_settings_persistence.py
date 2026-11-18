"""Unit tests: settings persistence and masking (no server)."""

import pytest

from vocal_api.routes import settings as settings_route
from vocal_core.config import vocal_settings


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("VOCAL_MODEL_STORAGE_PATH", str(tmp_path / "models"))
    original = {k: getattr(vocal_settings, k) for k in settings_route.EDITABLE_FIELDS}
    yield tmp_path
    for key, value in original.items():
        setattr(vocal_settings, key, value)


class TestSettingsPersistence:
    def test_file_lives_next_to_model_cache(self, isolated_settings):
        assert settings_route.settings_file_path() == isolated_settings / "settings.env"

    def test_roundtrip(self, isolated_settings):
        vocal_settings.STT_DEFAULT_LANGUAGE = "en"
        vocal_settings.VAD_SILENCE_MS = 750
        vocal_settings.CHAT_SYSTEM_PROMPT = "Answer in one short sentence."
        settings_route._persist_settings()

        vocal_settings.STT_DEFAULT_LANGUAGE = None
        vocal_settings.VAD_SILENCE_MS = 600
        vocal_settings.CHAT_SYSTEM_PROMPT = "changed"
        settings_route.load_persisted_settings()

        assert vocal_settings.STT_DEFAULT_LANGUAGE == "en"
        assert vocal_settings.VAD_SILENCE_MS == 750
        assert vocal_settings.CHAT_SYSTEM_PROMPT == "Answer in one short sentence."

    def test_nullable_empty_roundtrips_to_none(self, isolated_settings):
        vocal_settings.TTS_DEFAULT_VOICE = None
        settings_route._persist_settings()
        vocal_settings.TTS_DEFAULT_VOICE = "af_heart"
        settings_route.load_persisted_settings()
        assert vocal_settings.TTS_DEFAULT_VOICE is None

    def test_missing_file_is_noop(self, isolated_settings):
        before = vocal_settings.VAD_SILENCE_MS
        settings_route.load_persisted_settings()
        assert vocal_settings.VAD_SILENCE_MS == before

    def test_invalid_lines_are_skipped(self, isolated_settings):
        path = settings_route.settings_file_path()
        path.write_text("VAD_SILENCE_MS=not-a-number\nUNKNOWN_KEY=1\n# comment\nLOG_LEVEL=DEBUG\n", encoding="utf-8")
        before = vocal_settings.VAD_SILENCE_MS
        settings_route.load_persisted_settings()
        assert vocal_settings.VAD_SILENCE_MS == before
        assert vocal_settings.LOG_LEVEL == "DEBUG"


class TestSettingsMasking:
    def test_secret_masked_in_payload(self, isolated_settings):
        vocal_settings.LLM_API_KEY = "super-secret"
        values = settings_route._current_values()
        assert values["LLM_API_KEY"] == settings_route.API_KEY_MASK
        assert "super-secret" not in str(values)

    def test_empty_key_not_masked(self, isolated_settings):
        vocal_settings.LLM_API_KEY = ""
        values = settings_route._current_values()
        assert values["LLM_API_KEY"] in ("", None)
