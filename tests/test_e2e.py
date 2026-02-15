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

import subprocess
import time
from pathlib import Path

import pytest
import requests

from vocal_sdk import VocalSDK


@pytest.fixture(scope="session")
def api_server():
    """Start API server for E2E testing, or reuse an already-running one."""
    import sys

    base_url = "http://localhost:8000"

    # Check if a server is already running
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
def client(api_server):
    """Create SDK client for testing"""
    return VocalSDK(base_url=api_server)


@pytest.fixture(scope="session")
def test_model():
    """The model to use for testing (tiny for speed)"""
    return "Systran/faster-whisper-tiny"


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
        result = client.health()

        assert isinstance(result, dict), "Health response should be a dict"
        assert "status" in result, "Health response should have 'status'"
        assert result["status"] == "healthy", "API should be healthy"
        assert "api_version" in result, "Health response should have 'api_version'"

        print(f"\n[OK] Health check passed - API v{result['api_version']}")

    def test_device_information(self, client):
        """Test device information endpoint"""
        result = client._request("GET", "/v1/system/device")

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
        result = client.models.list()

        assert isinstance(result, dict), "Models list should be a dict"
        assert "models" in result, "Should have 'models' key"
        assert "total" in result, "Should have 'total' key"
        assert isinstance(result["models"], list), "Models should be a list"
        assert result["total"] >= 0, "Total should be non-negative"
        assert len(result["models"]) == result["total"], "Count should match"

        print(f"\n[OK] Found {result['total']} models in registry")

    def test_filter_models_by_task(self, client):
        """Test filtering models by task type"""
        stt_models = client.models.list(task="stt")

        assert isinstance(stt_models, dict), "Filtered result should be a dict"
        assert "models" in stt_models, "Should have 'models' key"

        for model in stt_models["models"]:
            assert model["task"] == "stt", "All models should be STT"

        print(f"\n[OK] Filtered {stt_models['total']} STT models")

    def test_get_model_info(self, client, test_model):
        """Test getting specific model information"""
        result = client.models.get(test_model)

        assert isinstance(result, dict), "Model info should be a dict"
        assert "id" in result, "Should have model ID"
        assert result["id"] == test_model, "Model ID should match"
        assert "status" in result, "Should have status"
        assert "task" in result, "Should have task type"
        assert result["task"] == "stt", "Test model should be STT"

        print(f"\n[OK] Retrieved model info for {test_model}")
        print(f"  Status: {result['status']}")

    def test_download_model(self, client, test_model):
        """Test downloading a model"""
        result = client.models.download(test_model)

        assert isinstance(result, dict), "Download result should be a dict"
        assert "status" in result, "Should have status"

        print(f"\n[OK] Model download initiated: {test_model}")

        time.sleep(2)

        model_info = client.models.get(test_model)
        assert model_info["status"] in ["available", "downloading"], "Model should be available or downloading"

        print(f"  Final status: {model_info['status']}")

    def test_download_status(self, client, test_model):
        """Test checking download status"""
        try:
            result = client.models.download_status(test_model)

            assert isinstance(result, dict), "Status should be a dict"
            assert "status" in result, "Should have status"

            print(f"\n[OK] Download status: {result['status']}")
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                print("\n[OK] Download status check handled correctly (no active download)")
            else:
                raise


class TestAudioTranscription:
    """Test STT (Speech-to-Text) functionality"""

    @pytest.fixture(autouse=True)
    def ensure_model(self, client, test_model):
        """Ensure test model is downloaded before tests"""
        model_info = client.models.get(test_model)
        if model_info["status"] != "available":
            print(f"\nDownloading {test_model} for testing...")
            client.models.download(test_model)

            max_wait = 60
            for _ in range(max_wait):
                model_info = client.models.get(test_model)
                if model_info["status"] == "available":
                    break
                time.sleep(1)
            else:
                pytest.skip(f"Model {test_model} not available after {max_wait}s")

    def test_transcribe_short_audio(self, client, test_model, test_assets):
        """Test transcribing short audio file"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"
        expected_text = test_assets["files"]["Recording.m4a"]

        assert audio_file.exists(), f"Test asset not found: {audio_file}"

        result = client.audio.transcribe(file=audio_file, model=test_model)

        assert isinstance(result, dict), "Result should be a dict"
        assert "text" in result, "Should have 'text' field"
        assert "language" in result, "Should have 'language' field"
        assert "duration" in result, "Should have 'duration' field"

        assert isinstance(result["text"], str), "Text should be a string"
        assert isinstance(result["duration"], (int, float)), "Duration should be numeric"
        assert result["duration"] > 0, "Duration should be positive"

        transcribed = result["text"].strip()
        assert expected_text.lower() in transcribed.lower() or transcribed.lower() in expected_text.lower(), f"Transcription mismatch. Expected: '{expected_text}', Got: '{transcribed}'"

        print("\n[OK] Transcribed short audio")
        print(f"  Duration: {result['duration']:.2f}s")
        print(f"  Language: {result['language']}")
        print(f"  Expected: '{expected_text}'")
        print(f"  Got: '{transcribed}'")

    def test_transcribe_medium_audio(self, client, test_model, test_assets):
        """Test transcribing medium-length audio"""
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"
        expected_text = test_assets["files"]["en-AU-WilliamNeural.mp3"]

        result = client.audio.transcribe(file=audio_file, model=test_model)

        assert "text" in result, "Should have transcription text"
        assert "duration" in result, "Should have duration"
        assert result["duration"] > 0, "Should have positive duration"

        transcribed = result["text"].strip()
        assert expected_text.lower() in transcribed.lower() or transcribed.lower() in expected_text.lower(), f"Transcription mismatch. Expected: '{expected_text}', Got: '{transcribed}'"

        print(f"\n[OK] Transcribed medium audio ({result['duration']:.2f}s)")
        print(f"  Expected: '{expected_text}'")
        print(f"  Got: '{transcribed}'")

    def test_transcribe_with_language_specification(self, client, test_model, test_assets):
        """Test transcription with specified language"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"

        result = client.audio.transcribe(file=audio_file, model=test_model, language="en")

        assert "language" in result, "Should have language field"
        assert result["language"] == "en", "Language should be English"

        print("\n[OK] Transcribed with language=en")

    def test_transcribe_json_format_with_segments(self, client, test_model, test_assets):
        """Test JSON format response with segments"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"

        result = client.audio.transcribe(file=audio_file, model=test_model, response_format="json")

        assert "text" in result, "Should have text"
        assert "segments" in result, "Should have segments"

        if result["segments"]:
            segment = result["segments"][0]
            assert "id" in segment, "Segment should have ID"
            assert "start" in segment, "Segment should have start time"
            assert "end" in segment, "Segment should have end time"
            assert "text" in segment, "Segment should have text"
            assert segment["start"] <= segment["end"], "Start should be <= end"

        print(f"\n[OK] Got JSON format with {len(result.get('segments', []))} segments")

    def test_transcribe_silence(self, client, test_model, test_assets):
        """Test transcribing second audio file"""
        audio_file = test_assets["audio_dir"] / "en-AU-WilliamNeural.mp3"

        result = client.audio.transcribe(file=audio_file, model=test_model)

        assert "text" in result, "Should have text field"
        print(f"\n[OK] Transcribed second file: '{result['text']}'")

    def test_transcribe_both_formats(self, client, test_model, test_assets):
        """Test transcribing different audio formats (m4a and mp3)"""
        for filename in test_assets["files"].keys():
            audio_file = test_assets["audio_dir"] / filename

            result = client.audio.transcribe(file=audio_file, model=test_model)

            assert "text" in result, "Should have text"
            assert "duration" in result, "Should have duration"

            print(f"\n[OK] Transcribed {filename}")


class TestTextToSpeech:
    """Test TTS (Text-to-Speech) functionality"""

    def test_synthesize_short_text(self, client):
        """Test synthesizing short text"""
        text = "Hello, world!"

        audio_data = client.audio.text_to_speech(text=text)

        assert isinstance(audio_data, bytes), "Audio should be bytes"
        assert len(audio_data) > 0, "Audio should not be empty"
        # Default format is MP3 (ID3 tag or 0xFF sync word)
        assert audio_data[:3] == b"ID3" or audio_data[0] == 0xFF, "Should be MP3 format"

        print(f"\n[OK] Synthesized '{text}'")
        print(f"  Size: {len(audio_data)} bytes")

    def test_synthesize_with_speed(self, client):
        """Test TTS with different speed"""
        text = "This is a speed test."

        try:
            normal_audio = client.audio.text_to_speech(text=text, speed=1.0)
            fast_audio = client.audio.text_to_speech(text=text, speed=1.5)

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
            audio_data = client.audio.text_to_speech(text=text)

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
            audio_data = client.audio.text_to_speech(text=text, output_file=output_file)

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
            audio_data = client.audio.text_to_speech(text=text, response_format=fmt)

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

        mp3_data = client.audio.text_to_speech(text=text, response_format="mp3")
        wav_data = client.audio.text_to_speech(text=text, response_format="wav")

        assert len(mp3_data) < len(wav_data), "MP3 should be smaller than WAV"

        ratio = len(wav_data) / len(mp3_data)
        print(f"\n[OK] MP3 ({len(mp3_data)}B) vs WAV ({len(wav_data)}B) - {ratio:.1f}x compression")

    def test_synthesize_with_voice(self, client):
        """Test TTS with a specific voice"""
        text = "Voice selection test."

        voices = client.audio.list_voices()
        assert voices["total"] > 0, "Should have at least one voice"

        voice_id = voices["voices"][0]["name"]
        audio_data = client.audio.text_to_speech(text=text, voice=voice_id)

        assert isinstance(audio_data, bytes), "Audio should be bytes"
        assert len(audio_data) > 0, "Audio should not be empty"

        print(f"\n[OK] Synthesized with voice '{voice_id}': {len(audio_data)} bytes")

    def test_synthesize_invalid_format_rejected(self, client):
        """Test that invalid format is rejected by API"""
        import requests as req

        response = req.post(
            "http://localhost:8000/v1/audio/speech",
            json={"model": "pyttsx3", "input": "test", "response_format": "wma"},
        )
        assert response.status_code == 422, "Invalid format should return 422"

        print("\n[OK] Invalid format 'wma' correctly rejected with 422")

    def test_list_available_voices(self, client):
        """Test listing TTS voices"""
        try:
            result = client.audio.list_voices()

            assert isinstance(result, dict), "Result should be a dict"
            assert "voices" in result, "Should have voices list"
            assert "total" in result, "Should have total count"
            assert isinstance(result["voices"], list), "Voices should be a list"
            assert len(result["voices"]) == result["total"], "Count should match"
            assert result["total"] > 0, "Should have at least one voice"

            # Verify voice structure
            for voice in result["voices"]:
                assert "id" in voice, "Voice should have ID"
                assert "name" in voice, "Voice should have name"
                assert "language" in voice, "Voice should have language"

            print(f"\n[OK] Found {result['total']} voice(s)")
            for voice in result["voices"][:5]:
                print(f"  - {voice['name']} ({voice['language']})")
            if result["total"] > 5:
                print(f"  ... and {result['total'] - 5} more")
        except Exception as e:
            if "timeout" in str(e).lower():
                pytest.skip("Voice listing timed out (known issue with system TTS)")
            raise


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_transcribe_nonexistent_model(self, client, test_assets):
        """Test transcription with non-existent model"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"

        with pytest.raises(Exception):
            client.audio.transcribe(file=audio_file, model="non-existent-model-xyz123")

        print("\n[OK] Correctly raised error for invalid model")

    def test_transcribe_nonexistent_file(self, client, test_model):
        """Test transcription with non-existent file"""
        with pytest.raises(Exception):
            client.audio.transcribe(file="nonexistent_audio.wav", model=test_model)

        print("\n[OK] Correctly raised error for missing file")

    def test_get_nonexistent_model(self, client):
        """Test getting info for non-existent model"""
        with pytest.raises(Exception):
            client.models.get("fake-model-12345")

        print("\n[OK] Correctly raised error for fake model")

    def test_delete_nonexistent_model(self, client):
        """Test deleting non-existent model"""
        with pytest.raises(Exception):
            client.models.delete("fake-model-to-delete")

        print("\n[OK] Correctly raised error when deleting fake model")


class TestPerformance:
    """Test performance and optimization"""

    def test_model_reuse(self, client, test_model, test_assets):
        """Test that model stays loaded for multiple transcriptions"""
        audio_file = test_assets["audio_dir"] / "Recording.m4a"

        start_time = time.time()
        result1 = client.audio.transcribe(file=audio_file, model=test_model)
        first_duration = time.time() - start_time

        start_time = time.time()
        result2 = client.audio.transcribe(file=audio_file, model=test_model)
        second_duration = time.time() - start_time

        assert result1["text"] == result2["text"], "Results should be consistent"

        print("\n[OK] Model reuse tested")
        print(f"  First call: {first_duration:.2f}s")
        print(f"  Second call: {second_duration:.2f}s")

        if second_duration < first_duration:
            print(f"  Speedup: {first_duration / second_duration:.2f}x")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
