"""Contract tests: settings API (GET/PUT /v1/settings).

The contract server runs with an isolated VOCAL_MODEL_STORAGE_PATH, so the
persisted settings file lands in a temp dir. Tests restore any value they
change so later tests see the original defaults.
"""

MASK = "********"


class TestSettingsGet:
    def test_get_settings_shape(self, client):
        resp = client.get_httpx_client().get("/v1/settings")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("STT_DEFAULT_MODEL", "TTS_DEFAULT_MODEL", "LLM_BASE_URL", "VAD_SPEECH_THRESHOLD", "CHAT_SYSTEM_PROMPT", "LOG_LEVEL"):
            assert key in body
        assert "llm_api_key_set" in body

    def test_api_key_is_masked(self, client):
        resp = client.get_httpx_client().get("/v1/settings")
        body = resp.json()
        # The default key ("ollama") must never be echoed back.
        assert body["LLM_API_KEY"] in (MASK, None, "")
        assert body["llm_api_key_set"] is True


class TestSettingsUpdate:
    def test_update_and_restore(self, client):
        http = client.get_httpx_client()
        original = http.get("/v1/settings").json()["STT_DEFAULT_MODEL"]
        try:
            resp = http.put("/v1/settings", json={"STT_DEFAULT_MODEL": "Systran/faster-whisper-base"})
            assert resp.status_code == 200
            assert resp.json()["STT_DEFAULT_MODEL"] == "Systran/faster-whisper-base"
            assert http.get("/v1/settings").json()["STT_DEFAULT_MODEL"] == "Systran/faster-whisper-base"
        finally:
            http.put("/v1/settings", json={"STT_DEFAULT_MODEL": original})

    def test_validation_rejects_out_of_range(self, client):
        resp = client.get_httpx_client().put("/v1/settings", json={"VAD_SPEECH_THRESHOLD": 5.0})
        assert resp.status_code == 422

    def test_validation_rejects_bad_log_level(self, client):
        resp = client.get_httpx_client().put("/v1/settings", json={"LOG_LEVEL": "VERBOSE"})
        assert resp.status_code == 422

    def test_validation_rejects_bad_llm_url(self, client):
        resp = client.get_httpx_client().put("/v1/settings", json={"LLM_BASE_URL": "not-a-url"})
        assert resp.status_code == 422

    def test_masked_key_keeps_current_key(self, client):
        http = client.get_httpx_client()
        resp = http.put("/v1/settings", json={"LLM_API_KEY": MASK})
        assert resp.status_code == 200
        assert resp.json()["llm_api_key_set"] is True
        assert resp.json()["LLM_API_KEY"] == MASK

    def test_empty_nullable_field_unsets(self, client):
        http = client.get_httpx_client()
        original = http.get("/v1/settings").json()["STT_DEFAULT_LANGUAGE"]
        try:
            resp = http.put("/v1/settings", json={"STT_DEFAULT_LANGUAGE": ""})
            assert resp.status_code == 200
            assert resp.json()["STT_DEFAULT_LANGUAGE"] is None
        finally:
            http.put("/v1/settings", json={"STT_DEFAULT_LANGUAGE": original or ""})

    def test_partial_update_leaves_other_fields(self, client):
        http = client.get_httpx_client()
        before = http.get("/v1/settings").json()
        resp = http.put("/v1/settings", json={"VAD_PREROLL_MS": before["VAD_PREROLL_MS"] + 1})
        assert resp.status_code == 200
        after = resp.json()
        assert after["VAD_PREROLL_MS"] == before["VAD_PREROLL_MS"] + 1
        assert after["STT_DEFAULT_MODEL"] == before["STT_DEFAULT_MODEL"]
        assert after["TTS_DEFAULT_MODEL"] == before["TTS_DEFAULT_MODEL"]
        http.put("/v1/settings", json={"VAD_PREROLL_MS": before["VAD_PREROLL_MS"]})
