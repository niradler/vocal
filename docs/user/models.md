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

Whisper-based models cover 99 languages and auto-detect language. The newer ASR families below are narrower but more accurate on English and European languages — check the Languages column before switching.

| Model ID | Size | Params | Min VRAM | Speed | Languages | Notes |
|----------|------|--------|----------|-------|-----------|-------|
| `Systran/faster-whisper-tiny` | ~75 MB | 39M | 1 GB | Fastest | 99 | Best for CPU |
| `Systran/faster-whisper-base` | ~145 MB | 74M | 1 GB | Fast | 99 | Good CPU option |
| `Systran/faster-whisper-small` | ~488 MB | 244M | 2 GB | Good | 99 | Balanced |
| `Systran/faster-whisper-medium` | ~1.5 GB | 769M | 5 GB | Better | 99 | GPU recommended |
| `Systran/faster-whisper-large-v3` | ~3.1 GB | 1.5B | 10 GB | Best | 99 | GPU required |
| `Qwen/Qwen3-ASR-0.6B-hf` | ~1.5 GB | 600M | 4 GB | Good | 30+ dialects | Native transformers path; needs the `-hf` checkpoint |
| `Qwen/Qwen3-ASR-1.7B-hf` | ~3.8 GB | 1.7B | 8 GB | Better | 30+ dialects | Most accurate open model on the Open ASR board |
| `ibm-granite/granite-speech-5.0-470m-turboctc` | ~0.95 GB | 473M | 4 GB | Fastest | 7 | CTC decoder, highest throughput; emits `<|nospeech|>` on silence |
| `ibm-granite/granite-speech-5.0-2b` | ~4.6 GB | 2.31B | 10 GB | Better | 6 | Keyword biasing, prompt-controlled language |
| `CohereLabs/cohere-transcribe-03-2026` | ~4.1 GB | 2.07B | 10 GB | Good | 14 | Long-form English leader; gated repo, needs an accepted HF licence + `HF_TOKEN` |
| `nvidia/nemotron-3.5-asr-streaming-0.6b` | ~2.4 GB | 638M | 6 GB | Fast | 40 locales | Built for voice agents: native streaming, automatic language detection |
| `mistralai/Voxtral-Mini-4B-Realtime-2602` | ~9 GB | 4B | 16 GB | Good | 13 | Requires `[voxtral]` + CUDA |

**Backend:** `Systran/faster-whisper-*` models use CTranslate2 (optimized, quantized). Qwen3-ASR, Granite Speech and Cohere Transcribe use HuggingFace Transformers (dedicated prompt/processor paths). Qwen3-ASR only works with the `*-hf` checkpoints (e.g. `Qwen/Qwen3-ASR-0.6B-hf`) because that layout matches transformers' native `Qwen3ASRForConditionalGeneration`; the original repos ship custom-code weights that require an older transformers. Nemotron 3.5 uses NeMo and needs a NeMo build that ships `nemotron-3.5` (>= 26.06). Voxtral uses `VoxtralRealtimeForConditionalGeneration` from transformers≥5.2.0.

**Timestamps:** Granite Speech, Cohere Transcribe, Nemotron 3.5 and Qwen3-ASR return text only. Use Whisper, WhisperX or Parakeet when you need word timestamps.

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

### Phonon 31M (CPU, Apache-2.0)

Requires: `pip install "vocal-ai[phonon]"`

| Model ID | Size | Params | VRAM | Languages | Voices |
|----------|------|--------|------|-----------|--------|
| `gradium/phonon-31m-en` | ~65 MB | 31M | CPU | English | 100+ shipped |

Rust/GGUF runtime with no PyTorch, so it stays out of the GPU entirely and starts in milliseconds. Supports true chunked streaming. It cannot clone a voice: the voice catalogue (`GET /v1/audio/voices?model=gradium/phonon-31m-en`) is a set of precomputed speaker latents.

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"gradium/phonon-31m-en","input":"Hello from Phonon.","voice":"Easton"}' \
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
| `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | ~4.2 GB | 1.7B | 8 GB+ | zh/en/ja/ko/de/fr/ru/pt/es/it |

Base models clone a voice from reference audio. VoiceDesign creates a voice from a text description passed as `voice`. Custom-voice models use preset speaker ids.

### Chatterbox Multilingual V3

Requires: `pip install "vocal-ai[chatterbox]"`

| Model ID | Size | Params | VRAM | Languages |
|----------|------|--------|------|-----------|
| `ResembleAI/chatterbox-multilingual-v3` | ~1 GB | 0.5B | 4 GB+ | 23 languages |

Zero-shot cloning from reference audio. Pass `language` as an ISO code such as `en`, `zh`, or `ja`.

### Supertonic 3 (CPU)

Requires: `pip install "vocal-ai[supertonic]"`

| Model ID | Size | Params | VRAM | Languages |
|----------|------|--------|------|-----------|
| `Supertone/supertonic-3` | ~400 MB | 99M | CPU | 31 languages |

ONNX, so it does not use the GPU. Preset voices are `M1`–`M5` and `F1`–`F5`.

### VoxCPM2 (CUDA)

Requires: `pip install "vocal-ai[voxcpm]"` + NVIDIA GPU

| Model ID | Size | Params | VRAM | Languages |
|----------|------|--------|------|-----------|
| `openbmb/VoxCPM2` | ~4 GB | 2B | 8 GB+ | 30 languages |

48 kHz output. Pass a voice description as `voice`, or clone from reference audio.

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

## External-Runtime Models (catalogued, not served in-process)

Some of the strongest open voice models cannot run inside Vocal's Python process — they need vLLM-Omni / SGLang-Omni, or they pin an incompatible `transformers`. Vocal still lists them so you can compare licenses and capabilities, but `/v1/audio/speech` returns a clear error explaining which engine to use. `GET /v1/models` reports `runtime: "external"` plus `runtime_note` for these.

| Model ID | Size | Params | Min VRAM | License | Commercial use | Why external |
|----------|------|--------|----------|---------|----------------|--------------|
| `inclusionAI/Ming-3.0-tts-0.5B` | ~3 GB | 1.48B | 8 GB | MIT | Yes | No PyPI package; vendored runtime pins `transformers==4.46.3` |
| `bosonai/higgs-tts-3-4b` | ~9.3 GB | 4.65B | 16 GB | Boson Higgs TTS 3 (non-commercial) | No (needs Boson agreement for hosted use) | Only vLLM-Omni / SGLang-Omni |
| `fishaudio/drama-3` | ~41.5 GB | 35.9B MoE | 48 GB+ | Fish Audio Community 1.0 | Under $500k revenue, **never** as a hosted TTS service | SGLang-Omni / vLLM-Omni, 48 GB+ |

To use one of them, serve the model with its own engine and point your OpenAI-compatible client at that server. Vocal does not proxy those engines yet.

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
| `license` | SPDX-style identifier of the weights license |
| `commercial_use` | Whether that license permits commercial or hosted use |
| `runtime` | `in_process` (Vocal serves it) or `external` (needs another engine) |
| `runtime_note` | The engine requirement when `runtime` is `external` |
| `maintenance_status` | `active`, `retired` (upstream dropped, still works) or `deprecated` |

Check `commercial_use` before shipping a model in a product — several top-ranked models (Voxtral TTS, Higgs, Drama 3) are non-commercial, and Llama-derived checkpoints such as Orpheus are no longer catalogued because they had no working adapter.

---

## Hardware Guide

| Setup | Recommended STT | Recommended TTS |
|-------|----------------|-----------------|
| CPU only | `faster-whisper-tiny` | `gradium/phonon-31m-en` |
| CPU + 4 GB RAM | `faster-whisper-base` | `gradium/phonon-31m-en` |
| GPU 4–8 GB VRAM | `granite-speech-5.0-470m-turboctc` | `hexgrad/Kokoro-82M` |
| GPU 8+ GB VRAM | `Qwen3-ASR-1.7B-hf` | `Qwen3-TTS-0.6B` |
| GPU 12+ GB VRAM | `CohereLabs/cohere-transcribe-03-2026` | `Qwen3-TTS-1.7B` |
| GPU 16+ GB VRAM | `Voxtral-Mini-4B-Realtime-2602` | `Voxtral-4B-TTS-2603` (via vLLM) |
| Voice agents | `nemotron-3.5-asr-streaming-0.6b` | `gradium/phonon-31m-en` (streaming, CPU) |

---

## Model Storage

Models are cached at `~/.cache/vocal/models/` by default. To share models between environments (e.g. Windows + WSL), symlink the directory:

```bash
# WSL: point to Windows cache
mkdir -p ~/.cache/vocal
ln -sfn /mnt/c/Users/<username>/.cache/vocal/models ~/.cache/vocal/models
```
