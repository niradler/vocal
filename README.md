# Vocal

**Generic Speech AI Platform - Ollama for Voice Models**

Vocal is an API-first speech AI platform with automatic OpenAPI spec generation, auto-generated SDK, and Ollama-style model management. Built with a generic registry pattern supporting multiple providers.

[![License: SSPL](https://img.shields.io/badge/License-SSPL-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 🚀 Quick Start (30 seconds)

```bash
# 1. Run with uvx (no installation needed!)
uvx vocal serve

# 2. Visit interactive docs
# Open: http://localhost:8000/docs

# 3. Pull a model and transcribe
uvx vocal models pull Systran/faster-whisper-tiny
uvx vocal run your_audio.mp3
```

**That's it!** Models auto-download on first use.

**Pro tip:** For development, clone the repo and run `make help` to see all available commands.

## Features

- 🎯 **API-First Architecture**: FastAPI with auto-generated OpenAPI spec
- 📖 **Interactive Docs**: Swagger UI at `/docs` endpoint
- 📦 **Auto-Generated SDK**: Python SDK generated from OpenAPI spec
- 🔄 **Ollama-Style**: Model registry with pull/list/delete commands
- 🚀 **Fast Inference**: faster-whisper (4x faster than OpenAI Whisper)
- ⚡ **GPU Acceleration**: Automatic CUDA detection with VRAM optimization
- 🌍 **99+ Languages**: Support for multilingual transcription
- 🔌 **Extensible**: Generic provider pattern (HuggingFace, local, custom)
- 🎤 **OpenAI Compatible**: `/v1/audio/transcriptions` endpoint
- 🔊 **Text-to-Speech**: Neural TTS with Piper or system voices
- 🎨 **CLI Tool**: Typer-based CLI with rich console output
- ✅ **Production Ready**: 23/23 E2E tests passing with real audio assets

## Quick Start

### 1. Installation

```bash
# Option 1: Using uvx (recommended - no install needed)
uvx vocal serve

# Option 2: Using pip
pip install vocal-ai
vocal serve

# Option 3: From source
git clone https://github.com/niradler/vocal
cd vocal
make install
make serve
```

### 2. Start API Server

```bash
# Using Makefile
make serve

# Or using uv directly
uv run uvicorn vocal_api.main:app --port 8000

# Development mode with auto-reload
make serve-dev
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs 🎉
- **OpenAPI Spec**: http://localhost:8000/openapi.json
- **Health**: http://localhost:8000/health

### 3. Use the SDK

```python
from vocal import VocalSDK

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

# Text-to-Speech
audio = client.audio.text_to_speech(
    text="Hello, world!",
    model="pyttsx3"
)
with open("output.wav", "wb") as f:
    f.write(audio)
```

### 4. CLI Commands

```bash
# Start server
vocal serve

# Transcribe audio
vocal run audio.mp3

# List models
vocal models list

# Download model
vocal models pull Systran/faster-whisper-tiny

# Delete model
vocal models delete Systran/faster-whisper-tiny
```

### 5. API Examples

**Transcribe Audio:**
```bash
curl -X POST "http://localhost:8000/v1/audio/transcriptions" \
  -F "file=@audio.mp3" \
  -F "model=Systran/faster-whisper-tiny"
```

**Text-to-Speech:**
```bash
curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"model":"pyttsx3","input":"Hello world"}' \
  --output speech.wav
```

### 6. Docker Deployment

```bash
# Basic usage
docker compose up

# With GPU support
docker compose --profile gpu up

# Custom port
docker run -p 9000:8000 niradler/vocal-api
```

### 7. Troubleshooting

**Port already in use:**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /F /PID <PID>

# Linux/Mac
lsof -ti:8000 | xargs kill
```

**GPU not detected:**
```bash
# Check CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Check device info
curl http://localhost:8000/v1/system/device
```

# Start API server
vocal serve --port 8000
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

### Text-to-Speech (OpenAI-compatible)

#### `POST /v1/audio/speech`

Convert text to speech.

**Parameters:**
- `model` (required): TTS model to use (e.g., "hexgrad/Kokoro-82M", "coqui/XTTS-v2")
- `input` (required): Text to synthesize
- `voice` (optional): Voice ID to use
- `speed` (optional): Speech speed multiplier (0.25-4.0, default: 1.0)
- `response_format` (optional): Audio format (default: "wav")

**Response:**
Returns audio file in specified format with headers:
- `X-Duration`: Audio duration in seconds
- `X-Sample-Rate`: Audio sample rate

#### `GET /v1/audio/voices`

List available TTS voices.

**Response:**
```json
{
  "voices": [
    {
      "id": "default",
      "name": "Default Voice",
      "language": "en",
      "gender": null
    }
  ],
  "total": 1
}
```

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

## Performance & Optimization

Vocal automatically detects and optimizes for your hardware:

### GPU Acceleration

When NVIDIA GPU is available:
- **Automatic Detection**: GPU is detected and used automatically
- **Optimal Compute Types**: 
  - 8GB+ VRAM: `float16` (best quality)
  - 4-8GB VRAM: `int8_float16` (balanced)
  - <4GB VRAM: `int8` (most efficient)
- **4x-10x Faster**: GPU inference is significantly faster than CPU
- **Memory Management**: Automatic GPU cache clearing

### CPU Optimization

When GPU is not available:
- **Multi-threading**: Uses optimal CPU threads based on core count
- **Quantization**: `int8` quantization for faster CPU inference
- **VAD Filtering**: Voice Activity Detection for improved performance

### Check Your Device

```bash
# View device info via API
curl http://localhost:8000/v1/system/device

# Or via SDK
from vocal_sdk import VocalSDK
client = VocalSDK()
info = client._request('GET', '/v1/system/device')
print(info)
```

**Example output:**
```json
{
  "platform": "Windows",
  "cpu_count": 16,
  "cuda_available": true,
  "gpu_count": 1,
  "gpu_devices": [{
    "name": "NVIDIA GeForce RTX 4090",
    "vram_gb": 24.0,
    "compute_capability": "8.9"
  }]
}
```

### Optimization Tips

1. **GPU Usage**: Models automatically use GPU when available
2. **Model Selection**: 
   - `tiny/base` models: Work well on CPU
   - `small/medium`: Best on GPU with 4GB+ VRAM
   - `large`: Requires GPU with 8GB+ VRAM
3. **Batch Processing**: Load model once, transcribe multiple files
4. **VAD Filter**: Enabled by default for better performance

## CLI Usage

The CLI provides an intuitive command-line interface for common tasks.

### Transcription

```bash
# Transcribe audio file
vocal run audio.mp3

# Specify model
vocal run audio.mp3 --model Systran/faster-whisper-base

# Specify language
vocal run audio.mp3 --language en

# Output formats
vocal run audio.mp3 --format text
vocal run audio.mp3 --format json
vocal run audio.mp3 --format srt
vocal run audio.mp3 --format vtt
```

### Model Management

```bash
# List all models
vocal models list

# Filter by status
vocal models list --status available
vocal models list --status not_downloaded

# Download a model
vocal models pull Systran/faster-whisper-tiny

# Delete a model
vocal models delete Systran/faster-whisper-tiny
vocal models delete Systran/faster-whisper-tiny --force
```

### Server Management

```bash
# Start API server (default: http://0.0.0.0:8000)
vocal serve

# Custom host and port
vocal serve --host localhost --port 9000

# Enable auto-reload for development
vocal serve --reload
```

## Development

### Project Structure

The project uses a **uv workspace** with multiple packages:

- `packages/core`: Core model registry and adapters (no dependencies on API)
- `packages/api`: FastAPI server (depends on core)
- `packages/sdk`: Auto-generated SDK (generates from API OpenAPI spec)
- `packages/cli`: CLI tool (uses SDK)

### Running Tests

All tests use real audio assets from `test_assets/audio/` with validated transcriptions.

#### Quick Validation (< 30 seconds)

```bash
# Using Makefile
make test-quick

# Or directly
uv run python scripts/validate.py
```

#### Full E2E Test Suite (~ 2 minutes)

```bash
# Using Makefile
make test

# With verbose output
make test-verbose

# Or using pytest directly
uv run python -m pytest tests/test_e2e.py -v
```

**Current Status: 23/23 tests passing ✅**

Test coverage includes:
- API health and device information (GPU detection)
- Model management (list, download, status, delete)
- Audio transcription with real M4A and MP3 files
- Text-to-Speech synthesis with speed control
- Error handling for invalid models and files
- Performance and model reuse optimization

#### Check GPU Support

```bash
make gpu-check
```

### Code Quality

```bash
# Using Makefile
make lint          # Check code quality
make format        # Format code
make check         # Lint + format check

# Or using ruff directly
uv run ruff format .
uv run ruff check .
```

## Makefile Commands

Vocal includes a comprehensive Makefile for common tasks:

```bash
make help          # Show all available commands

# Setup
make install       # Install dependencies
make sync          # Sync dependencies

# Testing
make test          # Run full test suite
make test-quick    # Quick validation
make test-verbose  # Verbose test output
make gpu-check     # Check GPU detection

# Development
make serve         # Start API server
make serve-dev     # Start with auto-reload
make cli           # Show CLI help
make docs          # Open API docs in browser

# Code Quality
make lint          # Run linter
make format        # Format code
make check         # Lint + format check

# Cleanup
make clean         # Remove cache files
make clean-models  # Remove downloaded models

# Quick aliases
make t             # Alias for test
make s             # Alias for serve
make l             # Alias for lint
make f             # Alias for format
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

- ✅ **Phase 3: CLI** 
  - `vocal run` - Transcribe audio files
  - `vocal models list/pull/delete` - Model management
  - `vocal serve` - Start API server
  - Rich console output with progress

- ✅ **Phase 4: Text-to-Speech**
  - TTS API endpoints (`/v1/audio/speech`)
  - Multiple adapters (pyttsx3, Piper)
  - Voice selection and management
  - Speed control and audio output

- ✅ **Phase 5: GPU Optimization**
  - Automatic CUDA detection
  - Dynamic compute type selection (float16/int8)
  - VRAM-based optimization
  - CPU multi-threading fallback
  - System device info endpoint

- ✅ **Phase 6: Testing & Production Ready**
  - 23 comprehensive E2E integration tests
  - Real audio asset validation (100% accuracy)
  - Full API stack coverage
  - TTS timeout handling
  - Error handling and edge cases
  - **All tests passing: 23/23 ✅**

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

**Server Side Public License (SSPL) v1**

Vocal is open source but protects against exploitation:
- ✅ Free for personal and commercial use
- ✅ Free for self-hosting
- ✅ Free to modify and distribute
- ❌ Cannot offer as SaaS without open-sourcing your infrastructure

See [LICENSE](LICENSE) for full details.

## Roadmap

### ✅ Completed (v0.3.x)
- Core model registry with provider pattern
- Model management API (list, download, delete)
- SDK generation from OpenAPI spec
- Interactive Swagger UI docs
- CLI tool (Typer-based)
- Text-to-Speech (TTS) support
- Keep-alive model caching (5min default)
- GPU acceleration with CUDA
- OpenAI-compatible endpoints
- Published to PyPI as `vocal-ai`

### 🎯 Next Release (v0.4.0)

**1. Fix Model Metadata**
- **Why:** Models currently show `0` size and missing info, looks unfinished
- **How:** Fetch actual sizes from HuggingFace, populate all fields in registry

**2. Model Show Command**
- **Why:** Users need to inspect models before downloading (like `ollama show`)
- **How:** `vocal models show whisper-tiny` displays params, size, languages, VRAM

**3. Model Aliases**
- **Why:** Typing full paths is tedious (`Systran/faster-whisper-tiny`)
- **How:** Use short names: `vocal run audio.mp3 -m whisper-tiny`

### 🚀 Future (v0.5.0+)

**4. Voice Registry System**
- **Why:** Voices should be managed like models, not just system TTS
- **How:** `vocal voices list/pull/show` with downloadable voice models

**5. Voice Cloning (XTTS-v2)**
- **Why:** Custom voices are the killer feature for TTS
- **How:** `vocal voices clone my-voice --sample recording.wav`

**6. Voice Preview**
- **Why:** Users want to test voices before using them
- **How:** `vocal voices sample kokoro-en "Hello world"` generates quick sample

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - STT engine
- [HuggingFace Hub](https://huggingface.co/) - Model distribution
- [uv](https://github.com/astral-sh/uv) - Python package manager
