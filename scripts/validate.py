"""
Quick validation script for Vocal API
Tests core functionality without full E2E suite
"""

import json
import sys
from pathlib import Path

try:
    from vocal_sdk import VocalClient
    from vocal_sdk.api.audio import list_voices_v1_audio_voices_get, text_to_speech_v1_audio_speech_post
    from vocal_sdk.api.health import health_health_get
    from vocal_sdk.api.models import download_model_v1_models_model_id_download_post, get_model_v1_models_model_id_get, list_models_v1_models_get
    from vocal_sdk.api.transcription import create_transcription_v1_audio_transcriptions_post
    from vocal_sdk.models import BodyCreateTranscriptionV1AudioTranscriptionsPost, ModelStatus, TTSRequest
    from vocal_sdk.types import File

    print("\n" + "=" * 60)
    print("  VOCAL API VALIDATION")
    print("=" * 60 + "\n")

    vc = VocalClient(base_url="http://localhost:8000", raise_on_unexpected_status=True)

    print("[1/7] Testing API connection...")
    try:
        health = json.loads(health_health_get.sync_detailed(client=vc).content)
        print(f"  [OK] API is healthy (v{health.get('api_version', 'unknown')})")
    except Exception as e:
        print(f"  [FAIL] API connection failed: {e}")
        sys.exit(1)

    print("\n[2/7] Testing model listing...")
    try:
        models = list_models_v1_models_get.sync(client=vc)
        assert models is not None
        print(f"  [OK] Found {models.total} models in registry")
    except Exception as e:
        print(f"  [FAIL] Model listing failed: {e}")
        sys.exit(1)

    print("\n[3/7] Testing model information...")
    test_model = "Systran/faster-whisper-tiny"
    try:
        model_info = get_model_v1_models_model_id_get.sync(model_id=test_model, client=vc)
        assert model_info is not None
        print(f"  [OK] Retrieved info for {test_model}")
        print(f"      Status: {model_info.status.value}")
    except Exception as e:
        print(f"  [FAIL] Get model info failed: {e}")
        sys.exit(1)

    print("\n[4/7] Testing model download...")
    try:
        if model_info.status != ModelStatus.AVAILABLE:
            print(f"  Downloading {test_model}...")
            download_model_v1_models_model_id_download_post.sync(model_id=test_model, client=vc)
            print("  [OK] Model download initiated")
        else:
            print("  [OK] Model already available")
    except Exception as e:
        print(f"  [FAIL] Model download failed: {e}")
        sys.exit(1)

    print("\n[5/7] Testing audio transcription...")
    audio_file = Path("test_assets/audio/Recording.m4a")

    if audio_file.exists():
        try:
            with open(audio_file, "rb") as fobj:
                body = BodyCreateTranscriptionV1AudioTranscriptionsPost(
                    file=File(payload=fobj, file_name=audio_file.name),
                    model=test_model,
                )
                result = create_transcription_v1_audio_transcriptions_post.sync(client=vc, body=body)
            assert result is not None
            print("  [OK] Transcription successful")
            print(f"      Duration: {result.duration:.2f}s")
            print(f"      Language: {result.language}")
            if result.text:
                print(f"      Text: '{result.text[:50]}...'")
        except Exception as e:
            print(f"  [FAIL] Transcription failed: {e}")
            sys.exit(1)
    else:
        print("  [SKIP] No test audio found")
        print("         Run: uv run python scripts/create_test_assets.py")

    print("\n[6/7] Testing text-to-speech...")
    try:
        body = TTSRequest(model="pyttsx3", input_="Hello, this is a test.")
        audio_data = text_to_speech_v1_audio_speech_post.sync_detailed(client=vc, body=body).content
        print("  [OK] TTS synthesis successful")
        print(f"      Audio size: {len(audio_data)} bytes")
        print(f"      Format: {'WAV' if audio_data[:4] == b'RIFF' else 'MP3/other'}")
    except Exception as e:
        print(f"  [FAIL] TTS failed: {e}")
        sys.exit(1)

    print("\n[7/7] Testing voice listing...")
    try:
        voices = list_voices_v1_audio_voices_get.sync(client=vc)
        assert voices is not None
        print(f"  [OK] Found {voices.total} voice(s)")
        for voice in voices.voices:
            print(f"      - {voice.name} ({voice.language})")
    except Exception as e:
        print(f"  [FAIL] Voice listing failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  ALL VALIDATIONS PASSED!")
    print("=" * 60)
    print("\nVocal API is working correctly.")
    print("\nNext steps:")
    print("  - Run full E2E tests: make test")
    print("  - Try CLI tool: uv run vocal --help")
    print("  - Visit API docs: http://localhost:8000/docs")
    print()

    sys.exit(0)

except ImportError as e:
    print(f"\nError: Missing dependency - {e}")
    print("Run: uv sync")
    sys.exit(1)
except KeyboardInterrupt:
    print("\n\nValidation interrupted by user")
    sys.exit(1)
except Exception as e:
    print(f"\n\nUnexpected error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
