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

- **CUDA index** — if `uv sync` fails because a package needs a newer torch than the index provides, check `nvidia-smi` and switch the pytorch index URL (cu128 → cu130 → cu132). This is a one-line change.
- **Packages that call pip at runtime** — some packages (e.g. spacy's `cli.download`) invoke pip internally. uv-managed venvs don't include pip. Fix: pre-declare the resource as an explicit dep (URL wheel if needed), not by adding pip to deps. Adding pip as a workaround allows arbitrary runtime installs and makes the environment non-reproducible.
- **Test failures** — the only real signal. Everything else is noise until proven otherwise.

## uv Override Dependencies

Located in root `pyproject.toml` under `[tool.uv] override-dependencies`. These force a version regardless of what sub-dependencies declare, resolving conflicts at the uv resolution level.

| Override | Reason |
|---|---|
| `ctranslate2>=4.9.0` | faster-whisper 1.2.x requires 4.9+ (`av.open`/quantization API changes) |
| `av>=17,<19` | faster-whisper calls `av.open(metadata_errors=...)`, which PyAV 19 removed |
| `transformers>=5.22,<5.23` | 5.23 registers native `qwen3_tts`/`qwen3_asr` configs that break `faster-qwen3-tts`; 5.22.x is the newest working minor (see below) |
| `setuptools>=70.0.0,<85` | setuptools 82 removed `pkg_resources`, needed by `perth`/chatterbox; 80.10.2 is installed |
| `numpy>=2.4.3` | chatterbox-tts pins `numpy>=1.24,<1.26`; numpy 2.x is backward compatible |
| `huggingface-hub>=2.4.0` | whisperx declares `huggingface-hub<1.0.0`; transformers 5.x needs hub 2.x |
| `torch>=2.15.0` | chatterbox-tts hard-pins `torch==2.6.0`; 2.15.0+cu132 is tested |
| `torchaudio>=2.11.1` | chatterbox-tts hard-pins `torchaudio==2.6.0`; must match torch |
| `torchvision>=0.29.1` | must match torch 2.15 — a mismatched build breaks `transformers` at import (`operator torchvision::nms does not exist`) |
| `torchcodec>=0.17.0` | torchaudio 2.11 audio I/O; unknown-to-PyPI builds were incompatible |
| `aiofiles>=25.1.0` | gradio 5.44.1 (via chatterbox-tts) declares `aiofiles<25`; 25.x works fine |
| `pydantic>=2.14.3` | gradio 5.44.1 declares `pydantic<2.12`; 2.14.x works fine |
| `websockets>=17.4` | gradio-client declares `websockets<16`; 17.x works fine |
| `safetensors>=0.8.0` | chatterbox-tts pins `safetensors==0.5.3`; 0.8.0 is compatible |

## pytorch CUDA Index

```
url = "https://download.pytorch.org/whl/cu132"
```

- Resolved versions: `torch 2.15.0+cu132`, `torchaudio 2.11.1+cu132`, `torchvision 0.29.2+cu132`, `torchcodec 0.17.0+cu132` (all from `[tool.uv.sources]`, none from PyPI)
- Requires a CUDA 13.2-capable driver. Tested on driver 610.88 (CUDA 13.2) on an RTX 4090
- torchcodec still needs FFmpeg shared DLLs at runtime on Windows; adapters avoid it anyway (soundfile + ffmpeg fallback)

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
- Current: `torch 2.15.0+cu132` / `torchaudio 2.11.1+cu132` / `torchvision 0.29.2+cu132`
- torch, torchaudio and torchvision must stay on mutually compatible versions — a torchvision built for an older torch breaks `transformers` at import
- Both chatterbox-tts and whisperx work with 2.15.0 via the overrides above

### transformers (v5 major bump, pinned `>=5.22,<5.23`)
- `huggingface-hub` does **not** depend on transformers — the override is needed because whisperx transitively pulls in huggingface-hub 1.x, which is incompatible with transformers 4.x's hard `<1.0` import-time check.
- **5.23.0 is excluded.** It ships native `qwen3_asr` / `qwen3_tts` registrations that break the `faster-qwen3-tts` tokenizer (`property 'upsample' ... has no setter`) and it validates sub-config token ids through `get_text_config()`, which crashes the talker config. 5.22.x keeps every model working (Granite Speech 5.0, Cohere Transcribe, Voxtral Realtime, Qwen3-ASR, Qwen3-TTS). Re-test before lifting the pin.
- Qwen3-ASR uses transformers' native `Qwen3ASRForConditionalGeneration` with the `*-hf` checkpoints. The abandoned `qwen-asr` PyPI package pins `transformers==4.57.6`, so it is **not** a dependency anymore.

### torchaudio (2.11.1 + cu132)
- **`torchaudio.io` module removed** — lhotse (NeMo's audio backend) used `torchaudio.io.AudioFileInfo` to probe audio metadata. Removed in torchaudio 2.7+. Fix: pre-convert unsupported formats (`.m4a`, `.aac`, `.wma`, `.amr`) to wav via ffmpeg in the NeMo adapter before passing to NeMo. Implemented in `vocal_core/adapters/stt/nemo_adapter.py`.
- **`torchaudio.save` requires torchcodec on Windows** — torchaudio uses torchcodec as its default backend. Torchcodec needs FFmpeg shared DLLs (`full-shared` build). The standard static FFmpeg build (e.g. essentials from gyan.dev) does not provide these DLLs. Fix: use `soundfile` for WAV output in adapters, and decode inputs with `soundfile` (+ an `ffmpeg` fallback for containers) instead of `transformers.audio_utils.load_audio`.

### setuptools (82.x)
- **`pkg_resources` removed in setuptools 82.0.0** (February 2026). `pkg_resources` was part of setuptools for decades and used by many older packages at runtime. Fix: pin `setuptools>=70.0.0,<85` via override. This restores `pkg_resources` and fixes `perth` (used by chatterbox-tts for audio watermarking), which silently set `PerthImplicitWatermarker = None` on import failure, causing `'NoneType' object is not callable` at synthesis time.

### kokoro
- Latest available: 0.9.4 — no update available
- `misaki[en]` (kokoro's G2P) calls `spacy.cli.download('en_core_web_sm')` at runtime, which uses pip — not available in uv-managed venvs. Fix: add `en-core-web-sm` as a URL dep in the kokoro extra (GitHub release wheel). Defined in `[tool.uv.sources]`. Do **not** add pip as a dep — that would allow arbitrary runtime installs and make the environment non-reproducible.

## Runtime Patches

Monkey-patches applied at adapter import time to bridge transformers 5.x API breaks in `faster_qwen3_tts` / `qwen_tts`. No library source edits, no forks.

### Patch Maintenance

**These patches are fragile.** Each one compensates for a specific API break between transformers 5.x and qwen_tts. On future upgrades:

1. **Check if patches are still needed.** After upgrading transformers or qwen packages, temporarily remove each patch and run the relevant tests. If a patch target already exists natively (e.g. `check_model_inputs` is re-added to transformers), the patch is stale — delete it.
2. **Check if patches still work.** If transformers changes the patched API again (e.g. `StaticLayer.lazy_initialization` gains a third arg), the patch will silently break. Test the actual model inference, not just import.
3. **Shared shims live in `vocal_core/adapters/_compat.py`.** `apply_transformers_shims()` is called from API startup and from each adapter that needs it; it is idempotent.
4. **Upstream fixes.** Monitor `faster-qwen3-tts` releases — once it supports transformers 5.23+, the pin and the patches can be lifted.

| Patch | File | What changed in transformers 5.x |
|---|---|---|
| `transformers.utils.generic.check_model_inputs = <tolerant decorator>` | `_compat.py`, used by `faster_qwen3_tts.py` | Signature changed from decorator factory to direct decorator |
| `ROPE_INIT_FUNCTIONS["default"] = <inv_freq fn>` | `_compat.py` | `"default"` key removed from RoPE registry |
| `Qwen3TTSTalkerConfig.pad_token_id = None` | `faster_qwen3_tts.py` | Same |
| `TokenizersBackend.__init__` wrapped to pop `fix_mistral_regex` from `kwargs` | `_compat.py` | `__init__` passes it both explicitly and via `**kwargs` when vocab > 100k — Python rejects the duplicate |
| `StaticLayer.lazy_initialization(self, key, value=None)` | `faster_qwen3_tts.py` | Signature gained required `value_states`; `faster_qwen3_tts` only passes one arg |
| `DynamicCache.__getitem__ = lambda self, i: (self.layers[i].keys, self.layers[i].values)` | `faster_qwen3_tts.py` | Subscript access removed; `faster_qwen3_tts` uses `cache[layer_idx]` |
| `MimiModel.upsample` property deleted | `faster_qwen3_tts.py` | Became a read-only deprecated property; `qwen_tts`'s tokenizer encoder assigns `self.upsample = None` |
| `Voxtral` processor helpers (`num_right_pad_tokens`, …) accept int or callable | `voxtral.py` | Became plain int attributes instead of methods |

## Open Issues (Upstream Blockers)

- **`transformers` 5.23.0** regresses `faster-qwen3-tts` (native `qwen3_tts` registration + sub-config token-id validation). Pinned to `>=5.22,<5.23` until `faster-qwen3-tts` ships a compatible release.
- **`openapi-python-client` 0.30** generates `httpx2` imports; the SDK stays on 0.29.x.
- **`av` 19** removed `metadata_errors`, which faster-whisper still passes. Pinned `<19`.

## Packages That Cannot Be Upgraded

| Package | Reason |
|---|---|
| `kokoro` | 0.9.4 is already latest |
| `transformers` | `<5.23` — 5.23 breaks `faster-qwen3-tts` (see above) |
| `av` | `<19` — faster-whisper calls `av.open(metadata_errors=...)` |
| `openapi-python-client` | `<0.30` — 0.30 emits `httpx2` imports |

## Upgrade History

| Date | Action |
|---|---|
| 2026-03-14 | Bulk upgrade all packages to latest; switched cu124→cu128; resolved chatterbox/whisperx/torch conflicts via overrides; added en-core-web-sm URL dep to fix kokoro G2P pip-call issue in uv venvs |
| 2026-03-14 | Added `setuptools<81` override (setuptools 82 removed `pkg_resources`, breaking `perth` → chatterbox); fixed NeMo m4a support via ffmpeg pre-conversion in adapter; fixed chatterbox WAV output via soundfile (replacing torchaudio.save which needs torchcodec DLLs); documented qwen-asr/qwen-tts as upstream blockers on transformers 5.x |
| 2026-03-14 | Resolved all qwen-asr and qwen-tts transformers 5.x incompatibilities via adapter-level monkey-patching (7 distinct API breaks fixed); `TestTransformersSTT` and `TestVoiceClone` now pass on Windows; all 3 test suites green, lint clean |
| 2026-11-18 | 0.4.0 maintenance: torch 2.15/torchaudio 2.11/torchvision 0.29/torchcodec 0.17 on cu132; transformers pinned `>=5.22,<5.23`; `av>=17,<19`; NeMo 3.0; whisperx 3.8.6; `uv.lock` committed and CI uses `uv sync --locked`; dropped `qwen-asr` (Qwen3-ASR now native transformers + `*-hf` checkpoints); adapters decode with soundfile/ffmpeg so a broken torchcodec never reaches inference |
| 2026-11-18 | Fixed streaming WAV/PCM in Kokoro and Phonon: open-ended RIFF headers overflowed uint32 (`36 + 0xFFFFFFFF`), Kokoro's worker assumed numpy when kokoro 0.9 yields torch tensors, and both swallowed worker exceptions into a truncated 200. Streaming now propagates errors and has unit + E2E regression coverage |

## Future Upgrade Checklist

Quick reference for the next bulk upgrade. Follow the step-by-step in "How to Upgrade All Dependencies" above, plus these extra checks:

### Before upgrading

- [ ] Read this file end-to-end — past pain saves future pain
- [ ] Note which overrides exist and why (table above)
- [ ] Check if `faster-qwen3-tts` supports the newest transformers — if so, the `<5.23` pin and the monkey-patches can be removed

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
| Monkey-patches in `_compat.py` / `faster_qwen3_tts.py` | Remove once `faster-qwen3-tts` supports transformers 5.23+ |
| Monkey-patches in `faster_qwen3_tts.py` | Remove once `faster-qwen3-tts` supports transformers 5.x natively |
| `torchaudio.io` removal workaround in `nemo_adapter.py` | Remove if lhotse/NeMo adds native support for torchaudio 2.7+ |
| `soundfile` workaround in `chatterbox.py` | Remove if torchcodec ships Windows DLLs or torchaudio restores non-torchcodec backend |
