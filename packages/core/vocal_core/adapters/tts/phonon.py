import asyncio
import importlib.util
import io
import logging
import struct
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from ...config import optional_dependency_install_hint
from .base import AudioFormat, TTSAdapter, TTSCapabilities, TTSResult, Voice

logger = logging.getLogger(__name__)

PHONON_AVAILABLE = importlib.util.find_spec("ptts") is not None

PHONON_MODEL_REF = "hf://gradium/phonon-31m-en"
PHONON_QUANT = "q8_0"
PHONON_DEFAULT_VOICE = "default"
SUPPORTED_FORMATS = {AudioFormat.WAV, AudioFormat.PCM}
_WEIGHT_SUFFIXES = (".gguf", ".safetensors", ".bin")


def _wav_header_open_ended(sample_rate: int, num_channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """Return a WAV header with 0xFFFFFFFF data-chunk size for streaming (no seek-back needed)."""
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = 0xFFFFFFFF
    riff_size = 36 + data_size
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )


def _has_local_weights(model_path: Path) -> bool:
    return any(model_path.glob(f"*{suffix}") for suffix in _WEIGHT_SUFFIXES)


class PhononTTSAdapter(TTSAdapter):
    """Phonon 31M (ptts) — CPU-only, ~65 MB, 100+ shipped voices, no cloning."""

    def __init__(self) -> None:
        self.model: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self.sample_rate: int = 24000
        self._voices: list[dict[str, Any]] | None = None

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not PHONON_AVAILABLE:
            raise ImportError(optional_dependency_install_hint("phonon", "ptts"))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path)

    def _load_sync(self, model_path: Path) -> None:
        import ptts

        self.model_path = model_path
        self.device = "cpu"
        model_ref = str(model_path) if _has_local_weights(model_path) else PHONON_MODEL_REF
        logger.info("Loading Phonon 31M from %s (quant=%s)", model_ref, PHONON_QUANT)
        try:
            self.model = ptts.TTS(model_ref, lang="en", quant=PHONON_QUANT)
        except Exception as exc:
            if model_ref == PHONON_MODEL_REF:
                raise
            logger.warning("Could not load Phonon from %s (%s); falling back to %s", model_ref, exc, PHONON_MODEL_REF)
            self.model = ptts.TTS(PHONON_MODEL_REF, lang="en", quant=PHONON_QUANT)
        self.sample_rate = int(self.model.sample_rate)
        logger.info("Phonon 31M loaded (sr=%d, voices=%d)", self.sample_rate, len(self._catalog()))

    async def unload_model(self) -> None:
        self.model = None
        self.model_path = None
        self._voices = None

    def is_loaded(self) -> bool:
        return self.model is not None

    def get_model_info(self) -> dict:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "sample_rate": self.sample_rate,
            "loaded": self.is_loaded(),
            "backend": "phonon",
        }

    def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_streaming=True,
            supports_voice_list=True,
            supports_voice_clone=False,
            supports_voice_design=False,
            requires_gpu=False,
            voice_mode="voice_id",
        )

    def _catalog(self) -> list[dict[str, Any]]:
        if self._voices is None:
            import ptts

            try:
                self._voices = [voice for voice in ptts.catalog_voices() if isinstance(voice, dict)]
            except Exception as exc:  # pragma: no cover - catalog is optional upstream data
                logger.warning("Could not load Phonon voice catalog: %s", exc)
                self._voices = []
        return self._voices

    def _resolve_voice(self, voice: str | None) -> str:
        if not voice or voice == PHONON_DEFAULT_VOICE:
            return PHONON_DEFAULT_VOICE
        known = {item.get("voice_id") for item in self._catalog()}
        if voice in known:
            return voice
        names = {item.get("name"): item.get("voice_id") for item in self._catalog()}
        if voice in names and names[voice]:
            return str(names[voice])
        raise ValueError(f"Unknown Phonon voice '{voice}'. Use GET /v1/audio/voices?model=gradium/phonon-31m-en to list the {len(known)} shipped voices.")

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = AudioFormat.WAV,
        language: str | None = None,
        **kwargs,
    ) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")
        if output_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Phonon only supports WAV and PCM output. Requested: '{output_format}'.")
        if speed != 1.0 or pitch != 1.0:
            logger.debug("Phonon 31M ignores speed/pitch adjustments")

        voice_id = self._resolve_voice(voice)
        loop = asyncio.get_running_loop()
        audio = await loop.run_in_executor(None, self._synth_sync, text, voice_id)
        duration = float(audio.shape[0]) / float(self.sample_rate)

        if output_format == AudioFormat.PCM:
            return TTSResult(audio_data=(np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes(), sample_rate=self.sample_rate, duration=duration, format=AudioFormat.PCM)

        import soundfile as sf

        buf = io.BytesIO()
        sf.write(buf, audio, self.sample_rate, format="WAV", subtype="PCM_16")
        return TTSResult(audio_data=buf.getvalue(), sample_rate=self.sample_rate, duration=duration, format=AudioFormat.WAV)

    def _synth_sync(self, text: str, voice_id: str) -> np.ndarray:
        audio = self.model.synth(text, voice=voice_id)
        return np.asarray(audio, dtype=np.float32).reshape(-1)

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        output_format: str = "wav",
        **kwargs,
    ) -> AsyncGenerator[bytes, None]:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")
        if output_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Phonon only supports WAV and PCM streaming. Requested: '{output_format}'.")

        voice_id = self._resolve_voice(voice)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        def _run() -> None:
            try:
                with self.model.stream(text, voice=voice_id) as stream:
                    for chunk in stream:
                        samples = np.asarray(chunk, dtype=np.float32).reshape(-1)
                        if samples.size:
                            loop.call_soon_threadsafe(queue.put_nowait, (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16).tobytes())
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        if output_format == AudioFormat.WAV:
            yield _wav_header_open_ended(self.sample_rate)

        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(_run)
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            executor.shutdown(wait=False)

    async def get_voices(self) -> list[Voice]:
        return [Voice(id=str(item.get("voice_id")), name=str(item.get("name") or item.get("voice_id")), language=str(item.get("language") or "en")) for item in self._catalog() if item.get("voice_id")]
