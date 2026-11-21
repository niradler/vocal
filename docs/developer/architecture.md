# Architecture

## Overview

Vocal follows an **API-first, adapter-driven** design. The core principle: everything flows through the model registry and service layer — no component bypasses the abstraction.

```
CLI → SDK → API → Core
              └── ModelRegistry
              └── TranscriptionService → STTAdapter (FasterWhisper | Transformers)
              └── TTSService          → TTSAdapter  (pyttsx3 | Kokoro | Piper | Qwen3)
```

**Dependency flow** (strict, no cycles):

```
core ← api ← sdk ← cli
```

Each package is independently installable from PyPI (`vocal-core`, `vocal-api`, `vocal-sdk`, `vocal-cli`, `vocal-ai` meta-package).

## Packages

### `vocal-core` — The Foundation

No web framework dependencies. Contains:

- **`vocal_core/config.py`** — `VocalSettings` (all defaults, env var overrides)
- **`vocal_core/logging.py`** — `setup_logging`, `get_logger`
- **`vocal_core/registry/`** — `ModelRegistry`, `ModelInfo`, `ModelBackend` enum, `capabilities.py`
- **`vocal_core/adapters/stt/`** — STT adapter interfaces and implementations
- **`vocal_core/adapters/tts/`** — TTS adapter interfaces and implementations

**Global config rule:** All default values (model names, sample rates, URLs, timeouts) live in `VocalSettings`. Never hardcode them anywhere else.

### `vocal-api` — The Server

FastAPI application. Routes → Services → Adapters (via core).

- **`vocal_api/routes/`** — HTTP and WebSocket route handlers
- **`vocal_api/services/`** — `TranscriptionService`, `TTSService` — adapter lifecycle
- **`vocal_api/dependencies.py`** — FastAPI dependency injection for services
- **`vocal_api/config.py`** — API-specific settings (port, version, upload limits)

Services are singletons via FastAPI `Depends`. Adapters are cached per model — loading a model is expensive, repeated calls reuse the same instance.

### `vocal-sdk` — Auto-generated Client

Generated from the live OpenAPI spec using `openapi-python-client`. **Do not manually edit** files under `vocal_sdk/api/` or `vocal_sdk/models/` — they are regenerated on each SDK rebuild.

To regenerate after API changes:
```bash
make serve &           # start the API
make generate-sdk      # regenerate from /openapi.json
```

### `vocal-cli` — The CLI

Typer application that calls the SDK. The CLI is a pure SDK consumer — it does not import from `vocal_api` or `vocal_core` directly except for `vocal_settings` (for defaults).

## Adapter Pattern

Every STT and TTS backend implements a base interface:

```python
# STT
class STTAdapter:
    async def load_model(self, model_path: Path, **kwargs) -> None: ...
    async def transcribe(self, audio, language, task, **kwargs) -> TranscriptionResult: ...
    async def transcribe_stream(self, audio_queue) -> AsyncIterator[TranscriptionSegment]: ...
    async def unload_model(self) -> None: ...

# TTS
class TTSAdapter:
    async def load_model(self, model_path: Path | str, **kwargs) -> None: ...
    async def synthesize(self, text, voice, speed, format, **kwargs) -> TTSResult: ...
    async def synthesize_stream(self, text, voice, **kwargs) -> AsyncIterator[bytes]: ...
    async def get_voices(self) -> list[VoiceInfo]: ...
    async def unload_model(self) -> None: ...
```

Service dispatch selects the adapter based on `ModelInfo.backend`:

```python
# In TranscriptionService._create_adapter()
match model.backend:
    case ModelBackend.CTRANSLATE2:
        return FasterWhisperAdapter()
    case ModelBackend.TRANSFORMERS:
        return TransformersSTTAdapter()
```

Adding a new backend: implement the base class, add a `ModelBackend` enum value, add a case to the service dispatch. See [adding-models.md](adding-models.md).

## Model Registry

`ModelRegistry` manages:
- **Discovery** — reads `supported_models.json` (catalog) + local downloaded models
- **Download** — delegates to `HuggingFaceProvider` (streams from HF Hub)
- **Metadata** — `ModelMetadataCache` (JSON files per model in `~/.cache/vocal/metadata/`)
- **Capabilities** — `capabilities.py` infers `supports_streaming`, `supports_voice_list`, etc. from model metadata

Model storage path: `~/.cache/vocal/models/<org>--<model>/`

## Capability System

`ModelInfo` carries capability flags set by `infer_model_capabilities()` in `registry/capabilities.py`:

| Flag | Meaning |
|------|---------|
| `supports_streaming` | Adapter yields audio incrementally |
| `supports_voice_list` | `get_voices()` returns a non-empty list |
| `supports_voice_clone` | `clone_synthesize()` is implemented |
| `requires_gpu` | Model cannot run usefully on CPU |

Routes and services check these flags to return clean 422 errors before attempting an unsupported operation.

## OpenAI Compatibility

Vocal maintains OpenAI API compatibility on:
- `POST /v1/audio/transcriptions` — same request shape (`language`, `prompt`, `temperature`, `response_format`, `timestamp_granularities[]`) and JSON / plain-text / SRT / VTT output
- `POST /v1/audio/speech` — same request shape, same audio response (`voice`, `language`, `speed`, `response_format`, `stream`)
- `POST /v1/audio/translations` — translate to English with the selected model (`language`, `prompt`, `temperature`, `response_format`)
- `GET /v1/models` — compatible listing format
- `WS /v1/realtime` — full OpenAI Realtime Transcription Session protocol, including nested `audio.input.transcription.language` and `audio.output.voice` session config

Extensions beyond OpenAI (Vocal-specific):
- `GET /v1/audio/voices` — voice listing per model
- `POST /v1/audio/clone` — voice cloning from reference audio
- `WS /v1/audio/stream` — lightweight binary PCM streaming
- `GET /v1/system/device` — hardware info
- Model download/delete endpoints

## WebSocket Architecture

### `/v1/audio/stream` (simple streaming ASR)

```
Client: binary PCM16 @16kHz frames
  → Server VAD (numpy RMS)
  → Buffer until silence
  → STT adapter
  → {"type":"transcript.delta","text":"..."} events
```

### `/v1/realtime` (OpenAI Realtime)

```
Client: base64 PCM16 @24kHz (OAI format)
  → Resample to 16kHz (numpy linear)
  → Server VAD
  → faster-whisper STT
  → [realtime mode] LLM (streaming via httpx)
  → [realtime mode] TTS (batch → chunked WebSocket frames)
```

## Logging Convention

All modules use stdlib `logging` via `vocal_core.logging`:

```python
import logging
logger = logging.getLogger(__name__)
```

`setup_logging()` is called once at API startup. Level is controlled by `LOG_LEVEL` env var. Never use `print()`.

## Testing Architecture

See [testing.md](testing.md) for the full breakdown. Short version:

| Tier | Location | Dependencies |
|------|----------|-------------|
| Unit | `tests/unit/` | None (pure Python) |
| Contract | `tests/contract/` | Isolated uvicorn, pyttsx3 |
| E2E | `tests/test_e2e.py` | Real models, running server |
