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
- 🎤 **OpenAI Compatible**: `/v1/audio/transcriptions` and `/v1/audio/speech` endpoints
- 🔊 **Neural TTS**: Kokoro-82M, Qwen3-TTS (0.6B / 1.7B), Piper, or system voices
- 📡 **Streaming TTS**: Chunked audio delivery via `"stream": true` — first bytes arrive immediately
- 🎙️ **Voice Agent**: `vocal chat` — full STT → LLM → TTS loop, OpenAI Realtime API compatible
- 🎨 **CLI Tool**: Typer-based CLI with rich console output
- 💻 **Cross-Platform**: Full support for Windows, macOS, and Linux
- ✅ **Production Ready**: 41/41 tests passing with real audio assets

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

# Optional backends (install what you need)
pip install vocal-ai[kokoro]     # Kokoro-82M neural TTS (CPU/GPU)
pip install vocal-ai[qwen3-tts]  # Qwen3-TTS 0.6B / 1.7B (CUDA required)
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

The SDK is auto-generated from the OpenAPI spec and provides a fully typed async/sync client.

```python
from pathlib import Path

from vocal_sdk import VocalClient
from vocal_sdk.api.models import (
    download_model_v1_models_model_id_download_post,
    list_models_v1_models_get,
)
from vocal_sdk.api.transcription import create_transcription_v1_audio_transcriptions_post
from vocal_sdk.api.audio import text_to_speech_v1_audio_speech_post
from vocal_sdk.models import (
    BodyCreateTranscriptionV1AudioTranscriptionsPost,
    TTSRequest,
    ModelStatus,
)
from vocal_sdk.types import File

client = VocalClient(base_url="http://localhost:8000")

# List models (Ollama-style)
resp = list_models_v1_models_get.sync(client=client)
for model in resp.models:
    print(f"{model.id}: {model.status.value}")

# Download model if needed (Ollama-style pull)
download_model_v1_models_model_id_download_post.sync(
    model_id="Systran/faster-whisper-tiny", client=client
)

# Transcribe audio (OpenAI-compatible)
with open("audio.mp3", "rb") as f:
    body = BodyCreateTranscriptionV1AudioTranscriptionsPost(
        file=File(payload=f, file_name="audio.mp3"),
        model="Systran/faster-whisper-tiny",
    )
    result = create_transcription_v1_audio_transcriptions_post.sync(client=client, body=body)
print(result.text)

# Text-to-Speech (default: mp3)
audio_bytes = text_to_speech_v1_audio_speech_post.sync(
    client=client,
    body=TTSRequest(model="pyttsx3", input="Hello, world!"),
)
Path("output.mp3").write_bytes(audio_bytes)
```

> **Backward compatibility:** The legacy `VocalSDK` dict-based wrapper is still available via `from vocal_sdk import VocalSDK` for existing code. New code should use `VocalClient` with the typed generated API functions above.

### CLI Commands

```bash
# Start server
uvx --from vocal-ai vocal serve

# Transcribe audio file
uvx --from vocal-ai vocal run audio.mp3

# Real-time microphone transcription (ASR streaming)
uvx --from vocal-ai vocal listen
uvx --from vocal-ai vocal listen --device "Razer"   # select mic by name
uvx --from vocal-ai vocal devices                   # list available microphones

# Voice agent — full STT → LLM → TTS loop
uvx --from vocal-ai vocal chat --device "Razer" --output-device 1
uvx --from vocal-ai vocal output-devices            # list available speakers

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

# Streaming: receive audio chunks as they are generated
curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","input":"Hello world","response_format":"pcm","stream":true}' \
  --output - | play -r 24000 -e signed -b 16 -c 1 -t raw -

# Kokoro neural TTS (requires: pip install vocal-ai[kokoro])
curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"model":"hexgrad/Kokoro-82M","input":"Hello world","voice":"af_heart"}' \
  --output speech.mp3

# Qwen3-TTS (requires: pip install vocal-ai[qwen3-tts] + CUDA GPU)
curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-tts-1.7b-custom","input":"Hello world","voice":"aiden"}' \
  --output speech.mp3
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

- `model` (required): TTS model to use (e.g., `"pyttsx3"`, `"hexgrad/Kokoro-82M"`, `"qwen3-tts-1.7b-custom"`)
- `input` (required): Text to synthesize
- `voice` (optional): Voice ID to use (see `GET /v1/audio/voices`)
- `speed` (optional): Speech speed multiplier (0.25-4.0, default: 1.0)
- `response_format` (optional): `mp3` (default), `wav`, `opus`, `aac`, `flac`, `pcm`
- `stream` (optional): `false` (default) — set to `true` to receive audio as chunked transfer. With Kokoro, `wav` and `pcm` formats yield real per-sentence chunks; other formats fall back to a single chunk after generation.

**Response (stream: false):**
Returns audio file in specified format with headers:

- `X-Duration`: Audio duration in seconds
- `X-Sample-Rate`: Audio sample rate

**Response (stream: true):**
Returns `Transfer-Encoding: chunked` streaming response. Audio bytes arrive as they are generated — first chunk delivered before full synthesis completes.

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

### STT (Speech-to-Text)

| Model ID                                 | Size   | Parameters | VRAM  | Speed       | Backend     |
| ---------------------------------------- | ------ | ---------- | ----- | ----------- | ----------- |
| `Systran/faster-whisper-tiny`            | ~75MB  | 39M        | 1GB+  | Fastest     | CTranslate2 |
| `Systran/faster-whisper-base`            | ~145MB | 74M        | 1GB+  | Fast        | CTranslate2 |
| `Systran/faster-whisper-small`           | ~488MB | 244M       | 2GB+  | Good        | CTranslate2 |
| `Systran/faster-whisper-medium`          | ~1.5GB | 769M       | 5GB+  | Better      | CTranslate2 |
| `Systran/faster-whisper-large-v3`        | ~3.1GB | 1.5B       | 10GB+ | Best        | CTranslate2 |

All STT models support 99+ languages. Use alias `whisper-tiny`, `whisper-base`, etc. for short names.

### TTS (Text-to-Speech)

| Alias / Model ID                              | Size   | Parameters | VRAM   | Languages       | Install extra  |
| --------------------------------------------- | ------ | ---------- | ------ | --------------- | -------------- |
| `pyttsx3`                                     | —      | —          | None   | System voices   | built-in       |
| `kokoro` / `hexgrad/Kokoro-82M`               | ~347MB | 82M        | 4GB+   | en (30+ voices) | `[kokoro]`     |
| `kokoro-onnx` / `onnx-community/Kokoro-82M-ONNX` | ~1.3GB | 82M     | 6GB+   | en              | `[kokoro]`     |
| `qwen3-tts-0.6b` / `Qwen/Qwen3-TTS-...-0.6B-Base` | ~2.3GB | 915M  | 8GB+   | zh/en/ja/ko/de/fr/ru/pt/es/it | `[qwen3-tts]` |
| `qwen3-tts-1.7b` / `Qwen/Qwen3-TTS-...-1.7B-Base` | ~4.2GB | 1.9B  | 8GB+   | zh/en/ja/ko/de/fr/ru/pt/es/it | `[qwen3-tts]` |
| `qwen3-tts-0.6b-custom`                       | ~2.3GB | 906M       | 8GB+   | zh/en/ja/ko/de/fr/ru/pt/es/it | `[qwen3-tts]` |
| `qwen3-tts-1.7b-custom`                       | ~4.2GB | 1.9B       | 8GB+   | zh/en/ja/ko     | `[qwen3-tts]` |

**Kokoro** runs on CPU or GPU and supports real per-sentence streaming. **Qwen3-TTS** requires an NVIDIA CUDA GPU.

```bash
# Install optional backends
pip install vocal-ai[kokoro]      # Kokoro neural TTS
pip install vocal-ai[qwen3-tts]   # Qwen3-TTS (CUDA required)
pip install vocal-ai[kokoro,qwen3-tts]  # Both
```

> **Note (Kokoro):** The `kokoro` package uses the spaCy `en_core_web_sm` model for English text processing. PyPI does not allow packages to declare direct URL dependencies, so it is not listed in the install extras. If Kokoro raises an error about a missing spaCy model, install it manually:
>
> ```bash
> python -m spacy download en_core_web_sm
> ```

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
from vocal_sdk import VocalClient
from vocal_sdk.api.system import get_device_v1_system_device_get

client = VocalClient(base_url="http://localhost:8000")
info = get_device_v1_system_device_get.sync(client=client)
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

# Filter by task
vocal models list --task stt
vocal models list --task tts

# Download a model
vocal models pull Systran/faster-whisper-tiny

# Delete a model
vocal models delete Systran/faster-whisper-tiny
vocal models delete Systran/faster-whisper-tiny --force
```

### Real-time Transcription (ASR Streaming)

Vocal has three real-time modes with different latency/complexity trade-offs:

| Command | Transport | Latency | How it works |
|---------|-----------|---------|--------------|
| `vocal listen` | REST (chunk-based) | ~1-2s | Sends audio after silence detected |
| `vocal live` | WebSocket streaming | ~200ms | Streams raw PCM, server returns partial tokens |
| `vocal chat` | WebSocket (OpenAI Realtime) | ~1-2s | Full STT → LLM → TTS voice agent loop |

#### `vocal listen` — Chunk-based (REST)

```bash
# Listen to default microphone and transcribe speech live
vocal listen

# Select microphone by name substring or index
vocal listen --device "Razer"
vocal listen --device 3

# Translate speech to English (any source language)
vocal listen --task translate

# Tuning options
vocal listen --model Systran/faster-whisper-tiny  # STT model to use
vocal listen --language en                         # force language (skips auto-detect)
vocal listen --silence-duration 2.0               # seconds of silence before sending chunk
vocal listen --max-chunk-duration 15.0            # max chunk length before forced send
vocal listen --silence-threshold 300              # manual RMS threshold (skip auto-calibration)
vocal listen --verbose                            # show API latency per chunk
```

**How it works:**
1. Calibrates mic noise floor for ~1.5s on startup (stay quiet)
2. Shows a live energy bar while listening
3. Sends audio chunks to the STT REST API when silence is detected
4. Prints transcribed text after each utterance

#### `vocal live` — WebSocket streaming (~200ms latency)

```bash
# Stream mic directly over WebSocket, get tokens as they arrive
vocal live

# All the same device/model/language options as vocal listen
vocal live --device "Razer" --model Systran/faster-whisper-tiny --language en
vocal live --task translate --verbose
```

**How it works:**
1. Connects to `ws://localhost:8000/v1/audio/stream` via WebSocket
2. Streams raw PCM16 frames continuously — no client-side VAD
3. Server does energy-based VAD, triggers faster-whisper's streaming transcription
4. Partial tokens arrive word-by-word as faster-whisper decodes each segment

#### `vocal chat` — Voice agent (STT → LLM → TTS)

```bash
# Full voice loop: speak → transcribe → LLM → speak back
vocal chat

# Select microphone and speaker
vocal chat --device "Razer" --output-device 1

# List available speakers first
vocal output-devices

# Options
vocal chat --device "Razer"              # select mic by name substring or index
vocal chat --output-device 1             # select speaker by index
vocal chat --language en                 # force STT language (faster)
vocal chat --model Systran/faster-whisper-tiny  # STT model
vocal chat --system-prompt "You are a pirate. Keep answers short."
vocal chat --verbose                     # show event trace (debug)
```

**How it works:**
1. Connects to `/v1/realtime` WebSocket in `realtime` session mode
2. Streams mic audio — server VAD detects speech start/end
3. Transcribes utterance with faster-whisper
4. Sends transcript to LLM (`LLM_BASE_URL`, default: local Ollama)
5. Synthesises LLM response with TTS, streams audio back
6. Mic is muted during playback to prevent echo

**LLM configuration** (via env vars or `.env`):

```env
LLM_BASE_URL=http://localhost:11434/v1   # Ollama (default)
LLM_MODEL=gemma3n:latest
LLM_API_KEY=ollama

# Or point at OpenAI:
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
```

#### `vocal devices` — List audio input devices

```bash
vocal devices
```

Shows all available microphone devices with index, name, channel count, and default sample rate. Use the index or a name substring with `--device` to select.

#### `vocal output-devices` — List audio output devices

```bash
vocal output-devices
```

Shows all available speaker/output devices. Use the index with `--output-device` in `vocal chat`.

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

**Current Status: 41/41 tests passing ✅**

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

All defaults are defined in `vocal_core/config.py` (`VocalSettings`) and can be overridden via environment variables or a `.env` file in your working directory.

```env
# LLM backend (used by vocal chat / /v1/realtime in realtime mode)
LLM_BASE_URL=http://localhost:11434/v1   # OpenAI-compatible endpoint (Ollama default)
LLM_MODEL=gemma3n:latest                 # Model to use
LLM_API_KEY=ollama                       # "ollama" = no auth; set sk-... for OpenAI

# STT defaults
STT_DEFAULT_MODEL=Systran/faster-whisper-tiny
STT_DEFAULT_LANGUAGE=                    # empty = auto-detect
STT_SAMPLE_RATE=16000                    # internal STT sample rate (Hz)

# VAD tuning (server-side voice activity detection)
VAD_THRESHOLD=400.0                      # RMS energy threshold (0–32768 scale)
VAD_SILENCE_FRAMES=15                    # silence frames before end-of-speech
VAD_MAX_BUFFER_FRAMES=150               # max buffer before forced commit
VAD_SPEECH_ONSET_FRAMES=3               # consecutive loud frames to trigger speech_started
VAD_MIN_SPEECH_FRAMES=4                 # min speech frames required before committing
VAD_SILENCE_DURATION_S=1.5              # vocal live: silence duration before sending chunk

# Audio / CLI
AUDIO_FRAME_SIZE=1600                    # mic frame size (samples)
AUDIO_CHANNELS=1                         # mono
PLAYBACK_COOLDOWN=0.5                    # seconds mic stays muted after TTS playback

# vocal chat default system prompt
CHAT_SYSTEM_PROMPT=You are a helpful voice assistant. Keep answers short and conversational, 1 sentence max, no symbols or punctuation.
```

**VAD tuning tips:**
- Too many false triggers (background noise) → raise `VAD_THRESHOLD` or `VAD_SPEECH_ONSET_FRAMES`
- Missing short utterances → lower `VAD_MIN_SPEECH_FRAMES` or `VAD_SPEECH_ONSET_FRAMES`
- Echo from speakers → raise `PLAYBACK_COOLDOWN`

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
- Kokoro-82M neural TTS adapter (CPU/GPU, 30+ voices, streaming)
- Qwen3-TTS 0.6B / 1.7B adapter (CUDA, 10 languages, custom-voice variants)
- Streaming TTS via `"stream": true` — chunked transfer, first bytes before full generation
- `faster-qwen3-tts` as optional install extra (`pip install vocal-ai[qwen3-tts]`)

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

### ✅ Completed (v0.4.0)

**`vocal live` + `/v1/audio/stream` — WebSocket Streaming ASR**

- `vocal live` streams raw PCM16 frames over WebSocket, server does VAD + faster-whisper streaming, client receives partial tokens at ~200ms latency
- `/v1/audio/stream` — binary WebSocket: PCM16 @16kHz in, `transcript.delta` / `transcript.done` JSON events out

**OpenAI Realtime API Drop-in (`/v1/realtime`)**

- Full WebSocket implementation of the OpenAI Realtime Transcription Session protocol
- Session types: `transcription` (STT only) and `realtime` (STT → LLM → TTS full loop)
- Implements: `session.created`, `input_audio_buffer.*`, `conversation.item.input_audio_transcription.*`, `response.*` events
- LLM is pluggable via `LLM_BASE_URL` env var (defaults to local Ollama at `http://localhost:11434/v1`)
- Any OpenAI-compatible client SDK can point at `ws://localhost:8000/v1/realtime` — no API key needed locally

```
/v1/realtime  (WebSocket, OpenAI Realtime protocol)
  transcription: mic PCM → faster-whisper → transcript delta events
  realtime:      mic PCM → faster-whisper → Ollama LLM → TTS → audio delta events
```

**Global Config (`vocal_core.config.VocalSettings`)**

All defaults live in `vocal_core/config.py` and are overridable via env vars or `.env`:

| Env var | Default | Purpose |
|---------|---------|---------|
| `LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible LLM endpoint (Ollama default) |
| `LLM_MODEL` | `gemma3n:latest` | LLM model for voice agent mode |
| `LLM_API_KEY` | `ollama` | API key (`ollama` = no auth; set `sk-...` for OpenAI) |
| `STT_DEFAULT_MODEL` | `Systran/faster-whisper-tiny` | Default STT model |
| `STT_SAMPLE_RATE` | `16000` | Internal STT sample rate (Hz) |
| `VAD_THRESHOLD` | `400.0` | RMS energy threshold for speech detection |
| `VAD_SPEECH_ONSET_FRAMES` | `3` | Consecutive loud frames before speech_started fires |
| `VAD_MIN_SPEECH_FRAMES` | `4` | Min speech frames before committing to Whisper |
| `VAD_SILENCE_FRAMES` | `15` | Silence frames before end-of-speech |
| `PLAYBACK_COOLDOWN` | `0.5` | Seconds mic stays muted after TTS finishes |
| `CHAT_SYSTEM_PROMPT` | `You are a helpful voice assistant...` | Default system prompt for `vocal chat` |

### 🚀 Future (v0.5.0+)

**5. Voice Registry System**

- **Why:** Voices should be managed like models, not just system TTS
- **How:** `vocal voices list/pull/show` with downloadable voice models

**6. Voice Cloning (XTTS-v2)**

- **Why:** Custom voices are the killer feature for TTS
- **How:** `vocal voices clone my-voice --sample recording.wav`

**7. Voice Preview**

- **Why:** Users want to test voices before using them
- **How:** `vocal voices sample kokoro-en "Hello world"` generates quick sample

## Credits

Built with:

- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - STT engine
- [HuggingFace Hub](https://huggingface.co/) - Model distribution
- [uv](https://github.com/astral-sh/uv) - Python package manager
