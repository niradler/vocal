"""Unit tests for pure audio utility functions shared across routes."""

import struct

import numpy as np
import pytest


def _make_pcm16(samples: list[int]) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


def _rms(pcm_bytes: bytes) -> float:
    if not pcm_bytes:
        return 0.0
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(arr**2))) if arr.size > 0 else 0.0


def _resample_pcm16(pcm_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
    if from_rate == to_rate:
        return bytes(pcm_bytes)
    arr = np.frombuffer(bytes(pcm_bytes), dtype=np.int16).astype(np.float32)
    if arr.size == 0:
        return b""
    new_len = int(len(arr) * to_rate / from_rate)
    indices = np.linspace(0, len(arr) - 1, new_len)
    resampled = np.interp(indices, np.arange(len(arr)), arr).astype(np.int16)
    return resampled.tobytes()


def test_rms_silence():
    silence = _make_pcm16([0] * 160)
    assert _rms(silence) == 0.0


def test_rms_signal():
    signal = _make_pcm16([1000] * 160)
    assert _rms(signal) == pytest.approx(1000.0)


def test_rms_empty():
    assert _rms(b"") == 0.0


def test_resample_same_rate():
    data = _make_pcm16([100, 200, 300])
    assert _resample_pcm16(data, 16000, 16000) == data


def test_resample_upsample():
    data = _make_pcm16([0, 1000, 0])
    result = _resample_pcm16(data, 16000, 24000)
    assert len(result) > len(data)
    assert len(result) % 2 == 0


def test_resample_downsample():
    data = _make_pcm16([i * 100 for i in range(100)])
    result = _resample_pcm16(data, 24000, 16000)
    assert len(result) < len(data)


def test_resample_empty():
    assert _resample_pcm16(b"", 16000, 24000) == b""
