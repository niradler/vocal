# Adding Models and Backends

This guide covers both adding a new model to the existing registry (catalog-only change) and adding a completely new backend (code change).

## Option A: Add a Model to the Catalog

If the model uses an **existing backend** (e.g. another HuggingFace Whisper variant), you only need to edit the registry JSON.

**File:** `packages/core/vocal_core/registry/supported_models.json`

```json
{
  "Systran/faster-whisper-large-v3-turbo": {
    "name": "Faster Whisper Large v3 Turbo",
    "description": "Distilled large-v3, similar quality at 8× speed",
    "parameters": "809M",
    "size": "1600000000",
    "backend": "ctranslate2",
    "task": "stt",
    "recommended_vram": "6GB+",
    "languages": ["multilingual"],
    "license": "MIT",
    "author": "Systran"
  }
}
```

Valid `backend` values: `ctranslate2`, `transformers`, `piper`, `kokoro`, `qwen3-tts`, `simple`

After adding, verify:
```bash
make serve &
curl "http://localhost:8000/v1/models?task=stt" | python -m json.tool | grep "large-v3-turbo"
```

## Option B: Add a New STT Backend

### 1. Implement the adapter

Create `packages/core/vocal_core/adapters/stt/<your_backend>.py`:

```python
import logging
from pathlib import Path
from typing import Any, BinaryIO, AsyncIterator

from .base import STTAdapter, TranscriptionResult, TranscriptionSegment

logger = logging.getLogger(__name__)


class MySTTAdapter(STTAdapter):
    def __init__(self) -> None:
        self.model = None
        self.model_path: Path | None = None

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        # Load your model here
        logger.info("Loading MySTT from %s on %s", model_path, device)
        self.model = ...   # your model load
        self.model_path = model_path

    async def unload_model(self) -> None:
        self.model = None

    def is_loaded(self) -> bool:
        return self.model is not None

    async def transcribe(
        self,
        audio: str | Path | BinaryIO,
        language: str | None = None,
        task: str = "transcribe",
        **kwargs,
    ) -> TranscriptionResult:
        # Run inference, return TranscriptionResult
        text = self.model.transcribe(str(audio), language=language)
        return TranscriptionResult(
            text=text,
            language=language or "unknown",
            duration=0.0,
        )

    # Optional — streaming support
    async def transcribe_stream(self, audio_queue) -> AsyncIterator[TranscriptionSegment]:
        raise NotImplementedError
```

### 2. Register the adapter in the STT adapters `__init__.py`

`packages/core/vocal_core/adapters/stt/__init__.py`:
```python
from .my_backend import MySTTAdapter

__all__ = [..., "MySTTAdapter"]
```

### 3. Add a `ModelBackend` enum value

`packages/core/vocal_core/registry/model_info.py`:
```python
class ModelBackend(str, Enum):
    ...
    MY_BACKEND = "my_backend"
```

### 4. Add dispatch in `TranscriptionService`

`packages/api/vocal_api/services/transcription_service.py`:
```python
from vocal_core.adapters.stt import MySTTAdapter

def _create_adapter(self, model: ModelInfo) -> STTAdapter:
    match model.backend:
        case ModelBackend.CTRANSLATE2:
            return FasterWhisperAdapter()
        case ModelBackend.TRANSFORMERS:
            return TransformersSTTAdapter()
        case ModelBackend.MY_BACKEND:         # ← add this
            return MySTTAdapter()
        case _:
            raise ValueError(f"Unsupported STT backend: {model.backend}")
```

### 5. Add capabilities

`packages/core/vocal_core/registry/capabilities.py` — add inference logic for your backend if needed (streaming support, GPU requirement, etc.).

### 6. Add the model to the catalog

See Option A above — use `"backend": "my_backend"` in `supported_models.json`.

## Option C: Add a New TTS Backend

Same pattern as STT. Key files:

1. `packages/core/vocal_core/adapters/tts/<your_backend>.py` — implement `TTSAdapter`
2. `packages/core/vocal_core/adapters/tts/__init__.py` — export it
3. `packages/core/vocal_core/registry/model_info.py` — add `ModelBackend` value
4. `packages/api/vocal_api/services/tts_service.py` — add to `_create_adapter` dispatch
5. `packages/core/vocal_core/registry/supported_models.json` — add model entry
6. `packages/core/vocal_core/registry/capabilities.py` — declare capabilities

**TTS adapter interface:**
```python
class TTSAdapter:
    async def load_model(self, model_path: Path | str, **kwargs) -> None: ...
    async def unload_model(self) -> None: ...
    def is_loaded(self) -> bool: ...
    async def synthesize(self, text: str, voice: str | None, speed: float, **kwargs) -> TTSResult: ...
    async def synthesize_stream(self, text: str, voice: str | None, **kwargs) -> AsyncIterator[bytes]: ...
    async def get_voices(self) -> list[VoiceInfo]: ...
    async def clone_synthesize(self, text: str, reference_audio: Path, **kwargs) -> TTSResult: ...
```

Implement only what the backend supports. Return `NotImplementedError` for unsupported operations and declare capabilities accordingly.

## Optional Backend Install Extras

If your backend has heavy dependencies (e.g. `torch`, model-specific packages), make them optional:

**Root `pyproject.toml`:**
```toml
[project.optional-dependencies]
my-backend = [
    "my-package>=1.0.0",
]
```

**`packages/core/pyproject.toml`:** same entry.

Use `importlib.util.find_spec` for availability checks — never import at module top level:
```python
MY_BACKEND_AVAILABLE = importlib.util.find_spec("my_package") is not None
```

Use `optional_dependency_install_hint("my-backend", "my-package")` from `vocal_core.config` to print a helpful error message when the package is missing.

## Cross-Platform Notes

- Use `asyncio.get_running_loop()` (not `get_event_loop()`) — consistent on all platforms
- Use `Path` for all file paths — handles Windows/Linux separators
- Avoid `shell=True` in `subprocess` calls — use argument lists
- If your model needs a temp file: use `tempfile.NamedTemporaryFile(delete=False)` and clean up in `try/finally`
- Test on both Windows and Linux if your adapter touches audio processing or subprocess calls

## Validation Checklist

After adding a new backend:
- [ ] `make lint` passes
- [ ] `make test-unit` passes
- [ ] Add a contract test in `tests/contract/` for the new model/backend
- [ ] `make test-contract` passes
- [ ] Manual smoke test: `curl http://localhost:8000/v1/models/<your-model-id>` shows correct capabilities
- [ ] If GPU-only: document `requires_gpu: true` in capabilities and model JSON
