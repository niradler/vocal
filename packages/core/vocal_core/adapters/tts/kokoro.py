from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import re
import struct
import tempfile
import wave
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import torch
    from kokoro import KPipeline

from ...config import optional_dependency_install_hint
from .base import TTSAdapter, TTSCapabilities, TTSResult, Voice
from .piper import SUPPORTED_FORMATS, _convert_audio

logger = logging.getLogger(__name__)

KOKORO_AVAILABLE: bool = importlib.util.find_spec("kokoro") is not None and importlib.util.find_spec("torch") is not None

KOKORO_SAMPLE_RATE = 24000

# OpenAI-compatible clients send these names by default. Map the ones Kokoro
# ships a close equivalent for; anything else is rejected with a 400 listing
# the real voices instead of failing deep inside synthesis (issue #13).
OPENAI_VOICE_ALIASES: dict[str, str] = {
    "alloy": "af_alloy",
    "echo": "am_echo",
    "fable": "bm_fable",
    "onyx": "am_onyx",
    "nova": "af_nova",
    "shimmer": "af_sky",
}

_VOICE_ID_PATTERN = re.compile(r"^[a-z]{1,2}_[a-z0-9_]+$")


def _as_float_numpy(audio) -> np.ndarray:
    """Kokoro returns torch tensors (possibly on GPU); normalise to float32 numpy."""
    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    return np.asarray(audio, dtype=np.float32).reshape(-1)


LANG_CODE_TO_LANGUAGE = {
    "a": "en-us",
    "b": "en-gb",
    "j": "ja",
    "z": "zh",
    "e": "es",
    "f": "fr",
    "h": "hi",
    "i": "it",
    "p": "pt-br",
}

KOKORO_VOICE_DATA: dict[str, dict] = {
    "af_heart": {"lang": "a", "gender": "female"},
    "af_alloy": {"lang": "a", "gender": "female"},
    "af_aoede": {"lang": "a", "gender": "female"},
    "af_bella": {"lang": "a", "gender": "female"},
    "af_jessica": {"lang": "a", "gender": "female"},
    "af_kore": {"lang": "a", "gender": "female"},
    "af_nicole": {"lang": "a", "gender": "female"},
    "af_nova": {"lang": "a", "gender": "female"},
    "af_river": {"lang": "a", "gender": "female"},
    "af_sarah": {"lang": "a", "gender": "female"},
    "af_sky": {"lang": "a", "gender": "female"},
    "am_adam": {"lang": "a", "gender": "male"},
    "am_echo": {"lang": "a", "gender": "male"},
    "am_eric": {"lang": "a", "gender": "male"},
    "am_fenrir": {"lang": "a", "gender": "male"},
    "am_liam": {"lang": "a", "gender": "male"},
    "am_michael": {"lang": "a", "gender": "male"},
    "am_onyx": {"lang": "a", "gender": "male"},
    "am_puck": {"lang": "a", "gender": "male"},
    "am_santa": {"lang": "a", "gender": "male"},
    "bf_alice": {"lang": "b", "gender": "female"},
    "bf_emma": {"lang": "b", "gender": "female"},
    "bf_isabella": {"lang": "b", "gender": "female"},
    "bf_lily": {"lang": "b", "gender": "female"},
    "bm_daniel": {"lang": "b", "gender": "male"},
    "bm_fable": {"lang": "b", "gender": "male"},
    "bm_george": {"lang": "b", "gender": "male"},
    "bm_lewis": {"lang": "b", "gender": "male"},
    "jf_alpha": {"lang": "j", "gender": "female"},
    "jf_gongitsune": {"lang": "j", "gender": "female"},
    "jf_nezumi": {"lang": "j", "gender": "female"},
    "jf_tebukuro": {"lang": "j", "gender": "female"},
    "jm_kumo": {"lang": "j", "gender": "male"},
    "zf_xiaobei": {"lang": "z", "gender": "female"},
    "zf_xiaoni": {"lang": "z", "gender": "female"},
    "zf_xiaoxiao": {"lang": "z", "gender": "female"},
    "zf_xiaoyi": {"lang": "z", "gender": "female"},
    "zm_yunjian": {"lang": "z", "gender": "male"},
    "zm_yunxi": {"lang": "z", "gender": "male"},
    "zm_yunxia": {"lang": "z", "gender": "male"},
    "zm_yunyang": {"lang": "z", "gender": "male"},
    "ef_dora": {"lang": "e", "gender": "female"},
    "em_alex": {"lang": "e", "gender": "male"},
    "em_santa": {"lang": "e", "gender": "male"},
    "ff_siwis": {"lang": "f", "gender": "female"},
    "hf_alpha": {"lang": "h", "gender": "female"},
    "hf_beta": {"lang": "h", "gender": "female"},
    "hm_omega": {"lang": "h", "gender": "male"},
    "hm_psi": {"lang": "h", "gender": "male"},
    "if_sara": {"lang": "i", "gender": "female"},
    "im_nicola": {"lang": "i", "gender": "male"},
    "pf_dora": {"lang": "p", "gender": "female"},
    "pm_alex": {"lang": "p", "gender": "male"},
    "pm_santa": {"lang": "p", "gender": "male"},
}

KOKORO_VOICES = list(KOKORO_VOICE_DATA.keys())


def _wav_header_open_ended(sample_rate: int, num_channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """Return a WAV header for a stream of unknown length.

    Both the RIFF and data sizes are 0xFFFFFFFF ("unknown"), which players and
    ffmpeg accept for pipes. Adding 36 to 0xFFFFFFFF would overflow the 32-bit
    field and raise ``struct.error`` (the streaming-WAV 500 from issue #13).
    """
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    unknown_size = 0xFFFFFFFF
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        unknown_size,
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
        unknown_size,
    )


def resolve_voice_name(voice_id: str) -> str:
    """Map OpenAI voice names (alloy, onyx, ...) to Kokoro voice ids."""
    return OPENAI_VOICE_ALIASES.get(voice_id.strip().lower(), voice_id.strip())


def _voice_lang_code(voice_id: str) -> str:
    first = resolve_voice_name(voice_id.split(",")[0])
    return first[0] if first and first[0] in LANG_CODE_TO_LANGUAGE else "a"


class KokoroTTSAdapter(TTSAdapter):
    def __init__(self):
        self._pipelines: dict[str, KPipeline] = {}
        self._shared_model = None
        self.model_path: Path | None = None
        self.device: str = "cpu"

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not KOKORO_AVAILABLE:
            raise ImportError(optional_dependency_install_hint("kokoro"))

        import torch

        self.model_path = model_path
        self.device = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            await loop.run_in_executor(executor, self._load_sync)

    def _load_sync(self) -> None:
        import torch
        from kokoro import KPipeline

        primary = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", device=self.device)
        self._shared_model = primary.model
        self._pipelines["a"] = primary
        self._pipelines["b"] = KPipeline(lang_code="b", model=self._shared_model, repo_id="hexgrad/Kokoro-82M", device=self.device)

        if self.device == "cuda":
            vram = torch.cuda.memory_allocated(0) / (1024**3)
            logger.info(f"Kokoro loaded on GPU: {torch.cuda.get_device_name(0)} | VRAM={vram:.2f}GB")
        else:
            logger.info(f"Kokoro loaded on {self.device}")

    def _get_pipeline(self, lang_code: str) -> KPipeline:
        from kokoro import KPipeline

        if lang_code not in self._pipelines:
            self._pipelines[lang_code] = KPipeline(
                lang_code=lang_code,
                model=self._shared_model,
                repo_id="hexgrad/Kokoro-82M",
                device=self.device,
            )
            logger.info(f"Kokoro pipeline created for lang_code={lang_code}")
        return self._pipelines[lang_code]

    async def unload_model(self) -> None:
        self._pipelines.clear()
        self._shared_model = None
        if self.device == "cuda":
            try:
                import torch

                torch.cuda.empty_cache()
            except Exception:
                pass

    def is_loaded(self) -> bool:
        return bool(self._pipelines)

    def get_model_info(self) -> dict:
        if not self.is_loaded():
            return {"status": "not_loaded"}
        info: dict = {
            "status": "loaded",
            "device": self.device,
            "model_path": str(self.model_path),
            "sample_rate": KOKORO_SAMPLE_RATE,
            "loaded_lang_codes": list(self._pipelines.keys()),
        }
        if self.device == "cuda":
            try:
                import torch

                info["gpu_name"] = torch.cuda.get_device_name(0)
                info["vram_allocated_gb"] = torch.cuda.memory_allocated(0) / (1024**3)
            except Exception:
                pass
        return info

    def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_streaming=True,
            supports_voice_list=True,
            voice_mode="voice_id",
        )

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "mp3",
        **kwargs,
    ) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if output_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{output_format}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}")

        voice_id = voice or "af_heart"
        lang_code = _voice_lang_code(voice_id)
        loop = asyncio.get_running_loop()

        with ThreadPoolExecutor(max_workers=1) as executor:
            audio_array = await loop.run_in_executor(executor, self._synthesize_sync, text, voice_id, lang_code, speed)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(KOKORO_SAMPLE_RATE)
                wav_file.writeframes((audio_array * 32767).astype(np.int16).tobytes())

            with ThreadPoolExecutor(max_workers=1) as executor:
                audio_bytes, sample_rate, duration = await loop.run_in_executor(executor, _convert_audio, temp_path, output_format)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        return TTSResult(audio_data=audio_bytes, sample_rate=sample_rate, duration=duration, format=output_format)

    async def synthesize_stream(  # noqa: C901
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        output_format: str = "pcm",
        **kwargs,
    ) -> AsyncGenerator[bytes, None]:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if output_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{output_format}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}")

        if output_format not in ("pcm", "wav"):
            async for chunk in super().synthesize_stream(text=text, voice=voice, speed=speed, output_format=output_format, **kwargs):
                yield chunk
            return

        voice_id = voice or "af_heart"
        lang_code = _voice_lang_code(voice_id)
        loop = asyncio.get_running_loop()
        # (bytes | None for end-of-stream | Exception to re-raise)
        queue: asyncio.Queue = asyncio.Queue()

        def _run() -> None:
            try:
                pipeline = self._get_pipeline(lang_code)
                loaded_voice = self._load_voice(voice_id)
                # Split on sentence boundaries as well as newlines so a single
                # paragraph streams per sentence instead of one silent blob.
                for _, _, audio_chunk in pipeline(text, voice=loaded_voice, speed=speed, split_pattern=r"\n+|(?<=[.!?])\s+"):
                    samples = _as_float_numpy(audio_chunk)
                    if samples.size == 0:
                        continue
                    pcm_bytes = (samples * 32767).astype(np.int16).tobytes()
                    loop.call_soon_threadsafe(queue.put_nowait, pcm_bytes)
            except Exception as exc:  # surface thread failures instead of silence
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        if output_format == "wav":
            yield _wav_header_open_ended(KOKORO_SAMPLE_RATE)

        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(_run)

        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                if isinstance(chunk, Exception):
                    raise chunk
                yield chunk
        finally:
            executor.shutdown(wait=False)

    def _load_single_voice(self, voice_id: str) -> torch.Tensor | str:
        import torch

        voice_id = resolve_voice_name(voice_id)
        if self.model_path:
            voice_pt = self.model_path / "voices" / f"{voice_id}.pt"
            if voice_pt.exists():
                return torch.load(str(voice_pt), weights_only=True, map_location="cpu")
        logger.warning(f"Voice file not found locally for '{voice_id}', falling back to HF download")
        return voice_id

    def validate_voice(self, voice: str | None) -> None:
        """Reject names this backend cannot synthesize, with the valid list."""
        if not voice:
            return
        for part in voice.split(","):
            candidate = part.strip()
            if not candidate:
                continue
            resolved = resolve_voice_name(candidate)
            if resolved in KOKORO_VOICE_DATA:
                continue
            if self.model_path and (self.model_path / "voices" / f"{resolved}.pt").exists():
                continue
            # Kokoro can pull arbitrary voice ids from the Hub (af_bella, ...).
            if _VOICE_ID_PATTERN.match(resolved):
                continue
            valid = ", ".join(sorted(KOKORO_VOICE_DATA))
            raise ValueError(f"Unknown voice '{candidate}'. Available voices: {valid}")

    def _load_voice(self, voice_id: str) -> torch.Tensor | str:
        import torch

        parts = [p.strip() for p in voice_id.split(",") if p.strip()]
        if len(parts) == 1:
            return self._load_single_voice(parts[0])
        tensors = [self._load_single_voice(p) for p in parts]
        loaded = [t for t in tensors if isinstance(t, torch.Tensor)]
        if len(loaded) == len(tensors):
            return torch.stack(loaded).mean(dim=0)
        return voice_id

    def _synthesize_sync(self, text: str, voice_id: str, lang_code: str, speed: float) -> np.ndarray:
        pipeline = self._get_pipeline(lang_code)
        voice = self._load_voice(voice_id)
        chunks = [audio for _, _, audio in pipeline(text, voice=voice, speed=speed, split_pattern=r"\n+")]
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    async def get_voices(self) -> list[Voice]:
        if not self.is_loaded():
            return []

        return [
            Voice(
                id=voice_id,
                name=voice_id.replace("_", " ").title(),
                language=LANG_CODE_TO_LANGUAGE.get(meta["lang"], "en-us"),
                gender=meta["gender"],
            )
            for voice_id, meta in KOKORO_VOICE_DATA.items()
        ]


__all__ = ["KokoroTTSAdapter", "KOKORO_AVAILABLE", "KOKORO_VOICES", "KOKORO_VOICE_DATA", "KOKORO_SAMPLE_RATE"]
