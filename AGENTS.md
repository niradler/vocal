# AGENTS.md - Vocal Coding Agent Reference

**Version:** 0.2.3 | **Python:** 3.11+ | **Tests:** 23 E2E (~55s)

---

## What is Vocal?

Vocal is an **Ollama-style platform for voice models** - a generic Speech AI API that manages STT (Speech-to-Text) and TTS (Text-to-Speech) models like Ollama manages LLMs. It provides OpenAI-compatible endpoints (`/v1/audio/speech`, `/v1/audio/transcriptions`) with model registry, download management, and automatic SDK generation from OpenAPI spec. Architecture follows API-first design: FastAPI generates OpenAPI schema → SDK auto-generates from schema → CLI uses SDK. The monorepo has 4 packages with strict dependency flow: `core` (registry/adapters) → `api` (FastAPI) → `sdk` (auto-generated) → `cli` (Typer-based).

---

## Essential Commands

```bash
make lint && make test    # ALWAYS run before completing tasks
make install              # Setup project
make serve               # Start API (http://localhost:8000)
```

---

## Project Structure

```
vocal/
├── packages/
│   ├── core/     # Registry & adapters (no API deps)
│   ├── api/      # FastAPI server
│   ├── sdk/      # Python SDK
│   └── cli/      # CLI tool
├── tests/        # 23 E2E tests
└── Makefile      # All commands
```

**Dependencies:** `cli → sdk → api → core`

---

## Development Workflow

1. Make changes
2. `make format` - Auto-fix style
3. `make lint` - Must pass
4. `make test` - Must pass (23/23)
5. Update docs if needed

---

## Makefile Reference

| Command | Purpose | Time |
|---------|---------|------|
| `make test` | Full test suite | 55s |
| `make test-quick` | Quick validation | 5s |
| `make lint` | Check code | 10s |
| `make format` | Fix style | 10s |
| `make serve` | Start API | - |
| `make serve-dev` | API + auto-reload | - |
| `make clean` | Clear cache | 5s |

**Aliases:** `t`, `l`, `f`, `s`, `sd`, `c`

---

## Testing

```bash
make test                      # All tests
make test-quick                # Fast validation
make test-verbose              # Debug output
uv run pytest tests/test_e2e.py::TestClass::test_name -vv  # Specific test
```

**Coverage:**
- API Health: 2
- Model Management: 5
- STT: 7
- TTS: 5
- Error Handling: 4
- Performance: 1

---

## Release Process

```bash
make bump-patch    # Bug fixes (0.2.3 → 0.2.4)
make bump-minor    # New features (0.2.3 → 0.3.0)
make bump-major    # Breaking changes (0.2.3 → 1.0.0)
```

**Release Checklist:**
1. `make lint && make test` ✅
2. Update `README.md` if API changed
3. `make bump-patch` (or minor/major)
4. `git add . && git commit -m "Release vX.Y.Z"`
5. `git tag vX.Y.Z && git push --tags`

**Auto-updated files:** All `pyproject.toml` + `__init__.py` in packages

---

## Architecture Patterns

### Service Pattern
```python
class Service:
    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self.adapters: dict[str, Adapter] = {}
    
    async def operation(self, model_id: str) -> Result:
        model_info = await self.registry.get_model(model_id)
        if not model_info:
            raise ValueError("Model not found")
        model_path = self.registry.get_model_path(model_id)
        if not model_path:
            raise ValueError("Model not downloaded")
        adapter = await self._get_or_create_adapter(...)
        return await adapter.operation(...)
```

### Registry Models
- Models in `vocal_core/registry/providers/huggingface.py`
- Must be downloaded before use
- Exception: `"pyttsx3"` = built-in TTS fallback

### API Endpoints
- OpenAI-compatible: `/v1/audio/speech`, `/v1/audio/transcriptions`
- Model management: `/v1/models`

---

## Code Standards

**Ruff:** Line length 120, PEP 8, Python 3.11+

```python
from pathlib import Path              # Stdlib
from fastapi import APIRouter         # Third-party
from vocal_core import ModelRegistry  # Local

async def func(text: str, model_id: str) -> TTSResult:
    """Brief description
    
    Args:
        text: Description
        model_id: Description
    
    Returns:
        Description
    """
```

**No comments unless asked**

---

## Common Tasks

### Add Model to Registry
Edit `packages/core/vocal_core/registry/providers/huggingface.py`:
```python
KNOWN_TTS_MODELS = {
    "model/id": {
        "name": "Name",
        "parameters": "100M",
        "backend": ModelBackend.ONNX,
        "recommended_vram": "2GB+",
        "languages": ["en"],
    },
}
```

### Fix Failing Test
```bash
make test-verbose                # See error
uv run pytest tests/test_e2e.py::TestClass::test_name -vv -s
# Fix issue
make lint && make test           # Verify
```

### Kill Port 8000
```bash
netstat -ano | findstr :8000
taskkill /F /PID <PID>
```

---

## Rules

### DO ✅
- Run `make lint && make test` before completing
- Follow existing patterns
- Use type hints
- Keep package dependencies correct
- Update docs when changing APIs
- Test with `test_assets/audio/`
- **REUSE existing markdown files** (README.md, AGENTS.md)

### DON'T ❌
- Skip tests/linting
- Add comments (unless asked)
- Create circular dependencies
- Bypass model registry
- Hardcode paths
- **Create new markdown files** (unless explicitly asked)
- Make breaking changes without major version bump

---

## Publishing to PyPI

**Package Name:** `vocal-ai` (not `vocal` - already taken on PyPI)

**Published Packages:**
1. `vocal-core` - Core registry/adapters
2. `vocal-sdk` - Python SDK
3. `vocal-api` - FastAPI server
4. `vocal-cli` - CLI tool
5. `vocal-ai` - Meta-package (installs all above)

**Publishing Order (Critical):**
```bash
# Build all packages
make build  # if available, or manually:
cd packages/core && uv run python -m build
cd packages/sdk && uv run python -m build
cd packages/api && uv run python -m build
cd packages/cli && uv run python -m build
cd ../.. && uv run python -m build

# Publish in dependency order
uv run twine upload packages/core/dist/*
uv run twine upload packages/sdk/dist/*
uv run twine upload packages/api/dist/*
uv run twine upload packages/cli/dist/*
uv run twine upload dist/*  # main package last
```

**PyPI Authentication:**
- Username: `__token__`
- Password: Your PyPI API token from https://pypi.org/manage/account/token/

**Version Bumping:**
- `make bump-patch` - Updates all packages (core, sdk, api, cli, main)
- Auto-updates: `pyproject.toml` files + `vocal/__init__.py`

**Installation:**
```bash
pip install vocal-ai  # Installs everything
# or
uvx vocal serve      # Run without installing
```

---

## Quick Checklist

**Every Task:**
- [ ] Make changes
- [ ] `make lint` passes
- [ ] `make test` passes (23/23)
- [ ] Docs updated (if API changed)
- [ ] Task complete

---

## References

- API Docs: http://localhost:8000/docs (when running)
- Tests: `tests/test_e2e.py`
- Registry: `packages/core/vocal_core/registry/`
- Routes: `packages/api/vocal_api/routes/`
