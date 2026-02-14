"""
Vocal API Client Example - Ollama-style model management
No manual downloads needed - everything through API calls
"""
import requests
import time
from pathlib import Path


class VocalClient:
    """Simple client for Vocal API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def list_models(self, status: str = None, task: str = None):
        """List all available models"""
        params = {}
        if status:
            params['status'] = status
        if task:
            params['task'] = task
        
        response = requests.get(f"{self.base_url}/v1/models", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_model(self, model_id: str):
        """Get model information"""
        response = requests.get(f"{self.base_url}/v1/models/{model_id}")
        response.raise_for_status()
        return response.json()
    
    def download_model(self, model_id: str, wait: bool = True):
        """Download a model (pull in Ollama terms)"""
        print(f"Pulling model: {model_id}")
        
        response = requests.post(f"{self.base_url}/v1/models/{model_id}/download")
        response.raise_for_status()
        
        if not wait:
            return response.json()
        
        while True:
            status_response = requests.get(
                f"{self.base_url}/v1/models/{model_id}/download/status"
            )
            
            if status_response.status_code == 404:
                model = self.get_model(model_id)
                if model['status'] == 'available':
                    print(f"Model {model_id} ready!")
                    return model
                time.sleep(2)
                continue
            
            status = status_response.json()
            progress = status.get('progress', 0) * 100
            
            print(f"Progress: {progress:.1f}% - {status.get('message', '')}")
            
            if status['status'] == 'available':
                print(f"Model {model_id} downloaded successfully!")
                return status
            elif status['status'] == 'error':
                raise Exception(f"Download failed: {status.get('message')}")
            
            time.sleep(2)
    
    def delete_model(self, model_id: str):
        """Delete a model"""
        response = requests.delete(f"{self.base_url}/v1/models/{model_id}")
        response.raise_for_status()
        return response.json()
    
    def transcribe(
        self,
        audio_path: str,
        model: str = "Systran/faster-whisper-tiny",
        language: str = None,
        response_format: str = "json"
    ):
        """Transcribe audio file"""
        with open(audio_path, "rb") as f:
            files = {"file": (Path(audio_path).name, f)}
            data = {
                "model": model,
                "response_format": response_format
            }
            if language:
                data["language"] = language
            
            response = requests.post(
                f"{self.base_url}/v1/audio/transcriptions",
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()


def main():
    """Demo: List models, download if needed, then transcribe"""
    client = VocalClient()
    
    print("=" * 60)
    print("Vocal API Demo - Ollama-style Model Management")
    print("=" * 60)
    
    print("\n1. Checking API health...")
    try:
        health = requests.get("http://localhost:8000/health").json()
        print(f"   API Status: {health['status']}")
    except:
        print("   ERROR: API not running!")
        print("   Start it with: uv run uvicorn vocal_api.main:app --port 8000")
        return
    
    print("\n2. Listing available models...")
    models = client.list_models()
    print(f"   Found {models['total']} models")
    
    for model in models['models'][:5]:
        status_mark = "[OK]" if model['status'] == 'available' else "[ ]"
        print(f"   {status_mark} {model['id']} - {model['name']} ({model['size_readable']})")
    
    model_id = "Systran/faster-whisper-tiny"
    
    print(f"\n3. Checking if {model_id} is downloaded...")
    model_info = client.get_model(model_id)
    
    if model_info['status'] != 'available':
        print(f"   Model not downloaded. Pulling...")
        client.download_model(model_id, wait=True)
    else:
        print(f"   Model already available!")
    
    print(f"\n4. Transcribing audio...")
    import sys
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        print(f"   Audio: {audio_file}")
        
        result = client.transcribe(audio_file, model=model_id)
        
        print(f"\n   Transcription: {result['text']}")
        print(f"   Language: {result['language']}")
        print(f"   Duration: {result['duration']:.2f}s")
    else:
        print("   No audio file provided. Usage: python vocal_client.py <audio_file>")
    
    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
