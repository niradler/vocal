"""
Example: Simple audio transcription using Vocal API

This example shows how to transcribe audio files using the Vocal API.
"""
import requests
import sys


def transcribe_audio(audio_path: str, model: str = "openai/whisper-tiny", language: str = None):
    """
    Transcribe an audio file using the Vocal API
    
    Args:
        audio_path: Path to audio file
        model: Model to use (default: openai/whisper-tiny)
        language: Language code (optional, auto-detect if None)
    
    Returns:
        dict: Transcription result
    """
    url = "http://localhost:11435/v1/audio/transcriptions"
    
    with open(audio_path, "rb") as audio_file:
        files = {"file": audio_file}
        data = {
            "model": model,
            "response_format": "json"
        }
        
        if language:
            data["language"] = language
        
        response = requests.post(url, files=files, data=data)
        response.raise_for_status()
        
        return response.json()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python example_transcribe.py <audio_file> [model] [language]")
        print("\nExamples:")
        print("  python example_transcribe.py recording.mp3")
        print("  python example_transcribe.py recording.mp3 openai/whisper-small")
        print("  python example_transcribe.py recording.mp3 openai/whisper-tiny en")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "openai/whisper-tiny"
    language = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"Transcribing: {audio_path}")
    print(f"Model: {model}")
    if language:
        print(f"Language: {language}")
    print("-" * 50)
    
    try:
        result = transcribe_audio(audio_path, model, language)
        
        print(f"\nText: {result['text']}")
        print(f"Language: {result['language']}")
        print(f"Duration: {result['duration']:.2f}s")
        
        if result.get('segments'):
            print(f"\nSegments ({len(result['segments'])}):")
            for seg in result['segments'][:5]:
                print(f"  [{seg['start']:.2f}s - {seg['end']:.2f}s]: {seg['text']}")
            if len(result['segments']) > 5:
                print(f"  ... and {len(result['segments']) - 5} more")
        
    except requests.exceptions.ConnectionError:
        print("\nError: Cannot connect to API server")
        print("Please start the server first:")
        print("  uv run uvicorn vocal_api.main:app --port 11435")
    except requests.exceptions.HTTPError as e:
        print(f"\nError: {e}")
        if e.response is not None:
            print(f"Details: {e.response.text}")
    except FileNotFoundError:
        print(f"\nError: Audio file not found: {audio_path}")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
