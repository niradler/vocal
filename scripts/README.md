# Scripts

Utility scripts for Vocal development and testing.

## Available Scripts

### `validate.py` - Quick System Validation
Fast 7-step validation of all API functionality.

```bash
uv run python scripts/validate.py
```

**Tests:** API health, models, STT, TTS, voices, error handling  
**Duration:** ~10-30 seconds  
**Purpose:** Quick smoke test

### `run_tests.py` - Full E2E Test Suite
Runs comprehensive integration tests.

```bash
uv run python scripts/run_tests.py
```

**Tests:** 24 E2E integration tests  
**Duration:** ~1-3 minutes (with GPU)  
**Purpose:** Full validation

## Usage

All scripts run from project root:

```bash
# Quick check
uv run python scripts/validate.py

# Full test suite
uv run python scripts/run_tests.py
```

## Requirements

- API server running: `uv run vocal serve`
- Tiny model downloaded: `uv run vocal models pull Systran/faster-whisper-tiny`
- GPU support: PyTorch with CUDA (`torch==2.6.0+cu124` or later)
