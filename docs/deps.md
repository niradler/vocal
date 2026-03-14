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
- `huggingface-hub` does **not** depend on transformers — the override is needed because whisperx transitively pulls in huggingface-hub 1.x, which is incompatible with transformers 4.x's hard `<1.0` import-time check.
- Transformers 5.x broke `qwen_asr` and `qwen_tts` in several ways. All fixed via adapter-level patches — see the **Runtime Patches** section below.

### torchaudio (2.10.0 + cu128)
- **`torchaudio.io` module removed** — lhotse (NeMo's audio backend) used `torchaudio.io.AudioFileInfo` to probe audio metadata. Removed in torchaudio 2.7+. Fix: pre-convert unsupported formats (`.m4a`, `.aac`, `.wma`, `.amr`) to wav via ffmpeg in the NeMo adapter before passing to NeMo. Implemented in `vocal_core/adapters/stt/nemo_adapter.py`.
- **`torchaudio.save` requires torchcodec on Windows** — torchaudio 2.10.0 uses torchcodec as its default backend. Torchcodec needs FFmpeg shared DLLs (`full-shared` build). The standard static FFmpeg build (e.g. essentials from gyan.dev) does not provide these DLLs. Fix: use `soundfile` for WAV output in adapters. Implemented in `chatterbox.py`.

### setuptools (82.x)
- **`pkg_resources` removed in setuptools 82.0.0** (February 2026). `pkg_resources` was part of setuptools for decades and used by many older packages at runtime. Fix: pin `setuptools>=70.0.0,<81` via override. This restores `pkg_resources` and fixes `perth` (used by chatterbox-tts for audio watermarking), which silently set `PerthImplicitWatermarker = None` on import failure, causing `'NoneType' object is not callable` at synthesis time.

### kokoro
- Latest available: 0.9.4 — no update available
- `misaki[en]` (kokoro's G2P) calls `spacy.cli.download('en_core_web_sm')` at runtime, which uses pip — not available in uv-managed venvs. Fix: add `en-core-web-sm` as a URL dep in the kokoro extra (GitHub release wheel). Defined in `[tool.uv.sources]`. Do **not** add pip as a dep — that would allow arbitrary runtime installs and make the environment non-reproducible.

## Runtime Patches

Monkey-patches applied at adapter import time to bridge transformers 5.x API breaks in `qwen_asr` / `qwen_tts`. No library source edits, no forks.

### Patch Maintenance

**These patches are fragile.** Each one compensates for a specific API break between transformers 5.x and qwen_asr/qwen_tts. On future upgrades:

1. **Check if patches are still needed.** After upgrading transformers or qwen packages, temporarily remove each patch and run the relevant tests. If a patch target already exists natively (e.g. `check_model_inputs` is re-added to transformers), the patch is stale — delete it.
2. **Check if patches still work.** If transformers changes the patched API again (e.g. `StaticLayer.lazy_initialization` gains a third arg), the patch will silently break. Test the actual model inference, not just import.
3. **Duplicated shims.** `check_model_inputs` and `ROPE_INIT_FUNCTIONS["default"]` are duplicated in both `transformers_adapter.py` and `faster_qwen3_tts.py`. If adding more patches, consider extracting shared shims to `vocal_core/adapters/_compat.py`.
4. **Upstream fixes.** Monitor `qwen-asr` and `faster-qwen3-tts` releases — once they officially support transformers 5.x, all patches for that package can be removed.

| Patch | File | What changed in transformers 5.x |
|---|---|---|
| `transformers.utils.generic.check_model_inputs = <no-op>` | `transformers_adapter.py`, `faster_qwen3_tts.py` | Decorator removed |
| `ROPE_INIT_FUNCTIONS["default"] = <inv_freq fn>` | `transformers_adapter.py`, `faster_qwen3_tts.py` | `"default"` key removed from RoPE registry |
| `Qwen3ASRThinkerTextRotaryEmbedding.compute_default_rope_parameters = <method>` | `transformers_adapter.py` | Method dropped from base class; `modeling_utils.py` calls it for `rope_type == "default"` |
| `Qwen3ASRThinkerConfig.pad_token_id = None` | `transformers_adapter.py` | `GenerationMixin` now requires the attribute on sub-configs |
| `Qwen3TTSTalkerConfig.pad_token_id = None` | `faster_qwen3_tts.py` | Same |
| `TokenizersBackend.__init__` wrapped to pop `fix_mistral_regex` from `kwargs` | `faster_qwen3_tts.py` | `__init__` passes it both explicitly and via `**kwargs` when vocab > 100k — Python rejects the duplicate |
| `StaticLayer.lazy_initialization(self, key, value=None)` | `faster_qwen3_tts.py` | Signature gained required `value_states`; `faster_qwen3_tts` only passes one arg |
| `DynamicCache.__getitem__ = lambda self, i: (self.layers[i].keys, self.layers[i].values)` | `faster_qwen3_tts.py` | Subscript access removed; `faster_qwen3_tts` uses `cache[layer_idx]` |

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

## Future Upgrade Checklist

Quick reference for the next bulk upgrade. Follow the step-by-step in "How to Upgrade All Dependencies" above, plus these extra checks:

### Before upgrading

- [ ] Read this file end-to-end — past pain saves future pain
- [ ] Note which overrides exist and why (table above)
- [ ] Check if `qwen-asr` / `faster-qwen3-tts` have released versions with native transformers 5.x support — if so, monkey-patches can be removed

### During upgrade

- [ ] Update all `>=` floors in every `pyproject.toml` (root + packages/core, api, sdk, cli)
- [ ] Run `uv sync` — fix resolution errors with overrides, not by downgrading
- [ ] Check CUDA index: if torch needs a newer CUDA, update the `[[tool.uv.index]]` URL (cu128 → cu1xx)
- [ ] Check `en-core-web-sm` URL in `[tool.uv.sources]` — new spacy major versions change the wheel URL

### After upgrade

- [ ] Run all 3 test suites: `uv run python -m pytest tests/unit/ tests/contract/ tests/test_e2e.py tests/test_tts_formats.py -q`
- [ ] Zero skips, zero failures — skips count as failures
- [ ] Test each monkey-patch: temporarily remove it, run the relevant adapter's tests, see if it's still needed
- [ ] Remove any override whose upstream package has fixed the version conflict
- [ ] Run `make lint`
- [ ] Update the "Upgrade History" table in this file

### Known areas of future breakage

| Area | What to watch for |
|---|---|
| `setuptools<81` override | Remove once `perth` (chatterbox dep) drops `pkg_resources` usage |
| `chatterbox-tts` torch pin | Remove override once chatterbox unpins from `torch==2.6.0` |
| `whisperx` huggingface-hub pin | Remove override once whisperx drops `huggingface-hub<1.0` constraint |
| `gradio` pins (aiofiles, pydantic, websockets) | Remove overrides once chatterbox upgrades its gradio dep or drops it |
| Monkey-patches in `transformers_adapter.py` | Remove once `qwen-asr` supports transformers 5.x natively |
| Monkey-patches in `faster_qwen3_tts.py` | Remove once `faster-qwen3-tts` supports transformers 5.x natively |
| `torchaudio.io` removal workaround in `nemo_adapter.py` | Remove if lhotse/NeMo adds native support for torchaudio 2.7+ |
| `soundfile` workaround in `chatterbox.py` | Remove if torchcodec ships Windows DLLs or torchaudio restores non-torchcodec backend |
