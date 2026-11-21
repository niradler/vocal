# AGENTS.md — Vocal Maintainer & Contributor Reference

**Version:** 0.4.1 | **Python:** 3.11+ | **License:** SSPL-1.0

> This file is the canonical reference for maintainers, contributors, and AI coding agents. Keep it accurate and concise. User documentation lives in [`docs/`](docs/README.md).

---

## What is Vocal?

Vocal is an **Ollama-style platform for voice models** — a self-hosted Speech AI API that manages STT (Speech-to-Text) and TTS (Text-to-Speech) models the way Ollama manages LLMs. It provides:

- OpenAI-compatible endpoints (`/v1/audio/transcriptions`, `/v1/audio/speech`, `/v1/realtime`)
- Model registry with download/list/delete (Ollama-style pull)
- Auto-generated Python SDK from the live OpenAPI spec
- WebSocket streaming ASR and a full voice-agent loop
- Voice listing and voice cloning APIs

**Architecture:** FastAPI generates OpenAPI schema → SDK auto-generates from schema → CLI uses SDK.

**Dependency flow (strict, no cycles):**

```
core ← api ← sdk ← cli
```

---

## Essential Commands

```bash
make install              # Setup workspace (uv workspace, all packages editable)
make install-dev          # Install ALL optional backends (kokoro, qwen3-tts, nemo, whisperx, chatterbox, supertonic, voxcpm, phonon, qwen3-omni)
make lint                 # Must pass before any commit
make test                 # Full E2E suite (~98 tests, ~2.5min, needs server + models)
make test-unit            # Unit tests, no server (~25s)
make test-contract        # Contract tests, isolated server (~10s)
make format               # Auto-fix code style
make serve                # Start API at http://localhost:8000
make serve-dev            # Start with auto-reload (dev)
```

**Before completing any task:** `make lint && make test-unit && make test`

> **Full test coverage requires optional backends.** Run `make install-dev` once after `make install` to install all optional backends. Without this, tests for the optional backends (Kokoro, NeMo, WhisperX, qwen3-tts, Chatterbox, Supertonic, VoxCPM, Phonon, Qwen-Omni) are skipped — and skips count as failures. Gated models (e.g. Cohere Transcribe) also need their HF licence accepted, or their E2E test skips.

---

## Project Structure

```
vocal/
├── packages/
│   ├── core/                          # No API deps — foundation
│   │   └── vocal_core/
│   │       ├── config.py              # VocalSettings — ALL defaults live here
│   │       ├── logging.py             # setup_logging, get_logger
│   │       ├── registry/              # ModelRegistry, ModelInfo, capabilities
│   │       └── adapters/
│   │           ├── stt/               # FasterWhisperAdapter, TransformersSTTAdapter
│   │           └── tts/               # SimpleTTSAdapter (pyttsx3), KokoroTTSAdapter, PiperTTSAdapter
│   ├── api/                           # FastAPI server
│   │   └── vocal_api/
│   │       ├── routes/                # tts.py, transcription.py, stream.py, realtime.py
│   │       ├── services/              # TranscriptionService, TTSService
│   │       ├── dependencies.py        # FastAPI DI
│   │       └── config.py             # API-specific settings
│   ├── sdk/                           # Auto-generated — do not edit api/ or models/ directly
│   └── cli/                           # Typer CLI — pure SDK consumer
│       └── vocal_cli/main.py
├── tests/
│   ├── unit/                          # No server, no models
│   ├── contract/                      # Isolated server, pyttsx3 only
│   │   └── conftest.py               # api_server + client fixtures
│   ├── test_e2e.py                    # Full journeys (primary local gate)
│   ├── test_tts_formats.py
│   └── test_assets/audio/            # Real audio fixtures
├── docs/
│   ├── README.md                      # Docs index
│   ├── user/                          # End-user documentation
│   └── developer/                     # Contributor + maintainer documentation
├── .github/workflows/ci.yml           # GitHub Actions: lint + unit + contract
├── .pre-commit-config.yaml            # Pre-commit hooks
└── Makefile
```

---

## Architecture Rules

### Global Config

All default values (model names, URLs, sample rates, timeouts) live in **`vocal_core/config.py`** (`VocalSettings`). Never hardcode them in routes, services, or CLI — always use `vocal_settings.*`.

```python
from vocal_core.config import vocal_settings
model = vocal_settings.STT_DEFAULT_MODEL   # ✅
model = "Systran/faster-whisper-tiny"       # ❌
```

### Logging

All modules use stdlib `logging` — never `print()`:

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Loading model from %s", path)
```

`setup_logging()` is called once at API startup from `vocal_core.logging`.

### Async / Concurrency

- Use `asyncio.get_running_loop()` — not `get_event_loop()` (deprecated, inconsistent on Windows vs Linux)
- CPU-bound model inference: `await loop.run_in_executor(None, self._load_sync, ...)`
- Never call `pyttsx3` from the event loop directly — run in a thread with a timeout

### File Paths

Use `pathlib.Path` everywhere — handles Windows/Linux separators automatically.

### Adapter Pattern

Every STT/TTS backend implements a base class in `adapters/stt/base.py` or `adapters/tts/base.py`. Services dispatch by `ModelInfo.backend`. New backends = implement base class + add to service dispatch. See [`docs/developer/adding-models.md`](docs/developer/adding-models.md).

### Model Catalog Invariants

`supported_models.json` is the product's claim about what Vocal supports. Keep it honest:

- Every entry declares `license` (SPDX id when one exists, otherwise the upstream license id), `commercial_use` (bool) and `maintenance_status` (`active`/`retired`/`deprecated`).
- `runtime` is `in_process` only when an adapter can actually run the model. Models that need vLLM-Omni, SGLang-Omni or a vendored runtime must use `"runtime": "external"` plus a `runtime_note`, and the services reject them with an actionable error via `assert_in_process_runtime()`.
- Do not add a catalog entry without an adapter — `tests/unit/test_catalog_coverage.py` fails on any `in_process` entry whose backend has no implementation.
- Refresh HF-derived facts (size, params, languages, downloads) with `make generate-supported-models`; it preserves curated fields.

### Dependency Locking

`uv.lock` is committed. CI runs `uv sync --locked`, so any dependency change must ship a regenerated lock.

- PyTorch comes from the `pytorch` index (`cu132`), and **torch, torchaudio and torchvision must stay on mutually compatible versions** — a torchvision built for an older torch breaks `transformers` at import with `operator torchvision::nms does not exist`.
- `chatterbox-tts` pins `safetensors==0.5.3`, so `safetensors` is force-upgraded through `[tool.uv] override-dependencies`.
- `faster-whisper` calls `av.open(metadata_errors=...)`, which PyAV 19 removed — `av` is pinned to `<19` in the overrides.
- `openapi-python-client` 0.30 emits `httpx2` imports; the SDK stays on 0.29.x so generated code and the hand-written client share `httpx`.
- `transformers` is pinned to `>=5.22,<5.23`: 5.23 registers native `qwen3_tts` configs that break `faster-qwen3-tts`, and validates sub-config token ids in a way the qwen3-tts talker config cannot satisfy. See `docs/deps.md`.
- `torchaudio` decoding needs `torchcodec` + FFmpeg shared DLLs; adapters decode with `soundfile` (falling back to `ffmpeg`) instead, so a broken torchcodec never reaches inference. All four torch packages (torch, torchaudio, torchvision, torchcodec) resolve from the `pytorch` cu132 index.

---

## Test Tiers

| Tier     | Command              | Time | Runs in CI        |
| -------- | -------------------- | ---- | ----------------- |
| Unit     | `make test-unit`     | ~25s   | ✅                |
| Contract | `make test-contract` | ~10s   | ✅                |
| E2E      | `make test`          | ~2.5min | ❌ (needs models) |
| Format   | `make format`        | ~5s  | ✅                |
| Lint     | `make lint`          | ~5s  | ✅                |

### Validation Rule — Non-Negotiable

**All 3 test suites must pass with zero skips before any task is considered complete.**

Prerequisites for zero-skip E2E runs:
1. `make install-dev` — installs all optional backends (kokoro, qwen3-tts, nemo, whisperx, chatterbox, supertonic, voxcpm, phonon, qwen3-omni)
2. Server running with all backends loaded (fresh start after `install-dev`)
3. GPU available (some backends require CUDA)

```bash
uv run python -m pytest tests/unit/ tests/contract/ tests/test_e2e.py tests/test_tts_formats.py -q
# Required: X passed, 0 failed, 0 skipped
```

- **Skipped = failure.** A skip means a test was bypassed — find out why and fix it or flag it explicitly to the user.
- **E2E tests are real user flows** — real models, real audio, real HTTP, no mocking. If it doesn't work like an actual user would use it, the test is not valid.
- **E2E tests reuse a running server** at `http://localhost:8000` if one exists; otherwise they start their own. Always restart the server after `make install-dev` to ensure all backends are available.
- **No disabling tests or patching around broken behavior.** If something is broken, fix it. Don't paper over it.

A result of "X passed, Y skipped" is **not** a passing validation. Only "X passed, 0 skipped, 0 failed" counts.

Targeted test runs:

```bash
uv run pytest tests/unit/test_config.py -v
uv run pytest tests/contract/test_tts_contract.py -v
uv run pytest tests/test_e2e.py::TestSTT -v
uv run pytest tests/test_e2e.py::TestClass::test_name -vv -s
```

---

## Cross-Platform Development

### Windows

```bash
make install && make install-dev   # base + all optional backends
make lint && make test-unit && make test-contract
make serve &
make test
```

Port conflicts:

```bash
netstat -ano | findstr :8000
taskkill /F /PID <PID>
```

### WSL / Linux

```bash
# System dependencies (pyttsx3 backend on Linux)
sudo apt install espeak-ng ffmpeg

# Use Linux-native venv (avoids Windows venv I/O errors)
UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv uv run pytest tests/unit/ -q

# Share Windows model cache (avoid re-downloading)
mkdir -p ~/.cache/vocal
ln -sfn /mnt/c/Users/<username>/.cache/vocal/models ~/.cache/vocal/models

# Start server and run E2E
UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv uv run uvicorn vocal_api.main:app --port 8001 &
sleep 8
API_BASE_URL=http://127.0.0.1:8001 UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv \
  uv run pytest tests/test_e2e.py tests/test_tts_formats.py -q
```

### macOS

Same as Linux but `espeak-ng` is not needed (uses NSSpeechSynthesizer). `brew install ffmpeg` for format conversion.

---

## Adding a New Model or Backend

**Catalog-only (new model, existing backend):** Edit `packages/core/vocal_core/registry/supported_models.json`.

**New backend:** See [`docs/developer/adding-models.md`](docs/developer/adding-models.md) for the full step-by-step including checklist.

Quick summary for new TTS backend:

1. Implement `TTSAdapter` in `packages/core/vocal_core/adapters/tts/<name>.py`
2. Add `ModelBackend.<NAME>` to `vocal_core/registry/model_info.py`
3. Add dispatch case to `packages/api/vocal_api/services/tts_service.py`
4. Declare capabilities in `vocal_core/registry/capabilities.py`
5. Add model entry to `supported_models.json`
6. Add contract test in `tests/contract/`

---

## SDK Regeneration

The SDK is auto-generated — never manually edit `vocal_sdk/api/` or `vocal_sdk/models/`:

```bash
make serve &                  # start API
sleep 5
make generate-sdk             # regenerate from /openapi.json
make lint                     # ensure generated code is clean
```

Regenerate after any API route change, new endpoint, or model schema change.

---

## Release Process

See [`docs/developer/release.md`](docs/developer/release.md) for the full checklist.

Quick version bump:

```bash
make bump-patch    # 0.4.1 → 0.4.2
make bump-minor    # 0.4.1 → 0.5.0
make bump-major    # 0.4.1 → 1.0.0
```

Auto-updates: all `pyproject.toml` + `__init__.py` files.

---

## Common Gotchas

| Problem | Fix |
|---------|-----|
| `pyttsx3` deadlock on Windows | `SimpleTTSAdapter` creates a fresh engine per call in a thread — do not share engine across calls |
| WSL venv I/O error | Use `UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv` to avoid Windows-style `.venv/Scripts/` |
| Port 8000 in use | `netstat -ano \| findstr :8000` then `taskkill /F /PID <pid>` |
| Model not found | Check `~/.cache/vocal/models/` — download with `vocal models pull <id>` |
| SDK out of date | Run `make generate-sdk` after any API route change |
| `asyncio.get_event_loop()` warning | Use `asyncio.get_running_loop()` instead — already fixed in `TransformersSTTAdapter` |
| `operator torchvision::nms does not exist` | torchvision is older than torch — add a matching `torchvision` on the pytorch index |
| `open() got an unexpected keyword argument 'metadata_errors'` | PyAV 19 dropped `metadata_errors`, which faster-whisper calls — the lock pins `av>=17,<19` |
| NeMo `PermissionError: manifest.json` on Windows | NeMo's lhotse tempdir cleanup races on Windows; the NeMo adapter passes a numpy array instead of a path |
| Model rejects with "external inference engine" | That catalog entry is `runtime: external` — serve it with the engine in `runtime_note` |

---

## DO / DON'T

**DO ✅**

- Run all 3 test suites before completing any task — unit + contract + e2e, zero skips
- Treat a skip the same as a failure — investigate and fix or flag it
- Use `vocal_settings.*` for all defaults — never hardcode strings
- Use `logging.getLogger(__name__)` — never `print()`
- Use `asyncio.get_running_loop()` in async code
- Use `pathlib.Path` for file paths (cross-platform)
- Test on both Windows and Linux for anything touching audio or subprocesses
- Regenerate SDK after API changes

**DON'T ❌**

- Import from `vocal_api` in `vocal_core` (breaks dependency order)
- Hardcode model names, URLs, or sample rates outside `config.py`
- Create circular dependencies between packages
- Use `get_event_loop()` (deprecated, platform-inconsistent)
- Edit `vocal_sdk/api/` or `vocal_sdk/models/` by hand
- Skip lint/tests before completing a task
- Count "X passed, Y skipped" as passing — skips are failures
- Mock in E2E tests — they must exercise real models, real audio, real HTTP
- Disable or patch around broken behavior to make tests pass — fix the root cause
- Create new markdown files unless explicitly asked

---

## References

| Resource               | Link                                                                 |
| ---------------------- | -------------------------------------------------------------------- |
| User docs              | [`docs/user/`](docs/user/)                                           |
| Developer docs         | [`docs/developer/`](docs/developer/)                                 |
| Architecture deep-dive | [`docs/developer/architecture.md`](docs/developer/architecture.md)   |
| Adding backends        | [`docs/developer/adding-models.md`](docs/developer/adding-models.md) |
| Test guide             | [`docs/developer/testing.md`](docs/developer/testing.md)             |
| Release process        | [`docs/developer/release.md`](docs/developer/release.md)             |
| Manual QA guide        | [`docs/manual-testing.md`](docs/manual-testing.md)                   |
| Interactive API docs   | http://localhost:8000/docs (when server running)                     |
| GitHub Issues          | https://github.com/niradler/vocal/issues                             |
