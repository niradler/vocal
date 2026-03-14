# Contributing to Vocal

Thanks for your interest in contributing! This guide covers everything you need to set up, develop, test, and submit changes.

## Quick Setup

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/<your-username>/vocal.git
cd vocal

# 2. Install everything (requires Python 3.11+ and uv)
make install

# 3. Run the test suite to confirm a working baseline
make lint && make test
```

`make install` creates a uv workspace with all four packages in editable mode.

## Development Workflow

```
make change → make format → make lint → make test → open PR
```

```bash
make format        # Auto-fix code style (ruff)
make lint          # Lint check — must pass before PR
make test-unit     # 33 unit tests, no server needed (~3s)
make test-contract # 31 contract tests, lightweight server (~10s)
make test          # 56 E2E tests with real models (~45s)
```

Run only the area you changed to stay fast:
```bash
uv run pytest tests/unit/test_config.py -v                      # config changes
uv run pytest tests/contract/test_tts_contract.py -v            # TTS API changes
uv run pytest tests/test_e2e.py::TestSTT -v                     # STT E2E
uv run pytest tests/test_e2e.py::TestTextToSpeech -v            # TTS E2E
```

See [testing.md](testing.md) for the full test tier breakdown.

## Pre-commit Hooks

Install once to auto-check on commit/push:
```bash
uvx pre-commit install
uvx pre-commit install --hook-type pre-push
```

Hooks run: ruff lint + format on commit, unit tests on push.

## Branching

- `master` — stable, always releasable
- `stable` — current release candidate / beta work
- Feature branches: `feature/<name>`, Bug fixes: `fix/<name>`

Open PRs against `master` (or `stable` if it's a release-cycle fix).

## Pull Request Checklist

- [ ] `make lint` passes (zero errors)
- [ ] `make test-unit` passes
- [ ] `make test-contract` passes
- [ ] `make test` passes if your change touches API behavior
- [ ] Docs updated if you changed public APIs, CLI commands, or config
- [ ] No new hardcoded strings — use `vocal_settings.*` from `vocal_core.config`
- [ ] No new `print()` — use `logging.getLogger(__name__)`

## Code Style

- Line length: 120 (ruff enforced)
- Type hints required on all public functions
- No comments unless explaining non-obvious intent
- Imports: stdlib → third-party → local, sorted by isort

Run `make format` to auto-fix most style issues.

## Project Structure

```
vocal/
├── packages/
│   ├── core/         # Model registry, adapters, config (no API dependency)
│   ├── api/          # FastAPI server
│   ├── sdk/          # Auto-generated Python client
│   └── cli/          # Typer CLI (depends on SDK)
├── tests/
│   ├── unit/         # Fast, no server
│   ├── contract/     # API contract tests (starts isolated server)
│   ├── test_e2e.py   # Full E2E with real models
│   └── test_assets/  # Audio fixtures
├── docs/
│   ├── user/         # End-user docs
│   └── developer/    # Contributor + maintainer docs
└── Makefile
```

See [architecture.md](architecture.md) for a deeper technical walkthrough.

## Getting Help

- [GitHub Issues](https://github.com/niradler/vocal/issues) — bugs, feature requests
- [GitHub Discussions](https://github.com/niradler/vocal/discussions) — questions, ideas
- Review [AGENTS.md](../../AGENTS.md) for the full maintainer reference used by AI coding agents
