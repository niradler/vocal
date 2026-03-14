.PHONY: help install test test-unit test-contract test-ci test-quick test-wsl test-verbose lint format clean serve serve-wsl cli docs gpu-check bump-patch bump-minor bump-major generate-supported-models generate-sdk

# Default target
help:
	@echo "Vocal - Available Commands"
	@echo "============================"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install       - Install base + dev dependencies (no heavy optional backends)"
	@echo "  make install-dev   - Install ALL backends for full local testing (kokoro, qwen3-tts, nemo, whisperx, chatterbox)"
	@echo "  make sync          - Sync dependencies with uv"
	@echo ""
	@echo "Testing:"
	@echo "  make test          - Run full E2E test suite (~55 sec) [local primary gate]"
	@echo "  make test-unit     - Run unit tests only (~5 sec, no server needed)"
	@echo "  make test-contract - Run contract tests (starts API, uses pyttsx3)"
	@echo "  make test-ci       - Run CI gate: unit + contract tests (no heavy models)"
	@echo "  make test-quick    - Quick validation checks (~5 sec)"
	@echo "  make test-wsl      - Run E2E tests inside WSL (needs: make serve-wsl)"
	@echo "  make test-verbose  - Run tests with verbose output"
	@echo "  make gpu-check     - Check GPU detection and optimization"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          - Run linter (ruff check)"
	@echo "  make format        - Format code (ruff format)"
	@echo "  make check         - Run both lint and format check"
	@echo ""
	@echo "Development:"
	@echo "  make serve         - Start API server (port 8000)"
	@echo "  make serve-wsl     - Start API server inside WSL (port 8001)"
	@echo "  make cli           - Run CLI — ARGS=\"<cmd>\" [URL=http://...] (default: localhost:8000)"
	@echo "                       e.g. make cli ARGS=\"models list\" URL=http://127.0.0.1:8001"
	@echo "  make serve-dev     - Start API server with auto-reload"
	@echo "  make docs          - Open API documentation in browser"
	@echo "  make generate-sdk              - Regenerate SDK from OpenAPI spec (needs API running)"
	@echo "  make generate-supported-models - Regenerate supported models metadata"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         - Remove cache files and build artifacts"
	@echo "  make clean-models  - Remove downloaded models"
	@echo ""
	@echo "Version Management:"
	@echo "  make bump-patch    - Bump patch version (0.2.1 -> 0.2.2)"
	@echo "  make bump-minor    - Bump minor version (0.2.1 -> 0.3.0)"
	@echo "  make bump-major    - Bump major version (0.2.1 -> 1.0.0)"
	@echo ""

# Setup & Installation
install:
	@echo "Installing base + dev dependencies..."
	uv sync
	@echo ""
	@echo "✓ Installation complete!"
	@echo "Run 'make serve' to start the API server"
	@echo "Run 'make install-dev' to also install optional backends (kokoro, qwen3-tts, nemo, whisperx, chatterbox)"

install-dev:
	@echo "Installing ALL optional backends for full local testing..."
	uv sync --extra kokoro --extra qwen3-tts --extra nemo --extra whisperx --extra chatterbox
	@echo ""
	@echo "✓ Full dev environment ready"
	@echo "Run 'make test-unit' to verify"

sync:
	@echo "Syncing dependencies..."
	uv sync

# Testing
test:
	@echo "Running full E2E test suite (local primary gate)..."
	@echo ""
	uv run python -m pytest tests/test_e2e.py tests/test_tts_formats.py -v --tb=short

test-unit:
	@echo "Running unit tests (no server or models needed)..."
	@echo ""
	uv run python -m pytest tests/unit/ -v --tb=short

test-contract:
	@echo "Running contract tests (starts API, uses pyttsx3 only)..."
	@echo ""
	uv run python -m pytest tests/contract/ -v --tb=short

test-ci:
	@echo "Running CI gate: unit + contract tests..."
	@echo ""
	uv run python -m pytest tests/unit/ tests/contract/ -v --tb=short

test-quick:
	@echo "Running quick validation checks..."
	@echo ""
	uv run python scripts/validate.py

test-wsl:
	@echo "Running E2E tests inside WSL (separate venv at /tmp/vocal_venv)..."
	@echo ""
	wsl bash -ic "cd /mnt/c/Projects/vocal && UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv VOCAL_TEST_URL=http://127.0.0.1:8001 uv run python -m pytest tests/test_e2e.py tests/test_tts_formats.py -v --tb=short"

test-verbose:
	@echo "Running tests with verbose output..."
	@echo ""
	uv run python -m pytest tests/test_e2e.py -vv -s --tb=long

gpu-check:
	@echo "Checking GPU detection and optimization..."
	@echo ""
	uv run python -c "from vocal_core.utils.device import get_device_info; import json; print(json.dumps(get_device_info(), indent=2))"

# Code Quality
lint:
	@echo "Running linter..."
	uv run ruff check .

format:
	@echo "Formatting code..."
	uv run ruff format .

check: lint
	@echo "Checking code format..."
	uv run ruff format --check . --fix

# Development
serve:
	@echo "Starting API server on http://localhost:8000"
	@echo "Documentation: http://localhost:8000/docs"
	@echo ""
	uv run uvicorn vocal_api.main:app --host 0.0.0.0 --port 8000

serve-wsl:
	@echo "Starting API server inside WSL on http://127.0.0.1:8001"
	@echo "Documentation: http://127.0.0.1:8001/docs"
	@echo ""
	wsl bash -ic "cd /mnt/c/Projects/vocal && UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv uv run uvicorn vocal_api.main:app --host 127.0.0.1 --port 8001"

cli:
	@echo "Running vocal CLI — Usage: make cli ARGS=\"models list\" [URL=http://localhost:8000]"
	@echo ""
	VOCAL_API_URL=$(or $(URL),http://localhost:8000) uv run vocal $(ARGS)

serve-dev:
	@echo "Starting API server with auto-reload..."
	@echo "Documentation: http://localhost:8000/docs"
	@echo ""
	uv run uvicorn vocal_api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir packages

docs:
	@echo "Opening API documentation..."
	@powershell -Command "Start-Process 'http://localhost:8000/docs'"

generate-sdk:
	@echo "Generating SDK from OpenAPI spec (API must be running: make serve)..."
	@echo ""
	uv run python packages/sdk/scripts/generate.py
	@echo ""
	@echo "Note: Commit the regenerated vocal_sdk/ to version control"

generate-supported-models:
	@echo "Regenerating supported models metadata from HuggingFace..."
	@echo ""
	uv run python scripts/generate_supported_models.py --force
	@echo ""
	@echo "Note: Commit the updated supported_models.json to version control"

# Cleanup
clean:
	@echo "Cleaning cache files..."
	@powershell -Command "Get-ChildItem -Recurse -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
	@powershell -Command "Get-ChildItem -Recurse -Filter '*.pyc' | Remove-Item -Force -ErrorAction SilentlyContinue"
	@powershell -Command "Get-ChildItem -Recurse -Filter '*.pyo' | Remove-Item -Force -ErrorAction SilentlyContinue"
	@powershell -Command "Get-ChildItem -Recurse -Filter '.pytest_cache' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
	@powershell -Command "Get-ChildItem -Recurse -Filter '.ruff_cache' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
	@echo "✓ Cache cleaned"

clean-models:
	@echo "This will delete all downloaded models from ~/.cache/vocal/models/"
	@echo "Press Ctrl+C to cancel or Enter to continue..."
	@powershell -Command "$$null = Read-Host"
	@powershell -Command "Remove-Item -Recurse -Force '$$env:USERPROFILE\.cache\vocal\models' -ErrorAction SilentlyContinue"
	@echo "✓ Models cleaned"

# Version Management
bump-patch:
	@echo "Bumping patch version..."
	@uv run bump-my-version bump patch
	@echo "✓ Version bumped!"

bump-minor:
	@echo "Bumping minor version..."
	@uv run bump-my-version bump minor
	@echo "✓ Version bumped!"

bump-major:
	@echo "Bumping major version..."
	@uv run bump-my-version bump major
	@echo "✓ Version bumped!"

# Quick aliases
t: test
tu: test-unit
tc: test-contract
tci: test-ci
tq: test-quick
tw: test-wsl
tv: test-verbose
s: serve
sw: serve-wsl
sd: serve-dev
l: lint
f: format
c: clean
h: help
