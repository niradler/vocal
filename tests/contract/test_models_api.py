"""Contract tests: model management endpoints (no downloads)."""

from vocal_sdk.api.models import get_model_v1_models_model_id_get, list_models_v1_models_get
from vocal_sdk.models import ModelStatus


class TestModelsList:
    def test_list_models_returns_list(self, client):
        result = list_models_v1_models_get.sync(client=client)
        assert result is not None
        assert isinstance(result.models, list)
        assert result.total >= 0
        assert len(result.models) == result.total

    def test_list_models_filter_stt(self, client):
        result = list_models_v1_models_get.sync(client=client, task="stt")
        assert result is not None
        for m in result.models:
            assert m.task.value == "stt"

    def test_list_models_filter_tts(self, client):
        result = list_models_v1_models_get.sync(client=client, task="tts")
        assert result is not None
        for m in result.models:
            assert m.task.value == "tts"

    def test_model_list_structure(self, client):
        result = list_models_v1_models_get.sync(client=client)
        assert result is not None
        if result.models:
            m = result.models[0]
            assert m.id
            assert m.task
            assert m.backend

    def test_supported_models_expose_capabilities(self, client):
        raw = client.get_httpx_client().get("/v1/models/supported")
        assert raw.status_code == 200
        body = raw.json()
        assert body["total"] >= 1
        qwen_clone = next(m for m in body["models"] if m["id"] == "Qwen/Qwen3-TTS-12Hz-0.6B-Base")
        assert qwen_clone["supports_voice_clone"] is True
        assert qwen_clone["clone_mode"] == "reference_audio"
        assert qwen_clone["requires_gpu"] is True

        kokoro = next(m for m in body["models"] if m["id"] == "hexgrad/Kokoro-82M")
        assert kokoro["supports_voice_list"] is True
        assert kokoro["voice_mode"] == "voice_id"


class TestModelGet:
    def test_get_known_stt_model(self, client):
        model_id = "Systran/faster-whisper-tiny"
        result = get_model_v1_models_model_id_get.sync(model_id=model_id, client=client)
        assert result is not None
        assert result.id == model_id
        assert result.task.value == "stt"
        assert result.backend.value == "faster_whisper"

    def test_get_known_tts_model(self, client):
        model_id = "hexgrad/Kokoro-82M"
        result = get_model_v1_models_model_id_get.sync(model_id=model_id, client=client)
        assert result is not None
        assert result.id == model_id
        assert result.task.value == "tts"

    def test_get_qwen3_asr_model(self, client):
        model_id = "Qwen/Qwen3-ASR-0.6B"
        result = get_model_v1_models_model_id_get.sync(model_id=model_id, client=client)
        assert result is not None
        assert result.task.value == "stt"
        assert result.backend.value == "transformers"

    def test_model_status_not_downloaded(self, client):
        model_id = "Qwen/Qwen3-ASR-1.7B"
        result = get_model_v1_models_model_id_get.sync(model_id=model_id, client=client)
        assert result is not None
        assert result.status in (ModelStatus.NOT_DOWNLOADED, ModelStatus.AVAILABLE)

    def test_unsupported_model_404(self, client):
        raw = client.get_httpx_client().get("/v1/models/does-not-exist/model")
        assert raw.status_code == 404
