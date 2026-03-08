# Vocal

**Ollama for Voice Models — Self-hosted Speech AI Platform**

[![License: SSPL-1.0](https://img.shields.io/badge/License-SSPL--1.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/vocal-ai.svg)](https://pypi.org/project/vocal-ai/)
[![CI](https://github.com/niradler/vocal/actions/workflows/ci.yml/badge.svg)](https://github.com/niradler/vocal/actions)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)](https://github.com/niradler/vocal)

Vocal manages STT (Speech-to-Text) and TTS (Text-to-Speech) models the way Ollama manages LLMs. It provides an OpenAI-compatible REST API, a Python SDK, and a CLI — with model download, caching, and multi-backend support built in.

---

## Quick Start

```bash
# Run without installing
uvx --from vocal-ai vocal serve

# Or install permanently
pip install vocal-ai
vocal serve
```

Interactive API docs are at **http://localhost:8000/docs**.

```bash
# Pull a model and transcribe
vocal models pull Systran/faster-whisper-tiny
vocal transcribe your_audio.wav

# Text-to-speech (built-in, no download)
vocal speak "Hello, world!"

# Real-time microphone transcription
vocal listen

# Full voice agent (STT → LLM → TTS)
vocal chat    # requires Ollama running locally
```

**Optional backends:**
```bash
pip install "vocal-ai[kokoro]"     # Kokoro-82M neural TTS (CPU/GPU)
pip install "vocal-ai[piper]"      # Piper TTS (offline, fast, multilingual)
pip install "vocal-ai[qwen3-tts]"  # Qwen3-TTS (CUDA required)
```

---

## Features

- **OpenAI-compatible** — `/v1/audio/transcriptions`, `/v1/audio/speech`, `/v1/realtime`
- **Ollama-style model management** — pull, list, delete models from the CLI or API
- **Auto-generated SDK** — typed Python client generated from the live OpenAPI spec
- **Streaming TTS** — first audio bytes before full synthesis completes
- **WebSocket ASR** — ~200 ms latency with server-side VAD
- **Voice agent** — full STT → LLM → TTS loop, OpenAI Realtime protocol compatible
- **Voice selection** — list and select voices per model
- **Voice cloning** — clone a voice from a 3–30 s reference recording
- **Cross-platform** — Windows, macOS, Linux (WSL supported)
- **GPU acceleration** — automatic CUDA detection with VRAM optimization

---

## Documentation

| | |
|--|--|
| [Getting Started](docs/user/getting-started.md) | Install, first transcription, platform notes |
| [Available Models](docs/user/models.md) | STT/TTS catalog, hardware guide |
| [CLI Reference](docs/user/cli.md) | All commands with options |
| [Configuration](docs/user/configuration.md) | Environment variables, `.env` |
| [Contributing](docs/developer/contributing.md) | Dev setup, PR workflow |
| [Architecture](docs/developer/architecture.md) | Package structure, adapter pattern |
| [Adding Models](docs/developer/adding-models.md) | New STT/TTS backends |
| [Testing](docs/developer/testing.md) | Test tiers, CI, cross-platform |
| [Release Process](docs/developer/release.md) | Version bump, PyPI publish |

---

## API Overview

### Speech-to-Text (OpenAI-compatible)
```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@audio.mp3" \
  -F "model=Systran/faster-whisper-tiny"
```

### Text-to-Speech (OpenAI-compatible)
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"pyttsx3","input":"Hello, world!","response_format":"wav"}' \
  --output speech.wav
```

### Voice Cloning
```bash
curl -X POST http://localhost:8000/v1/audio/clone \
  -F "text=Synthesize in my voice." \
  -F "reference_audio=@speaker.wav" \
  --output clone.wav
```

### Model Management (Ollama-style)
```bash
curl http://localhost:8000/v1/models               # list
curl -X POST http://localhost:8000/v1/models/Systran/faster-whisper-tiny/download
curl -X DELETE http://localhost:8000/v1/models/Systran/faster-whisper-tiny
```

### SDK

```python
from vocal_sdk import VocalClient
from vocal_sdk.api.audio import text_to_speech_v1_audio_speech_post
from vocal_sdk.models import TTSRequest

client = VocalClient(base_url="http://localhost:8000")
audio = text_to_speech_v1_audio_speech_post.sync(
    client=client,
    body=TTSRequest(model="pyttsx3", input="Hello from the SDK."),
)
open("output.wav", "wb").write(audio)
```

---

## Cross-Platform

| Platform | TTS Engine | Notes |
|----------|------------|-------|
| Windows | SAPI5 (pyttsx3) | Built-in, no extra install |
| macOS | NSSpeechSynthesizer | Built-in, no extra install |
| Linux / WSL | espeak-ng (pyttsx3) | `sudo apt install espeak-ng ffmpeg` |

All audio formats (mp3, wav, opus, aac, flac, pcm) work on all platforms via ffmpeg.

---

## Contributing

```bash
git clone https://github.com/niradler/vocal.git
cd vocal
make install
make lint && make test
```

See [docs/developer/contributing.md](docs/developer/contributing.md) for the full workflow.

---

## License

[Server Side Public License (SSPL-1.0)](LICENSE) — free to use and self-host. If you offer Vocal as a managed service to third parties, you must open-source your full service stack under the same license.

Built with [FastAPI](https://fastapi.tiangolo.com/), [faster-whisper](https://github.com/guillaumekln/faster-whisper), [HuggingFace Hub](https://huggingface.co/), and [uv](https://github.com/astral-sh/uv).
