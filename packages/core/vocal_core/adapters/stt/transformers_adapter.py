import asyncio
import importlib.util
import logging
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from .base import STTAdapter, TranscriptionResult, TranscriptionSegment

logger = logging.getLogger(__name__)

TRANSFORMERS_AVAILABLE = importlib.util.find_spec("transformers") is not None and importlib.util.find_spec("torch") is not None


class TransformersSTTAdapter(STTAdapter):
    """
    HuggingFace Transformers STT adapter.

    Supports Whisper variants via the transformers pipeline, plus prompt/processor-driven
    families loaded natively: Qwen3-ASR (``*-hf`` checkpoints), Cohere Transcribe and
    IBM Granite Speech 5.0 / TurboCTC.
    """

    def __init__(self) -> None:
        self.pipe: Any = None
        self._prompt_model: Any = None
        self._prompt_processor: Any = None
        self._prompt_kind: str | None = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self._is_ctc: bool = False

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
            self._load_qwen3_asr(model_path, resolved, dtype)
        elif model_type == "cohere_asr":
            self._load_cohere_asr(model_path, resolved, dtype)
        elif model_type == "granite_speech":
            self._load_granite_speech(model_path, resolved, dtype)
        elif model_type == "granite_speech5_ctc":
            self._load_granite_ctc(model_path, resolved, dtype)
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

    def _load_qwen3_asr(self, model_path: Path, device: str, dtype: Any) -> None:
        """Load Qwen3-ASR through transformers' native implementation.

        Only the ``*-hf`` checkpoints match the native architecture; the original repos ship
        custom-code weights that need the (transformers 4.x pinned) ``qwen-asr`` package.
        """
        from transformers import AutoProcessor, Qwen3ASRForConditionalGeneration

        logger.info("Loading Qwen3-ASR model from %s", model_path)
        self._prompt_processor = AutoProcessor.from_pretrained(str(model_path))
        self._prompt_model = Qwen3ASRForConditionalGeneration.from_pretrained(str(model_path), torch_dtype=dtype, device_map=device)
        self._prompt_kind = "qwen3_asr"

    def _load_cohere_asr(self, model_path: Path, device: str, dtype: Any) -> None:
        from transformers import AutoProcessor, CohereAsrForConditionalGeneration

        logger.info("Loading Cohere ASR model from %s", model_path)
        self._prompt_processor = AutoProcessor.from_pretrained(str(model_path))
        self._prompt_model = CohereAsrForConditionalGeneration.from_pretrained(str(model_path), torch_dtype=dtype, device_map=device)
        self._prompt_kind = "cohere"

    def _load_granite_speech(self, model_path: Path, device: str, dtype: Any) -> None:
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

        logger.info("Loading Granite Speech model from %s", model_path)
        self._prompt_processor = AutoProcessor.from_pretrained(str(model_path))
        self._prompt_model = AutoModelForSpeechSeq2Seq.from_pretrained(str(model_path), torch_dtype=dtype, device_map=device)
        self._prompt_kind = "granite"

    def _load_granite_ctc(self, model_path: Path, device: str, dtype: Any) -> None:
        from transformers import AutoModelForCTC, AutoProcessor

        logger.info("Loading Granite Speech CTC model from %s", model_path)
        self._prompt_processor = AutoProcessor.from_pretrained(str(model_path))
        self._prompt_model = AutoModelForCTC.from_pretrained(str(model_path), torch_dtype=dtype, device_map=device)
        self._prompt_kind = "granite_ctc"

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
        self._prompt_model = None
        self._prompt_processor = None
        self._prompt_kind = None
        self.model_path = None
        if self.device == "cuda":
            try:
                import torch

                torch.cuda.empty_cache()
            except Exception:
                pass

    def is_loaded(self) -> bool:
        return self.pipe is not None or self._prompt_model is not None

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
        prompt: str | None = None,
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

            if self._prompt_kind is not None:
                result = await loop.run_in_executor(None, self._run_prompt_model, audio_path, language)
            else:
                generate_kwargs: dict[str, Any] = {}
                if not self._is_ctc:
                    if language:
                        generate_kwargs["language"] = language
                    if task == "translate":
                        generate_kwargs["task"] = "translate"
                    if prompt:
                        prompt_ids = self._build_prompt_ids(prompt)
                        if prompt_ids is not None:
                            generate_kwargs["prompt_ids"] = prompt_ids
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

    # Cohere Transcribe supports 14 languages; the processor expects ISO codes.
    _COHERE_LANGUAGES = frozenset({"en", "fr", "de", "it", "es", "pt", "el", "nl", "pl", "zh", "ja", "ko", "vi", "ar"})

    # Granite Speech 5.0 2B takes a language-id prompt naming the language in English.
    _GRANITE_LANGUAGE_NAMES = {
        "en": "English",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "pt": "Portuguese",
        "ja": "Japanese",
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

    def _run_prompt_model(self, audio_path: str, language: str | None) -> TranscriptionResult:
        """Dispatch prompt/processor-driven ASR families (Qwen3-ASR, Cohere Transcribe, IBM Granite Speech)."""
        if self._prompt_kind == "qwen3_asr":
            text = self._run_qwen3_asr(audio_path, language)
        elif self._prompt_kind == "cohere":
            text = self._run_cohere_asr(audio_path, language)
        elif self._prompt_kind == "granite":
            text = self._run_granite_speech(audio_path, language)
        else:
            text = self._run_granite_ctc(audio_path)

        return TranscriptionResult(text=text, language=language or "unknown", duration=self._get_audio_duration(audio_path), segments=None)

    def _run_qwen3_asr(self, audio_path: str, language: str | None) -> str:
        """Transcribe with the native Qwen3-ASR processor + chat prompt."""
        import numpy as np
        import torch

        sampling_rate = 16000
        audio = self._load_mono_audio(audio_path, sampling_rate)
        # The encoder requires whole 100-frame windows (1 s of audio).
        padded = int(np.ceil(len(audio) / sampling_rate) * sampling_rate)
        if len(audio) < padded:
            audio = np.pad(audio, (0, padded - len(audio))).astype(np.float32)

        messages = [
            {"role": "system", "content": ""},
            {"role": "user", "content": [{"type": "audio", "audio": ""}]},
        ]
        prompt = self._prompt_processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        if language:
            prompt = f"{prompt}language {self._QWEN_LANG_MAP.get(language, language)}<asr_text>"

        inputs = self._prompt_processor(text=[prompt], audio=[audio], return_tensors="pt", padding=True)
        inputs = inputs.to(self._prompt_model.device).to(self._prompt_model.dtype)
        with torch.no_grad():
            outputs = self._prompt_model.generate(**inputs, max_new_tokens=256, do_sample=False)
        new_tokens = outputs[:, inputs["input_ids"].shape[1] :]
        text = str(self._prompt_processor.batch_decode(new_tokens, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0])
        return text.split("<asr_text>")[-1].strip()

    @staticmethod
    def _load_mono_audio(audio_path: str, sampling_rate: int) -> Any:
        """Decode audio to mono float32 at ``sampling_rate`` without touching torchcodec.

        ``soundfile`` cannot open container formats such as ``.m4a``; those are transcoded to a
        temporary WAV with ffmpeg first (same approach as the NeMo adapter).
        """
        import os
        import subprocess
        import tempfile

        import numpy as np
        import soundfile as sf

        try:
            audio, source_rate = sf.read(audio_path, dtype="float32", always_2d=False)
        except Exception:
            fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "quiet", "-i", audio_path, tmp_wav],
                    check=True,
                    timeout=120,
                )
                audio, source_rate = sf.read(tmp_wav, dtype="float32", always_2d=False)
            finally:
                Path(tmp_wav).unlink(missing_ok=True)

        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if source_rate != sampling_rate:
            import librosa

            audio = librosa.resample(np.asarray(audio, dtype=np.float32), orig_sr=source_rate, target_sr=sampling_rate)
        return np.asarray(audio, dtype=np.float32)

    def _run_cohere_asr(self, audio_path: str, language: str | None) -> str:
        if language and language not in self._COHERE_LANGUAGES:
            raise ValueError(f"Cohere Transcribe does not support language '{language}'. Supported: {', '.join(sorted(self._COHERE_LANGUAGES))}")

        audio = self._load_mono_audio(audio_path, 16000)
        process_kwargs: dict[str, Any] = {"sampling_rate": 16000, "return_tensors": "pt"}
        if language:
            process_kwargs["language"] = language

        inputs = self._prompt_processor(audio, **process_kwargs)
        inputs = inputs.to(self._prompt_model.device, dtype=self._prompt_model.dtype)
        outputs = self._prompt_model.generate(**inputs, max_new_tokens=256)
        return str(self._prompt_processor.decode(outputs, skip_special_tokens=True)).strip()

    def _run_granite_speech(self, audio_path: str, language: str | None) -> str:
        import torch

        audio = torch.from_numpy(self._load_mono_audio(audio_path, 16000)).unsqueeze(0)
        tokenizer = self._prompt_processor.tokenizer

        # IBM documents a language-id prompt for multilingual ASR (README: "ASR with language ID").
        instruction = "transcribe the speech with proper punctuation and capitalization."
        if language:
            name = self._GRANITE_LANGUAGE_NAMES.get(language)
            if name is None:
                raise ValueError(f"Granite Speech 5.0 2B does not support language '{language}'. Supported: {', '.join(sorted(self._GRANITE_LANGUAGE_NAMES))}")
            instruction = f"The speech is in {name}. Transcribe it exactly; do not translate. can you transcribe the speech into a written format?"

        chat = [{"role": "user", "content": f"<|audio|>{instruction}"}]
        prompt = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)

        inputs = self._prompt_processor(prompt, audio, device=self._prompt_model.device, return_tensors="pt").to(self._prompt_model.device)
        outputs = self._prompt_model.generate(**inputs, max_new_tokens=200, do_sample=False, num_beams=1)
        prompt_tokens = inputs["input_ids"].shape[-1]
        new_tokens = outputs[0, prompt_tokens:].unsqueeze(0)
        return str(tokenizer.batch_decode(new_tokens, add_special_tokens=False, skip_special_tokens=True)[0]).strip()

    def _run_granite_ctc(self, audio_path: str) -> str:
        sampling_rate = int(self._prompt_processor.feature_extractor.sampling_rate)
        audio = self._load_mono_audio(audio_path, sampling_rate)
        inputs = self._prompt_processor(audio, sampling_rate=sampling_rate, device=self._prompt_model.device, return_tensors="pt")
        inputs = inputs.to(self._prompt_model.device, dtype=self._prompt_model.dtype)
        outputs = self._prompt_model.generate(**inputs)
        text = str(self._prompt_processor.batch_decode(outputs, skip_special_tokens=True)[0]).strip()
        return "" if text == "<|nospeech|>" else text

    def _build_prompt_ids(self, prompt: str):
        """Tokenize an OpenAI-style prompt for Whisper generation (None when unsupported)."""
        tokenizer = getattr(self.pipe, "tokenizer", None)
        get_prompt_ids = getattr(tokenizer, "get_prompt_ids", None)
        if not callable(get_prompt_ids):
            return None
        try:
            prompt_ids = get_prompt_ids(prompt, return_tensors="pt")
            device = getattr(getattr(self.pipe, "model", None), "device", None)
            return prompt_ids.to(device) if device is not None else prompt_ids
        except Exception as exc:
            logger.warning("Ignoring prompt for this model: %s", exc)
            return None

    def _run_pipeline(self, audio_path: str, generate_kwargs: dict) -> TranscriptionResult:
        # Hand the pipeline a decoded array so it never reaches for torchcodec/ffmpeg backends
        # that may be missing on Windows.
        feature_extractor = getattr(self.pipe, "feature_extractor", None)
        sampling_rate = int(getattr(feature_extractor, "sampling_rate", 16000) or 16000)
        audio = self._load_mono_audio(audio_path, sampling_rate)
        raw = self.pipe(
            {"array": audio, "sampling_rate": sampling_rate},
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
