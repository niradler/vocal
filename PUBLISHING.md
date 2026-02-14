# PyPI Publishing Guide

## Packages Built

All packages have been built successfully in v0.3.0:

1. **vocal-core** - Core model registry and adapters
2. **vocal-sdk** - Python SDK (OpenAI-compatible client)  
3. **vocal-api** - FastAPI server
4. **vocal-cli** - Command-line tool

## Package Locations

```
packages/core/dist/
├── vocal_core-0.3.0-py3-none-any.whl
└── vocal_core-0.3.0.tar.gz

packages/sdk/dist/
├── vocal_sdk-0.3.0-py3-none-any.whl
└── vocal_sdk-0.3.0.tar.gz

packages/api/dist/
├── vocal_api-0.3.0-py3-none-any.whl
└── vocal_api-0.3.0.tar.gz

packages/cli/dist/
├── vocal_cli-0.3.0-py3-none-any.whl
└── vocal_cli-0.3.0.tar.gz
```

## Before Publishing

1. **Update GitHub URLs** in all `pyproject.toml` files:
   - Replace `https://github.com/yourusername/vocal` with your actual repo URL

2. **Test Installation Locally**:
   ```bash
   # Test each package
   uv pip install packages/core/dist/vocal_core-0.3.0-py3-none-any.whl
   uv pip install packages/sdk/dist/vocal_sdk-0.3.0-py3-none-any.whl
   uv pip install packages/api/dist/vocal_api-0.3.0-py3-none-any.whl
   uv pip install packages/cli/dist/vocal_cli-0.3.0-py3-none-any.whl
   ```

3. **Create PyPI Account**:
   - Go to https://pypi.org/account/register/
   - Verify email
   - Enable 2FA (required for publishing)

4. **Create API Token**:
   - Go to https://pypi.org/manage/account/token/
   - Create token with "Upload packages" scope
   - Save token securely (you'll only see it once)

## Publishing to PyPI

### Option 1: Using twine (Recommended)

```bash
# Install twine
uv add --dev twine

# Publish packages (in dependency order)
uv run twine upload packages/core/dist/*
uv run twine upload packages/sdk/dist/*
uv run twine upload packages/api/dist/*
uv run twine upload packages/cli/dist/*
```

When prompted:
- Username: `__token__`
- Password: `pypi-...` (your API token)

### Option 2: Using uv (if supported)

```bash
uv publish packages/core/dist/*
uv publish packages/sdk/dist/*
uv publish packages/api/dist/*
uv publish packages/cli/dist/*
```

## Publishing Order (IMPORTANT!)

Publish in this order due to dependencies:

1. **vocal-core** (no dependencies on other vocal packages)
2. **vocal-sdk** (no dependencies on other vocal packages)
3. **vocal-api** (depends on vocal-core)
4. **vocal-cli** (depends on vocal-sdk)

## Test Installation from PyPI

After publishing:

```bash
# Create new environment to test
uv venv test-env
source test-env/bin/activate  # or test-env\Scripts\activate on Windows

# Install from PyPI
pip install vocal-core
pip install vocal-sdk
pip install vocal-api
pip install vocal-cli

# Test
vocal --help
python -c "from vocal_sdk import VocalSDK; print('Success!')"
```

## Publishing to TestPyPI First (Recommended)

Test on TestPyPI before publishing to real PyPI:

1. **Create TestPyPI Account**: https://test.pypi.org/account/register/

2. **Publish to TestPyPI**:
   ```bash
   uv run twine upload --repository testpypi packages/core/dist/*
   uv run twine upload --repository testpypi packages/sdk/dist/*
   uv run twine upload --repository testpypi packages/api/dist/*
   uv run twine upload --repository testpypi packages/cli/dist/*
   ```

3. **Test Installation**:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ vocal-core
   ```

4. **If everything works, publish to real PyPI**

## Post-Publishing

1. **Update README.md** with installation instructions:
   ```bash
   pip install vocal-core vocal-sdk vocal-api vocal-cli
   ```

2. **Create GitHub Release**:
   - Tag: v0.3.0
   - Title: "Release v0.3.0: TTS Model Parameter + Keep-Alive"
   - Attach wheel files

3. **Monitor PyPI Stats**:
   - https://pypi.org/project/vocal-core/
   - Check download statistics

## Troubleshooting

### "Package already exists"
- Can't re-upload same version
- Bump version and rebuild

### "Invalid credentials"
- Use `__token__` as username
- Paste full token including `pypi-` prefix

### "Package has invalid metadata"
- Check `pyproject.toml` for errors
- Validate URLs are correct

## Package Sizes

- vocal-core: ~19KB (wheel), ~13KB (sdist)
- vocal-sdk: ~4KB (wheel), ~7KB (sdist)
- vocal-api: ~12KB (wheel), ~8KB (sdist)
- vocal-cli: ~4KB (wheel), ~3KB (sdist)

**Total: ~70KB for all packages**

## License Note

All packages use SSPL-1.0 license. This is:
- ✅ Allowed on PyPI
- ✅ Open source
- ❌ NOT OSI-approved
- ⚠️ Restricts SaaS offerings

Users can:
- Install and use freely
- Modify and distribute
- Use in commercial applications
- Self-host

Users cannot:
- Offer as SaaS without open-sourcing infrastructure

## Ready to Publish?

```bash
# 1. Update GitHub URLs in all pyproject.toml
# 2. Get PyPI token
# 3. Run:
make publish  # if you create this target
# or manually:
uv run twine upload packages/*/dist/*
```
