"""
Test script to transcribe audio using the Vocal API
"""
import requests
import sys
from pathlib import Path


def test_transcription(audio_file: str, model: str = "openai/whisper-tiny"):
    """Test audio transcription via API"""
    
    if not Path(audio_file).exists():
        print(f"Error: Audio file not found: {audio_file}")
        return
    
    url = "http://127.0.0.1:11435/v1/audio/transcriptions"
    
    print(f"\nTranscribing: {audio_file}")
    print(f"Model: {model}")
    print("-" * 50)
    
    with open(audio_file, "rb") as f:
        files = {"file": (Path(audio_file).name, f, "audio/mpeg")}
        data = {
            "model": model,
            "response_format": "json",
        }
        
        try:
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            
            result = response.json()
            
            print("\nTranscription Result:")
            print(f"Text: {result['text']}")
            print(f"Language: {result['language']}")
            print(f"Duration: {result['duration']:.2f}s")
            
            if result.get('segments'):
                print(f"\nSegments: {len(result['segments'])}")
                for seg in result['segments'][:3]:
                    print(f"  [{seg['start']:.2f}s - {seg['end']:.2f}s]: {seg['text']}")
            
            print("\nSuccess!")
            
        except requests.exceptions.RequestException as e:
            print(f"\nError: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")


def test_health():
    """Test API health endpoint"""
    try:
        response = requests.get("http://127.0.0.1:11435/health")
        response.raise_for_status()
        print("API Health:", response.json())
        return True
    except Exception as e:
        print(f"API not reachable: {e}")
        return False


if __name__ == "__main__":
    print("Testing Vocal API")
    print("=" * 50)
    
    if not test_health():
        print("\nPlease start the API first:")
        print("  uv run uvicorn vocal_api.main:app --port 11435")
        sys.exit(1)
    
    if len(sys.argv) < 2:
        print("\nUsage: python test_api.py <audio_file> [model]")
        print("\nExample:")
        print("  python test_api.py sample.mp3")
        print("  python test_api.py sample.mp3 openai/whisper-tiny")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "openai/whisper-tiny"
    
    test_transcription(audio_file, model)
