"""
Quick validation script for Vocal API
Tests core functionality without full E2E suite
"""

import sys
from pathlib import Path

try:
    from vocal_sdk import VocalSDK

    print("\n" + "=" * 60)
    print("  VOCAL API VALIDATION")
    print("=" * 60 + "\n")

    # Test 1: API Connection
    print("[1/7] Testing API connection...")
    client = VocalSDK(base_url="http://localhost:8000")

    try:
        health = client.health()
        print(f"  [OK] API is healthy (v{health.get('api_version', 'unknown')})")
    except Exception as e:
        print(f"  [FAIL] API connection failed: {e}")
        sys.exit(1)

    # Test 2: Models List
    print("\n[2/7] Testing model listing...")
    try:
        models = client.models.list()
        print(f"  [OK] Found {models['total']} models in registry")
    except Exception as e:
        print(f"  [FAIL] Model listing failed: {e}")
        sys.exit(1)

    # Test 3: Get Model Info
    print("\n[3/7] Testing model information...")
    test_model = "Systran/faster-whisper-tiny"
    try:
        model_info = client.models.get(test_model)
        print(f"  [OK] Retrieved info for {test_model}")
        print(f"      Status: {model_info['status']}")
    except Exception as e:
        print(f"  [FAIL] Get model info failed: {e}")
        sys.exit(1)

    # Test 4: Download Model (if needed)
    print("\n[4/7] Testing model download...")
    try:
        if model_info["status"] != "available":
            print(f"  Downloading {test_model}...")
            client.models.download(test_model)
            print("  [OK] Model download initiated")
        else:
            print("  [OK] Model already available")
    except Exception as e:
        print(f"  [FAIL] Model download failed: {e}")
        sys.exit(1)

    # Test 5: Transcription
    print("\n[5/7] Testing audio transcription...")
    audio_file = Path("test_assets/audio/Recording.m4a")

    if audio_file.exists():
        try:
            result = client.audio.transcribe(file=audio_file, model=test_model)
            print("  [OK] Transcription successful")
            print(f"      Duration: {result['duration']:.2f}s")
            print(f"      Language: {result['language']}")
            if result["text"]:
                print(f"      Text: '{result['text'][:50]}...'")
        except Exception as e:
            print(f"  [FAIL] Transcription failed: {e}")
            sys.exit(1)
    else:
        print("  [SKIP] No test audio found")
        print("         Run: uv run python scripts/create_test_assets.py")

    # Test 6: TTS
    print("\n[6/7] Testing text-to-speech...")
    try:
        audio_data = client.audio.text_to_speech(
            text="Hello, this is a test.", speed=1.0
        )
        print("  [OK] TTS synthesis successful")
        print(f"      Audio size: {len(audio_data)} bytes")
        print(f"      Format: {'WAV' if audio_data[:4] == b'RIFF' else 'Unknown'}")
    except Exception as e:
        print(f"  [FAIL] TTS failed: {e}")
        sys.exit(1)

    # Test 7: Voice Listing
    print("\n[7/7] Testing voice listing...")
    try:
        voices = client.audio.list_voices()
        print(f"  [OK] Found {voices['total']} voice(s)")
        for voice in voices["voices"]:
            print(f"      - {voice['name']} ({voice['language']})")
    except Exception as e:
        print(f"  [FAIL] Voice listing failed: {e}")
        sys.exit(1)

    # Summary
    print("\n" + "=" * 60)
    print("  ALL VALIDATIONS PASSED!")
    print("=" * 60)
    print("\nVocal API is working correctly.")
    print("\nNext steps:")
    print("  - Run full E2E tests: uv run python run_tests.py")
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
