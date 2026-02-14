"""
Example: Using Vocal SDK (auto-generated from OpenAPI spec)

This demonstrates the clean SDK interface for interacting with Vocal API.
"""

import sys

from vocal_sdk import VocalSDK


def main():
    """Demo using the auto-generated SDK"""

    # Initialize SDK client
    client = VocalSDK(base_url="http://localhost:8000")

    print("=" * 60)
    print("Vocal SDK Demo - Auto-Generated from OpenAPI")
    print("=" * 60)

    # 1. Check API health
    print("\n1. Checking API health...")
    try:
        health = client.health()
        print(f"   Status: {health['status']}")
        print(f"   Version: {health['api_version']}")
    except Exception as e:
        print(f"   ERROR: {e}")
        print("   Make sure API is running: uv run uvicorn vocal_api.main:app --port 8000")
        return

    # 2. List available models
    print("\n2. Listing available models...")
    models_response = client.models.list()
    print(f"   Found {models_response['total']} models")

    for model in models_response["models"][:5]:
        status = "[OK]" if model["status"] == "available" else "[ ]"
        print(f"   {status} {model['id']}")
        print(f"       {model['name']} - {model['parameters']}, {model['recommended_vram']}")

    # 3. Ensure model is downloaded
    model_id = "Systran/faster-whisper-tiny"
    print(f"\n3. Checking model: {model_id}")

    model_info = client.models.get(model_id)
    if model_info["status"] != "available":
        print("   Downloading model...")
        client.models.download(model_id)
        print("   Download started!")
    else:
        print("   Model ready!")

    # 4. Transcribe audio
    if len(sys.argv) < 2:
        print("\n4. No audio file provided")
        print("   Usage: python sdk_example.py <audio_file>")
        print("\nSDK is ready! Try:")
        print("  python sdk_example.py Recording.m4a")
        return

    audio_file = sys.argv[1]
    print(f"\n4. Transcribing: {audio_file}")

    try:
        result = client.audio.transcribe(file=audio_file, model=model_id, response_format="json")

        print(f"\n   Text: {result['text']}")
        print(f"   Language: {result['language']}")
        print(f"   Duration: {result['duration']:.2f}s")

        if result.get("segments"):
            print("\n   Segments:")
            for seg in result["segments"][:3]:
                print(f"     [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}")

    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n" + "=" * 60)
    print("Done! SDK generated from OpenAPI at:")
    print("  http://localhost:8000/openapi.json")
    print("Interactive docs at:")
    print("  http://localhost:8000/docs")
    print("=" * 60)


if __name__ == "__main__":
    main()
