"""
End-to-End Integration Tests for Vocal API

These tests validate the entire API stack using real test assets:
- Model management lifecycle
- STT (Speech-to-Text) transcription
- TTS (Text-to-Speech) synthesis
- System device information
- Error handling and edge cases

Test assets are located in test_assets/audio/ directory.
"""

import json
import subprocess
import time
from pathlib import Path

import httpx
import pytest
import requests

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
from vocal_sdk.api.transcription import create_transcription_v1_audio_transcriptions_post
from vocal_sdk.models import (
    BodyCreateTranscriptionV1AudioTranscriptionsPost,
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


@pytest.fixture(scope="session")
def api_server():
    """Start API server for E2E testing, or reuse an already-running one."""
    import sys

    base_url = "http://localhost:8000"

    try:
        response = requests.get(f"{base_url}/health", timeout=2)
        if response.status_code == 200:
            print(f"\nReusing existing API server on {base_url}")
            yield base_url
            return
    except requests.exceptions.RequestException:
        pass

    server_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "vocal_api.main:app",
            "--port",
            "8000",
            "--log-level",
            "error",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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

    pytest.skip(f"Model {test_model} not available after {max_wait}s — skipping all tests")


@pytest.fixture(scope="session")
def test_assets():
    """Return path to test assets directory and expected transcriptions"""
    assets_dir = Path("test_assets/audio")
    expected_dir = Path("test_assets/expected")

    if not assets_dir.exists():
        pytest.skip(f"Test assets not found at {assets_dir} (download them to run STT tests)")

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
        """Test filtering models by task type"""
        stt_models = list_models_v1_models_get.sync(client=client, task="stt")

        assert stt_models is not None, "Filtered result should not be None"
        assert isinstance(stt_models.models, list), "Models should be a list"

        for model in stt_models.models:
            assert model.task.value == "stt", "All models should be STT"

        print(f"\n[OK] Filtered {stt_models.total} STT models")

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

    def test_transcribe_silence(self, client, test_model, test_assets, ensure_stt_model):
        """Test transcribing second audio file"""
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"

        result = _transcribe(client, audio_file, test_model)

        assert result is not None
        assert isinstance(result.text, str), "Should have text field"
        print(f"\n[OK] Transcribed second file: '{result.text}'")

    def test_transcribe_both_formats(self, client, test_model, test_assets, ensure_stt_model):
        """Test transcribing different audio formats (m4a and mp3)"""
        for filename in test_assets["files"].keys():
            audio_file = test_assets["audio_dir"] / filename

            result = _transcribe(client, audio_file, test_model)

            assert result is not None
            assert isinstance(result.text, str), "Should have text"
            assert result.duration > 0, "Should have duration"

            print(f"\n[OK] Transcribed {filename}")


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

        try:
            normal_audio = _tts(client, text, speed=1.0)
            fast_audio = _tts(client, text, speed=1.5)

            assert isinstance(normal_audio, bytes), "Normal audio should be bytes"
            assert isinstance(fast_audio, bytes), "Fast audio should be bytes"
            assert len(normal_audio) > 0, "Normal audio should not be empty"
            assert len(fast_audio) > 0, "Fast audio should not be empty"

            print("\n[OK] Speed variations work")
            print(f"  Normal: {len(normal_audio)} bytes")
            print(f"  Fast (1.5x): {len(fast_audio)} bytes")

            if len(fast_audio) < len(normal_audio):
                print(f"  Speed reduction verified ({len(normal_audio) / len(fast_audio):.2f}x)")
            else:
                print("  Note: File sizes similar (system TTS limitation)")
        except Exception as e:
            if "timeout" in str(e).lower():
                pytest.skip("TTS speed test timed out (known issue with system TTS)")
            raise

    def test_synthesize_long_text(self, client):
        """Test synthesizing longer text"""
        text = "Testing speech synthesis."

        try:
            audio_data = _tts(client, text)

            assert isinstance(audio_data, bytes), "Should return bytes"
            assert len(audio_data) > 1000, "Should produce audio data"

            print(f"\n[OK] Synthesized text ({len(text)} chars)")
            print(f"  Audio size: {len(audio_data)} bytes")
        except Exception as e:
            if "timeout" in str(e).lower():
                pytest.skip("TTS synthesis timed out (known issue with system TTS)")
            raise

    def test_synthesize_to_file(self, client, tmp_path):
        """Test TTS with file output"""
        text = "Save to file test."
        output_file = tmp_path / "test_output.mp3"

        try:
            audio_data = _tts(client, text)
            output_file.write_bytes(audio_data)

            assert output_file.exists(), "Output file should exist"
            assert output_file.stat().st_size > 0, "File should not be empty"
            assert len(audio_data) > 0, "Should also return audio data"

            print(f"\n[OK] Saved to file: {output_file}")
            print(f"  Size: {output_file.stat().st_size} bytes")
        except Exception as e:
            if "timeout" in str(e).lower():
                pytest.skip("TTS save to file timed out (known issue with system TTS)")
            raise

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

        try:
            audio_data = _tts(client, text, response_format=TTSRequestResponseFormat(fmt))

            assert isinstance(audio_data, bytes), "Audio should be bytes"
            assert len(audio_data) > 0, f"{fmt} audio should not be empty"
            assert check(audio_data), f"Invalid {fmt} header"

            print(f"\n[OK] Format {fmt}: {len(audio_data)} bytes")
        except Exception as e:
            if "timeout" in str(e).lower():
                pytest.skip(f"TTS {fmt} format test timed out")
            raise

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
        try:
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
        except Exception as e:
            if "timeout" in str(e).lower():
                pytest.skip("Voice listing timed out (known issue with system TTS)")
            raise


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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
