import importlib.util
import logging

import numpy as np

from .base import VADAdapter

logger = logging.getLogger(__name__)

SILERO_AVAILABLE = importlib.util.find_spec("silero_vad") is not None

_CHUNK_SAMPLES: dict[int, int] = {
    8000: 256,
    16000: 512,
}
_DEFAULT_CHUNK_SAMPLES = 512


class SileroVADAdapter(VADAdapter):
    """
    Silero VAD — neural voice activity detection.

    Sub-1ms per chunk on CPU, 2MB model, MIT license.
    Buffers incoming audio to meet Silero's minimum window requirement
    (512 samples @ 16kHz, 256 @ 8kHz) and processes complete windows.

    Requires: pip install silero-vad
    """

    def __init__(self) -> None:
        if not SILERO_AVAILABLE:
            raise ImportError("silero-vad failed to import. It is a required dependency — reinstall with: pip install --upgrade silero-vad")
        from silero_vad import load_silero_vad

        self._model = load_silero_vad()
        self._buffer = np.array([], dtype=np.float32)
        self._last_prob: float = 0.0

    def get_probability(self, pcm_bytes: bytes, sample_rate: int) -> float:
        import torch

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        self._buffer = np.concatenate([self._buffer, samples])

        chunk_size = _CHUNK_SAMPLES.get(sample_rate, _DEFAULT_CHUNK_SAMPLES)

        if len(self._buffer) < chunk_size:
            return self._last_prob

        probs: list[float] = []
        while len(self._buffer) >= chunk_size:
            chunk = self._buffer[:chunk_size]
            self._buffer = self._buffer[chunk_size:]
            tensor = torch.from_numpy(chunk).unsqueeze(0)
            with torch.no_grad():
                prob = float(self._model(tensor, sample_rate).item())
            probs.append(prob)

        self._last_prob = max(probs)
        return self._last_prob

    def reset(self) -> None:
        self._buffer = np.array([], dtype=np.float32)
        self._last_prob = 0.0
        try:
            self._model.reset_states()
        except Exception:
            pass
