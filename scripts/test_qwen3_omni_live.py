"""Live smoke test for Qwen-Omni STT and TTS adapters.

Tests with Qwen2.5-Omni-3B (small enough for consumer GPUs).

Usage:
    uv run python scripts/test_qwen3_omni_live.py
"""

import asyncio
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

MODEL_ID = "Qwen/Qwen2.5-Omni-3B"


def create_test_audio(path: str, duration: float = 2.0, sample_rate: int = 16000) -> None:
    """Create a simple sine-wave WAV file for testing."""
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes((audio * 32767).astype(np.int16).tobytes())


def find_model_path() -> Path:
    from huggingface_hub import scan_cache_dir

    cache = scan_cache_dir()
    for repo in cache.repos:
        if repo.repo_id == MODEL_ID:
            for rev in repo.revisions:
                return Path(rev.snapshot_path)
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(MODEL_ID))


async def test_stt(model_path: Path) -> bool:
    print("\n=== Testing Qwen-Omni STT ===")
    from vocal_core.adapters.stt.qwen3_omni import Qwen3OmniSTTAdapter

    adapter = Qwen3OmniSTTAdapter()

    print("Loading model for STT...")
    t0 = time.time()
    await adapter.load_model(model_path, device="auto")
    print(f"Loaded in {time.time() - t0:.1f}s")
    print(f"Model info: {adapter.get_model_info()}")

    assert adapter.is_loaded(), "Model should be loaded"

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        test_wav = f.name
    create_test_audio(test_wav)

    print(f"Transcribing test audio (sine wave): {test_wav}")
    t0 = time.time()
    result = await adapter.transcribe(audio=test_wav, language="en")
    elapsed = time.time() - t0
    print(f"Transcription: '{result.text}'")
    print(f"Language: {result.language}, Duration: {result.duration:.2f}s")
    print(f"Inference: {elapsed:.2f}s")

    Path(test_wav).unlink(missing_ok=True)

    await adapter.unload_model()
    assert not adapter.is_loaded(), "Model should be unloaded"
    print("STT test PASSED")
    return True


async def test_tts(model_path: Path) -> bool:
    print("\n=== Testing Qwen-Omni TTS ===")
    from vocal_core.adapters.tts.qwen3_omni import Qwen3OmniTTSAdapter

    adapter = Qwen3OmniTTSAdapter()

    print("Loading model for TTS...")
    t0 = time.time()
    await adapter.load_model(model_path, device="auto")
    print(f"Loaded in {time.time() - t0:.1f}s")
    print(f"Model info: {adapter.get_model_info()}")
    print(f"Capabilities: {adapter.get_capabilities()}")

    assert adapter.is_loaded(), "Model should be loaded"

    voices = await adapter.get_voices()
    print(f"Available voices: {[v.id for v in voices]}")

    test_text = "Hello, this is a test of Qwen Omni text to speech."
    print(f"Synthesizing: '{test_text}'")
    t0 = time.time()
    result = await adapter.synthesize(
        text=test_text,
        voice="Ethan",
        output_format="wav",
    )
    elapsed = time.time() - t0
    print(f"TTS result: {len(result.audio_data)} bytes, {result.sample_rate}Hz, {result.duration:.2f}s")
    print(f"Inference: {elapsed:.2f}s")

    out_path = Path("test_qwen_omni_output.wav")
    out_path.write_bytes(result.audio_data)
    print(f"Saved to {out_path}")

    await adapter.unload_model()
    assert not adapter.is_loaded(), "Model should be unloaded"
    print("TTS test PASSED")
    return True


async def main():
    print(f"Qwen-Omni Live Smoke Test ({MODEL_ID})")
    print("=" * 50)

    model_path = find_model_path()
    print(f"Model path: {model_path}")

    stt_ok = False
    tts_ok = False

    try:
        stt_ok = await test_stt(model_path)
    except Exception as e:
        print(f"STT test FAILED: {e}")
        import traceback
        traceback.print_exc()

    try:
        tts_ok = await test_tts(model_path)
    except Exception as e:
        print(f"TTS test FAILED: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 50)
    print(f"STT: {'PASSED' if stt_ok else 'FAILED'}")
    print(f"TTS: {'PASSED' if tts_ok else 'FAILED'}")

    if not (stt_ok and tts_ok):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
