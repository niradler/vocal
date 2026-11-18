"""Streaming PCM16 helpers (stateful, cross-platform, no scipy requirement)."""

from __future__ import annotations

import numpy as np


def pcm16_to_float(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32)


def float_to_pcm16(samples: np.ndarray) -> bytes:
    return np.clip(samples, -32768, 32767).astype(np.int16).tobytes()


def resample_pcm16(pcm: bytes | bytearray, from_rate: int, to_rate: int) -> bytes:
    """One-shot resample for a complete buffer."""
    if from_rate == to_rate or not pcm:
        return bytes(pcm)
    arr = pcm16_to_float(bytes(pcm))
    new_len = max(1, int(round(len(arr) * to_rate / from_rate)))
    positions = np.linspace(0, len(arr) - 1, new_len)
    return float_to_pcm16(np.interp(positions, np.arange(len(arr)), arr))


class PCM16Resampler:
    """Stateful linear resampler for chunk-by-chunk streaming.

    Keeps the fractional read position and the previous sample between calls so
    chunk boundaries do not click or drift.
    """

    def __init__(self, from_rate: int, to_rate: int) -> None:
        if from_rate <= 0 or to_rate <= 0:
            raise ValueError("sample rates must be positive")
        self.from_rate = from_rate
        self.to_rate = to_rate
        self.step = from_rate / to_rate
        self._prev = 0.0
        self._phase = 0.0

    def process(self, pcm: bytes) -> bytes:
        if not pcm:
            return b""
        if self.from_rate == self.to_rate:
            return bytes(pcm)

        new = pcm16_to_float(pcm)
        x = np.concatenate((np.array([self._prev], dtype=np.float32), new))

        out: list[float] = []
        pos = self._phase
        last = len(x) - 1
        while pos < last:
            index = int(pos)
            frac = pos - index
            out.append(float(x[index] * (1.0 - frac) + x[index + 1] * frac))
            pos += self.step

        self._phase = pos - last
        self._prev = float(x[-1])
        if not out:
            return b""
        return float_to_pcm16(np.asarray(out, dtype=np.float32))

    def flush(self) -> bytes:
        self._phase = 0.0
        return b""
