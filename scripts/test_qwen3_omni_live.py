"""Live smoke test for the Qwen-Omni adapters.

- STT runs in-process (transformers) against Qwen2.5-Omni-3B pulled into Vocal.
- TTS is a proxy to a vLLM-Omni / SGLang-Omni engine (QWEN_OMNI_TTS_URL). It is
  exercised only if that engine is reachable; otherwise it is reported as skipped.

Usage:
    uv run python scripts/test_qwen3_omni_live.py
"""

import asyncio
import sys
import time
from pathlib import Path

MODEL_ID = "Qwen/Qwen2.5-Omni-3B"
REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_AUDIO = REPO_ROOT / "test_assets" / "audio" / "en-AU-WilliamNeural.mp3"


def find_model_path() -> Path:
    from vocal_core import ModelRegistry

    registry = ModelRegistry()
    local = registry.get_model_path(MODEL_ID)
    if local:
        return local

    from huggingface_hub import scan_cache_dir

    cache = scan_cache_dir()
    for repo in cache.repos:
        if repo.repo_id == MODEL_ID:
            for rev in repo.revisions:
                return Path(rev.snapshot_path)
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(MODEL_ID))


async def test_stt(model_path: Path) -> bool:
    print("\n=== Testing Qwen-Omni STT (in-process) ===")
    from vocal_core.adapters.stt.qwen3_omni import Qwen3OmniSTTAdapter

    adapter = Qwen3OmniSTTAdapter()
    print("Loading model for STT...")
    t0 = time.time()
    await adapter.load_model(model_path, device="auto")
    print(f"Loaded in {time.time() - t0:.1f}s")
    print(f"Model info: {adapter.get_model_info()}")
    assert adapter.is_loaded(), "Model should be loaded"

    if not FIXTURE_AUDIO.exists():
        print(f"Fixture audio missing: {FIXTURE_AUDIO}")
        return False

    print(f"Transcribing fixture audio: {FIXTURE_AUDIO}")
    t0 = time.time()
    result = await adapter.transcribe(audio=FIXTURE_AUDIO, language="en")
    print(f"Transcription: '{result.text}'")
    print(f"Language: {result.language}, Duration: {result.duration:.2f}s, Inference: {time.time() - t0:.2f}s")
    assert result.text.strip(), "Transcription should not be empty for real speech"

    await adapter.unload_model()
    assert not adapter.is_loaded(), "Model should be unloaded"
    print("STT test PASSED")
    return True


async def test_tts(model_path: Path) -> str:
    """Returns 'passed', 'skipped' (no engine), or 'failed'."""
    print("\n=== Testing Qwen-Omni TTS (vLLM-Omni proxy) ===")
    import httpx

    from vocal_core.adapters.tts.qwen3_omni import Qwen3OmniTTSAdapter

    adapter = Qwen3OmniTTSAdapter()
    await adapter.load_model(model_path, device="auto")
    print(f"Proxy target: {adapter.base_url} (model {adapter._model_id})")
    print(f"Available voices: {[v.id for v in await adapter.get_voices()]}")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(f"{adapter.base_url}/v1/models")
    except httpx.HTTPError as exc:
        print(f"TTS SKIPPED — no vLLM-Omni engine at {adapter.base_url} ({type(exc).__name__}).")
        print("Start one, e.g.: vllm serve Qwen/Qwen2.5-Omni-3B --omni, and set QWEN_OMNI_TTS_URL.")
        return "skipped"

    test_text = "Hello, this is a test of Qwen Omni text to speech."
    print(f"Synthesizing: '{test_text}'")
    t0 = time.time()
    result = await adapter.synthesize(text=test_text, voice="Ethan", output_format="wav")
    print(f"TTS result: {len(result.audio_data)} bytes, {result.sample_rate}Hz, Inference: {time.time() - t0:.2f}s")
    assert len(result.audio_data) > 1000, "Synthesized audio should not be empty"

    import tempfile

    out_path = Path(tempfile.gettempdir()) / "test_qwen_omni_output.wav"
    out_path.write_bytes(result.audio_data)
    print(f"Saved to {out_path}")
    print("TTS test PASSED")
    return "passed"


async def main():
    print(f"Qwen-Omni Live Smoke Test ({MODEL_ID})")
    print("=" * 50)

    model_path = find_model_path()
    print(f"Model path: {model_path}")

    stt_ok = False
    tts_status = "failed"
    try:
        stt_ok = await test_stt(model_path)
    except Exception as e:
        print(f"STT test FAILED: {e}")
        import traceback

        traceback.print_exc()

    try:
        tts_status = await test_tts(model_path)
    except Exception as e:
        print(f"TTS test FAILED: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 50)
    print(f"STT: {'PASSED' if stt_ok else 'FAILED'}")
    print(f"TTS: {tts_status.upper()}")

    # STT must pass; TTS passes or is skipped when no engine is running.
    if not stt_ok or tts_status == "failed":
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
