import logging
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from faster_whisper import WhisperModel

from ...utils import optimize_inference_settings
from .base import (
    STTAdapter,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)

logger = logging.getLogger(__name__)


class FasterWhisperAdapter(STTAdapter):
    """
    faster-whisper implementation with GPU optimization

    Automatically detects and uses GPU when available for 4x+ faster inference.
    Falls back to optimized CPU inference when GPU is not available.
    """

    def __init__(self):
        self.model: WhisperModel | None = None
        self.model_path: Path | None = None
        self.device: str = "auto"
        self.compute_type: str = "auto"

    async def load_model(
        self,
        model_path: Path,
        device: str = "auto",
        compute_type: str = "auto",
        **kwargs,
    ) -> None:
        """
        Load Whisper model with optimal settings

        Args:
            model_path: Path to model files
            device: Device to use ('cpu', 'cuda', 'auto')
            compute_type: Compute type ('int8', 'int8_float16', 'float16', 'float32', 'auto')
            **kwargs: Additional faster-whisper parameters
        """
        if self.model is not None:
            await self.unload_model()

        self.model_path = model_path

        model_size = "base"
        if "tiny" in str(model_path):
            model_size = "tiny"
        elif "small" in str(model_path):
            model_size = "small"
        elif "medium" in str(model_path):
            model_size = "medium"
        elif "large" in str(model_path):
            model_size = "large"

        settings = optimize_inference_settings(device, model_size)

        self.device = settings["device"]
        self.compute_type = settings["compute_type"] if compute_type == "auto" else compute_type

        load_kwargs = {
            "device": self.device,
            "compute_type": self.compute_type,
        }

        if self.device == "cpu" and "num_workers" in settings:
            load_kwargs["num_workers"] = settings["num_workers"]
            load_kwargs["cpu_threads"] = settings.get("cpu_threads", 0)

        load_kwargs.update(kwargs)

        logger.info(f"Loading model from {model_path} on {self.device} with compute_type={self.compute_type}")

        self.model = WhisperModel(str(model_path), **load_kwargs)

        logger.info(f"Model loaded successfully on {self.device}")

    async def unload_model(self) -> None:
        """Unload model from memory and free GPU/CPU resources"""
        if self.model is not None:
            del self.model
            self.model = None
            self.model_path = None

            if self.device == "cuda":
                try:
                    import torch

                    torch.cuda.empty_cache()
                    logger.info("GPU memory cleared")
                except Exception as e:
                    logger.warning(f"Failed to clear GPU cache: {e}")

    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None

    def get_model_info(self) -> dict[str, Any]:
        """Get model information including device and optimization details"""
        info = {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "compute_type": self.compute_type,
            "loaded": self.is_loaded(),
        }

        if self.device == "cuda":
            try:
                import torch

                if torch.cuda.is_available():
                    info["gpu_name"] = torch.cuda.get_device_name(0)
                    info["vram_allocated_gb"] = torch.cuda.memory_allocated(0) / (1024**3)
                    info["vram_total_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            except Exception:
                pass

        return info

    async def transcribe(
        self,
        audio: str | Path | BinaryIO,
        language: str | None = None,
        task: str = "transcribe",
        temperature: float = 0.0,
        word_timestamps: bool = False,
        beam_size: int = 5,
        vad_filter: bool = True,
        **kwargs,
    ) -> TranscriptionResult:
        """
        Transcribe audio with optimized settings

        Args:
            audio: Audio file path or file-like object
            language: Language code or None for auto-detect
            task: 'transcribe' or 'translate'
            temperature: Sampling temperature (0.0 for greedy)
            word_timestamps: Enable word-level timestamps
            beam_size: Beam size (5 is a good balance, 1 for faster greedy decoding)
            vad_filter: Enable Voice Activity Detection for better performance
            **kwargs: Additional faster-whisper parameters

        Returns:
            TranscriptionResult with text and metadata
        """
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        temp_file = None
        try:
            if isinstance(audio, (str, Path)):
                audio_path = str(audio)
            else:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
                temp_file.write(audio.read())
                temp_file.close()
                audio_path = temp_file.name

            transcribe_kwargs = {
                "language": language,
                "task": task,
                "temperature": temperature,
                "word_timestamps": word_timestamps,
                "beam_size": beam_size,
                "vad_filter": vad_filter,
            }
            transcribe_kwargs.update(kwargs)

            segments, info = self.model.transcribe(audio_path, **transcribe_kwargs)

            segments_list = []
            words_list = []
            full_text = []

            for idx, segment in enumerate(segments):
                full_text.append(segment.text)

                seg = TranscriptionSegment(
                    id=idx,
                    start=segment.start,
                    end=segment.end,
                    text=segment.text,
                    avg_logprob=segment.avg_logprob,
                    no_speech_prob=segment.no_speech_prob,
                )
                segments_list.append(seg)

                if word_timestamps and hasattr(segment, "words"):
                    for word in segment.words:
                        words_list.append(
                            TranscriptionWord(
                                word=word.word,
                                start=word.start,
                                end=word.end,
                                probability=word.probability if hasattr(word, "probability") else None,
                            )
                        )

            return TranscriptionResult(
                text=" ".join(full_text).strip(),
                language=info.language,
                duration=info.duration if hasattr(info, "duration") else 0.0,
                segments=segments_list if segments_list else None,
                words=words_list if words_list else None,
            )

        finally:
            if temp_file and Path(temp_file.name).exists():
                Path(temp_file.name).unlink()
