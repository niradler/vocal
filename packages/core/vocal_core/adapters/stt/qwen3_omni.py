import asyncio
import importlib.util
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from .base import STTAdapter, TranscriptionResult

logger = logging.getLogger(__name__)

QWEN3_OMNI_STT_AVAILABLE: bool = (
    importlib.util.find_spec("transformers") is not None
    and importlib.util.find_spec("torch") is not None
    and importlib.util.find_spec("qwen_omni_utils") is not None
)


def _detect_omni_generation(model_path: Path) -> str:
    """Detect whether this is a Qwen2.5-Omni or Qwen3-Omni model."""
    cfg_file = model_path / "config.json"
    if cfg_file.exists():
        with open(cfg_file) as f:
            model_type = json.load(f).get("model_type", "")
        if "qwen2_5_omni" in model_type or "qwen2.5" in model_type.lower():
            return "2.5"
    # Check directory name
    dir_lower = str(model_path).lower()
    if "qwen2.5" in dir_lower or "qwen2_5" in dir_lower:
        return "2.5"
    return "3"


class Qwen3OmniSTTAdapter(STTAdapter):
    """Qwen-Omni STT adapter using transformers.

    Supports both Qwen2.5-Omni and Qwen3-Omni models, auto-detecting
    the correct model class from config.json.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._processor: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self._generation: str = "3"  # "2.5" or "3"

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not QWEN3_OMNI_STT_AVAILABLE:
            raise ImportError(
                "transformers, torch, and qwen-omni-utils are required for Qwen-Omni. "
                "Install with: pip install transformers torch qwen-omni-utils"
            )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch

        from vocal_core.adapters._compat import apply_transformers_shims

        apply_transformers_shims()

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        dtype = torch.bfloat16 if resolved == "cuda" else torch.float32
        model_name = self._resolve_model_name(model_path)
        self._generation = _detect_omni_generation(model_path)

        logger.info("Loading Qwen%s-Omni STT from %s on %s", self._generation, model_path, resolved)

        if self._generation == "2.5":
            from transformers import Qwen2_5OmniForConditionalGeneration, Qwen2_5OmniProcessor

            self._processor = Qwen2_5OmniProcessor.from_pretrained(model_name)
            self._model = Qwen2_5OmniForConditionalGeneration.from_pretrained(
                model_name,
                torch_dtype=dtype,
                device_map="auto",
            )
        else:
            from transformers import Qwen3OmniMoeForConditionalGeneration, Qwen3OmniMoeProcessor

            self._processor = Qwen3OmniMoeProcessor.from_pretrained(model_name)
            self._model = Qwen3OmniMoeForConditionalGeneration.from_pretrained(
                model_name,
                torch_dtype=dtype,
                device_map="auto",
            )

        self.model_path = model_path
        self.device = resolved
        logger.info("Qwen%s-Omni STT loaded on %s", self._generation, resolved)

    @staticmethod
    def _resolve_model_name(model_path: Path) -> str:
        dir_name = model_path.name
        if "--" in dir_name:
            return dir_name.replace("--", "/", 1)
        return str(model_path)

    async def unload_model(self) -> None:
        self._model = None
        self._processor = None
        self.model_path = None
        if self.device == "cuda":
            try:
                import torch

                torch.cuda.empty_cache()
            except Exception:
                pass

    def is_loaded(self) -> bool:
        return self._model is not None

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "loaded": self.is_loaded(),
            "backend": "qwen3_omni_stt",
            "generation": self._generation,
        }

    async def transcribe(
        self,
        audio: str | Path | BinaryIO,
        language: str | None = None,
        task: str = "transcribe",
        temperature: float = 0.0,
        word_timestamps: bool = False,
        **kwargs,
    ) -> TranscriptionResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        temp_path: str | None = None
        try:
            if isinstance(audio, (str, Path)):
                audio_path = str(audio)
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio.read())
                    temp_path = tmp.name
                audio_path = temp_path

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._transcribe_sync, audio_path, language, task)
            return result
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    def _transcribe_sync(self, audio_path: str, language: str | None, task: str) -> TranscriptionResult:
        prompt = "Transcribe the speech in this audio."
        if task == "translate":
            prompt = "Translate the speech in this audio to English."
        if language:
            prompt += f" The audio is in {self._LANG_MAP.get(language, language)}."

        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "audio", "audio": audio_path},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        from qwen_omni_utils import process_mm_info

        audios, images, videos = process_mm_info(conversation, use_audio_in_video=False)

        text_input = self._processor.apply_chat_template(conversation, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(
            text=text_input,
            audios=audios,
            images=images,
            videos=videos,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to(self._model.device)

        text_ids = self._model.generate(
            **inputs,
            max_new_tokens=512,
            return_audio=False,
        )

        input_len = inputs["input_ids"].shape[-1]
        generated_ids = text_ids[:, input_len:]
        text = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

        duration = self._get_audio_duration(audio_path)

        return TranscriptionResult(
            text=text,
            language=language or "unknown",
            duration=duration,
        )

    @staticmethod
    def _get_audio_duration(audio_path: str) -> float:
        try:
            import soundfile as sf

            info = sf.info(audio_path)
            return info.duration
        except Exception:
            pass
        try:
            import subprocess

            out = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return float(out.stdout.strip())
        except Exception:
            return 0.0

    _LANG_MAP: dict[str, str] = {
        "en": "English",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "pt": "Portuguese",
        "ru": "Russian",
        "it": "Italian",
        "ar": "Arabic",
        "nl": "Dutch",
        "sv": "Swedish",
        "da": "Danish",
        "fi": "Finnish",
        "pl": "Polish",
        "cs": "Czech",
        "hi": "Hindi",
        "tr": "Turkish",
    }


__all__ = ["Qwen3OmniSTTAdapter", "QWEN3_OMNI_STT_AVAILABLE"]
