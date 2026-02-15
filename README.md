# Vocal

**Generic Speech AI Platform - Ollama for Voice Models**

Vocal is an API-first speech AI platform with automatic OpenAPI spec generation, auto-generated SDK, and Ollama-style model management. Built with a generic registry pattern supporting multiple providers.

[![License: SSPL](https://img.shields.io/badge/License-SSPL-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform Support](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)](https://github.com/niradler/vocal)

## 🚀 Quick Start (30 seconds)

```bash
# 1. Run with uvx (no installation needed!)
uvx --from vocal-ai vocal serve

# 2. Visit interactive docs
# Open: http://localhost:8000/docs

# 3. Pull a model and transcribe
uvx --from vocal-ai vocal models pull Systran/faster-whisper-tiny
uvx --from vocal-ai vocal run your_audio.mp3
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
- 🔊 **Text-to-Speech**: Neural TTS with Piper or system voices (SAPI5 on Windows, nsss on macOS, espeak on Linux)
- 🎨 **CLI Tool**: Typer-based CLI with rich console output
- 💻 **Cross-Platform**: Full support for Windows, macOS, and Linux
- ✅ **Production Ready**: 47/47 tests passing with real audio assets

## Prerequisites

- **Python 3.10+**
- **ffmpeg** — required for audio format conversion (mp3, opus, aac, flac, pcm). WAV output works without it.

  ```bash
  # macOS
  brew install ffmpeg
  # Ubuntu / Debian
  sudo apt install ffmpeg
  # Windows
  choco install ffmpeg
  ```

## Installation & Usage

### Quick Start (Recommended)

```bash
# Run directly with uvx (no installation needed)
uvx --from vocal-ai vocal serve

# Or install with pip
pip install vocal-ai
vocal serve
```

### From Source

```bash
git clone https://github.com/niradler/vocal
cd vocal
make install
make serve
```

### Start API Server

The API will be available at:

- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs 🎉
- **OpenAPI Spec**: http://localhost:8000/openapi.json
- **Health**: http://localhost:8000/health

```bash
# Production
uvx --from vocal-ai vocal serve

# Development with auto-reload (from source)
make serve-dev
```

### Use the SDK

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

# Text-to-Speech (default: mp3)
audio = client.audio.text_to_speech(
    text="Hello, world!",
    model="pyttsx3"
)
with open("output.mp3", "wb") as f:
    f.write(audio)

# TTS with specific format and voice
audio = client.audio.text_to_speech(
    text="Hello!",
    response_format="wav",  # mp3, wav, opus, aac, flac, pcm
    voice="Samantha"
)
```

### CLI Commands

```bash
# Start server
uvx --from vocal-ai vocal serve

# Transcribe audio
uvx --from vocal-ai vocal run audio.mp3

# List models
uvx --from vocal-ai vocal models list

# Download model
uvx --from vocal-ai vocal models pull Systran/faster-whisper-tiny

# Delete model
uvx --from vocal-ai vocal models delete Systran/faster-whisper-tiny
```

### API Examples

**Transcribe Audio:**

```bash
curl -X POST "http://localhost:8000/v1/audio/transcriptions" \
  -F "file=@audio.mp3" \
  -F "model=Systran/faster-whisper-tiny"
```

**Text-to-Speech:**

```bash
# Default format is mp3
curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"model":"pyttsx3","input":"Hello world"}' \
  --output speech.mp3

# Request specific format (mp3, wav, opus, aac, flac, pcm)
curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"model":"pyttsx3","input":"Hello world","response_format":"wav"}' \
  --output speech.wav
```

### Docker Deployment

```bash
# Basic usage
docker compose up

# With GPU support
docker compose --profile gpu up

# Custom port
docker run -p 9000:8000 niradler/vocal-api
```

### Troubleshooting

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

## Cross-Platform Support

Vocal runs on **Windows**, **macOS**, and **Linux** out of the box. The TTS engine automatically selects the best available backend per platform:

| Platform | TTS Backend                 | Notes                            |
| -------- | --------------------------- | -------------------------------- |
| macOS    | `say` (NSSpeechSynthesizer) | 170+ built-in voices             |
| Linux    | `espeak` / `espeak-ng`      | Install via `apt install espeak` |
| Windows  | SAPI5 (via pyttsx3)         | Uses system voices               |

Audio output is normalized through ffmpeg, supporting all formats (mp3, wav, opus, aac, flac, pcm) regardless of platform. Requires `ffmpeg` for non-WAV output formats.

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

- `model` (required): TTS model to use (e.g., "pyttsx3" for system voices, "hexgrad/Kokoro-82M")
- `input` (required): Text to synthesize
- `voice` (optional): Voice ID to use (see `GET /v1/audio/voices`)
- `speed` (optional): Speech speed multiplier (0.25-4.0, default: 1.0)
- `response_format` (optional): `mp3` (default), `wav`, `opus`, `aac`, `flac`, `pcm` - matches OpenAI TTS API

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

| Model ID                                 | Size   | Parameters | VRAM  | Speed       | Status      |
| ---------------------------------------- | ------ | ---------- | ----- | ----------- | ----------- |
| `Systran/faster-whisper-tiny`            | ~75MB  | 39M        | 1GB+  | Fastest     | CTranslate2 |
| `Systran/faster-whisper-base`            | ~145MB | 74M        | 1GB+  | Fast        | CTranslate2 |
| `Systran/faster-whisper-small`           | ~488MB | 244M       | 2GB+  | Good        | CTranslate2 |
| `Systran/faster-whisper-medium`          | ~1.5GB | 769M       | 5GB+  | Better      | CTranslate2 |
| `Systran/faster-whisper-large-v3`        | ~3.1GB | 1.5B       | 10GB+ | Best        | CTranslate2 |
| `Systran/faster-distil-whisper-large-v3` | ~756MB | 809M       | 6GB+  | Fast & Good | CTranslate2 |

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
  "gpu_devices": [
    {
      "name": "NVIDIA GeForce RTX 4090",
      "vram_gb": 24.0,
      "compute_capability": "8.9"
    }
  ]
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

**Current Status: 47/47 tests passing ✅**

Test coverage includes:

- API health and device information (GPU detection)
- Model management (list, download, status, delete)
- Audio transcription with real M4A and MP3 files
- Text-to-Speech synthesis in all formats (mp3, wav, opus, aac, flac, pcm)
- TTS voice selection and speed control
- Audio format validation and Content-Type headers
- Error handling for invalid models, files, and formats
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

## Configuration

### Environment Variables

Create a `.env` file:

```env
APP_NAME=Vocal API
VERSION=0.1.0
DEBUG=true
CORS_ORIGINS=["*"]
MAX_UPLOAD_SIZE=26214400

# TTS Configuration
VOCAL_TTS_SAMPLE_RATE=16000  # Output sample rate in Hz (default: 16000)
```

**TTS Configuration:**
- `VOCAL_TTS_SAMPLE_RATE`: Output sample rate for all TTS audio (default: `16000` Hz / 16 kHz)
  - Common values: `8000` (phone quality), `16000` (wideband), `22050` (CD half), `44100` (CD quality), `48000` (professional)
  - All TTS output will be resampled to this rate via ffmpeg

### Model Storage

Models are cached at: `~/.cache/vocal/models/`

## Contributing

We welcome contributions!

```bash
# Fork and clone
git clone <your-fork-url>
cd vocal

# Setup
uv venv && uv sync

# Run tests
make test

# Submit PR
git checkout -b feature/your-feature
# Make changes, commit, and push
```

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
