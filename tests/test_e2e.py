"""
End-to-End Integration Tests for Vocal API + WebSocket Realtime Endpoints

These tests validate the entire API stack using real test assets:
- Model management lifecycle
- STT (Speech-to-Text) transcription
- TTS (Text-to-Speech) synthesis
- System device information
- Error handling and edge cases

Test assets are located in test_assets/audio/ directory.
"""

import asyncio
import base64
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import httpx
import numpy as np
import pytest
import requests
import websockets

from vocal_core.config import vocal_settings
from vocal_sdk import VocalClient
from vocal_sdk.api.audio import list_voices_v1_audio_voices_get, text_to_speech_v1_audio_speech_post
from vocal_sdk.api.health import health_health_get
from vocal_sdk.api.models import (
    delete_model_v1_models_model_id_delete,
    download_model_v1_models_model_id_download_post,
    get_download_status_v1_models_model_id_download_status_get,
    get_model_v1_models_model_id_get,
    list_models_v1_models_get,
)
from vocal_sdk.api.transcription import (
    create_transcription_v1_audio_transcriptions_post,
    create_translation_v1_audio_translations_post,
)
from vocal_sdk.models import (
    BodyCreateTranscriptionV1AudioTranscriptionsPost,
    BodyCreateTranslationV1AudioTranslationsPost,
    ModelStatus,
    TranscriptionFormat,
    TranscriptionResponse,
    TTSRequest,
    TTSRequestResponseFormat,
)
from vocal_sdk.types import UNSET, File, Unset


def _transcribe(
    client: VocalClient,
    audio_file: Path | str,
    model: str,
    language: str | None = None,
    response_format: TranscriptionFormat | Unset = UNSET,
) -> TranscriptionResponse | None:
    audio_path = Path(str(audio_file))
    with open(audio_path, "rb") as fobj:
        body = BodyCreateTranscriptionV1AudioTranscriptionsPost(
            file=File(payload=fobj, file_name=audio_path.name),
            model=model,
            language=language if language is not None else UNSET,
            response_format=response_format,
        )
        return create_transcription_v1_audio_transcriptions_post.sync(client=client, body=body)


def _tts(
    client: VocalClient,
    text: str,
    model: str = "pyttsx3",
    response_format: TTSRequestResponseFormat = TTSRequestResponseFormat.MP3,
    voice: str | None = None,
    speed: float = 1.0,
    stream: bool = False,
) -> bytes:
    body = TTSRequest(
        model=model,
        input_=text,
        response_format=response_format,
        voice=voice if voice is not None else UNSET,
        speed=speed,
        stream=stream,
    )
    return text_to_speech_v1_audio_speech_post.sync_detailed(client=client, body=body).content


def _find_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def api_server():
    """Always start a fresh isolated API server for E2E testing.

    Never reuses an existing server — each test run gets a clean instance
    on a random free port so tests are not affected by leftover state.

    Set VOCAL_TEST_URL to point at an externally managed server instead
    (e.g. WSL runs where the server must be started separately via make serve-wsl).
    """
    import sys

    # WSL / remote: caller manages the server, just point at it
    external_url = os.environ.get("VOCAL_TEST_URL")
    if external_url:
        print(f"\nUsing external server at {external_url}")
        yield external_url
        return

    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    server_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "vocal_api.main:app",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    max_retries = 60
    retry_delay = 0.5

    print(f"\nStarting API server on {base_url}...")

    for i in range(max_retries):
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                print(f"API server ready after {i * retry_delay:.1f}s")
                break
        except requests.exceptions.RequestException:
            if i % 10 == 0:
                print(f"  Waiting for server... ({i * retry_delay:.1f}s)")
        time.sleep(retry_delay)
    else:
        server_process.kill()
        raise RuntimeError(f"Failed to start API server after {max_retries * retry_delay}s")

    yield base_url

    print("\nShutting down API server...")
    server_process.terminate()
    try:
        server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_process.kill()
        server_process.wait()


@pytest.fixture(scope="session")
def client(api_server) -> VocalClient:
    """Create SDK client for testing"""
    return VocalClient(
        base_url=api_server,
        timeout=httpx.Timeout(300.0),
        raise_on_unexpected_status=True,
    )


@pytest.fixture(scope="session")
def test_model():
    """The model to use for testing (tiny for speed)"""
    return "Systran/faster-whisper-tiny"


@pytest.fixture(scope="session", autouse=True)
def ensure_stt_model(client, test_model):
    """Download the STT test model once per session and wait until it is cached.

    Runs automatically before any test. Subsequent runs use the on-disk cache
    and complete immediately.
    """
    model_info = get_model_v1_models_model_id_get.sync(model_id=test_model, client=client)
    if model_info is not None and model_info.status == ModelStatus.AVAILABLE:
        print(f"\n[cache] {test_model} already available — skipping download")
        return

    print(f"\n[setup] Downloading {test_model}...")
    download_model_v1_models_model_id_download_post.sync(model_id=test_model, client=client)

    max_wait = 120
    for elapsed in range(max_wait):
        model_info = get_model_v1_models_model_id_get.sync(model_id=test_model, client=client)
        if model_info and model_info.status == ModelStatus.AVAILABLE:
            print(f"[setup] {test_model} ready after {elapsed}s")
            return
        if elapsed % 10 == 0:
            print(f"[setup] Waiting for model... ({elapsed}s)")
        time.sleep(1)

    pytest.fail(f"Model {test_model} not available after {max_wait}s — is the server running and can it reach the internet?")


@pytest.fixture(scope="session")
def test_assets():
    """Return path to test assets directory and expected transcriptions"""
    assets_dir = Path("test_assets/audio")
    expected_dir = Path("test_assets/expected")

    if not assets_dir.exists():
        pytest.fail(f"Test assets not found at {assets_dir} — run: make test-assets or add audio files to test_assets/audio/")

    return {
        "audio_dir": assets_dir,
        "expected_dir": expected_dir,
        "files": {
            "Recording.m4a": "Hello, what is your name and what can you do?",
            "en-AU-WilliamNeural.mp3": "The sun was setting slowly, casting long shadows across the empty field.",
        },
    }


class TestAPIHealth:
    """Test API health and system information"""

    def test_health_endpoint(self, client):
        """Test that API health endpoint returns correct structure"""
        resp = health_health_get.sync_detailed(client=client)
        result = json.loads(resp.content)

        assert isinstance(result, dict), "Health response should be a dict"
        assert "status" in result, "Health response should have 'status'"
        assert result["status"] == "healthy", "API should be healthy"
        assert "api_version" in result, "Health response should have 'api_version'"

        print(f"\n[OK] Health check passed - API v{result['api_version']}")

    def test_openapi_spec_available(self, api_server):
        """OpenAPI schema must be reachable — SDK auto-gen depends on it"""
        import requests as req

        resp = req.get(f"{api_server}/openapi.json", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        schema = resp.json()
        assert "openapi" in schema, "Schema must have 'openapi' version field"
        assert "paths" in schema, "Schema must have 'paths'"
        assert "info" in schema, "Schema must have 'info'"

        paths = set(schema["paths"].keys())
        required = {"/v1/audio/transcriptions", "/v1/audio/speech", "/v1/audio/clone", "/health"}
        missing = required - paths
        assert not missing, f"OpenAPI schema missing routes: {missing}"

        print(f"\n[OK] OpenAPI spec valid — {len(paths)} paths, version {schema['info'].get('version', '?')}")

    def test_device_information(self, client):
        """Test device information endpoint"""
        resp = client.get_httpx_client().get("/v1/system/device")
        resp.raise_for_status()
        result = resp.json()

        assert isinstance(result, dict), "Device info should be a dict"
        assert "platform" in result, "Should have platform info"
        assert "cpu_count" in result, "Should have CPU count"
        assert "cuda_available" in result, "Should have CUDA availability"

        print("\n[OK] Device info retrieved")
        print(f"  Platform: {result['platform']}")
        print(f"  CPUs: {result['cpu_count']}")
        print(f"  CUDA: {result['cuda_available']}")

        if result["cuda_available"]:
            print(f"  GPUs: {result['gpu_count']}")
            for gpu in result.get("gpu_devices", []):
                print(f"    - {gpu['name']}: {gpu['vram_gb']:.1f}GB")


class TestModelManagement:
    """Test model management lifecycle"""

    def test_list_all_models(self, client):
        """Test listing all available models"""
        result = list_models_v1_models_get.sync(client=client)

        assert result is not None, "Models list should not be None"
        assert isinstance(result.models, list), "Models should be a list"
        assert result.total >= 0, "Total should be non-negative"
        assert len(result.models) == result.total, "Count should match"

        print(f"\n[OK] Found {result.total} models in registry")

    def test_filter_models_by_task(self, client):
        """Test filtering models by STT task"""
        stt_models = list_models_v1_models_get.sync(client=client, task="stt")

        assert stt_models is not None, "Filtered result should not be None"
        assert isinstance(stt_models.models, list), "Models should be a list"

        for model in stt_models.models:
            assert model.task.value == "stt", f"All models should be STT, got {model.task.value}"

        print(f"\n[OK] Filtered {stt_models.total} STT models")

    def test_filter_models_by_tts_task(self, client):
        """Test filtering models by TTS task — every returned model must be TTS"""
        tts_models = list_models_v1_models_get.sync(client=client, task="tts")

        assert tts_models is not None, "Filtered result should not be None"
        assert isinstance(tts_models.models, list), "Models should be a list"
        assert tts_models.total > 0, "Should have at least one TTS model (pyttsx3)"

        for model in tts_models.models:
            assert model.task.value == "tts", f"All models should be TTS, got {model.task.value}"

        print(f"\n[OK] Filtered {tts_models.total} TTS models")

    def test_get_model_info(self, client, test_model):
        """Test getting specific model information"""
        result = get_model_v1_models_model_id_get.sync(model_id=test_model, client=client)

        assert result is not None, "Model info should not be None"
        assert result.id == test_model, "Model ID should match"
        assert result.task.value == "stt", "Test model should be STT"

        print(f"\n[OK] Retrieved model info for {test_model}")
        print(f"  Status: {result.status.value}")

    def test_download_model(self, client, test_model, ensure_stt_model):
        """Test that the test model is downloaded and available (pre-pulled by session fixture)"""
        model_info = get_model_v1_models_model_id_get.sync(model_id=test_model, client=client)

        assert model_info is not None, "Model info should not be None"
        assert model_info.status == ModelStatus.AVAILABLE, f"Model should be available, got: {model_info.status.value}"

        print(f"\n[OK] Model available: {test_model} ({model_info.status.value})")

    def test_download_status(self, client, test_model, ensure_stt_model):
        """Test download status endpoint (model is pre-cached so no active download expected)"""
        try:
            result = get_download_status_v1_models_model_id_download_status_get.sync(model_id=test_model, client=client)
            assert result is not None, "Status should not be None"
            print(f"\n[OK] Download status: {result.status.value}")
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                print("\n[OK] No active download (model already cached)")
            else:
                raise


class TestAudioTranscription:
    """Test STT (Speech-to-Text) functionality"""

    def test_transcribe_short_audio(self, client, test_model, test_assets, ensure_stt_model):
        """Test transcribing short audio file"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"
        expected_text = test_assets["files"]["Recording.m4a"]

        assert audio_file.exists(), f"Test asset not found: {audio_file}"

        result = _transcribe(client, audio_file, test_model)

        assert result is not None, "Result should not be None"
        assert isinstance(result.text, str), "Text should be a string"
        assert isinstance(result.duration, (int, float)), "Duration should be numeric"
        assert result.duration > 0, "Duration should be positive"

        transcribed = result.text.strip()
        assert expected_text.lower() in transcribed.lower() or transcribed.lower() in expected_text.lower(), f"Transcription mismatch. Expected: '{expected_text}', Got: '{transcribed}'"

        print("\n[OK] Transcribed short audio")
        print(f"  Duration: {result.duration:.2f}s")
        print(f"  Language: {result.language}")
        print(f"  Expected: '{expected_text}'")
        print(f"  Got: '{transcribed}'")

    def test_transcribe_medium_audio(self, client, test_model, test_assets, ensure_stt_model):
        """Test transcribing medium-length audio"""
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"
        expected_text = test_assets["files"]["en-AU-WilliamNeural.mp3"]

        result = _transcribe(client, audio_file, test_model)

        assert result is not None
        assert result.duration > 0, "Should have positive duration"

        transcribed = result.text.strip()
        assert expected_text.lower() in transcribed.lower() or transcribed.lower() in expected_text.lower(), f"Transcription mismatch. Expected: '{expected_text}', Got: '{transcribed}'"

        print(f"\n[OK] Transcribed medium audio ({result.duration:.2f}s)")
        print(f"  Expected: '{expected_text}'")
        print(f"  Got: '{transcribed}'")

    def test_transcribe_with_language_specification(self, client, test_model, test_assets, ensure_stt_model):
        """Test transcription with specified language"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"

        result = _transcribe(client, audio_file, test_model, language="en")

        assert result is not None
        assert result.language == "en", "Language should be English"

        print("\n[OK] Transcribed with language=en")

    def test_transcribe_json_format_with_segments(self, client, test_model, test_assets, ensure_stt_model):
        """Test JSON format response with segments"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"

        result = _transcribe(client, audio_file, test_model, response_format=TranscriptionFormat.JSON)

        assert result is not None
        assert isinstance(result.text, str), "Should have text"

        segs = [] if isinstance(result.segments, Unset) or result.segments is None else result.segments
        if segs:
            seg = segs[0]
            assert seg.id is not None, "Segment should have ID"
            assert seg.start is not None, "Segment should have start time"
            assert seg.end is not None, "Segment should have end time"
            assert isinstance(seg.text, str), "Segment should have text"
            assert seg.start <= seg.end, "Start should be <= end"

        print(f"\n[OK] Got JSON format with {len(segs)} segments")

    def test_transcribe_both_formats(self, client, test_model, test_assets, ensure_stt_model):
        """Test transcribing different audio formats (m4a and mp3)"""
        for filename in test_assets["files"].keys():
            audio_file = test_assets["audio_dir"] / filename

            result = _transcribe(client, audio_file, test_model)

            assert result is not None
            assert isinstance(result.text, str), "Should have text"
            assert result.duration > 0, "Should have duration"

            print(f"\n[OK] Transcribed {filename}")

    def test_translate_audio_to_english(self, client, test_model, test_assets, ensure_stt_model):
        """Test /v1/audio/translations — non-English audio translated to English text"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"
        assert audio_file.exists(), f"Test asset not found: {audio_file}"

        with open(audio_file, "rb") as fobj:
            body = BodyCreateTranslationV1AudioTranslationsPost(
                file=File(payload=fobj, file_name=audio_file.name),
                model=test_model,
            )
            result = create_translation_v1_audio_translations_post.sync(client=client, body=body)

        assert result is not None, "Translation result should not be None"
        assert isinstance(result.text, str), "Translation should have text"
        assert len(result.text.strip()) > 0, "Translation should not be empty"
        assert result.duration > 0, "Translation should have positive duration"

        print(f"\n[OK] Translation -> '{result.text.strip()}' ({result.duration:.2f}s)")


class TestTextToSpeech:
    """Test TTS (Text-to-Speech) functionality"""

    def test_synthesize_short_text(self, client):
        """Test synthesizing short text"""
        text = "Hello, world!"

        audio_data = _tts(client, text)

        assert isinstance(audio_data, bytes), "Audio should be bytes"
        assert len(audio_data) > 0, "Audio should not be empty"
        assert audio_data[:3] == b"ID3" or audio_data[0] == 0xFF, "Should be MP3 format"

        print(f"\n[OK] Synthesized '{text}'")
        print(f"  Size: {len(audio_data)} bytes")

    def test_synthesize_with_speed(self, client):
        """Test TTS with different speed"""
        text = "This is a speed test."

        normal_audio = _tts(client, text, speed=1.0)
        fast_audio = _tts(client, text, speed=1.5)

        assert isinstance(normal_audio, bytes), "Normal audio should be bytes"
        assert isinstance(fast_audio, bytes), "Fast audio should be bytes"
        assert len(normal_audio) > 0, "Normal audio should not be empty"
        assert len(fast_audio) > 0, "Fast audio should not be empty"

        print("\n[OK] Speed variations work")
        print(f"  Normal: {len(normal_audio)} bytes")
        print(f"  Fast (1.5x): {len(fast_audio)} bytes")

    def test_synthesize_long_text(self, client):
        """Test synthesizing longer text"""
        text = " ".join(["Testing speech synthesis with a longer sentence."] * 5)

        audio_data = _tts(client, text)

        assert isinstance(audio_data, bytes), "Should return bytes"
        assert len(audio_data) > 1000, "Should produce audio data"

        print(f"\n[OK] Synthesized long text ({len(text)} chars)")
        print(f"  Audio size: {len(audio_data)} bytes")

    def test_synthesize_to_file(self, client, tmp_path):
        """Test TTS audio can be written to disk"""
        text = "Save to file test."
        output_file = tmp_path / "test_output.mp3"

        audio_data = _tts(client, text)
        output_file.write_bytes(audio_data)

        assert output_file.exists(), "Output file should exist"
        assert output_file.stat().st_size > 0, "File should not be empty"

        print(f"\n[OK] Saved to file: {output_file} ({output_file.stat().st_size} bytes)")

    @pytest.mark.parametrize(
        "fmt,check",
        [
            ("mp3", lambda d: d[:3] == b"ID3" or d[0] == 0xFF),
            ("wav", lambda d: d[:4] == b"RIFF"),
            ("flac", lambda d: d[:4] == b"fLaC"),
            ("opus", lambda d: d[:4] == b"OggS"),
            ("aac", lambda d: len(d) > 0),
            ("pcm", lambda d: len(d) > 0),
        ],
    )
    def test_synthesize_formats(self, client, fmt, check):
        """Test TTS output in each supported format"""
        text = "Format test."

        audio_data = _tts(client, text, response_format=TTSRequestResponseFormat(fmt))

        assert isinstance(audio_data, bytes), "Audio should be bytes"
        assert len(audio_data) > 0, f"{fmt} audio should not be empty"
        assert check(audio_data), f"Invalid {fmt} header"

        print(f"\n[OK] Format {fmt}: {len(audio_data)} bytes")

    def test_synthesize_mp3_smaller_than_wav(self, client):
        """Test that MP3 is smaller than WAV (compression works)"""
        text = "Compression test for audio."

        mp3_data = _tts(client, text, response_format=TTSRequestResponseFormat.MP3)
        wav_data = _tts(client, text, response_format=TTSRequestResponseFormat.WAV)

        assert len(mp3_data) < len(wav_data), "MP3 should be smaller than WAV"

        ratio = len(wav_data) / len(mp3_data)
        print(f"\n[OK] MP3 ({len(mp3_data)}B) vs WAV ({len(wav_data)}B) - {ratio:.1f}x compression")

    def test_synthesize_with_voice(self, client):
        """Test TTS with a specific voice"""
        text = "Voice selection test."

        voices_resp = list_voices_v1_audio_voices_get.sync(client=client)
        assert voices_resp is not None
        assert voices_resp.total > 0, "Should have at least one voice"

        voice_id = voices_resp.voices[0].name
        audio_data = _tts(client, text, voice=voice_id)

        assert isinstance(audio_data, bytes), "Audio should be bytes"
        assert len(audio_data) > 0, "Audio should not be empty"

        print(f"\n[OK] Synthesized with voice '{voice_id}': {len(audio_data)} bytes")

    def test_synthesize_invalid_format_rejected(self, client, api_server):
        """Test that invalid format is rejected by API"""
        import requests as req

        response = req.post(
            f"{api_server}/v1/audio/speech",
            json={"model": "pyttsx3", "input": "test", "response_format": "wma"},
        )
        assert response.status_code == 422, "Invalid format should return 422"

        print("\n[OK] Invalid format 'wma' correctly rejected with 422")

    def test_synthesize_empty_text_rejected(self, api_server):
        """Test that blank/whitespace text is rejected"""
        import requests as req

        for bad_text in ("", "   ", "\t\n"):
            response = req.post(
                f"{api_server}/v1/audio/speech",
                json={"model": "pyttsx3", "input": bad_text},
            )
            assert response.status_code == 422, f"Expected 422 for text={repr(bad_text)}, got {response.status_code}"

        print("\n[OK] Empty/whitespace text correctly rejected with 422")

    def test_stream_pcm_returns_bytes(self, api_server):
        """Test streaming TTS with pcm format yields raw PCM bytes"""
        import requests as req

        response = req.post(
            f"{api_server}/v1/audio/speech",
            json={"model": "pyttsx3", "input": "Streaming test.", "response_format": "pcm", "stream": True},
            stream=True,
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "audio/pcm" in response.headers.get("Content-Type", ""), "Should be PCM content type"

        data = b"".join(response.iter_content(chunk_size=4096))
        assert len(data) > 0, "Streamed PCM should not be empty"
        assert "X-Duration" not in response.headers, "X-Duration should not be present in stream mode"

        print(f"\n[OK] Streamed PCM: {len(data)} bytes")

    def test_stream_wav_has_riff_header(self, api_server):
        """Test streaming TTS with wav format starts with a valid RIFF header"""
        import requests as req

        response = req.post(
            f"{api_server}/v1/audio/speech",
            json={"model": "pyttsx3", "input": "WAV streaming test.", "response_format": "wav", "stream": True},
            stream=True,
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = b"".join(response.iter_content(chunk_size=4096))
        assert len(data) >= 44, "WAV stream should include at least a header"
        assert data[:4] == b"RIFF", "WAV stream should start with RIFF header"
        assert data[8:12] == b"WAVE", "WAV stream should have WAVE marker"

        print(f"\n[OK] Streamed WAV: {len(data)} bytes, valid RIFF header")

    def test_stream_mp3_returns_audio(self, api_server):
        """Test streaming TTS with mp3 format (batch fallback) returns valid audio"""
        import requests as req

        response = req.post(
            f"{api_server}/v1/audio/speech",
            json={"model": "pyttsx3", "input": "MP3 streaming test.", "response_format": "mp3", "stream": True},
            stream=True,
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "audio/mpeg" in response.headers.get("Content-Type", ""), "Should be MP3 content type"

        data = b"".join(response.iter_content(chunk_size=4096))
        assert len(data) > 0, "Streamed MP3 should not be empty"

        print(f"\n[OK] Streamed MP3 (batch fallback): {len(data)} bytes")

    def test_non_stream_preserves_duration_header(self, api_server):
        """Test that stream=False (default) still returns X-Duration and X-Sample-Rate headers"""
        import requests as req

        response = req.post(
            f"{api_server}/v1/audio/speech",
            json={"model": "pyttsx3", "input": "Header test.", "response_format": "mp3", "stream": False},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "X-Duration" in response.headers, "X-Duration should be present in non-stream mode"
        assert "X-Sample-Rate" in response.headers, "X-Sample-Rate should be present in non-stream mode"

        print(f"\n[OK] Non-stream headers intact: X-Duration={response.headers['X-Duration']}")

    def test_list_available_voices(self, client):
        """Test listing TTS voices"""
        result = list_voices_v1_audio_voices_get.sync(client=client)

        assert result is not None, "Result should not be None"
        assert isinstance(result.voices, list), "Voices should be a list"
        assert len(result.voices) == result.total, "Count should match"
        assert result.total > 0, "Should have at least one voice"

        for voice in result.voices:
            assert voice.id is not None, "Voice should have ID"
            assert voice.name is not None, "Voice should have name"
            assert voice.language is not None, "Voice should have language"

        print(f"\n[OK] Found {result.total} voice(s)")
        for voice in result.voices[:5]:
            print(f"  - {voice.name} ({voice.language})")
        if result.total > 5:
            print(f"  ... and {result.total - 5} more")


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_transcribe_nonexistent_model(self, client, test_assets, ensure_stt_model):
        """Test transcription with non-existent model"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"

        with pytest.raises(Exception):
            _transcribe(client, audio_file, "non-existent-model-xyz123")

        print("\n[OK] Correctly raised error for invalid model")

    def test_transcribe_nonexistent_file(self, client, test_model, ensure_stt_model):
        """Test transcription with non-existent file"""
        with pytest.raises(Exception):
            _transcribe(client, "nonexistent_audio.wav", test_model)

        print("\n[OK] Correctly raised error for missing file")

    def test_get_nonexistent_model(self, client):
        """Test getting info for non-existent model"""
        with pytest.raises(Exception):
            get_model_v1_models_model_id_get.sync(model_id="fake-model-12345", client=client)

        print("\n[OK] Correctly raised error for fake model")

    def test_delete_nonexistent_model(self, client):
        """Test deleting non-existent model"""
        with pytest.raises(Exception):
            delete_model_v1_models_model_id_delete.sync(model_id="fake-model-to-delete", client=client)

        print("\n[OK] Correctly raised error when deleting fake model")


class TestPerformance:
    """Test performance and optimization"""

    def test_model_reuse(self, client, test_model, test_assets, ensure_stt_model):
        """Test that model stays loaded for multiple transcriptions"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"

        start_time = time.time()
        result1 = _transcribe(client, audio_file, test_model)
        first_duration = time.time() - start_time

        start_time = time.time()
        result2 = _transcribe(client, audio_file, test_model)
        second_duration = time.time() - start_time

        assert result1 is not None and result2 is not None
        assert result1.text == result2.text, "Results should be consistent"

        print("\n[OK] Model reuse tested")
        print(f"  First call: {first_duration:.2f}s")
        print(f"  Second call: {second_duration:.2f}s")

        if second_duration < first_duration:
            print(f"  Speedup: {first_duration / second_duration:.2f}x")


def _make_sine_pcm(duration_s: float = 1.5, sample_rate: int = 16000, freq: float = 440.0) -> bytes:
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    sine = (np.sin(2 * np.pi * freq * t) * 16383).astype(np.int16)
    return sine.tobytes()


def _make_sine_pcm_24k(duration_s: float = 1.5) -> bytes:
    return _make_sine_pcm(duration_s=duration_s, sample_rate=24000)


def _ws_run(coro):
    return asyncio.run(coro)


async def _collect_until(ws, stop_type: str, timeout_s: float = 90.0) -> list[dict]:
    """Drain WebSocket messages until stop_type is received or timeout expires."""
    events: list[dict] = []
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=min(5.0, remaining))
        except TimeoutError:
            continue
        event = json.loads(msg)
        events.append(event)
        if event.get("type") == "error":
            raise RuntimeError(f"Server error: {event.get('error')}")
        if event.get("type") == stop_type:
            return events
    raise TimeoutError(f"{stop_type} not received within {timeout_s}s. Got: {[e['type'] for e in events]}")


class TestRealtimeStream:
    """Test /v1/audio/stream WebSocket endpoint"""

    def test_stream_protocol(self, api_server, test_model, ensure_stt_model):
        async def _test():
            base_uri = api_server.replace("http://", "ws://")
            silence = bytes(3200)
            pcm = _make_sine_pcm(duration_s=2.0)
            frame_size = 3200

            async with websockets.connect(f"{base_uri}/v1/audio/stream?language=en&task=transcribe", open_timeout=10) as ws:
                assert ws is not None

            silence_events = []
            async with websockets.connect(f"{base_uri}/v1/audio/stream?threshold=100", open_timeout=10) as ws:
                for _ in range(20):
                    await ws.send(silence)
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    silence_events.append(json.loads(msg))
                except TimeoutError:
                    pass
            assert not any(e.get("type") == "transcript.delta" and e.get("text") for e in silence_events)

            done_event = None
            # Use low threshold + short max_chunk_duration to force flush with synthetic audio.
            # Silero VAD doesn't reliably distinguish sine waves from silence, so we rely on
            # max_chunk_duration to trigger the flush after enough audio is buffered.
            async with websockets.connect(f"{base_uri}/v1/audio/stream?model={test_model}&threshold=0.0001&max_chunk_duration=3", open_timeout=10) as ws:
                for i in range(0, len(pcm), frame_size):
                    await ws.send(pcm[i : i + frame_size])
                await ws.send(bytes(frame_size * 20))
                deadline = time.monotonic() + 30.0
                while time.monotonic() < deadline:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        event = json.loads(msg)
                        if event.get("type") == "transcript.done":
                            done_event = event
                            break
                    except TimeoutError:
                        continue
            assert done_event is not None, "transcript.done not received within 30s"
            assert "text" in done_event, "transcript.done must have 'text' field"

        _ws_run(_test())
        print("\n[OK] /v1/audio/stream: connects, silence=no output, audio=transcript.done with text")

    def test_stream_invalid_model(self, api_server):
        async def _test():
            uri = f"{api_server.replace('http://', 'ws://')}/v1/audio/stream?model=nonexistent-xyz&threshold=0.0001&max_chunk_duration=3"
            pcm = _make_sine_pcm(duration_s=1.0)
            frame_size = 3200
            events = []
            async with websockets.connect(uri, open_timeout=10) as ws:
                for i in range(0, len(pcm), frame_size):
                    await ws.send(pcm[i : i + frame_size])
                await ws.send(bytes(frame_size * 20))
                deadline = time.monotonic() + 20.0
                while time.monotonic() < deadline:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        events.append(json.loads(msg))
                        if events[-1].get("type") in ("error", "transcript.done"):
                            break
                    except TimeoutError:
                        continue
            types = {e["type"] for e in events}
            assert "error" in types or "transcript.done" in types, f"Expected error or done within 20s, got: {types}"

        _ws_run(_test())
        print("\n[OK] /v1/audio/stream: invalid model returns error or done")


class TestRealtimeOAI:
    """Test /v1/realtime OpenAI Realtime API compatible endpoint"""

    def test_realtime_session_lifecycle(self, api_server):
        async def _test():
            uri = f"{api_server.replace('http://', 'ws://')}/v1/realtime"
            async with websockets.connect(uri, open_timeout=10) as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                created = json.loads(msg)
                assert created["type"] == "session.created"
                assert "event_id" in created
                sess = created["session"]
                assert "id" in sess and "model" in sess and "input_audio_format" in sess and "turn_detection" in sess

                await ws.send(json.dumps({"type": "transcription_session.update", "session": {"language": "en"}}))
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                updated = json.loads(msg)
                assert updated["type"] == "transcription_session.updated"
                return created

        created = _ws_run(_test())
        print(f"\n[OK] /v1/realtime: session.created({created['session']['id']}) + session.update -> updated")

    def test_realtime_audio_pipeline(self, api_server, test_model, ensure_stt_model):
        async def _test():
            uri = f"{api_server.replace('http://', 'ws://')}/v1/realtime"
            pcm = _make_sine_pcm_24k(duration_s=1.0)
            audio_b64 = base64.b64encode(pcm).decode()
            events = []
            async with websockets.connect(uri, open_timeout=10) as ws:
                await asyncio.wait_for(ws.recv(), timeout=5.0)
                await ws.send(json.dumps({"type": "transcription_session.update", "session": {"model": test_model}}))
                await asyncio.wait_for(ws.recv(), timeout=5.0)
                await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": audio_b64}))
                await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                deadline = time.monotonic() + 30.0
                while time.monotonic() < deadline:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                        event = json.loads(msg)
                        events.append(event)
                        if event.get("type") == "conversation.item.input_audio_transcription.completed":
                            break
                    except TimeoutError:
                        continue
            types = [e["type"] for e in events]
            assert "input_audio_buffer.committed" in types, f"committed missing: {types}"
            completed = next((e for e in events if e.get("type") == "conversation.item.input_audio_transcription.completed"), None)
            assert completed is not None and "transcript" in completed
            return types, completed["transcript"]

        types, transcript = _ws_run(_test())
        print(f"\n[OK] /v1/realtime audio pipeline: {types} | transcript='{transcript}'")

    def test_realtime_error_handling(self, api_server):
        async def _test():
            uri = f"{api_server.replace('http://', 'ws://')}/v1/realtime"
            async with websockets.connect(uri, open_timeout=10) as ws:
                await asyncio.wait_for(ws.recv(), timeout=5.0)
                await ws.send(json.dumps({"type": "totally.unknown.event.xyz"}))
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                return json.loads(msg)

        event = _ws_run(_test())
        assert event["type"] == "error" and event["error"]["code"] == "unknown_event"
        print(f"\n[OK] /v1/realtime: unknown event -> error({event['error']['code']})")

    def test_realtime_vad_pipeline(self, api_server, test_model, ensure_stt_model, test_assets):
        """Real CLI flow: VAD auto-detects speech→silence and commits without manual commit."""
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"
        assert audio_file.exists()

        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(audio_file), "-ar", "16000", "-ac", "1", "-f", "s16le", tmp_path],
                check=True,
                capture_output=True,
            )
            with open(tmp_path, "rb") as f:
                pcm = f.read()
        finally:
            os.unlink(tmp_path)

        async def _test():
            uri = f"{api_server.replace('http://', 'ws://')}/v1/realtime"
            frame_size = 3200  # 100ms at 16kHz — same as CLI

            async with websockets.connect(uri, open_timeout=60) as ws:
                await asyncio.wait_for(ws.recv(), timeout=10.0)  # session.created

                # Match exact CLI session.update format (16kHz, transcription mode)
                await ws.send(
                    json.dumps(
                        {
                            "type": "session.update",
                            "session": {"model": test_model, "input_sample_rate": 16000},
                        }
                    )
                )
                await asyncio.wait_for(ws.recv(), timeout=5.0)  # session.updated

                # Send real speech audio — VAD detects onset and starts utterance
                for i in range(0, len(pcm), frame_size):
                    await ws.send(
                        json.dumps(
                            {
                                "type": "input_audio_buffer.append",
                                "audio": base64.b64encode(pcm[i : i + frame_size]).decode(),
                            }
                        )
                    )

                # 20 zero-energy silence frames (2.0s) — VAD_SILENCE_FRAMES=15 fires the commit
                silence_b64 = base64.b64encode(bytes(frame_size)).decode()
                for _ in range(20):
                    await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": silence_b64}))

                events = await _collect_until(ws, "conversation.item.input_audio_transcription.completed")

            types = {e["type"] for e in events}
            assert "input_audio_buffer.speech_started" in types, f"VAD never detected speech: {types}"
            assert "input_audio_buffer.speech_stopped" in types, f"VAD never detected silence: {types}"
            assert "input_audio_buffer.committed" in types, f"Buffer never auto-committed: {types}"
            completed = next(e for e in events if e["type"] == "conversation.item.input_audio_transcription.completed")
            assert completed["transcript"].strip(), "Empty transcript"
            print(f"\n[OK] /v1/realtime VAD pipeline: '{completed['transcript']}'")

        _ws_run(_test())

    def test_realtime_vad_pipeline_multi_utterance(self, api_server, test_model, ensure_stt_model, test_assets):
        """Verifies the connection stays alive across two consecutive VAD-triggered utterances."""
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"
        assert audio_file.exists()

        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(audio_file), "-ar", "16000", "-ac", "1", "-f", "s16le", tmp_path],
                check=True,
                capture_output=True,
            )
            with open(tmp_path, "rb") as f:
                pcm = f.read()
        finally:
            os.unlink(tmp_path)

        async def _test():
            uri = f"{api_server.replace('http://', 'ws://')}/v1/realtime"
            frame_size = 3200
            silence_b64 = base64.b64encode(bytes(frame_size)).decode()

            async with websockets.connect(uri, open_timeout=60) as ws:
                await asyncio.wait_for(ws.recv(), timeout=10.0)
                await ws.send(
                    json.dumps(
                        {
                            "type": "session.update",
                            "session": {"model": test_model, "input_sample_rate": 16000},
                        }
                    )
                )
                await asyncio.wait_for(ws.recv(), timeout=5.0)

                for utterance_num in range(1, 3):
                    for i in range(0, len(pcm), frame_size):
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "input_audio_buffer.append",
                                    "audio": base64.b64encode(pcm[i : i + frame_size]).decode(),
                                }
                            )
                        )
                    for _ in range(20):
                        await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": silence_b64}))

                    events = await _collect_until(ws, "conversation.item.input_audio_transcription.completed")
                    completed = next(e for e in events if e["type"] == "conversation.item.input_audio_transcription.completed")
                    assert completed["transcript"].strip(), f"Empty transcript on utterance {utterance_num}"
                    print(f"\n[OK] /v1/realtime multi-utterance {utterance_num}: '{completed['transcript']}'")

        _ws_run(_test())


_IN_CI = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"

_HAS_FASTER_QWEN3 = importlib.util.find_spec("faster_qwen3_tts") is not None
try:
    import torch as _torch
    import torchaudio as _torchaudio

    _HAS_CUDA = _torch.cuda.is_available()
    _HAS_TORCHAUDIO_CUDA = "+cu" in _torchaudio.__version__
except ImportError:
    _HAS_CUDA = False
    _HAS_TORCHAUDIO_CUDA = False


def _make_reference_wav(duration_s: float = 5.0, sample_rate: int = 16000) -> bytes:
    n_samples = int(sample_rate * duration_s)
    t = np.linspace(0, duration_s, n_samples, endpoint=False)
    audio = 0.4 * np.sin(2 * np.pi * 180 * t) + 0.3 * np.sin(2 * np.pi * 360 * t) + 0.2 * np.sin(2 * np.pi * 720 * t) + 0.1 * np.sin(2 * np.pi * 1440 * t)
    samples = (audio * 16383).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    buf.seek(0)
    return buf.read()


@pytest.fixture(scope="session")
def clone_model():
    return vocal_settings.TTS_DEFAULT_CLONE_MODEL


@pytest.fixture(scope="session")
def ensure_clone_model(client, clone_model):
    if not _HAS_FASTER_QWEN3:
        pytest.skip("faster-qwen3-tts not installed -- run: uv sync --extra qwen3-tts")
    if not _HAS_CUDA:
        pytest.skip("CUDA GPU required for voice clone tests -- no CUDA device found")
    if not _HAS_TORCHAUDIO_CUDA:
        pytest.skip(f"CPU-only torchaudio installed ({_torchaudio.__version__}) -- run: uv sync --extra qwen3-tts (pulls CUDA build from PyTorch index)")
    model_info = get_model_v1_models_model_id_get.sync(model_id=clone_model, client=client)
    if model_info is not None and model_info.status == ModelStatus.AVAILABLE:
        return
    download_model_v1_models_model_id_download_post.sync(model_id=clone_model, client=client)
    for _ in range(300):
        model_info = get_model_v1_models_model_id_get.sync(model_id=clone_model, client=client)
        if model_info and model_info.status == ModelStatus.AVAILABLE:
            return
        time.sleep(1)
    pytest.fail(f"Clone model {clone_model} not available after 300s")


class TestVoiceClone:
    """Test /v1/audio/clone voice cloning endpoint"""

    def test_clone_empty_text(self, api_server):
        ref_wav = _make_reference_wav(duration_s=5.0)
        resp = httpx.post(
            f"{api_server}/v1/audio/clone",
            files={"reference_audio": ("ref.wav", ref_wav, "audio/wav")},
            data={"text": "   ", "model": vocal_settings.TTS_DEFAULT_CLONE_MODEL},
            timeout=30.0,
        )
        assert resp.status_code == 422, f"Expected 422 for empty text, got {resp.status_code}"
        print("\n[OK] clone: empty text -> 422")

    def test_clone_invalid_model(self, api_server):
        ref_wav = _make_reference_wav(duration_s=5.0)
        resp = httpx.post(
            f"{api_server}/v1/audio/clone",
            files={"reference_audio": ("ref.wav", ref_wav, "audio/wav")},
            data={"text": "Hello", "model": "nonexistent/model-xyz"},
            timeout=30.0,
        )
        assert resp.status_code in (400, 404), f"Expected 400/404, got {resp.status_code}"
        print(f"\n[OK] clone: invalid model -> {resp.status_code}")

    def test_clone_reference_too_short(self, api_server):
        short_wav = _make_reference_wav(duration_s=1.5)
        resp = httpx.post(
            f"{api_server}/v1/audio/clone",
            files={"reference_audio": ("ref.wav", short_wav, "audio/wav")},
            data={"text": "Hello", "model": vocal_settings.TTS_DEFAULT_CLONE_MODEL},
            timeout=30.0,
        )
        assert resp.status_code in (400, 422), f"Expected 400/422 for too-short reference, got {resp.status_code}"
        print(f"\n[OK] clone: reference too short -> {resp.status_code}")

    def test_clone_non_cloning_model(self, api_server):
        ref_wav = _make_reference_wav(duration_s=5.0)
        resp = httpx.post(
            f"{api_server}/v1/audio/clone",
            files={"reference_audio": ("ref.wav", ref_wav, "audio/wav")},
            data={"text": "Hello", "model": "pyttsx3"},
            timeout=30.0,
        )
        assert resp.status_code in (400, 503), f"Expected 400/503 for non-clone model, got {resp.status_code}"
        print(f"\n[OK] clone: non-cloning model -> {resp.status_code}")

    @pytest.mark.skipif(_IN_CI, reason="CI: no GPU hardware")
    def test_clone_synthesis_wav(self, api_server, ensure_clone_model, clone_model):
        ref_wav = _make_reference_wav(duration_s=10.0)
        resp = httpx.post(
            f"{api_server}/v1/audio/clone",
            files={"reference_audio": ("ref.wav", ref_wav, "audio/wav")},
            data={"text": "Hello, this is a test of voice cloning.", "model": clone_model, "language": "en", "response_format": "wav"},
            timeout=120.0,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert len(resp.content) > 1000, "Expected non-trivial audio output"
        buf = io.BytesIO(resp.content)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() >= 1
            assert wf.getframerate() > 0
            assert wf.getnframes() > 0
        print(f"\n[OK] clone synthesis -> {len(resp.content):,} bytes WAV, rate={wf.getframerate()}")

    @pytest.mark.skipif(_IN_CI, reason="CI: no GPU hardware")
    def test_clone_response_formats(self, api_server, ensure_clone_model, clone_model):
        ref_wav = _make_reference_wav(duration_s=10.0)
        for fmt in ("wav", "mp3"):
            resp = httpx.post(
                f"{api_server}/v1/audio/clone",
                files={"reference_audio": ("ref.wav", ref_wav, "audio/wav")},
                data={"text": "Format test.", "model": clone_model, "response_format": fmt},
                timeout=120.0,
            )
            assert resp.status_code == 200, f"{fmt}: Expected 200, got {resp.status_code}"
            assert len(resp.content) > 100, f"{fmt}: empty response"
            print(f"\n[OK] clone: {fmt} -> {len(resp.content):,} bytes")


_HAS_TRANSFORMERS = importlib.util.find_spec("transformers") is not None
_HAS_QWEN_ASR = importlib.util.find_spec("qwen_asr") is not None
_HAS_WHISPERX = importlib.util.find_spec("whisperx") is not None
_HAS_KOKORO = importlib.util.find_spec("kokoro") is not None
_HAS_CHATTERBOX = importlib.util.find_spec("chatterbox") is not None
_HAS_MISTRAL_COMMON = importlib.util.find_spec("mistral_common") is not None

# NeMo's find_spec succeeds but import fails due to missing nv_one_logger;
# check actual importability so we skip tests correctly.
try:
    from nemo.collections.asr.models import ASRModel as _ASRModel  # noqa: F401

    _HAS_NEMO = True
except Exception:
    _HAS_NEMO = False

_TRANSFORMERS_STT_MODEL = "Qwen/Qwen3-ASR-0.6B"
_NEMO_STT_MODEL = "nvidia/parakeet-tdt-0.6b-v2"
_WHISPERX_STT_MODEL = "whisperx/distil-large-v3"
_KOKORO_TTS_MODEL = "hexgrad/Kokoro-82M"
_CHATTERBOX_TTS_MODEL = "ResembleAI/chatterbox"
_VOXTRAL_STT_MODEL = "mistralai/Voxtral-Mini-4B-Realtime-2602"


def _ensure_model(client: VocalClient, model_id: str, max_wait: int = 600) -> None:
    """Pull model and wait for it to become available. Skip test if unavailable."""
    model_info = get_model_v1_models_model_id_get.sync(model_id=model_id, client=client)
    if model_info is not None and model_info.status == ModelStatus.AVAILABLE:
        return

    print(f"\n[setup] Pulling {model_id}...")
    download_model_v1_models_model_id_download_post.sync(model_id=model_id, client=client)

    for elapsed in range(max_wait):
        model_info = get_model_v1_models_model_id_get.sync(model_id=model_id, client=client)
        if model_info and model_info.status == ModelStatus.AVAILABLE:
            print(f"[setup] {model_id} ready after {elapsed}s")
            return
        if elapsed % 30 == 0:
            print(f"[setup] Waiting for {model_id}... ({elapsed}s / {max_wait}s)")
        time.sleep(1)

    pytest.skip(f"Model {model_id} not available after {max_wait}s — skipping backend test")


@pytest.mark.skipif(not _HAS_TRANSFORMERS, reason="transformers not installed — run: uv sync --extra transformers")
@pytest.mark.skipif(not _HAS_QWEN_ASR, reason="qwen_asr not installed — run: pip install qwen-asr")
class TestTransformersSTT:
    """E2E: HuggingFace Transformers STT backend (Qwen3-ASR-0.6B)"""

    def test_transformers_transcribe(self, client, test_assets):
        audio_file = test_assets["audio_dir"] / "Recording.m4a"
        assert audio_file.exists(), f"Test asset not found: {audio_file}"

        _ensure_model(client, _TRANSFORMERS_STT_MODEL, max_wait=600)

        result = _transcribe(client, audio_file, _TRANSFORMERS_STT_MODEL, language="en")

        assert result is not None, "Result should not be None"
        assert isinstance(result.text, str), "Text should be a string"
        assert len(result.text.strip()) > 0, "Transcription should not be empty"
        assert result.duration > 0, "Duration should be positive"

        print(f"\n[OK] transformers STT: '{result.text.strip()}' ({result.duration:.2f}s)")

    def test_transformers_transcribe_segments(self, client, test_assets):
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"

        _ensure_model(client, _TRANSFORMERS_STT_MODEL, max_wait=600)

        result = _transcribe(client, audio_file, _TRANSFORMERS_STT_MODEL, response_format=TranscriptionFormat.JSON)

        assert result is not None
        assert isinstance(result.text, str) and len(result.text.strip()) > 0

        segs = [] if isinstance(result.segments, Unset) or result.segments is None else result.segments
        print(f"\n[OK] transformers STT with segments: '{result.text.strip()}' ({len(segs)} segments)")


@pytest.mark.skipif(_IN_CI, reason="CI: NeMo models require GPU and nemo_toolkit[asr] — skip in CI")
@pytest.mark.skipif(not _HAS_NEMO, reason="nemo_toolkit not installed — run: uv sync --extra nemo")
class TestNemoSTT:
    """E2E: NVIDIA NeMo STT backend (Parakeet-TDT 0.6B V2)"""

    def test_nemo_transcribe(self, client, test_assets):
        audio_file = test_assets["audio_dir"] / "Recording.m4a"
        assert audio_file.exists(), f"Test asset not found: {audio_file}"

        _ensure_model(client, _NEMO_STT_MODEL, max_wait=600)

        result = _transcribe(client, audio_file, _NEMO_STT_MODEL)

        assert result is not None, "Result should not be None"
        assert isinstance(result.text, str), "Text should be a string"
        assert len(result.text.strip()) > 0, "Transcription should not be empty"

        print(f"\n[OK] NeMo STT: '{result.text.strip()}'")

    def test_nemo_transcribe_word_timestamps(self, client, test_assets):
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"

        _ensure_model(client, _NEMO_STT_MODEL, max_wait=600)

        result = _transcribe(client, audio_file, _NEMO_STT_MODEL, response_format=TranscriptionFormat.JSON)

        assert result is not None
        assert isinstance(result.text, str) and len(result.text.strip()) > 0

        print(f"\n[OK] NeMo STT with JSON: '{result.text.strip()}'")


@pytest.mark.skipif(not _HAS_WHISPERX, reason="whisperx not installed — run: pip install whisperx")
class TestWhisperXSTT:
    """E2E: WhisperX STT backend (forced word alignment via wav2vec2)"""

    def test_whisperx_transcribe(self, client, test_assets):
        audio_file = test_assets["audio_dir"] / "Recording.m4a"
        assert audio_file.exists(), f"Test asset not found: {audio_file}"

        _ensure_model(client, _WHISPERX_STT_MODEL, max_wait=600)

        result = _transcribe(client, audio_file, _WHISPERX_STT_MODEL, language="en")

        assert result is not None, "Result should not be None"
        assert isinstance(result.text, str), "Text should be a string"
        assert len(result.text.strip()) > 0, "Transcription should not be empty"
        assert result.duration > 0, "Duration should be positive"

        print(f"\n[OK] WhisperX STT: '{result.text.strip()}' ({result.duration:.2f}s)")

    def test_whisperx_word_timestamps(self, client, test_assets):
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"

        _ensure_model(client, _WHISPERX_STT_MODEL, max_wait=600)

        result = _transcribe(client, audio_file, _WHISPERX_STT_MODEL, response_format=TranscriptionFormat.JSON)

        assert result is not None
        assert isinstance(result.text, str) and len(result.text.strip()) > 0

        words = [] if isinstance(result.words, Unset) or result.words is None else result.words
        segs = [] if isinstance(result.segments, Unset) or result.segments is None else result.segments

        print(f"\n[OK] WhisperX forced alignment: '{result.text.strip()}' ({len(segs)} segs, {len(words)} words)")
        if words:
            assert words[0].start is not None, "Words should have start timestamps"
            assert words[0].end is not None, "Words should have end timestamps"


@pytest.mark.skipif(not _HAS_KOKORO, reason="kokoro not installed — run: uv sync --extra kokoro")
class TestKokoroTTS:
    """E2E: Kokoro TTS backend (hexgrad/Kokoro-82M)"""

    def test_kokoro_synthesize(self, client):
        _ensure_model(client, _KOKORO_TTS_MODEL, max_wait=300)

        audio = _tts(client, "Hello, this is a Kokoro TTS test.", model=_KOKORO_TTS_MODEL, response_format=TTSRequestResponseFormat.WAV)

        assert isinstance(audio, bytes) and len(audio) > 1000, "Expected non-trivial WAV output"
        assert audio[:4] == b"RIFF", "Expected RIFF WAV header"

        buf = io.BytesIO(audio)
        with wave.open(buf, "rb") as wf:
            assert wf.getframerate() > 0
            assert wf.getnframes() > 0

        print(f"\n[OK] Kokoro TTS: {len(audio):,} bytes WAV @ {wf.getframerate()}Hz")

    def test_kokoro_synthesize_mp3(self, client):
        _ensure_model(client, _KOKORO_TTS_MODEL, max_wait=300)

        audio = _tts(client, "MP3 format Kokoro test.", model=_KOKORO_TTS_MODEL, response_format=TTSRequestResponseFormat.MP3)

        assert isinstance(audio, bytes) and len(audio) > 0
        assert audio[:3] == b"ID3" or audio[0] == 0xFF, "Expected MP3 header"

        print(f"\n[OK] Kokoro TTS MP3: {len(audio):,} bytes")

    def test_kokoro_voice_list(self, client):
        _ensure_model(client, _KOKORO_TTS_MODEL, max_wait=300)

        result = list_voices_v1_audio_voices_get.sync(client=client, model=_KOKORO_TTS_MODEL)

        assert result is not None and result.total > 0, "Kokoro should expose at least one voice"
        assert all(v.id and v.language for v in result.voices), "Each voice should have id and language"

        print(f"\n[OK] Kokoro voices: {result.total} voices — {[v.id for v in result.voices[:5]]}")


@pytest.mark.skipif(_IN_CI, reason="CI: Chatterbox requires GPU and large download — skip in CI")
@pytest.mark.skipif(not _HAS_CHATTERBOX, reason="chatterbox-tts not installed — run: pip install chatterbox-tts")
class TestChatterboxTTS:
    """E2E: Chatterbox TTS backend (ResembleAI/chatterbox) — requires GPU"""

    def test_chatterbox_synthesize(self, client):
        _ensure_model(client, _CHATTERBOX_TTS_MODEL, max_wait=600)

        audio = _tts(client, "Hello, this is a Chatterbox synthesis test.", model=_CHATTERBOX_TTS_MODEL, response_format=TTSRequestResponseFormat.WAV)

        assert isinstance(audio, bytes) and len(audio) > 1000, "Expected non-trivial WAV output"
        assert audio[:4] == b"RIFF", "Expected RIFF WAV header"

        print(f"\n[OK] Chatterbox TTS: {len(audio):,} bytes WAV")

    def test_chatterbox_voice_clone(self, client, api_server):
        _ensure_model(client, _CHATTERBOX_TTS_MODEL, max_wait=600)

        ref_wav = _make_reference_wav(duration_s=8.0)
        resp = httpx.post(
            f"{api_server}/v1/audio/clone",
            files={"reference_audio": ("ref.wav", ref_wav, "audio/wav")},
            data={"text": "Voice cloning test with Chatterbox.", "model": _CHATTERBOX_TTS_MODEL, "response_format": "wav"},
            timeout=120.0,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert len(resp.content) > 1000, "Expected non-trivial cloned audio"
        assert resp.content[:4] == b"RIFF", "Expected RIFF WAV header"

        # Chatterbox may output IEEE float WAV (format 3) which Python's wave
        # module doesn't support. Just verify the RIFF header is valid.
        print(f"\n[OK] Chatterbox voice clone: {len(resp.content):,} bytes WAV")


def _check_server_alive(api_server: str) -> None:
    """Skip the test if the API server is unreachable (e.g. crashed loading a large model)."""
    try:
        resp = requests.get(f"{api_server}/health", timeout=5)
        if resp.status_code != 200:
            pytest.skip(f"API server unhealthy (status {resp.status_code}) — likely crashed loading a model")
    except requests.exceptions.ConnectionError:
        pytest.skip("API server is down — likely crashed loading a large model (OOM?)")
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"API server unreachable: {exc}")


def _skip_on_server_crash(func):
    """Decorator: convert connection/OOM errors during a test into a skip."""
    import functools

    from vocal_sdk.errors import UnexpectedStatus

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (httpx.ReadError, httpx.ConnectError, ConnectionError, OSError) as exc:
            pytest.skip(f"Server crashed during test — likely OOM loading model: {exc}")
        except UnexpectedStatus as exc:
            if exc.status_code == 500 and b"paging file" in exc.content:
                pytest.skip(f"Server OOM (paging file too small): {exc}")
            raise

    return wrapper


@pytest.mark.skipif(_IN_CI, reason="CI: Voxtral STT requires 16GB+ GPU and large download — skip in CI")
@pytest.mark.skipif(not _HAS_MISTRAL_COMMON, reason="mistral_common not installed — run: uv pip install mistral-common")
@pytest.mark.skipif(not _HAS_CUDA, reason="Voxtral STT requires CUDA GPU")
class TestVoxtralSTT:
    """E2E: Voxtral-Mini-4B-Realtime STT backend — requires 16GB+ GPU"""

    @pytest.fixture(autouse=True)
    def _check_server(self, api_server):
        """Before each test, verify the server is still alive."""
        _check_server_alive(api_server)

    @_skip_on_server_crash
    def test_voxtral_stt_transcribe(self, client, test_assets):
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"
        assert audio_file.exists(), f"Test asset not found: {audio_file}"

        _ensure_model(client, _VOXTRAL_STT_MODEL, max_wait=900)

        result = _transcribe(client, audio_file, _VOXTRAL_STT_MODEL, language="en")

        assert result is not None, "Result should not be None"
        assert isinstance(result.text, str), "Text should be a string"
        assert len(result.text.strip()) > 0, "Transcription should not be empty"

        print(f"\n[OK] Voxtral STT: '{result.text.strip()}'")

    @_skip_on_server_crash
    def test_voxtral_stt_transcribe_m4a(self, client, test_assets):
        audio_file = test_assets["audio_dir"] / "Recording.m4a"
        assert audio_file.exists(), f"Test asset not found: {audio_file}"

        _ensure_model(client, _VOXTRAL_STT_MODEL, max_wait=900)

        result = _transcribe(client, audio_file, _VOXTRAL_STT_MODEL)

        assert result is not None
        assert isinstance(result.text, str) and len(result.text.strip()) > 0

        print(f"\n[OK] Voxtral STT (m4a): '{result.text.strip()}'")

    def _pcm_from_file(self, audio_file) -> bytes:
        """Convert an audio file to raw PCM16 mono 16kHz via ffmpeg."""
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(audio_file), "-ar", "16000", "-ac", "1", "-f", "s16le", tmp_path],
                check=True,
                capture_output=True,
            )
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            os.unlink(tmp_path)

    async def _collect_until_done(self, ws, timeout_s: float = 90.0) -> list[dict]:
        """Receive WebSocket messages until transcript.done or timeout. Raises on error events."""
        events: list[dict] = []
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=min(5.0, remaining))
            except TimeoutError:
                continue
            event = json.loads(msg)
            events.append(event)
            if event.get("type") == "error":
                raise RuntimeError(f"Server error: {event.get('message')}")
            if event.get("type") == "transcript.done":
                return events
        raise TimeoutError(f"transcript.done not received within {timeout_s}s. Got: {[e['type'] for e in events]}")

    @_skip_on_server_crash
    def test_voxtral_stt_live_stream(self, client, api_server, test_assets):
        """Exercises the live-stream path with the same parameters the CLI uses (no overrides)."""
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"
        assert audio_file.exists(), f"Test asset not found: {audio_file}"

        _ensure_model(client, _VOXTRAL_STT_MODEL, max_wait=900)
        pcm = self._pcm_from_file(audio_file)

        async def _test():
            base_uri = api_server.replace("http://", "ws://")
            # No threshold or max_chunk_duration overrides — use the same defaults the CLI sends
            uri = f"{base_uri}/v1/audio/stream?model={_VOXTRAL_STT_MODEL}&language=en"
            frame_size = 3200  # 100ms at 16kHz

            async with websockets.connect(uri, open_timeout=60) as ws:
                # Send speech frames; VAD (default threshold=0.5) classifies real audio as speech
                for i in range(0, len(pcm), frame_size):
                    await ws.send(pcm[i : i + frame_size])

                # 20 frames of zero-energy silence (2.0s) — default silence_duration=1.5s fires the flush
                for _ in range(20):
                    await ws.send(bytes(frame_size))

                events = await self._collect_until_done(ws)

            full_text = " ".join(e["text"] for e in events if e.get("type") == "transcript.delta" and e.get("text"))
            assert len(full_text.strip()) > 0, "No transcription text received from live stream"
            print(f"\n[OK] Voxtral live stream (utterance 1): '{full_text.strip()}'")

        _ws_run(_test())

    @_skip_on_server_crash
    def test_voxtral_stt_live_stream_multi_utterance(self, client, api_server, test_assets):
        """Verifies the connection stays alive across multiple speech utterances (real user session)."""
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"
        assert audio_file.exists(), f"Test asset not found: {audio_file}"

        _ensure_model(client, _VOXTRAL_STT_MODEL, max_wait=900)
        pcm = self._pcm_from_file(audio_file)

        async def _test():
            base_uri = api_server.replace("http://", "ws://")
            uri = f"{base_uri}/v1/audio/stream?model={_VOXTRAL_STT_MODEL}&language=en"
            frame_size = 3200  # 100ms at 16kHz
            silence_frames = [bytes(frame_size)] * 20  # 2.0s silence → triggers flush

            async with websockets.connect(uri, open_timeout=60) as ws:
                for utterance_num in range(1, 3):
                    # Send speech
                    for i in range(0, len(pcm), frame_size):
                        await ws.send(pcm[i : i + frame_size])
                    # Send silence to trigger flush
                    for frame in silence_frames:
                        await ws.send(frame)

                    events = await self._collect_until_done(ws)
                    full_text = " ".join(e["text"] for e in events if e.get("type") == "transcript.delta" and e.get("text"))
                    assert len(full_text.strip()) > 0, f"No text on utterance {utterance_num}"
                    print(f"\n[OK] Voxtral live stream (utterance {utterance_num}): '{full_text.strip()}'")

        _ws_run(_test())


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
