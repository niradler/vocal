"""Unit tests for PCM16 resampling helpers (streaming and one-shot)."""

import numpy as np

from vocal_core.audio.resample import PCM16Resampler, float_to_pcm16, pcm16_to_float, resample_pcm16


def sine(freq: float, seconds: float, rate: int, amp: int = 8000) -> np.ndarray:
    t = np.arange(int(seconds * rate)) / rate
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def zero_crossings(samples: np.ndarray) -> int:
    signs = np.signbit(samples.astype(np.int32))
    return int(np.count_nonzero(signs[1:] != signs[:-1]))


def test_pcm_float_round_trip():
    pcm = sine(440, 0.05, 16000)
    restored = float_to_pcm16(pcm16_to_float(pcm.tobytes()))
    got = np.frombuffer(restored, dtype=np.int16)
    assert np.array_equal(got, pcm)


def test_float_to_pcm16_clips():
    out = np.frombuffer(float_to_pcm16(np.array([1e6, -1e6], dtype=np.float32)), dtype=np.int16)
    assert out.tolist() == [32767, -32768]


def test_one_shot_resample_changes_length_and_preserves_pitch():
    src = sine(440, 0.5, 16000)
    out = np.frombuffer(resample_pcm16(src.tobytes(), 16000, 24000), dtype=np.int16)
    assert abs(len(out) - len(src) * 3 // 2) <= 2
    # Same tone, same rate of zero crossings per second (~2 * 440).
    src_hz = zero_crossings(src) / 0.5
    out_hz = zero_crossings(out) / (len(out) / 24000)
    assert abs(src_hz - out_hz) / src_hz < 0.05


def test_one_shot_resample_same_rate_is_passthrough():
    src = sine(440, 0.05, 16000).tobytes()
    assert resample_pcm16(src, 16000, 16000) == src
    assert resample_pcm16(b"", 24000, 16000) == b""


def test_streaming_resampler_matches_one_shot_length():
    src = sine(440, 0.5, 16000)
    resampler = PCM16Resampler(16000, 24000)
    chunks = [resampler.process(src[i : i + 1600].tobytes()) for i in range(0, len(src), 1600)]
    total = sum(len(c) for c in chunks)
    expected = int(round(len(src) * 24000 / 16000)) * 2
    assert abs(total - expected) <= 4


def test_streaming_resampler_is_continuous_across_chunks():
    """No clicks: the output must not jump at chunk boundaries."""
    src = sine(440, 0.3, 16000)
    resampler = PCM16Resampler(16000, 24000)
    out = b"".join(resampler.process(src[i : i + 320].tobytes()) for i in range(0, len(src), 320))
    samples = np.frombuffer(out, dtype=np.int16)
    assert samples.size > 0
    # A click shows up as a step much larger than one sine step.
    steps = np.abs(np.diff(samples.astype(np.int32)))
    assert int(steps.max()) < 1200


def test_streaming_resampler_same_rate_passthrough():
    resampler = PCM16Resampler(16000, 16000)
    chunk = sine(440, 0.05, 16000).tobytes()
    assert resampler.process(chunk) == chunk
    assert resampler.process(b"") == b""


def test_streaming_resampler_rejects_bad_rates():
    for bad in (0, -1):
        try:
            PCM16Resampler(bad, 16000)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError")
