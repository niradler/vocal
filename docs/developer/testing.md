# Testing

Vocal uses three test tiers. **E2E is the primary confidence path** for local development. Unit and contract tests gate CI (since heavy models can't run in GitHub Actions).

## Test Tiers

| Tier | Command | Time | What runs | Server? | Models? |
|------|---------|------|-----------|---------|---------|
| Unit | `make test-unit` | ~3 s | Config, registry, adapters, utils | No | No |
| Contract | `make test-contract` | ~10 s | REST API shape, validation, errors | Isolated (pyttsx3) | No |
| E2E | `make test` | ~45 s | Full user journeys with real speech | Running at :8000 | Yes |
| Format | `make format` | ~5 s | Auto-fix code style | No | No |
| Lint | `make lint` | ~5 s | Ruff check | No | No |

## Running Tests

```bash
# All tiers
make lint && make test-unit && make test-contract && make test

# Just unit tests (fastest feedback loop)
make test-unit

# Contract tests (need no real models)
make test-contract

# E2E (requires running server + downloaded models)
make serve &        # start server first
make test

# Specific test
uv run pytest tests/test_e2e.py::TestSTT::test_transcribe_english -vv -s
uv run pytest tests/unit/test_config.py -v
uv run pytest tests/contract/test_tts_contract.py::TestTTSSpeech -v
```

## E2E Tests

E2E tests require:
1. A running API server on port 8000 (`make serve`)
2. At least `Systran/faster-whisper-tiny` downloaded

```bash
# Start server (if not already running)
make serve &
sleep 5

# Run full E2E
make test
```

The server URL can be overridden:
```bash
API_BASE_URL=http://localhost:9000 uv run pytest tests/test_e2e.py -v
```

### Test coverage (56 tests total)

| Domain | File / Class | Tests |
|--------|-------------|-------|
| Health | `TestAPIHealth` | 2 |
| Models | `TestModelManagement` | 5 |
| STT | `TestSTT` | 7 |
| TTS | `TestTextToSpeech` | 5 |
| TTS formats | `test_tts_formats.py` | 6 |
| Streaming ASR | `TestStreamingASR` | 7 |
| OAI Realtime | `TestRealtimeOAI` | 7 |
| Error handling | various | 4 |
| Performance | `TestPerformance` | 1 |

## Contract Tests

Contract tests verify the API's public interface (status codes, response shapes, validation) without requiring real STT/TTS models. They start an isolated uvicorn instance per test session on a random free port.

```bash
make test-contract

# Or directly
uv run pytest tests/contract/ -v
```

**Linux prerequisite:** `pyttsx3` needs `espeak-ng`:
```bash
sudo apt install espeak-ng ffmpeg
```

The GitHub Actions CI workflow handles this automatically.

## Unit Tests

Unit tests cover core logic without any network or file I/O. Fast, deterministic, always green.

```bash
make test-unit

# Run specific file
uv run pytest tests/unit/test_config.py -v
uv run pytest tests/unit/test_registry_models.py -v
uv run pytest tests/unit/test_logging.py -v
uv run pytest tests/unit/test_tts_capabilities.py -v
```

## CI (GitHub Actions)

The CI workflow (`.github/workflows/ci.yml`) runs on every PR to `main`/`master`:

1. **Lint** — `ruff check` + `ruff format --check`
2. **Unit tests** — `pytest tests/unit/`
3. **Contract tests** — installs `espeak-ng` + `ffmpeg`, starts isolated API, runs `pytest tests/contract/`

E2E tests are **not** run in CI (require real model downloads, GPU access). They run locally before opening a PR.

## Pre-commit Hooks

Install once:
```bash
uvx pre-commit install            # runs on commit
uvx pre-commit install --hook-type pre-push  # runs on push
```

Hooks:
- **commit**: ruff lint + format (auto-fix)
- **push**: unit tests

Config: `.pre-commit-config.yaml`

## Cross-Platform Testing

Before a release, run all tiers on:

**Windows:**
```bash
make lint
make test-unit
make test-contract   # server auto-starts
make test            # start server first: make serve &
```

**WSL / Linux:**
```bash
# Install system deps (once)
sudo apt install espeak-ng ffmpeg

# Use Linux-native venv to avoid Windows/Linux venv conflicts
UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv_linux uv run pytest tests/unit/ -q
UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv_linux uv run pytest tests/contract/ -q

# Symlink Windows model cache so models don't need re-downloading
mkdir -p ~/.cache/vocal
ln -sfn /mnt/c/Users/<username>/.cache/vocal/models ~/.cache/vocal/models

# E2E against a WSL-internal server
UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv_linux uv run uvicorn vocal_api.main:app --port 8001 &
sleep 8
API_BASE_URL=http://127.0.0.1:8001 UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv_linux \
  uv run pytest tests/test_e2e.py tests/test_tts_formats.py -q
```

**macOS:** Same as Linux but without the WSL path tricks; models path is `~/.cache/vocal/models/`.

## Writing New Tests

### Unit test

```python
# tests/unit/test_my_feature.py
def test_my_setting_default():
    from vocal_core.config import VocalSettings
    s = VocalSettings()
    assert s.MY_SETTING == "expected_default"
```

### Contract test

```python
# tests/contract/test_my_endpoint.py
def test_my_endpoint_returns_200(client):
    from vocal_sdk.api.my_module import my_endpoint
    result = my_endpoint.sync(client=client)
    assert result is not None
```

The `client` fixture is in `tests/contract/conftest.py` — it provides an SDK client pointed at the isolated test server.

### E2E test

```python
# tests/test_e2e.py — add to existing class or new class
class TestMyFeature:
    def test_my_flow(self, client, api_base):
        import requests
        resp = requests.post(f"{api_base}/v1/audio/transcriptions", ...)
        assert resp.status_code == 200
```

See [manual-testing.md](../manual-testing.md) for the human-readable test guide organized by domain.
