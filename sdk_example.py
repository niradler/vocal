"""
Example: Using Vocal SDK (auto-generated from OpenAPI spec)

This demonstrates the typed SDK interface for interacting with Vocal API.
"""

import sys
from pathlib import Path

from vocal_sdk import VocalClient
from vocal_sdk.api.health import health_health_get
from vocal_sdk.api.models import download_model_v1_models_model_id_download_post, get_model_v1_models_model_id_get, list_models_v1_models_get
from vocal_sdk.api.transcription import create_transcription_v1_audio_transcriptions_post
from vocal_sdk.models import BodyCreateTranscriptionV1AudioTranscriptionsPost, ModelStatus
from vocal_sdk.types import File, Unset


def main():
    vc = VocalClient(base_url="http://localhost:8000", raise_on_unexpected_status=True)

    print("=" * 60)
    print("Vocal SDK Demo - Auto-Generated from OpenAPI")
    print("=" * 60)

    print("\n1. Checking API health...")
    try:
        import json

        health = json.loads(health_health_get.sync_detailed(client=vc).content)
        print(f"   Status: {health['status']}")
        print(f"   Version: {health['api_version']}")
    except Exception as e:
        print(f"   ERROR: {e}")
        print("   Make sure API is running: uv run uvicorn vocal_api.main:app --port 8000")
        return

    print("\n2. Listing available models...")
    models_resp = list_models_v1_models_get.sync(client=vc)
    if models_resp is None:
        print("   ERROR: Could not list models")
        return

    print(f"   Found {models_resp.total} models")
    for model in models_resp.models[:5]:
        status_ok = model.status == ModelStatus.AVAILABLE
        marker = "[OK]" if status_ok else "[ ]"
        params = "Unknown" if isinstance(model.parameters, Unset) else model.parameters
        vram = "Unknown" if isinstance(model.recommended_vram, Unset) else model.recommended_vram
        print(f"   {marker} {model.id}")
        print(f"       {model.name} - {params}, {vram}")

    model_id = "Systran/faster-whisper-tiny"
    print(f"\n3. Checking model: {model_id}")

    model_info = get_model_v1_models_model_id_get.sync(model_id=model_id, client=vc)
    if model_info is None or model_info.status != ModelStatus.AVAILABLE:
        print("   Downloading model...")
        download_model_v1_models_model_id_download_post.sync(model_id=model_id, client=vc)
        print("   Download started!")
    else:
        print("   Model ready!")

    if len(sys.argv) < 2:
        print("\n4. No audio file provided")
        print("   Usage: python sdk_example.py <audio_file>")
        print("\nSDK is ready! Try:")
        print("  python sdk_example.py Recording.m4a")
        return

    audio_file = sys.argv[1]
    print(f"\n4. Transcribing: {audio_file}")

    try:
        with open(audio_file, "rb") as fobj:
            body = BodyCreateTranscriptionV1AudioTranscriptionsPost(
                file=File(payload=fobj, file_name=Path(audio_file).name),
                model=model_id,
            )
            result = create_transcription_v1_audio_transcriptions_post.sync(client=vc, body=body)

        if result is None:
            print("   ERROR: Transcription failed")
            return

        print(f"\n   Text: {result.text}")
        print(f"   Language: {result.language}")
        print(f"   Duration: {result.duration:.2f}s")

        segs = [] if isinstance(result.segments, Unset) or result.segments is None else result.segments
        if segs:
            print("\n   Segments:")
            for seg in segs[:3]:
                print(f"     [{seg.start:.2f}s - {seg.end:.2f}s] {seg.text}")

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
