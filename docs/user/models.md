# Models

Vocal uses an Ollama-style model registry. Models are downloaded on demand and cached at `~/.cache/vocal/models/`.

## Managing Models

```bash
# List all available models (downloaded + catalog)
vocal models list
vocal models list --task stt
vocal models list --task tts

# Show detailed info for a model
vocal models show Systran/faster-whisper-tiny

# Download a model
vocal models pull Systran/faster-whisper-tiny

# Delete a downloaded model
vocal models delete Systran/faster-whisper-tiny
```

Via API:
```bash
curl http://localhost:8000/v1/models
curl http://localhost:8000/v1/models/Systran/faster-whisper-tiny
curl -X POST http://localhost:8000/v1/models/Systran/faster-whisper-tiny/download
curl -X DELETE http://localhost:8000/v1/models/Systran/faster-whisper-tiny
```

---

## STT Models (Speech-to-Text)

All STT models support 99+ languages and auto-detect language by default.

| Model ID | Size | Params | Min VRAM | Speed | Notes |
|----------|------|--------|----------|-------|-------|
| `Systran/faster-whisper-tiny` | ~75 MB | 39M | 1 GB | Fastest | Best for CPU |
| `Systran/faster-whisper-base` | ~145 MB | 74M | 1 GB | Fast | Good CPU option |
| `Systran/faster-whisper-small` | ~488 MB | 244M | 2 GB | Good | Balanced |
| `Systran/faster-whisper-medium` | ~1.5 GB | 769M | 5 GB | Better | GPU recommended |
| `Systran/faster-whisper-large-v3` | ~3.1 GB | 1.5B | 10 GB | Best | GPU required |
| `Qwen/Qwen3-ASR-0.6B` | ~1.5 GB | 600M | 4 GB | Good | Transformers backend |
| `Qwen/Qwen3-ASR-1.7B` | ~3.5 GB | 1.7B | 8 GB | Better | Transformers backend |
| `mistralai/Voxtral-Mini-4B-Realtime-2602` | ~9 GB | 4B | 16 GB | Good | Requires `[voxtral]` + CUDA |

**Backend:** All `Systran/faster-whisper-*` models use CTranslate2 (optimized, quantized). Qwen3-ASR uses HuggingFace Transformers. Voxtral uses `VoxtralRealtimeForConditionalGeneration` from transformers≥5.2.0.

**Recommended starting point:** `Systran/faster-whisper-tiny` — runs on CPU, downloads in seconds.

---

## TTS Models (Text-to-Speech)

### pyttsx3 (built-in, no download)

| Model ID | VRAM | Languages | Install |
|----------|------|-----------|---------|
| `pyttsx3` | None | System voices | Built-in |

Uses the OS speech engine (SAPI5 on Windows, NSSpeechSynthesizer on macOS, espeak-ng on Linux). No GPU, no download. Good for development and simple use cases.

```bash
# List available voices
vocal voices --model pyttsx3
curl "http://localhost:8000/v1/audio/voices?model=pyttsx3"
```

### Kokoro-82M (neural, CPU/GPU)

Requires: `pip install "vocal-ai[kokoro]"`

| Model ID | Size | Params | VRAM | Languages | Voices |
|----------|------|--------|------|-----------|--------|
| `hexgrad/Kokoro-82M` | ~347 MB | 82M | 4 GB+ | English | 30+ |

High-quality neural TTS. Supports **streaming** (first audio chunk arrives before full synthesis). 30+ voices with distinct characteristics.

```bash
# List voices
curl "http://localhost:8000/v1/audio/voices?model=hexgrad/Kokoro-82M"

# Example voice IDs: af, af_bella, af_heart, af_sarah, am_adam, am_michael, bf_emma, bm_george
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"hexgrad/Kokoro-82M","input":"Hello","voice":"af_heart"}' \
  --output speech.wav
```

### Piper (offline, fast, many languages)

Requires: `pip install "vocal-ai[piper]"`

Fast offline TTS with models for 30+ languages. Models downloaded per voice.

```bash
# Use a piper model
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"piper","input":"Hello, world!"}' \
  --output speech.wav
```

### Qwen3-TTS (CUDA required)

Requires: `pip install "vocal-ai[qwen3-tts]"` + NVIDIA GPU

| Model ID | Size | Params | VRAM | Languages |
|----------|------|--------|------|-----------|
| `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | ~2.3 GB | 0.6B | 8 GB+ | zh/en/ja/ko/de/fr/ru/pt/es/it |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | ~4.2 GB | 1.7B | 8 GB+ | zh/en/ja/ko/de/fr/ru/pt/es/it |

Custom-voice variants support [voice cloning](getting-started.md) from a reference audio recording.

### Voxtral-4B-TTS (CUDA + vLLM required)

Requires: `pip install "vocal-ai[voxtral]"` + NVIDIA GPU (16 GB+ VRAM) + a running vLLM server

| Model ID | Size | VRAM | Voices | License |
|----------|------|------|--------|---------|
| `mistralai/Voxtral-4B-TTS-2603` | ~8 GB | 16 GB+ | 20 preset | CC BY-NC 4.0 |

Unlike other TTS models, Voxtral-TTS is **not loaded in-process**. It connects to a locally-running vLLM server:

```bash
# Start the vLLM server (requires vLLM installed)
vllm serve mistralai/Voxtral-4B-TTS-2603 --omni

# Point Vocal at it (default: http://localhost:8080)
export VOXTRAL_TTS_URL=http://localhost:8080
```

```bash
# List the 20 preset voices
curl "http://localhost:8000/v1/audio/voices?model=mistralai/Voxtral-4B-TTS-2603"

# Synthesize
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"mistralai/Voxtral-4B-TTS-2603","input":"Hello","voice":"calm_female"}' \
  --output speech.mp3
```

**License:** CC BY-NC 4.0 — non-commercial use only.

---

## Model Capabilities

Each model in the catalog declares its capabilities. You can inspect them via the API:

```bash
curl http://localhost:8000/v1/models/hexgrad/Kokoro-82M | python -m json.tool
```

Key capability fields:

| Field | Meaning |
|-------|---------|
| `supports_streaming` | Real-time chunked TTS output |
| `supports_voice_list` | Can enumerate available voices |
| `supports_voice_clone` | Can clone voice from reference audio |
| `requires_gpu` | Needs CUDA GPU to run |

---

## Hardware Guide

| Setup | Recommended STT | Recommended TTS |
|-------|----------------|-----------------|
| CPU only | `faster-whisper-tiny` | `pyttsx3` |
| CPU + 4 GB RAM | `faster-whisper-base` | `hexgrad/Kokoro-82M` |
| GPU 4–8 GB VRAM | `faster-whisper-small` | `hexgrad/Kokoro-82M` |
| GPU 8+ GB VRAM | `faster-whisper-medium` | `Qwen3-TTS-0.6B` |
| GPU 12+ GB VRAM | `faster-whisper-large-v3` | `Qwen3-TTS-1.7B` |
| GPU 16+ GB VRAM | `Voxtral-Mini-4B-Realtime-2602` | `Voxtral-4B-TTS-2603` (via vLLM) |

---

## Model Storage

Models are cached at `~/.cache/vocal/models/` by default. To share models between environments (e.g. Windows + WSL), symlink the directory:

```bash
# WSL: point to Windows cache
mkdir -p ~/.cache/vocal
ln -sfn /mnt/c/Users/<username>/.cache/vocal/models ~/.cache/vocal/models
```
