# Vocal SDK

Auto-generated Python SDK for the Vocal API.

## Installation

```bash
cd packages/sdk
uv pip install -e .
```

## Usage

```python
from vocal_sdk import VocalSDK

# Initialize client
client = VocalSDK(base_url="http://localhost:8000")

# Check health
health = client.health()
print(health)

# List models
models = client.models.list()
for model in models['models']:
    print(f"{model['id']}: {model['status']}")

# Download a model if needed
model_id = "Systran/faster-whisper-tiny"
model_info = client.models.get(model_id)
if model_info['status'] != 'available':
    client.models.download(model_id)

# Transcribe audio
result = client.audio.transcribe(
    file="path/to/audio.mp3",
    model=model_id,
    language="en"  # optional
)
print(f"Transcription: {result['text']}")
print(f"Language: {result['language']}")
print(f"Duration: {result['duration']}s")
```

## Regenerating the SDK

When the API changes, regenerate the SDK models:

```bash
# 1. Make sure API is running
uv run uvicorn vocal_api.main:app --port 8000

# 2. Download latest OpenAPI spec
curl http://localhost:8000/openapi.json -o packages/sdk/openapi.json

# 3. Generate models (optional - for type hints)
cd packages/sdk
uv run python scripts/generate.py
```

## API Documentation

Interactive API docs available at: http://localhost:8000/docs
