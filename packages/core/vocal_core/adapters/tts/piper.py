import asyncio
import json
import logging
import os
import platform
import subprocess
import tempfile
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import aiofiles
import numpy as np

from ...utils import detect_device
from .base import TTSAdapter, TTSResult, Voice

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_SAMPLE_RATE = int(os.getenv("VOCAL_TTS_SAMPLE_RATE", "16000"))

try:
    from piper import PiperVoice

    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False

try:
    import pyttsx3

    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    import scipy.signal

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


SUPPORTED_FORMATS = {"mp3", "opus", "aac", "flac", "wav", "pcm"}

# ffmpeg output flags per format
_FFMPEG_FORMAT_ARGS: dict[str, list[str]] = {
    "mp3": ["-f", "mp3", "-acodec", "libmp3lame", "-q:a", "2"],
    "opus": ["-f", "opus", "-acodec", "libopus"],
    "aac": ["-f", "adts", "-acodec", "aac"],
    "flac": ["-f", "flac", "-acodec", "flac"],
    "wav": ["-f", "wav", "-acodec", "pcm_s16le"],
    "pcm": ["-f", "s16le", "-acodec", "pcm_s16le"],
}


def _convert_audio(path: str, target_format: str = "mp3", target_sample_rate: int = DEFAULT_OUTPUT_SAMPLE_RATE) -> tuple[bytes, int, float]:
    """Convert any audio file to the requested format via ffmpeg.

    Accepts any audio input (WAV, AIFF, etc.) and converts to the target format.
    Returns (audio_data, sample_rate, duration).
    """
    if target_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{target_format}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}")

    # Probe duration and sample rate from source
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            check=True,
            capture_output=True,
            timeout=5,
        )
        streams = json.loads(probe.stdout).get("streams", [{}])
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), streams[0] if streams else {})
        duration = float(audio_stream.get("duration", 0))
    except (FileNotFoundError, Exception) as e:
        logger.warning(f"ffprobe failed: {e}, using defaults")
        duration = 0.0

    # Convert to target format with resampling
    ext = target_format if target_format != "pcm" else "raw"
    out_path = path + f".converted.{ext}"
    fmt_args = _FFMPEG_FORMAT_ARGS[target_format]

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-ar", str(target_sample_rate)] + fmt_args + [out_path],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg conversion timed out after 60s")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg is required for audio format conversion. Install ffmpeg: brew install ffmpeg (macOS), apt install ffmpeg (Linux), choco install ffmpeg (Windows)")

    with open(out_path, "rb") as f:
        audio_data = f.read()
    os.unlink(out_path)

    # Recalculate duration based on resampled rate
    if duration > 0:
        duration = duration
    elif target_format == "pcm":
        duration = len(audio_data) / (target_sample_rate * 2)

    return audio_data, target_sample_rate, duration


class PiperTTSAdapter(TTSAdapter):
    """
    Piper TTS adapter with GPU optimization

    Piper is a fast, local neural text-to-speech system that produces
    high-quality voices. Models are downloaded from HuggingFace.
    Automatically uses GPU when available for faster synthesis.
    """

    def __init__(self):
        self.model = None
        self.model_path: Path | None = None
        self.config = None
        self._voices_cache: list[Voice] | None = None
        self.device: str = "cpu"

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        """
        Load Piper TTS model with GPU support

        Args:
            model_path: Path to model files (.onnx and .json)
            device: Device to load model on (cpu/cuda/auto)
            **kwargs: Additional parameters (use_cuda=True for GPU)
        """
        if not PIPER_AVAILABLE:
            raise ImportError("piper-tts is required for TTS. Install with: uv sync --extra piper")

        self.model_path = model_path
        onnx_path = model_path / "model.onnx"
        config_path = model_path / "config.json"

        if not onnx_path.exists() or not config_path.exists():
            raise FileNotFoundError(f"Model files not found at {model_path}. Expected model.onnx and config.json")

        if device == "auto":
            self.device = detect_device()
        else:
            self.device = device

        use_cuda = self.device == "cuda" and kwargs.get("use_cuda", True)

        if use_cuda:
            logger.info("Loading Piper model with CUDA acceleration")
        else:
            logger.info("Loading Piper model on CPU")

        self.model = PiperVoice.load(str(onnx_path), str(config_path), use_cuda=use_cuda)

        async with aiofiles.open(config_path) as f:
            content = await f.read()
            self.config = json.loads(content)

        logger.info(f"Piper model loaded successfully on {self.device}")

    async def unload_model(self) -> None:
        """Unload model from memory"""
        self.model = None
        self.config = None
        self._voices_cache = None

        if self.device == "cuda":
            try:
                import torch

                torch.cuda.empty_cache()
                logger.info("GPU memory cleared")
            except Exception as e:
                logger.warning(f"Failed to clear GPU cache: {e}")

    def is_loaded(self) -> bool:
        """Check if model is currently loaded"""
        return self.model is not None

    def get_model_info(self) -> dict:
        """Get information about the loaded model"""
        if not self.is_loaded():
            return {"status": "not_loaded"}

        info = {
            "status": "loaded",
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "config": self.config,
        }

        if self.device == "cuda":
            try:
                import torch

                if torch.cuda.is_available():
                    info["gpu_name"] = torch.cuda.get_device_name(0)
                    info["vram_allocated_gb"] = torch.cuda.memory_allocated(0) / (1024**3)
            except Exception:
                pass

        return info

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "mp3",
        **kwargs,
    ) -> TTSResult:
        """
        Synthesize text to speech with GPU acceleration

        Args:
            text: Text to convert to speech
            voice: Voice ID (not used, Piper uses model-specific voice)
            speed: Speech speed multiplier
            pitch: Voice pitch multiplier (not supported by Piper)
            output_format: Output audio format (mp3, opus, aac, flac, wav, pcm)
            **kwargs: Additional parameters

        Returns:
            TTSResult with audio data
        """
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if output_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{output_format}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}")

        audio_chunks = []

        for audio_chunk in self.model.synthesize_stream_raw(text):
            audio_chunks.append(audio_chunk)

        audio_data = b"".join(audio_chunks)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        if speed != 1.0:
            if SCIPY_AVAILABLE:
                audio_array = scipy.signal.resample(audio_array, int(len(audio_array) / speed)).astype(np.int16)
            else:
                logger.warning("scipy not available, speed adjustment disabled")

        sample_rate = self.config.get("sample_rate", 22050)

        # Write intermediate WAV to temp file, then convert to target format
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_array.tobytes())

            audio_bytes, sample_rate, duration = _convert_audio(temp_path, output_format)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        return TTSResult(
            audio_data=audio_bytes,
            sample_rate=sample_rate,
            duration=duration,
            format=output_format,
        )

    async def get_voices(self) -> list[Voice]:
        """
        Get list of available voices

        For Piper, each model is a voice, so this returns info about the loaded model.
        """
        if not self.is_loaded():
            return []

        if self._voices_cache:
            return self._voices_cache

        model_name = self.model_path.name if self.model_path else "unknown"
        language = self.config.get("language", {}).get("code", "en")

        voice = Voice(
            id=model_name,
            name=model_name,
            language=language,
            gender=self.config.get("speaker_id_map", {}).get("gender"),
        )

        self._voices_cache = [voice]
        return self._voices_cache


class SimpleTTSAdapter(TTSAdapter):
    """
    Simple TTS adapter using system native TTS commands.

    Uses the best available system TTS on each platform:
    - macOS: `say` command (NSSpeechSynthesizer)
    - Linux: `espeak` / `espeak-ng`
    - Windows: pyttsx3 (SAPI5)

    Falls back to pyttsx3 if native commands are not available.
    No model downloads required.
    """

    def __init__(self):
        self._loaded = False
        self._engine = None  # pyttsx3 engine, used on Windows and for voice listing

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if PYTTSX3_AVAILABLE:
            self._engine = pyttsx3.init()
        self._loaded = True

    async def unload_model(self) -> None:
        if self._engine:
            self._engine.stop()
            self._engine = None
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def get_model_info(self) -> dict:
        if not self._loaded:
            return {"status": "not_loaded"}
        return {"status": "loaded", "engine": "system", "backend": "native"}

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "mp3",
        **kwargs,
    ) -> TTSResult:
        if not self._loaded:
            raise RuntimeError("Engine not initialized. Call load_model() first.")

        if output_format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{output_format}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            # Run blocking TTS in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                await loop.run_in_executor(
                    executor,
                    self._synthesize_to_file,
                    text,
                    temp_path,
                    voice,
                    speed,
                )

            # Run blocking ffmpeg conversion in thread pool
            with ThreadPoolExecutor(max_workers=1) as executor:
                audio_data, sample_rate, duration = await loop.run_in_executor(
                    executor,
                    _convert_audio,
                    temp_path,
                    output_format,
                )

            return TTSResult(audio_data=audio_data, sample_rate=sample_rate, duration=duration, format=output_format)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _synthesize_to_file(self, text: str, path: str, voice: str | None = None, speed: float = 1.0) -> None:
        """Synthesize text to file using the best available system TTS."""
        system = platform.system()

        if system == "Darwin":
            self._say_macos(text, path, voice=voice, speed=speed)
        elif system == "Linux":
            self._say_linux(text, path, voice=voice, speed=speed)
        else:
            self._say_pyttsx3(text, path, voice=voice, speed=speed)

    def _say_macos(self, text: str, path: str, voice: str | None = None, speed: float = 1.0) -> None:
        """Use macOS `say` command."""
        cmd = ["say"]
        if voice:
            cmd += ["-v", voice]
        rate = int(200 * speed)
        cmd += ["-r", str(rate), "-o", path, "--data-format=LEI16@22050", text]
        subprocess.run(cmd, check=True, capture_output=True, timeout=20)

    def _say_linux(self, text: str, path: str, voice: str | None = None, speed: float = 1.0) -> None:
        """Use espeak/espeak-ng on Linux."""
        wpm = int(175 * speed)
        for espeak_cmd in ["espeak-ng", "espeak"]:
            try:
                cmd = [espeak_cmd, "-w", path, "-s", str(wpm)]
                if voice:
                    cmd += ["-v", voice]
                cmd.append(text)
                subprocess.run(cmd, check=True, capture_output=True, timeout=20)
                return
            except FileNotFoundError:
                continue
        # Fallback to pyttsx3
        self._say_pyttsx3(text, path, voice=voice, speed=speed)

    def _say_pyttsx3(self, text: str, path: str, voice: str | None = None, speed: float = 1.0) -> None:
        """Use pyttsx3 (Windows SAPI5 or fallback)."""
        if not self._engine:
            raise RuntimeError("No TTS engine available. Install pyttsx3 or espeak.")

        if voice:
            for v in self._engine.getProperty("voices"):
                if v.id == voice or v.name == voice:
                    self._engine.setProperty("voice", v.id)
                    break

        rate = self._engine.getProperty("rate")
        self._engine.setProperty("rate", int(rate * speed))

        self._engine.save_to_file(text, path)

        # Run with timeout to prevent hanging (Windows SAPI5 can hang)
        def run_engine():
            try:
                self._engine.runAndWait()
            except Exception as e:
                logger.warning(f"pyttsx3: Engine error: {e}")

        thread = threading.Thread(target=run_engine, daemon=True)
        thread.start()
        thread.join(timeout=10.0)

        # Give it a moment to finalize file writes
        if thread.is_alive():
            logger.warning("pyttsx3: Engine timeout after 10s, continuing with partial output")
            time.sleep(0.5)

        if not os.path.exists(path) or os.path.getsize(path) == 0:
            raise RuntimeError(f"pyttsx3 failed to create audio file at {path}")

    async def get_voices(self) -> list[Voice]:
        if not self._engine:
            return []
        voices = []
        for v in self._engine.getProperty("voices"):
            voices.append(
                Voice(
                    id=v.id,
                    name=v.name,
                    language=v.languages[0] if v.languages else "en",
                    gender=None,
                )
            )
        return voices


__all__ = ["PiperTTSAdapter", "SimpleTTSAdapter"]
