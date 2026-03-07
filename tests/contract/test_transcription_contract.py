"""Contract tests: transcription API surface (schema, errors, unsupported formats)."""
import io


class TestTranscriptionContract:
    def test_missing_file_returns_422(self, client):
        raw = client.get_httpx_client().post("/v1/audio/transcriptions", data={"model": "Systran/faster-whisper-tiny"})
        assert raw.status_code == 422

    def test_missing_model_returns_422(self, client):
        raw = client.get_httpx_client().post(
            "/v1/audio/transcriptions",
            files={"file": ("test.wav", io.BytesIO(b"fake"), "audio/wav")},
        )
        assert raw.status_code in (400, 422)

    def test_unknown_model_returns_error(self, client):
        raw = client.get_httpx_client().post(
            "/v1/audio/transcriptions",
            files={"file": ("test.wav", io.BytesIO(b"RIFF" + b"\x00" * 44), "audio/wav")},
            data={"model": "nonexistent/model"},
        )
        assert raw.status_code in (400, 422, 500)

    def test_translation_unknown_model_returns_error(self, client):
        raw = client.get_httpx_client().post(
            "/v1/audio/translations",
            files={"file": ("test.wav", io.BytesIO(b"fake"), "audio/wav")},
            data={"model": "nonexistent/model"},
        )
        assert raw.status_code in (400, 422, 500)


class TestCloneContract:
    def test_clone_no_model_downloaded_returns_error(self, client):
        fake_audio = b"RIFF" + b"\x00" * 44
        raw = client.get_httpx_client().post(
            "/v1/audio/clone",
            files={"reference_audio": ("ref.wav", io.BytesIO(fake_audio), "audio/wav")},
            data={"text": "hello", "model": "Qwen/Qwen3-TTS-12Hz-0.6B-Base"},
        )
        assert raw.status_code in (400, 422, 500)

    def test_clone_missing_reference_returns_422(self, client):
        raw = client.get_httpx_client().post("/v1/audio/clone", data={"text": "hello"})
        assert raw.status_code == 422
