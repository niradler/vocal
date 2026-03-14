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
| `transformers>=5.3.0` | Force v5 because transformers 4.x hard-checks `huggingface-hub<1.0` at import time and refuses to start |
| `setuptools>=70.0.0,<81` | setuptools 82.0.0 removed `pkg_resources`; pin below 81 to keep it for perth/chatterbox and other legacy packages |
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
- `huggingface-hub` does **not** depend on transformers — the override note "huggingface-hub 1.x pulls it in" was incorrect. The override is needed because whisperx (and others) transitively pull in huggingface-hub 1.x, which is incompatible with transformers 4.x's hard `<1.0` version check at import time.
- Transformers 5.x introduced multiple breaking API changes that affect `qwen_asr` and `qwen_tts`. All resolved via adapter-level monkey-patching (no source editing, no forks):
  - `check_model_inputs` removed from `transformers.utils.generic` → shim added before `qwen_asr` import in `_apply_qwen_asr_shims()`
  - `"default"` RoPE type removed from `ROPE_INIT_FUNCTIONS` → re-added with standard inv_freq formula
  - `Qwen3ASRThinkerTextRotaryEmbedding` missing `compute_default_rope_parameters` method (called by `modeling_utils.py` weight init) → method added to class
  - `Qwen3ASRThinkerConfig` and `Qwen3TTSTalkerConfig` missing `pad_token_id` (required by transformers 5.x `GenerationMixin`) → set to `None` as class attribute
  - `TokenizersBackend.__init__` passes `fix_mistral_regex` both as an explicit kwarg and via `**kwargs` when vocab > 100k → wrap `__init__` to pop it first
  - `StaticLayer.lazy_initialization` now requires both `key_states` and `value_states`; `faster_qwen3_tts` only passes one → default `value_states = key_states`
  - `DynamicCache` subscript access removed (`cache[i]` → `cache.layers[i].keys/values`) → add `__getitem__` returning `(layer.keys, layer.values)`

### torchaudio (2.10.0 + cu128)
- **`torchaudio.io` module removed** — lhotse (NeMo's audio backend) used `torchaudio.io.AudioFileInfo` to probe audio metadata. Removed in torchaudio 2.7+. Fix: pre-convert unsupported formats (`.m4a`, `.aac`, `.wma`, `.amr`) to wav via ffmpeg in the NeMo adapter before passing to NeMo. Implemented in `vocal_core/adapters/stt/nemo_adapter.py`.
- **`torchaudio.save` requires torchcodec on Windows** — torchaudio 2.10.0 uses torchcodec as its default backend. Torchcodec needs FFmpeg shared DLLs (`full-shared` build). The standard static FFmpeg build (e.g. essentials from gyan.dev) does not provide these DLLs. Fix: use `soundfile` for WAV output in adapters. Implemented in `chatterbox.py`.

### setuptools (82.x)
- **`pkg_resources` removed in setuptools 82.0.0** (February 2026). `pkg_resources` was part of setuptools for decades and used by many older packages at runtime. Fix: pin `setuptools>=70.0.0,<81` via override. This restores `pkg_resources` and fixes `perth` (used by chatterbox-tts for audio watermarking), which silently set `PerthImplicitWatermarker = None` on import failure, causing `'NoneType' object is not callable` at synthesis time.

### kokoro
- Latest available: 0.9.4 — no update available
- `misaki[en]` (kokoro's G2P) calls `spacy.cli.download('en_core_web_sm')` at runtime, which uses pip — not available in uv-managed venvs. Fix: add `en-core-web-sm` as a URL dep in the kokoro extra (GitHub release wheel). Defined in `[tool.uv.sources]`. Do **not** add pip as a dep — that would allow arbitrary runtime installs and make the environment non-reproducible.

## Open Issues (Upstream Blockers)

No outstanding upstream blockers remain. All previously open issues have been resolved via adapter-level monkey-patching. See the transformers v5 notes above.

## Packages That Cannot Be Upgraded

| Package | Reason |
|---|---|
| `kokoro` | 0.9.4 is already latest |

## Upgrade History

| Date | Action |
|---|---|
| 2026-03-14 | Bulk upgrade all packages to latest; switched cu124→cu128; resolved chatterbox/whisperx/torch conflicts via overrides; added en-core-web-sm URL dep to fix kokoro G2P pip-call issue in uv venvs |
| 2026-03-14 | Added `setuptools<81` override (setuptools 82 removed `pkg_resources`, breaking `perth` → chatterbox); fixed NeMo m4a support via ffmpeg pre-conversion in adapter; fixed chatterbox WAV output via soundfile (replacing torchaudio.save which needs torchcodec DLLs); documented qwen-asr/qwen-tts as upstream blockers on transformers 5.x |
| 2026-03-14 | Resolved all qwen-asr and qwen-tts transformers 5.x incompatibilities via adapter-level monkey-patching (7 distinct API breaks fixed); `TestTransformersSTT` and `TestVoiceClone` now pass on Windows; all 3 test suites green, lint clean |
