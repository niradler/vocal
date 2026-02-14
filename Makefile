.PHONY: help install test test-quick test-verbose lint format clean serve cli docs gpu-check bump-patch bump-minor bump-major

# Default target
help:
	@echo "Vocal - Available Commands"
	@echo "============================"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install       - Install dependencies and setup project"
	@echo "  make sync          - Sync dependencies with uv"
	@echo ""
	@echo "Testing:"
	@echo "  make test          - Run full E2E test suite (~55 sec)"
	@echo "  make test-quick    - Quick validation checks (~5 sec)"
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
	@echo "  make serve-dev     - Start API server with auto-reload"
	@echo "  make cli           - Show CLI help"
	@echo "  make docs          - Open API documentation in browser"
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
	@echo "Installing dependencies..."
	uv sync
	@echo ""
	@echo "✓ Installation complete!"
	@echo "Run 'make serve' to start the API server"

sync:
	@echo "Syncing dependencies..."
	uv sync

# Testing
test:
	@echo "Running full E2E test suite..."
	@echo ""
	uv run python -m pytest tests/test_e2e.py -v --tb=short

test-quick:
	@echo "Running quick validation checks..."
	@echo ""
	uv run python scripts/validate.py

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

serve-dev:
	@echo "Starting API server with auto-reload..."
	@echo "Documentation: http://localhost:8000/docs"
	@echo ""
	uv run uvicorn vocal_api.main:app --host 0.0.0.0 --port 8000 --reload

cli:
	@echo "Vocal CLI Help"
	@echo "=============="
	@echo ""
	uv run vocal --help

docs:
	@echo "Opening API documentation..."
	@powershell -Command "Start-Process 'http://localhost:8000/docs'"

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
tq: test-quick
tv: test-verbose
s: serve
sd: serve-dev
l: lint
f: format
c: clean
h: help
