import asyncio
import importlib.util
import logging
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from .base import STTAdapter, TranscriptionResult, TranscriptionSegment

logger = logging.getLogger(__name__)

TRANSFORMERS_AVAILABLE = importlib.util.find_spec("transformers") is not None and importlib.util.find_spec("torch") is not None
QWEN_ASR_AVAILABLE = importlib.util.find_spec("qwen_asr") is not None


class TransformersSTTAdapter(STTAdapter):
    """
    HuggingFace Transformers STT adapter.

    Supports Whisper variants via transformers pipeline, and Qwen3-ASR via the
    dedicated qwen_asr package (which wraps the model's custom architecture).
    """

    def __init__(self) -> None:
        self.pipe: Any = None
        self._qwen_model: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self._is_ctc: bool = False
        self._is_qwen_asr: bool = False

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers and torch are required. Install with: pip install transformers torch")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        dtype = torch.float16 if resolved == "cuda" else torch.float32

        logger.info("Loading transformers STT model from %s on %s", model_path, resolved)

        # Detect model type from config.json before calling AutoConfig, because
        # AutoConfig raises for unrecognised architectures like qwen3_asr.
        model_type = self._read_model_type(model_path)

        if model_type == "qwen3_asr":
            self._load_qwen_asr(model_path, resolved)
        else:
            self._load_pipeline(model_path, resolved, dtype, model_type)

        self.model_path = model_path
        self.device = resolved
        logger.info("Transformers STT model loaded on %s (type=%s)", resolved, model_type)

    @staticmethod
    def _read_model_type(model_path: Path) -> str:
        """Read model_type from config.json without AutoConfig (avoids errors for unknown architectures)."""
        import json as _json

        cfg_file = model_path / "config.json"
        if cfg_file.exists():
            with open(cfg_file) as f:
                return _json.load(f).get("model_type", "")
        return ""

    @staticmethod
    def _apply_qwen_asr_shims() -> None:
        import torch

        from vocal_core.adapters._compat import apply_transformers_shims

        apply_transformers_shims()

        # --- qwen_asr-specific patches (not shared with TTS) -----------------
        from qwen_asr.core.transformers_backend.modeling_qwen3_asr import Qwen3ASRThinkerTextRotaryEmbedding as _RotEmb

        try:
            from qwen_asr.core.transformers_backend.configuration_qwen3_asr import Qwen3ASRThinkerConfig as _ThinkerCfg

            if not hasattr(_ThinkerCfg, "pad_token_id"):
                _ThinkerCfg.pad_token_id = None
        except (ImportError, AttributeError):
            pass

        if not hasattr(_RotEmb, "compute_default_rope_parameters"):

            def _default_rope_params(self, config):
                base = getattr(config, "rope_theta", 10000.0)
                dim = getattr(config, "head_dim", config.hidden_size // config.num_attention_heads)
                inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2, dtype=torch.float32) / dim))
                return inv_freq, 1.0

            _RotEmb.compute_default_rope_parameters = _default_rope_params

    def _load_qwen_asr(self, model_path: Path, device: str) -> None:
        if not QWEN_ASR_AVAILABLE:
            raise ImportError("qwen_asr is required for Qwen3-ASR models. Install with: pip install qwen-asr")
        import torch

        self._apply_qwen_asr_shims()

        from qwen_asr import Qwen3ASRModel

        # Derive HF model name from directory (org--repo → org/repo)
        dir_name = model_path.name
        if "--" in dir_name:
            model_name = dir_name.replace("--", "/", 1)
        else:
            model_name = str(model_path)

        dtype = torch.float16 if device == "cuda" else torch.float32
        self._qwen_model = Qwen3ASRModel.from_pretrained(
            model_name,
            torch_dtype=dtype,
            device_map=device,
        )
        self._is_qwen_asr = True

    def _load_pipeline(self, model_path: Path, device: str, dtype: Any, model_type: str) -> None:
        from transformers import pipeline

        self._is_ctc = model_type in {"wav2vec2", "wav2vec2-conformer", "hubert", "data2vec-audio", "unispeech", "unispeech-sat", "wavlm"}
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=str(model_path),
            torch_dtype=dtype,
            device=device,
            chunk_length_s=30,
        )

    async def unload_model(self) -> None:
        self.pipe = None
        self._qwen_model = None
        self._is_qwen_asr = False
        self.model_path = None
        if self.device == "cuda":
            try:
                import torch

                torch.cuda.empty_cache()
            except Exception:
                pass

    def is_loaded(self) -> bool:
        return self.pipe is not None or self._qwen_model is not None

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "loaded": self.is_loaded(),
            "backend": "transformers",
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
                with tempfile.NamedTemporaryFile(delete=False, suffix=".audio") as tmp:
                    tmp.write(audio.read())
                    temp_path = tmp.name
                audio_path = temp_path

            loop = asyncio.get_running_loop()

            if self._is_qwen_asr:
                result = await loop.run_in_executor(None, self._run_qwen_asr, audio_path, language, word_timestamps)
            else:
                generate_kwargs: dict[str, Any] = {}
                if not self._is_ctc:
                    if language:
                        generate_kwargs["language"] = language
                    if task == "translate":
                        generate_kwargs["task"] = "translate"
                result = await loop.run_in_executor(None, self._run_pipeline, audio_path, generate_kwargs)

            return result
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    # Qwen3-ASR expects full language names, not ISO codes.
    _QWEN_LANG_MAP: dict[str, str] = {
        "en": "English",
        "zh": "Chinese",
        "yue": "Cantonese",
        "ar": "Arabic",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "pt": "Portuguese",
        "id": "Indonesian",
        "it": "Italian",
        "ko": "Korean",
        "ru": "Russian",
        "th": "Thai",
        "vi": "Vietnamese",
        "ja": "Japanese",
        "tr": "Turkish",
        "hi": "Hindi",
        "ms": "Malay",
        "nl": "Dutch",
        "sv": "Swedish",
        "da": "Danish",
        "fi": "Finnish",
        "pl": "Polish",
        "cs": "Czech",
        "fil": "Filipino",
        "fa": "Persian",
        "el": "Greek",
        "ro": "Romanian",
        "hu": "Hungarian",
        "mk": "Macedonian",
    }

    @staticmethod
    def _get_audio_duration(audio_path: str) -> float:
        """Estimate audio duration in seconds."""
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

    def _run_qwen_asr(self, audio_path: str, language: str | None, word_timestamps: bool) -> TranscriptionResult:
        qwen_lang = self._QWEN_LANG_MAP.get(language, language) if language else None
        results = self._qwen_model.transcribe(
            audio=audio_path,
            language=qwen_lang,
            return_time_stamps=word_timestamps,
        )
        if not results:
            return TranscriptionResult(text="", language=language or "unknown", duration=0.0)

        r = results[0]
        segments = None
        duration = 0.0

        if r.time_stamps:
            segments = []
            for i, ts in enumerate(r.time_stamps):
                start = float(ts.get("start", 0.0)) if isinstance(ts, dict) else 0.0
                end = float(ts.get("end", 0.0)) if isinstance(ts, dict) else 0.0
                text = ts.get("text", "") if isinstance(ts, dict) else str(ts)
                duration = max(duration, end)
                segments.append(TranscriptionSegment(id=i, start=start, end=end, text=text))

        if duration == 0.0:
            duration = self._get_audio_duration(audio_path)

        return TranscriptionResult(
            text=r.text.strip(),
            language=r.language or language or "unknown",
            duration=duration,
            segments=segments,
        )

    def _run_pipeline(self, audio_path: str, generate_kwargs: dict) -> TranscriptionResult:
        raw = self.pipe(
            audio_path,
            return_timestamps=True,
            generate_kwargs=generate_kwargs if generate_kwargs else None,
        )

        text = raw.get("text", "").strip()
        chunks = raw.get("chunks", [])
        last_ts: float | None = None
        if chunks:
            try:
                last_ts = chunks[-1].get("timestamp", (None, None))[1]
            except (IndexError, TypeError):
                last_ts = None
        duration = float(last_ts) if last_ts else 0.0

        segments = None
        if chunks:
            segments = [
                TranscriptionSegment(
                    id=i,
                    start=c["timestamp"][0] or 0.0,
                    end=c["timestamp"][1] or 0.0,
                    text=c["text"],
                )
                for i, c in enumerate(chunks)
            ]

        return TranscriptionResult(
            text=text,
            language="unknown",
            duration=duration,
            segments=segments,
        )
