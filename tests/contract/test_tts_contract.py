"""Contract tests: TTS endpoints using pyttsx3 (no model download needed)."""

from vocal_sdk.api.audio import list_voices_v1_audio_voices_get, text_to_speech_v1_audio_speech_post
from vocal_sdk.models import TTSRequest, TTSRequestResponseFormat


class TestTTSSpeech:
    def test_synthesize_mp3(self, client):
        body = TTSRequest(model="pyttsx3", input_="Hello world.", response_format=TTSRequestResponseFormat.MP3)
        resp = text_to_speech_v1_audio_speech_post.sync_detailed(client=client, body=body)
        assert resp.status_code == 200
        assert len(resp.content) > 0

    def test_synthesize_wav(self, client):
        body = TTSRequest(model="pyttsx3", input_="Testing.", response_format=TTSRequestResponseFormat.WAV)
        resp = text_to_speech_v1_audio_speech_post.sync_detailed(client=client, body=body)
        assert resp.status_code == 200
        assert resp.content[:4] == b"RIFF"

    def test_synthesize_pcm(self, client):
        body = TTSRequest(model="pyttsx3", input_="PCM test.", response_format=TTSRequestResponseFormat.PCM)
        resp = text_to_speech_v1_audio_speech_post.sync_detailed(client=client, body=body)
        assert resp.status_code == 200
        assert len(resp.content) > 0

    def test_content_type_mp3(self, client):
        body = TTSRequest(model="pyttsx3", input_="hi", response_format=TTSRequestResponseFormat.MP3)
        resp = text_to_speech_v1_audio_speech_post.sync_detailed(client=client, body=body)
        assert "audio" in resp.headers.get("content-type", "")

    def test_duration_header(self, client):
        body = TTSRequest(model="pyttsx3", input_="duration test")
        resp = text_to_speech_v1_audio_speech_post.sync_detailed(client=client, body=body)
        assert resp.status_code == 200
        assert "x-duration" in resp.headers or "X-Duration" in resp.headers

    def test_unknown_model_returns_error(self, client):
        raw = client.get_httpx_client().post("/v1/audio/speech", json={"model": "not-a-real-model", "input": "fail"})
        assert raw.status_code in (400, 422, 500)

    def test_empty_text_handled(self, client):
        raw = client.get_httpx_client().post("/v1/audio/speech", json={"model": "pyttsx3", "input": ""})
        assert raw.status_code in (200, 400, 422)


class TestVoices:
    def test_list_voices_pyttsx3(self, client):
        result = list_voices_v1_audio_voices_get.sync(client=client)
        assert result is not None
        assert result.total >= 0
        assert isinstance(result.voices, list)

    def test_voices_have_required_fields(self, client):
        result = list_voices_v1_audio_voices_get.sync(client=client)
        assert result is not None
        for v in result.voices:
            assert v.id
            assert v.name
            assert v.language
