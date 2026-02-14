from pathlib import Path
from typing import Optional, List
import io
import wave
import numpy as np
import logging

from .base import TTSAdapter, TTSResult, Voice
from ...utils import detect_device

logger = logging.getLogger(__name__)


class PiperTTSAdapter(TTSAdapter):
    """
    Piper TTS adapter with GPU optimization

    Piper is a fast, local neural text-to-speech system that produces
    high-quality voices. Models are downloaded from HuggingFace.
    Automatically uses GPU when available for faster synthesis.
    """

    def __init__(self):
        self.model = None
        self.model_path: Optional[Path] = None
        self.config = None
        self._voices_cache: Optional[List[Voice]] = None
        self.device: str = "cpu"

    async def load_model(
        self, model_path: Path, device: str = "auto", **kwargs
    ) -> None:
        """
        Load Piper TTS model with GPU support

        Args:
            model_path: Path to model files (.onnx and .json)
            device: Device to load model on (cpu/cuda/auto)
            **kwargs: Additional parameters (use_cuda=True for GPU)
        """
        try:
            from piper import PiperVoice
        except ImportError:
            raise ImportError(
                "piper-tts is required for TTS. Install with: uv sync --extra piper"
            )

        self.model_path = model_path
        onnx_path = model_path / "model.onnx"
        config_path = model_path / "config.json"

        if not onnx_path.exists() or not config_path.exists():
            raise FileNotFoundError(
                f"Model files not found at {model_path}. "
                "Expected model.onnx and config.json"
            )

        if device == "auto":
            self.device = detect_device()
        else:
            self.device = device

        use_cuda = self.device == "cuda" and kwargs.get("use_cuda", True)

        if use_cuda:
            logger.info("Loading Piper model with CUDA acceleration")
        else:
            logger.info("Loading Piper model on CPU")

        self.model = PiperVoice.load(
            str(onnx_path), str(config_path), use_cuda=use_cuda
        )

        with open(config_path) as f:
            import json

            self.config = json.load(f)

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
                    info["vram_allocated_gb"] = torch.cuda.memory_allocated(0) / (
                        1024**3
                    )
            except Exception:
                pass

        return info

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "wav",
        **kwargs,
    ) -> TTSResult:
        """
        Synthesize text to speech with GPU acceleration

        Args:
            text: Text to convert to speech
            voice: Voice ID (not used, Piper uses model-specific voice)
            speed: Speech speed multiplier
            pitch: Voice pitch multiplier (not supported by Piper)
            output_format: Output audio format (only 'wav' supported)
            **kwargs: Additional parameters

        Returns:
            TTSResult with audio data
        """
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if output_format != "wav":
            raise ValueError(f"Piper only supports WAV output, got: {output_format}")

        audio_chunks = []

        for audio_chunk in self.model.synthesize_stream_raw(text):
            audio_chunks.append(audio_chunk)

        audio_data = b"".join(audio_chunks)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        if speed != 1.0:
            try:
                import scipy.signal

                audio_array = scipy.signal.resample(
                    audio_array, int(len(audio_array) / speed)
                ).astype(np.int16)
            except ImportError:
                logger.warning("scipy not available, speed adjustment disabled")

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.config.get("sample_rate", 22050))
            wav_file.writeframes(audio_array.tobytes())

        wav_buffer.seek(0)
        audio_bytes = wav_buffer.read()

        sample_rate = self.config.get("sample_rate", 22050)
        duration = len(audio_array) / sample_rate

        return TTSResult(
            audio_data=audio_bytes,
            sample_rate=sample_rate,
            duration=duration,
            format="wav",
        )

    async def get_voices(self) -> List[Voice]:
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
    Simple TTS adapter using pyttsx3 for basic offline TTS

    This is a fallback adapter that doesn't require downloading models.
    Uses system TTS engines (SAPI5 on Windows, nsss on macOS, espeak on Linux).
    """

    def __init__(self):
        self.engine = None

    async def load_model(
        self, model_path: Path, device: str = "auto", **kwargs
    ) -> None:
        """
        Initialize pyttsx3 engine (no model download needed)

        Args:
            model_path: Not used for system TTS
            device: Not used for system TTS
        """
        try:
            import pyttsx3
        except ImportError:
            raise ImportError("pyttsx3 is required. Install with: uv add pyttsx3")

        self.engine = pyttsx3.init()

    async def unload_model(self) -> None:
        """Unload engine"""
        if self.engine:
            self.engine.stop()
            self.engine = None

    def is_loaded(self) -> bool:
        """Check if engine is initialized"""
        return self.engine is not None

    def get_model_info(self) -> dict:
        """Get information about the TTS engine"""
        if not self.is_loaded():
            return {"status": "not_loaded"}

        return {
            "status": "loaded",
            "engine": "pyttsx3",
            "backend": "system",
        }

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "wav",
        **kwargs,
    ) -> TTSResult:
        """
        Synthesize text to speech using system TTS

        Args:
            text: Text to convert to speech
            voice: Voice ID to use
            speed: Speech speed (words per minute, scaled by multiplier)
            pitch: Not supported by pyttsx3
            output_format: Only 'wav' supported

        Returns:
            TTSResult with audio data
        """
        if not self.is_loaded():
            raise RuntimeError("Engine not initialized. Call load_model() first.")

        if output_format != "wav":
            raise ValueError(f"Only WAV output supported, got: {output_format}")

        if voice:
            voices = self.engine.getProperty("voices")
            for v in voices:
                if v.id == voice or v.name == voice:
                    self.engine.setProperty("voice", v.id)
                    break

        rate = self.engine.getProperty("rate")
        self.engine.setProperty("rate", int(rate * speed))

        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            self.engine.save_to_file(text, temp_path)

            import threading
            import time

            def run_engine():
                try:
                    self.engine.runAndWait()
                except Exception as e:
                    logger.error(f"TTS engine error: {e}")

            thread = threading.Thread(target=run_engine, daemon=True)
            thread.start()
            thread.join(timeout=10.0)

            if thread.is_alive():
                logger.warning("TTS synthesis timeout, using current output")
                time.sleep(0.5)

            with open(temp_path, "rb") as f:
                audio_data = f.read()

            with wave.open(temp_path, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                n_frames = wav_file.getnframes()
                duration = n_frames / sample_rate

            return TTSResult(
                audio_data=audio_data,
                sample_rate=sample_rate,
                duration=duration,
                format="wav",
            )
        finally:
            import os

            if os.path.exists(temp_path):
                os.unlink(temp_path)

    async def get_voices(self) -> List[Voice]:
        """Get list of available system voices"""
        if not self.is_loaded():
            return []

        voices = []
        for voice in self.engine.getProperty("voices"):
            voices.append(
                Voice(
                    id=voice.id,
                    name=voice.name,
                    language=voice.languages[0] if voice.languages else "en",
                    gender=None,
                )
            )

        return voices


__all__ = ["PiperTTSAdapter", "SimpleTTSAdapter"]
