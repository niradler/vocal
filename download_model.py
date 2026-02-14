"""
Quick script to download a model for testing
"""
import asyncio
from vocal_core import ModelRegistry


async def main():
    print("Initializing model registry...")
    registry = ModelRegistry()
    
    model_id = "openai/whisper-tiny"
    print(f"\nDownloading {model_id}...")
    print("This may take a few minutes on first run...")
    
    async for downloaded, total, status in registry.download_model(model_id):
        if total > 0:
            progress = (downloaded / total) * 100
            print(f"Progress: {progress:.1f}% ({downloaded}/{total} bytes) - Status: {status}")
    
    print(f"\nModel {model_id} downloaded successfully!")
    print(f"Location: {registry.get_model_path(model_id)}")


if __name__ == "__main__":
    asyncio.run(main())
