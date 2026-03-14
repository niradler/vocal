# Dependency Notes & Conflicts

This document tracks known dependency conflicts, version decisions, and the overrides required to resolve them. Update this when upgrading packages.

## How to Upgrade All Dependencies (The Right Way)

**TL;DR: Update the version. Run the tests. Only skip something if the tests actually fail.**

The real mistake is declaring something "too hard to upgrade" based on resolution errors or reading metadata — without ever actually testing it. uv resolution conflicts say nothing about runtime compatibility. The tests do.

### Step-by-step

1. **Set all packages to latest** in every `pyproject.toml` across the workspace (use PyPI JSON API: `https://pypi.org/pypi/<pkg>/json`)

2. **Run `uv sync`** — if resolution fails, add an override to `[tool.uv] override-dependencies` in root `pyproject.toml` and retry. Don't investigate why — just override and move on.

3. **Run all 3 test suites:**
   ```
   uv run python -m pytest tests/unit/ tests/contract/ tests/test_e2e.py tests/test_tts_formats.py -q
   ```

4. If tests pass — **done**. If a test fails — now you have a real problem worth investigating.

### The rule

> A package is only "too hard to upgrade" if the **tests fail**. Not if uv complains. Not if the metadata looks scary. Only if tests fail.

Resolution errors are metadata mismatches, not runtime failures. `chatterbox-tts` pins `torch==2.6.0` in its metadata but runs fine on 2.10.0. You'd never know that without testing it.

### What to watch for (genuine blockers)

- **CUDA index** — if `uv sync` fails because a package needs a newer torch than the index provides, check `nvidia-smi` and switch the pytorch index URL (cu124 → cu126 → cu128). This is a one-line change.
- **Packages that call pip at runtime** — some packages (e.g. spacy's `cli.download`) invoke pip internally. uv-managed venvs don't include pip. Fix: pre-declare the resource as an explicit dep (URL wheel if needed), not by adding pip to deps. Adding pip as a workaround allows arbitrary runtime installs and makes the environment non-reproducible.
- **Test failures** — the only real signal. Everything else is noise until proven otherwise.

## uv Override Dependencies

Located in root `pyproject.toml` under `[tool.uv] override-dependencies`. These force a version regardless of what sub-dependencies declare, resolving conflicts at the uv resolution level.

| Override | Reason |
|---|---|
| `ctranslate2>=4.7.1` | Ensure minimum version for faster-whisper compatibility |
| `transformers>=5.3.0` | Force v5 — huggingface-hub 1.x pulls it in anyway |
| `numpy>=2.4.3` | chatterbox-tts pins `numpy>=1.24,<1.26`; numpy 2.x is backward compatible |
| `huggingface-hub>=1.7.1` | whisperx<3.8.2 declares `huggingface-hub<1.0.0`; 1.7.1 works fine at runtime |
| `torch>=2.8.0` | chatterbox-tts hard-pins `torch==2.6.0`; tested and works with 2.10.0 |
| `torchaudio>=2.8.0` | chatterbox-tts hard-pins `torchaudio==2.6.0`; works with 2.10.0 |
| `aiofiles>=25.1.0` | gradio 5.44.1 (via chatterbox-tts) declares `aiofiles<25`; 25.x works fine |
| `pydantic>=2.12.5` | gradio 5.44.1 declares `pydantic<2.12`; 2.12.x works fine |
| `websockets>=16.0` | gradio-client declares `websockets<16`; 16.x works fine |

## pytorch CUDA Index

```
url = "https://download.pytorch.org/whl/cu128"
```

- Switched from **cu124 → cu128** to unlock torch 2.7+ (cu124 tops out at torch 2.6.0)
- Requires CUDA 12.8+ driver. Tested on CUDA 13.0 (driver 581.57) — fully compatible via backward compat

## Package-Specific Notes

### chatterbox-tts (all versions ≤0.1.6)
- Hard-pins `torch==2.6.0` and `torchaudio==2.6.0` — every single release
- Pulls in `gradio==5.44.1` (pinned exact) which then conflicts with:
  - `aiofiles>=25` (gradio wants `<25`)
  - `pydantic>=2.12` (gradio wants `<2.12`)
  - `websockets>=16` (gradio-client wants `<16`)
- All overridden and tested — works at runtime

### whisperx (≥3.5.0)
- Requires `torch>=2.7.1` — was blocked when using cu124 index (max torch 2.6.0)
- whisperx ≥3.7.8 also declares `huggingface-hub<1.0.0` — overridden
- Resolved by switching to cu128 index (torch 2.10.0 now installed)

### torch / torchaudio
- Current: `2.10.0+cu128`
- cu124 index capped at 2.6.0; cu128 provides up to 2.10.0+
- Both chatterbox-tts and whisperx now work with 2.10.0 via overrides

### transformers (v5 major bump)
- huggingface-hub 1.x transitively requires transformers 5.x
- No breaking changes observed in tests — all 208 pass

### kokoro
- Latest available: 0.9.4 — no update available
- `misaki[en]` (kokoro's G2P) calls `spacy.cli.download('en_core_web_sm')` at runtime, which uses pip — not available in uv-managed venvs. Fix: add `en-core-web-sm` as a URL dep in the kokoro extra (GitHub release wheel). Defined in `[tool.uv.sources]`.

## Packages That Cannot Be Upgraded

| Package | Reason |
|---|---|
| `kokoro` | 0.9.4 is already latest |

## Upgrade History

| Date | Action |
|---|---|
| 2026-03-14 | Bulk upgrade all packages to latest; switched cu124→cu128; resolved chatterbox/whisperx/torch conflicts via overrides; added en-core-web-sm URL dep to fix kokoro G2P pip-call issue in uv venvs |
