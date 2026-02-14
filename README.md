# Vocal

**Generic Speech AI Platform - Ollama for Voice Models**

Vocal is an API-first speech AI platform with automatic OpenAPI spec generation, auto-generated SDK, and Ollama-style model management. Built with a generic registry pattern supporting multiple providers.

[![License: SSPL](https://img.shields.io/badge/License-SSPL-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 🚀 Quick Start (5 minutes)

```bash
# 1. Clone and setup
git clone <repo-url>
cd vocal
uv sync

# 2. Start API
uv run uvicorn vocal_api.main:app --port 8000

# 3. Visit interactive docs
# Open: http://localhost:8000/docs

# 4. Use SDK to transcribe
python sdk_example.py your_audio.mp3
```

**That's it!** Models auto-download on first use.

## Features

- 🎯 **API-First Architecture**: FastAPI with auto-generated OpenAPI spec
- 📖 **Interactive Docs**: Swagger UI at `/docs` endpoint
- 📦 **Auto-Generated SDK**: Python SDK generated from OpenAPI spec
- 🔄 **Ollama-Style**: Model registry with pull/list/delete commands
- 🚀 **Fast Inference**: faster-whisper (4x faster than OpenAI Whisper)
- 🌍 **99+ Languages**: Support for multilingual transcription
- 🔌 **Extensible**: Generic provider pattern (HuggingFace, local, custom)
- 🎤 **OpenAI Compatible**: `/v1/audio/transcriptions` endpoint

## Quick Start

### 1. Installation

```bash
git clone <repo-url>
cd vocal

uv venv
uv sync
uv add --editable packages/core
uv add --editable packages/api
uv add --editable packages/sdk
```

### 2. Start API Server

```bash
uv run uvicorn vocal_api.main:app --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs 🎉
- **OpenAPI Spec**: http://localhost:8000/openapi.json
- **Health**: http://localhost:8000/health

### 3. Use the SDK

```python
from vocal_sdk import VocalSDK

# Initialize client
client = VocalSDK(base_url="http://localhost:8000")

# List models (Ollama-style)
models = client.models.list()
for model in models['models']:
    print(f"{model['id']}: {model['status']}")

# Download model if needed (Ollama-style pull)
client.models.download("Systran/faster-whisper-tiny")

# Transcribe audio (OpenAI-compatible)
result = client.audio.transcribe(
    file="audio.mp3",
    model="Systran/faster-whisper-tiny"
)
print(result['text'])
```

Or use the example:

```bash
uv run python sdk_example.py Recording.m4a
```

## Architecture

See [VOICESTACK_API_FIRST_ARCHITECTURE.md](VOICESTACK_API_FIRST_ARCHITECTURE.md) for detailed architecture documentation.

**Key Principles:**
- API-first design with auto-generated OpenAPI spec
- Generic registry pattern for extensibility  
- Ollama-style model management
- OpenAI-compatible endpoints
- Type-safe throughout with Pydantic

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

### Model Management (Ollama-style)

#### `GET /v1/models`
List all available models

**Query params:**
- `status`: Filter by status (available, downloading, not_downloaded)
- `task`: Filter by task (stt, tts)

#### `GET /v1/models/{model_id}`
Get model information

#### `POST /v1/models/{model_id}/download`
Download a model (Ollama-style "pull")

#### `GET /v1/models/{model_id}/download/status`
Check download progress

#### `DELETE /v1/models/{model_id}`
Delete a downloaded model

### Audio Transcription (OpenAI-compatible)

#### `POST /v1/audio/transcriptions`

Transcribe audio to text.

**Parameters:**
- `file` (required): Audio file (mp3, wav, m4a, etc.)
- `model` (required): Model ID (e.g., "Systran/faster-whisper-tiny")
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

#### `POST /v1/audio/translations`

Translate audio to English text.

### Health & Docs

#### `GET /health`
Health check endpoint

#### `GET /docs`
Interactive Swagger UI for API testing

#### `GET /openapi.json`
OpenAPI specification (auto-generated)

## Available Models

| Model ID | Size | Parameters | VRAM | Speed | Status |
|----------|------|------------|------|-------|--------|
| `Systran/faster-whisper-tiny` | ~75MB | 39M | 1GB+ | Fastest | CTranslate2 |
| `Systran/faster-whisper-base` | ~145MB | 74M | 1GB+ | Fast | CTranslate2 |
| `Systran/faster-whisper-small` | ~488MB | 244M | 2GB+ | Good | CTranslate2 |
| `Systran/faster-whisper-medium` | ~1.5GB | 769M | 5GB+ | Better | CTranslate2 |
| `Systran/faster-whisper-large-v3` | ~3.1GB | 1.5B | 10GB+ | Best | CTranslate2 |
| `Systran/faster-distil-whisper-large-v3` | ~756MB | 809M | 6GB+ | Fast & Good | CTranslate2 |

All models support 99+ languages including English, Spanish, French, German, Chinese, Japanese, Arabic, and more.

**Note:** These use the CTranslate2-optimized models from Systran for faster-whisper, which are ~4x faster than the original OpenAI Whisper models.

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
  - Generic model registry with provider pattern
  - HuggingFace provider with automatic downloads
  - faster-whisper adapter (4x faster than OpenAI)
  - Model storage & caching

- ✅ **Phase 1: API Layer**
  - FastAPI with auto-generated OpenAPI spec
  - Model management endpoints (Ollama-style)
  - Transcription endpoints (OpenAI-compatible)
  - Interactive Swagger UI at `/docs`
  - Health & status endpoints

- ✅ **Phase 2: SDK**
  - Auto-generated from OpenAPI spec
  - Clean Python client interface
  - Type-safe with Pydantic models
  - Namespaced APIs (models, audio)

- ⏳ **Phase 3: CLI** (Coming soon)
  - `vocal run` - Transcribe audio
  - `vocal models list` - List models
  - `vocal models pull` - Download model
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

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Clone the repository
git clone <repo-url>
cd vocal

# Set up environment
uv venv
uv sync

# Install packages in development mode
uv add --editable packages/core
uv add --editable packages/api
uv add --editable packages/sdk

# Run tests
uv run pytest packages/core/tests -v
```

### Making Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `uv run pytest`
6. Update documentation if needed
7. Commit with clear messages: `git commit -m "feat: add feature X"`
8. Push and create a pull request

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all functions
- Add docstrings for public APIs
- Keep functions focused and testable

### Adding New Models

To add support for a new model provider:

1. Create a new provider class in `packages/core/vocal_core/registry/providers/`
2. Implement the `ModelProvider` interface
3. Add tests
4. Update documentation

### Regenerating SDK

When API changes:

```bash
# Start API server
uv run uvicorn vocal_api.main:app --port 8000

# Download new OpenAPI spec
curl http://localhost:8000/openapi.json -o packages/sdk/openapi.json

# SDK client is hand-crafted, just update if needed
```

## License

**Server Side Public License (SSPL) v1** - Like MongoDB and Redis

Vocal is open source but protects against cloud provider exploitation:
- ✅ Free for personal and commercial use
- ✅ Free for self-hosting
- ✅ Free to modify and distribute
- ❌ Cannot offer as SaaS without open-sourcing your infrastructure

See [LICENSE](LICENSE) for full details.

## Roadmap

- [x] Core model registry with provider pattern
- [x] Model management API (list, download, delete)
- [x] SDK generation from OpenAPI spec
- [x] Interactive Swagger UI docs
- [ ] CLI tool (Typer-based)
- [ ] Text-to-Speech (TTS) support
- [ ] Streaming transcription
- [ ] WebSocket support for real-time transcription
- [ ] Rate limiting middleware
- [ ] Authentication (optional - JWT/API keys)
- [ ] Docker deployment
- [ ] Batch transcription
- [ ] Custom model providers

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - STT engine
- [HuggingFace Hub](https://huggingface.co/) - Model distribution
- [uv](https://github.com/astral-sh/uv) - Python package manager
