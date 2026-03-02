# Vocal SDK

Auto-generated Python SDK for the Vocal API (generated via `openapi-python-client`).

## Installation

```bash
cd packages/sdk
uv pip install -e .
```

## Usage

The SDK provides a fully typed sync/async client generated from the Vocal OpenAPI spec.

```python
from pathlib import Path

from vocal_sdk import VocalClient
from vocal_sdk.api.models import (
    download_model_v1_models_model_id_download_post,
    get_model_v1_models_model_id_get,
    list_models_v1_models_get,
)
from vocal_sdk.api.transcription import create_transcription_v1_audio_transcriptions_post
from vocal_sdk.models import BodyCreateTranscriptionV1AudioTranscriptionsPost, ModelStatus
from vocal_sdk.types import File

client = VocalClient(base_url="http://localhost:8000", raise_on_unexpected_status=True)

# List models
resp = list_models_v1_models_get.sync(client=client)
for model in resp.models:
    print(f"{model.id}: {model.status.value}")

# Download a model if needed
model_id = "Systran/faster-whisper-tiny"
model_info = get_model_v1_models_model_id_get.sync(model_id=model_id, client=client)
if model_info.status != ModelStatus.AVAILABLE:
    download_model_v1_models_model_id_download_post.sync(model_id=model_id, client=client)

# Transcribe audio (sync)
with open("audio.mp3", "rb") as f:
    body = BodyCreateTranscriptionV1AudioTranscriptionsPost(
        file=File(payload=f, file_name="audio.mp3"),
        model=model_id,
        language="en",
    )
    result = create_transcription_v1_audio_transcriptions_post.sync(client=client, body=body)

print(f"Transcription: {result.text}")
print(f"Language: {result.language}")
print(f"Duration: {result.duration}s")
```

### Async usage

Every endpoint module exposes `.asyncio()` and `.asyncio_detailed()` variants:

```python
import asyncio
from vocal_sdk import VocalClient
from vocal_sdk.api.models import list_models_v1_models_get

async def main():
    client = VocalClient(base_url="http://localhost:8000")
    resp = await list_models_v1_models_get.asyncio(client=client)
    for model in resp.models:
        print(model.id)

asyncio.run(main())
```

### Backward compatibility

The legacy dict-based `VocalSDK` wrapper is still available for existing code:

```python
from vocal_sdk import VocalSDK

client = VocalSDK(base_url="http://localhost:8000")
models = client.models.list()          # returns dict
result = client.audio.transcribe(...)  # returns dict
```

New code should prefer `VocalClient` with the typed generated API functions.

## Regenerating the SDK

When the API changes, regenerate from the running server:

```bash
# 1. Start the API
make serve

# 2. Regenerate (from repo root)
make generate-sdk
```

Or from a local spec file:

```bash
uv run python packages/sdk/scripts/generate.py --path packages/sdk/openapi.json
```

## API Documentation

Interactive API docs available at: http://localhost:8000/docs
