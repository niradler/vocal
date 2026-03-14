# Getting Started with Vocal

Vocal is a self-hosted Speech AI platform — think Ollama but for voice models. It manages STT (Speech-to-Text) and TTS (Text-to-Speech) models with an OpenAI-compatible REST API, a Python SDK, and a CLI.

## Prerequisites

- **Python 3.11+**
- **ffmpeg** — required for audio format conversion (mp3, opus, aac, flac, pcm)

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian / WSL
sudo apt install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

## Install

```bash
# Run directly with uvx — no installation needed
uvx --from vocal-ai vocal serve

# Or install permanently
pip install vocal-ai
vocal serve
```

The API is now running at **http://localhost:8000**. Open http://localhost:8000/docs for the interactive Swagger UI.

## Your First Transcription

```bash
# 1. Pull a model (small, fast, CPU-friendly)
vocal models pull Systran/faster-whisper-tiny

# 2. Transcribe a file
vocal transcribe your_audio.wav
# or via API:
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@your_audio.wav" \
  -F "model=Systran/faster-whisper-tiny"
```

## Your First Text-to-Speech

```bash
# pyttsx3 is built-in, no download needed
vocal speak "Hello, world!"

# or via API:
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"pyttsx3","input":"Hello, world!"}' \
  --output hello.wav
```

## Install Optional Backends

Optional TTS/STT backends are installed as extras:

```bash
pip install "vocal-ai[kokoro]"     # Kokoro-82M neural TTS (CPU/GPU, 30+ voices)
pip install "vocal-ai[piper]"      # Piper TTS (offline, fast, many languages)
pip install "vocal-ai[qwen3-tts]"  # Qwen3-TTS 0.6B/1.7B (CUDA required)

# Or use uvx for one-off runs:
uvx --from "vocal-ai[kokoro]" vocal serve
```

If a backend is missing, Vocal prints the exact install command.

## Real-time Microphone Transcription

```bash
# Chunk-based (1-2s latency, REST)
vocal listen

# WebSocket streaming (~200ms latency)
vocal live

# Full voice agent: speak → LLM → speak back
vocal chat    # requires Ollama running locally
```

## What's Next

- [Available Models](models.md) — full model catalog and hardware requirements
- [CLI Reference](cli.md) — all commands with options
- [Configuration](configuration.md) — environment variables, `.env` file
- [API Reference](../developer/architecture.md) — REST endpoints and SDK usage

## Platform Notes

| Platform | TTS built-in engine | Notes |
|----------|---------------------|-------|
| Windows  | SAPI5 (pyttsx3)     | Works out of the box |
| macOS    | NSSpeechSynthesizer | Works out of the box |
| Linux    | espeak-ng (pyttsx3) | `sudo apt install espeak-ng` |

> **Linux:** If you get a TTS error about a missing engine, install `espeak-ng`:
> `sudo apt install espeak-ng`
