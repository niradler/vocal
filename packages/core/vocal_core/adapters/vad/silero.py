import importlib.util
import logging

import numpy as np

from .base import VADAdapter

logger = logging.getLogger(__name__)

SILERO_AVAILABLE = importlib.util.find_spec("silero_vad") is not None
ONNXRUNTIME_AVAILABLE = importlib.util.find_spec("onnxruntime") is not None

# Silero only accepts these window sizes.
_CHUNK_SAMPLES: dict[int, int] = {
    8000: 256,
    16000: 512,
}
_DEFAULT_CHUNK_SAMPLES = 512


class SileroVADAdapter(VADAdapter):
    """
    Silero VAD — neural voice activity detection.

    Runs on ONNX Runtime when available (2-4x faster on CPU and no torch graph
    overhead per frame), otherwise on PyTorch. The model is ~2 MB and MIT
    licensed.

    Incoming audio is buffered into Silero's required window (512 samples at
    16 kHz, 256 at 8 kHz) and every complete window is scored; the returned
    probability is the maximum over the windows completed in this call.
    """

    def __init__(self, use_onnx: bool | None = None) -> None:
        if not SILERO_AVAILABLE:
            raise ImportError("silero-vad failed to import. It is a required dependency — reinstall with: pip install --upgrade silero-vad")
        from silero_vad import load_silero_vad

        self.backend = "onnx" if (use_onnx if use_onnx is not None else ONNXRUNTIME_AVAILABLE) else "torch"
        try:
            self._model = load_silero_vad(onnx=self.backend == "onnx")
        except Exception:
            if self.backend != "onnx":
                raise
            logger.warning("Silero ONNX runtime unavailable, falling back to torch", exc_info=True)
            self.backend = "torch"
            self._model = load_silero_vad(onnx=False)

        self._buffer = np.zeros(0, dtype=np.float32)
        self._last_prob: float = 0.0

    def get_probability(self, pcm_bytes: bytes, sample_rate: int) -> float:
        if not pcm_bytes:
            return self._last_prob

        chunk_size = _CHUNK_SAMPLES.get(sample_rate, _DEFAULT_CHUNK_SAMPLES)
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Keep only the unprocessed tail; avoid re-concatenating the whole
        # history on every call (that made long utterances quadratic).
        if self._buffer.size:
            samples = np.concatenate((self._buffer, samples))

        complete = (samples.size // chunk_size) * chunk_size
        if complete == 0:
            self._buffer = samples
            return self._last_prob

        import torch

        probs: list[float] = []
        # silero-vad 6.x validates `x.dim()`, so both its ONNX wrapper and the
        # torch model require a tensor — even though the ONNX path only uses
        # the tensor to build its input dict.
        with torch.no_grad():
            for start in range(0, complete, chunk_size):
                window = torch.from_numpy(samples[start : start + chunk_size]).unsqueeze(0)
                probs.append(float(self._model(window, sample_rate).item()))

        self._buffer = samples[complete:].copy()
        self._last_prob = max(probs)
        return self._last_prob

    def reset(self) -> None:
        self._buffer = np.zeros(0, dtype=np.float32)
        self._last_prob = 0.0
        try:
            self._model.reset_states()
        except Exception:
            pass
