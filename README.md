# Vocal

**Generic Speech AI Platform (STT + TTS)**

Vocal is an API-first speech AI platform with a generic model registry supporting multiple providers. Currently implements Speech-to-Text (STT) with plans for Text-to-Speech (TTS).

## Features

- **Generic Model Registry**: Support for multiple model providers (HuggingFace, local, custom)
- **FastAPI Server**: RESTful API with automatic OpenAPI documentation
- **faster-whisper Integration**: 4x faster than OpenAI Whisper with same accuracy
- **Modular Architecture**: Clean separation between core, API, SDK, and CLI
- **Type-Safe**: Full type hints with Pydantic validation

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repo-url>
cd vocal

# Create virtual environment and install dependencies
uv venv
uv sync
uv add --editable packages/core
uv add --editable packages/api
```

### 2. Download a Model

```bash
# Download Whisper tiny model (fastest, good for testing)
uv run python download_model.py

# Or download a larger model for better accuracy
# Edit download_model.py and change model_id to:
# - openai/whisper-base
# - openai/whisper-small
# - openai/whisper-medium
# - openai/whisper-large-v3
```

### 3. Start the API Server

```bash
uv run uvicorn vocal_api.main:app --reload --port 11435
```

The API will be available at:
- API: http://localhost:11435
- Docs: http://localhost:11435/docs
- Health: http://localhost:11435/health

### 4. Transcribe Audio

**Using curl:**

```bash
curl -X POST "http://localhost:11435/v1/audio/transcriptions" \
  -F "file=@your_audio.mp3" \
  -F "model=openai/whisper-tiny" \
  -F "language=en"
```

**Using Python:**

```python
import requests

url = "http://localhost:11435/v1/audio/transcriptions"

with open("your_audio.mp3", "rb") as f:
    files = {"file": ("audio.mp3", f, "audio/mpeg")}
    data = {
        "model": "openai/whisper-tiny",
        "response_format": "json",
    }
    
    response = requests.post(url, files=files, data=data)
    result = response.json()
    
    print(f"Transcription: {result['text']}")
    print(f"Language: {result['language']}")
    print(f"Duration: {result['duration']}s")
```

**Using the test script:**

```bash
uv run python test_api.py your_audio.mp3
```

## Architecture

```
vocal/
├── packages/
│   ├── core/           # Model registry & adapters ✅
│   │   └── vocal_core/
│   │       ├── registry/      # Generic model registry
│   │       │   ├── providers/ # HuggingFace, local, custom
│   │       │   └── model_info.py
│   │       └── adapters/      # STT/TTS adapters
│   │           └── stt/       # faster-whisper implementation
│   │
│   ├── api/            # FastAPI server ✅
│   │   └── vocal_api/
│   │       ├── models/        # Pydantic schemas
│   │       ├── routes/        # API endpoints
│   │       ├── services/      # Business logic
│   │       └── main.py        # FastAPI app
│   │
│   ├── sdk/            # Auto-generated Python SDK ⏳
│   └── cli/            # CLI using SDK ⏳
│
├── pyproject.toml      # uv workspace config
└── .gitignore
```

## API Endpoints

### POST `/v1/audio/transcriptions`

Transcribe audio to text.

**Parameters:**
- `file` (required): Audio file (mp3, wav, m4a, etc.)
- `model` (required): Model ID (e.g., "openai/whisper-tiny")
- `language` (optional): 2-letter language code (e.g., "en", "es")
- `response_format` (optional): "json" (default), "text", "srt", "vtt"
- `temperature` (optional): Sampling temperature (0.0-1.0, default: 0.0)

**Response:**
```json
{
  "text": "Hello, how are you today?",
  "language": "en",
  "duration": 2.5,
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 2.5,
      "text": "Hello, how are you today?"
    }
  ]
}
```

### POST `/v1/audio/translations`

Translate audio to English text.

### GET `/health`

Health check endpoint.

## Available Models

| Model ID | Size | Parameters | VRAM | Speed |
|----------|------|------------|------|-------|
| `openai/whisper-tiny` | ~150MB | 39M | 1GB+ | Fastest |
| `openai/whisper-base` | ~290MB | 74M | 1GB+ | Fast |
| `openai/whisper-small` | ~967MB | 244M | 2GB+ | Good |
| `openai/whisper-medium` | ~3GB | 769M | 5GB+ | Better |
| `openai/whisper-large-v3` | ~3.1GB | 1.5B | 10GB+ | Best |
| `openai/whisper-large-v3-turbo` | ~1.6GB | 809M | 6GB+ | Fast & Good |

All models support 99+ languages including English, Spanish, French, German, Chinese, Japanese, Arabic, and more.

## Development

### Project Structure

The project uses a **uv workspace** with multiple packages:

- `packages/core`: Core model registry and adapters (no dependencies on API)
- `packages/api`: FastAPI server (depends on core)
- `packages/sdk`: Auto-generated SDK (generates from API OpenAPI spec)
- `packages/cli`: CLI tool (uses SDK)

### Running Tests

```bash
# Test core package
uv run pytest packages/core/tests -v

# Test API (coming soon)
uv run pytest packages/api/tests -v
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .
```

## Implementation Status

- ✅ **Phase 0: Core Foundation**
  - Generic model registry
  - HuggingFace provider
  - faster-whisper adapter
  - Model storage & caching

- ✅ **Phase 1: API Layer**
  - Pydantic models
  - Transcription endpoint
  - FastAPI app with CORS
  - Health endpoints

- ⏳ **Phase 2: SDK Generation**
  - Auto-generate from OpenAPI spec
  - High-level client wrapper

- ⏳ **Phase 3: CLI**
  - `vocal run` - Transcribe audio
  - `vocal models` - Manage models
  - `vocal serve` - Start API server

## Configuration

### Environment Variables

Create a `.env` file:

```env
APP_NAME=Vocal API
VERSION=0.1.0
DEBUG=true
CORS_ORIGINS=["*"]
MAX_UPLOAD_SIZE=26214400
```

### Model Storage

Models are cached at: `~/.cache/vocal/models/`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

AGPL-3.0

## Roadmap

- [ ] Model management API endpoints (list, download, delete)
- [ ] SDK generation from OpenAPI spec
- [ ] CLI tool
- [ ] Text-to-Speech (TTS) support
- [ ] Streaming transcription
- [ ] WebSocket support
- [ ] Rate limiting
- [ ] Authentication (optional)

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - STT engine
- [HuggingFace Hub](https://huggingface.co/) - Model distribution
- [uv](https://github.com/astral-sh/uv) - Python package manager
