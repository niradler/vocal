# Vocal Manual Testing Guide

> **Audience:** QA, developers verifying a change, release validation.
> **Related:** [Automated testing guide](developer/testing.md) · [Docs index](README.md) · [CLI reference](user/cli.md)

Each domain below can be tested independently. Run the API server first (`make serve`), then work through whichever domain you changed.

**Prerequisites:**
```bash
make install   # install all packages
make serve     # start API on http://localhost:8000
```
API docs live at http://localhost:8000/docs while the server is running.

---

## 1. Health & System

### 1.1 Root + health endpoints
```bash
curl http://localhost:8000/
curl http://localhost:8000/health
```
Expected: `{"status":"healthy","api_version":"..."}` (200 OK)

### 1.2 Device info
```bash
curl http://localhost:8000/v1/system/device
```
Expected: JSON with `device` (`cpu` or `cuda`), `cuda_available`, `platform`.

---

## 2. Model Management

### 2.1 List all models
```bash
curl http://localhost:8000/v1/models
```
Expected: JSON array of model objects, each with `id`, `task`, `status`, `backend`.

### 2.2 Filter by task
```bash
curl "http://localhost:8000/v1/models?task=tts"
curl "http://localhost:8000/v1/models?task=stt"
```
Expected: only models matching the requested task.

### 2.3 Show model info
```bash
curl "http://localhost:8000/v1/models/Systran/faster-whisper-tiny"
curl "http://localhost:8000/v1/models/pyttsx3"
```
Expected: full model info including `supports_streaming`, `supports_voice_list`, `supports_voice_clone`, `requires_gpu`.

### 2.4 Download a model
```bash
curl -X POST "http://localhost:8000/v1/models/Systran/faster-whisper-tiny/download"
```
Expected: streaming progress events or 200 on completion.

### 2.5 Delete a model
```bash
curl -X DELETE "http://localhost:8000/v1/models/Systran/faster-whisper-tiny"
```
Expected: `{"deleted":true}` (re-download it after if needed for other tests).

### 2.6 CLI model commands
```bash
vocal models list
vocal models list --task stt
vocal models list --task tts
vocal models show Systran/faster-whisper-tiny
vocal models pull Systran/faster-whisper-tiny
```

---

## 3. Speech-to-Text (STT / Transcription)

**Requires:** `Systran/faster-whisper-tiny` downloaded. Use `tests/test_assets/audio/` samples.

### 3.1 Basic transcription
```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@tests/test_assets/audio/harvard.wav" \
  -F "model=Systran/faster-whisper-tiny"
```
Expected: `{"text":"...","language":"en",...}` — transcript of the Harvard sentences.

### 3.2 Verbose JSON (with segments + timestamps)
```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@tests/test_assets/audio/harvard.wav" \
  -F "model=Systran/faster-whisper-tiny" \
  -F "response_format=verbose_json"
```
Expected: response includes `segments` array with `start`, `end`, `text` per segment.

### 3.3 Plain text response
```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@tests/test_assets/audio/harvard.wav" \
  -F "model=Systran/faster-whisper-tiny" \
  -F "response_format=text"
```
Expected: plain text string (no JSON wrapper).

### 3.4 Translation to English
```bash
curl -X POST http://localhost:8000/v1/audio/translations \
  -F "file=@tests/test_assets/audio/harvard.wav" \
  -F "model=Systran/faster-whisper-tiny"
```
Expected: English text output.

### 3.5 Error — missing file
```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "model=Systran/faster-whisper-tiny"
```
Expected: 422 Unprocessable Entity.

### 3.6 Error — model not downloaded
```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@tests/test_assets/audio/harvard.wav" \
  -F "model=Systran/faster-whisper-large-v3"
```
Expected: 404 or 503 with clear error message (model not available).

### 3.7 CLI transcription
```bash
vocal transcribe tests/test_assets/audio/harvard.wav
vocal transcribe tests/test_assets/audio/harvard.wav --model Systran/faster-whisper-tiny
vocal transcribe tests/test_assets/audio/harvard.wav --language en
```

---

## 4. Text-to-Speech (TTS)

**Requires:** `pyttsx3` works out of the box (built-in). For Kokoro: download `hexgrad/Kokoro-82M` first.

### 4.1 Basic synthesis (pyttsx3 fallback)
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello, this is a test.", "model":"pyttsx3", "voice":"default"}' \
  --output test_out.wav
```
Expected: valid WAV file, playable.

### 4.2 Output formats
```bash
# MP3
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello world.", "model":"pyttsx3", "response_format":"mp3"}' \
  --output test_out.mp3

# PCM (raw)
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello world.", "model":"pyttsx3", "response_format":"pcm"}' \
  --output test_out.pcm
```
Expected: correct binary format, `Content-Type` header matches format.

### 4.3 Speed control
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello world.", "model":"pyttsx3", "speed":0.5}' \
  --output slow.wav

curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello world.", "model":"pyttsx3", "speed":2.0}' \
  --output fast.wav
```
Expected: `X-Audio-Duration` header present, audio noticeably slower/faster.

### 4.4 Error — empty input
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"", "model":"pyttsx3"}'
```
Expected: 422 Unprocessable Entity (min_length=1 validation).

### 4.5 Error — unknown model
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello.", "model":"nonexistent/model"}'
```
Expected: 404 or 503 with descriptive message.

### 4.6 CLI speech synthesis
```bash
vocal speak "Hello, world!" --output out.wav
vocal speak "Hello, world!" --model pyttsx3 --output out.wav
vocal speak "Hello, world." --format mp3 --output out.mp3
```

---

## 5. Voice Selection

**Tests the `/v1/audio/voices` endpoint and model capability system.**

### 5.1 List all voices (pyttsx3)
```bash
curl "http://localhost:8000/v1/audio/voices?model=pyttsx3"
```
Expected: array of voice objects with `voice_id`, `name`, `language`.

### 5.2 Use a specific voice
```bash
# First, get a voice ID from the list above, then:
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello, I am a specific voice.", "model":"pyttsx3", "voice":"<voice_id_from_list>"}' \
  --output voiced.wav
```
Expected: audio with the selected voice characteristics.

### 5.3 List Kokoro voices (requires download)
```bash
curl "http://localhost:8000/v1/audio/voices?model=hexgrad/Kokoro-82M"
```
Expected: array of Kokoro voice IDs (af, af_bella, af_sarah, etc.).

### 5.4 CLI voice listing
```bash
vocal voices
vocal voices --model pyttsx3
```

---

## 6. Voice Cloning

**New endpoint — requires a model with `supports_voice_clone: true`.** Currently this requires Qwen3-TTS which needs GPU. Validates API contract without GPU via error path testing.

### 6.1 Contract — missing model (expected error)
```bash
curl -X POST http://localhost:8000/v1/audio/clone \
  -F "text=Hello, this is my cloned voice." \
  -F "model=pyttsx3" \
  -F "reference_audio=@tests/test_assets/audio/harvard.wav"
```
Expected: 422 or 400 — `pyttsx3` does not support voice cloning.

### 6.2 Contract — empty text
```bash
curl -X POST http://localhost:8000/v1/audio/clone \
  -F "text=" \
  -F "model=pyttsx3" \
  -F "reference_audio=@tests/test_assets/audio/harvard.wav"
```
Expected: 422 (empty text not allowed).

### 6.3 Contract — too-short reference audio
```bash
# Create a 1-second clip (requires ffmpeg):
ffmpeg -i tests/test_assets/audio/harvard.wav -t 1 /tmp/short.wav -y
curl -X POST http://localhost:8000/v1/audio/clone \
  -F "text=Hello." \
  -F "model=pyttsx3" \
  -F "reference_audio=@/tmp/short.wav"
```
Expected: 422 — reference audio must be 3-30 seconds.

### 6.4 Full cloning (GPU only — skip if no CUDA)
```bash
# Only if Qwen/Qwen3-TTS-12Hz-0.6B-Base is downloaded and GPU is available:
curl -X POST http://localhost:8000/v1/audio/clone \
  -F "text=Hello, I am speaking in your voice." \
  -F "model=Qwen/Qwen3-TTS-12Hz-0.6B-Base" \
  -F "reference_audio=@your_voice_sample.wav" \
  --output cloned.wav
```
Expected: WAV file with synthesized speech matching the reference voice.

### 6.5 CLI cloning
```bash
vocal clone --help
vocal clone "Hello, world." --reference tests/test_assets/audio/harvard.wav --output clone_out.wav
```

---

## 7. WebSocket Streaming ASR (`/v1/audio/stream`)

**Real-time microphone transcription with server-side VAD.**

### 7.1 CLI live transcription
```bash
vocal live --model Systran/faster-whisper-tiny
# Speak into microphone — transcription appears in real time
# Press Ctrl+C to stop
```
Expected: text printed to console as you speak, with ~200ms latency.

### 7.2 CLI live with language hint
```bash
vocal live --model Systran/faster-whisper-tiny --language en
```

### 7.3 WebSocket direct test (requires `wscat` or `websocat`)
```bash
# Install: npm install -g wscat
wscat -c "ws://localhost:8000/v1/audio/stream?model=Systran/faster-whisper-tiny"
# Then send raw PCM16 binary frames (16kHz mono)
```
Expected: `{"type":"transcript.delta","text":"..."}` events as audio is decoded.

### 7.4 VAD threshold tuning
```bash
vocal live --threshold 800 --silence-duration 2.0
```
Expected: higher threshold = less sensitive (ignores background noise), longer silence waits more before flushing.

---

## 8. OpenAI Realtime (`/v1/realtime`)

**Full OpenAI Realtime API compatible endpoint.**

### 8.1 CLI real-time voice agent
```bash
vocal realtime
# Speak a question — model transcribes, LLM replies, TTS speaks back
# Press Ctrl+C to stop
```
Expected: conversational voice loop. Requires Ollama running locally with `gemma3n:latest` (or override `LLM_BASE_URL`).

### 8.2 Transcription-only session
```bash
vocal realtime --session-type transcription
```
Expected: transcribes speech only, no LLM/TTS response.

### 8.3 OpenAI-compatible client test
```python
from openai import AsyncOpenAI
client = AsyncOpenAI(base_url="http://localhost:8000", api_key="local")
# Connect with Realtime API — same client code works against Vocal as against OpenAI
```

### 8.4 Error — invalid model
```bash
# Via WebSocket with invalid model:
wscat -c "ws://localhost:8000/v1/realtime?model=nonexistent"
# Send: {"type":"session.update","session":{"model":"nonexistent"}}
```
Expected: `{"type":"error","error":{"code":"model_not_found","message":"..."}}`.

---

## 9. CLI — Microphone / Listen

**Chunk-based microphone transcription (polling REST, no WebSocket).**

### 9.1 Basic listen
```bash
vocal listen
# Speak into microphone — transcript appears after silence
# Press Ctrl+C to stop
```
Expected: transcript printed after each speech segment.

### 9.2 Listen with translation
```bash
vocal listen --task translate --language fr
# Speak French — output in English
```

### 9.3 List audio devices
```bash
vocal devices
```
Expected: numbered list of input audio devices.

---

## 10. Configuration & Environment

### 10.1 Override STT default model
```bash
STT_DEFAULT_MODEL=Systran/faster-whisper-base vocal serve
# Then transcribe without specifying model:
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@tests/test_assets/audio/harvard.wav"
```
Expected: uses `faster-whisper-base` instead of `faster-whisper-tiny`.

### 10.2 Override TTS default
```bash
TTS_DEFAULT_MODEL=pyttsx3 vocal serve
```

### 10.3 Point to external OpenAI-compatible LLM
```bash
LLM_BASE_URL=https://api.openai.com/v1 LLM_API_KEY=sk-... vocal serve
# Then test realtime — LLM replies come from OpenAI
```

### 10.4 Log level control
```bash
LOG_LEVEL=DEBUG vocal serve
```
Expected: detailed request/model/adapter logs in stderr.

### 10.5 `.env` file
```
# Create .env in project root:
STT_DEFAULT_MODEL=Systran/faster-whisper-tiny
TTS_DEFAULT_MODEL=pyttsx3
LOG_LEVEL=INFO
```
```bash
vocal serve  # picks up .env automatically
```

---

## 11. SDK

### 11.1 Basic SDK usage
```python
from vocal_sdk import Client

client = Client(base_url="http://localhost:8000")

# List models
from vocal_sdk.api.models import list_models_v1_models_get
result = list_models_v1_models_get.sync(client=client)
print(result)
```

### 11.2 TTS via SDK
```python
from vocal_sdk.api.audio import text_to_speech_v1_audio_speech_post
from vocal_sdk.models import TTSRequest

req = TTSRequest(input="Hello from the SDK.", model="pyttsx3")
resp = text_to_speech_v1_audio_speech_post.sync(client=client, body=req)
with open("sdk_out.wav", "wb") as f:
    f.write(resp.content)
```

### 11.3 Voice clone via SDK
```python
from vocal_sdk.api.audio import voice_clone_v1_audio_clone_post
from vocal_sdk.models import BodyVoiceCloneV1AudioClonePost
import httpx

body = BodyVoiceCloneV1AudioClonePost(
    text="Hello from cloned voice.",
    reference_audio=open("speaker.wav", "rb"),
)
resp = voice_clone_v1_audio_clone_post.sync(client=client, body=body)
```

---

## 12. Automated Test Tiers (reference)

| Command | What runs | When to use |
|---------|-----------|-------------|
| `make test-unit` | 33 unit tests, no server | Always — after any change |
| `make test-contract` | 31 contract tests, lightweight server | After API changes |
| `make test` | 56 E2E tests with real models | Full local validation |
| `make lint` | ruff check + format | Before committing |

Run only the domain you changed:
```bash
uv run pytest tests/unit/test_config.py -v            # config changes
uv run pytest tests/unit/test_registry_models.py -v   # model/capability changes
uv run pytest tests/contract/test_tts_contract.py -v  # TTS API changes
uv run pytest tests/contract/test_transcription_contract.py -v  # STT API changes
uv run pytest tests/test_e2e.py::TestTextToSpeech -v  # TTS E2E
uv run pytest tests/test_e2e.py::TestSTT -v           # STT E2E
uv run pytest tests/test_e2e.py::TestRealtimeOAI -v   # Realtime E2E
```
