# Release Process

## Version Numbering

Vocal uses semantic versioning: `MAJOR.MINOR.PATCH`

| Change type | Command | Example |
|-------------|---------|---------|
| Bug fix | `make bump-patch` | 0.3.5 → 0.3.6 |
| New feature | `make bump-minor` | 0.3.5 → 0.4.0 |
| Breaking change | `make bump-major` | 0.3.5 → 1.0.0 |

`make bump-*` updates all `pyproject.toml` files and `__init__.py` files in one command (via `bump-my-version`).

## Pre-release Checklist

Run through these in order before tagging a release.

### 1. Validate all tiers pass

```bash
make lint                  # zero ruff errors
make test-unit             # 33 unit tests green
make test-contract         # 31 contract tests green (start fresh server first)
make test                  # 56 E2E green (server running)
```

### 2. Validate on both platforms

**Windows:**
```bash
make lint && make test-unit && make test-contract
make serve &
make test
```

**WSL / Linux:**
```bash
sudo apt install espeak-ng ffmpeg   # if not already installed
UV_PROJECT_ENVIRONMENT=/tmp/vocal_venv uv run pytest tests/unit/ tests/contract/ -q
# E2E — see testing.md for WSL setup
```

### 3. Check the SDK is regenerated

```bash
make serve &
sleep 5
make generate-sdk          # regenerate from live API spec
git diff packages/sdk/     # review any changes
make lint                  # ensure regenerated SDK passes lint
```

If the SDK changed, include it in the release commit.

### 4. Review public-facing docs

- `README.md` — quick start examples still work?
- `docs/user/models.md` — model table accurate?
- `docs/user/cli.md` — all commands match current `vocal --help`?
- `docs/user/configuration.md` — all env vars match `VocalSettings`?

### 5. Bump the version

```bash
make bump-patch   # or bump-minor / bump-major
```

### 6. Commit and tag

```bash
git add .
git commit -m "Release v$(uv run python -c 'import vocal; print(vocal.__version__)')"
git tag v0.3.6              # use the new version
git push && git push --tags
```

## Publish to PyPI

Packages must be published **in dependency order** so dependent packages can find their requirements.

```bash
# Build all packages
cd packages/core && uv run python -m build && cd ../..
cd packages/api  && uv run python -m build && cd ../..
cd packages/sdk  && uv run python -m build && cd ../..
cd packages/cli  && uv run python -m build && cd ../..
uv run python -m build   # root vocal-ai meta-package

# Publish all (token from ~/.pypirc)
UV_PUBLISH_TOKEN=pypi-... uv publish dist/*0.3.8*
```

## Post-release

1. Create a GitHub Release from the tag with a changelog
2. Update `README.md` Roadmap section if needed
3. Announce in Discussions if it's a significant release

## Rollback

If a release has a critical bug:
1. Yank the bad version on PyPI: go to the release page → "Yank release"
2. Fix the bug on a `fix/<issue>` branch
3. `make bump-patch` and release the patch version
4. Un-yank the previous stable if needed

## Changelog Template

```markdown
## v0.3.6 — 2026-03-15

### Added
- ...

### Fixed
- ...

### Changed
- ...

### Removed
- ...
```
