import asyncio
import importlib.util
import inspect
import io
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ...config import optional_dependency_install_hint, vocal_settings
from .base import AudioFormat, TTSAdapter, TTSCapabilities, TTSResult, Voice, VoiceCloneRequest

logger = logging.getLogger(__name__)

CHATTERBOX_AVAILABLE = importlib.util.find_spec("chatterbox") is not None

MULTILINGUAL_LANGUAGES = {
    "ar": "Arabic",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "sv": "Swedish",
    "sw": "Swahili",
    "tr": "Turkish",
    "zh": "Chinese",
}

_V3_CHECKPOINT = "t3_mtl23ls_v3.safetensors"
_V2_CHECKPOINT_NAME = "t3_mtl23ls_v2.safetensors"
_MULTILINGUAL_FILES = (
    "ve.pt",
    "s3gen.pt",
    "grapheme_mtl_merged_expanded_v1.json",
    "conds.pt",
    "Cangjie5_TC.json",
)


def chatterbox_kind(model_path: Path) -> str:
    name = model_path.name.lower()
    if "multilingual" in name:
        return "multilingual_v3"
    return "default"


def _load_multilingual_v3(device: str, model_path: Path) -> Any:
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    parameters = inspect.signature(ChatterboxMultilingualTTS.from_pretrained).parameters
    if "t3_model" in parameters:
        return ChatterboxMultilingualTTS.from_pretrained(device, t3_model="v3")

    if (model_path / _V3_CHECKPOINT).is_file():
        checkpoint_dir = model_path
    else:
        from huggingface_hub import snapshot_download

        checkpoint_dir = Path(
            snapshot_download(
                repo_id="ResembleAI/chatterbox",
                allow_patterns=[_V3_CHECKPOINT, *_MULTILINGUAL_FILES],
            )
        )
    v3_weights = checkpoint_dir / _V3_CHECKPOINT
    if not v3_weights.exists():
        raise RuntimeError(f"Chatterbox Multilingual V3 checkpoint {_V3_CHECKPOINT} was not found in ResembleAI/chatterbox.")

    staging = Path(tempfile.mkdtemp(prefix="chatterbox-v3-"))
    for name in _MULTILINGUAL_FILES:
        source = checkpoint_dir / name
        if source.exists():
            shutil.copy2(source, staging / name)
    shutil.copy2(v3_weights, staging / _V2_CHECKPOINT_NAME)
    logger.info("Loading Chatterbox Multilingual V3 weights with the installed chatterbox-tts loader")
    return ChatterboxMultilingualTTS.from_local(staging, device)


class ChatterboxTTSAdapter(TTSAdapter):
    """
    Chatterbox TTS adapter — zero-shot voice cloning, emotion exaggeration control.

    Supports both standard synthesis and reference-audio voice cloning.
    Requires: pip install chatterbox-tts torchaudio
    """

    def __init__(self) -> None:
        self.model: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"
        self.sample_rate: int = 24000
        self._kind: str = "default"

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not CHATTERBOX_AVAILABLE:
            raise ImportError(optional_dependency_install_hint("chatterbox", "chatterbox-tts"))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch
        from chatterbox.tts import ChatterboxTTS

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        self.device = resolved
        self._kind = chatterbox_kind(model_path)
        self.model_path = model_path

        logger.info("Loading Chatterbox TTS (%s) from %s on %s", self._kind, model_path, resolved)
        if self._kind == "multilingual_v3":
            self.model = _load_multilingual_v3(resolved, model_path)
        else:
            self.model = ChatterboxTTS.from_pretrained(device=resolved)
        self.sample_rate = self.model.sr
        logger.info("Chatterbox TTS model loaded on %s (sr=%d)", resolved, self.sample_rate)

    async def unload_model(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
            self.model_path = None
            if self.device == "cuda":
                try:
                    import torch

                    torch.cuda.empty_cache()
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return self.model is not None

    def get_model_info(self) -> dict:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "sample_rate": self.sample_rate,
            "loaded": self.is_loaded(),
            "backend": "chatterbox",
        }

    def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            supports_streaming=False,
            supports_voice_list=False,
            supports_voice_clone=True,
            supports_voice_design=False,
            requires_gpu=False,
            clone_mode="reference_audio",
            reference_audio_min_seconds=3.0,
            reference_audio_max_seconds=30.0,
        )

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = AudioFormat.WAV,
        exaggeration: float | None = None,
        cfg_weight: float | None = None,
        **kwargs,
    ) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if output_format != AudioFormat.WAV:
            raise ValueError(f"Chatterbox only supports WAV output. Requested: '{output_format}'. Convert the result yourself if another format is needed.")

        exaggeration = exaggeration if exaggeration is not None else vocal_settings.CHATTERBOX_EXAGGERATION
        cfg_weight = cfg_weight if cfg_weight is not None else vocal_settings.CHATTERBOX_CFG_WEIGHT
        language = kwargs.get("language")
        loop = asyncio.get_running_loop()
        audio_bytes, duration = await loop.run_in_executor(None, self._synthesize_sync, text, None, exaggeration, cfg_weight, language)
        return TTSResult(audio_data=audio_bytes, sample_rate=self.sample_rate, duration=duration, format=AudioFormat.WAV)

    async def clone_synthesize(self, request: VoiceCloneRequest) -> TTSResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        output_format = request.output_format if request.output_format else AudioFormat.WAV
        if output_format != AudioFormat.WAV:
            raise ValueError(f"Chatterbox only supports WAV output. Requested: '{output_format}'. Convert the result yourself if another format is needed.")

        exaggeration = vocal_settings.CHATTERBOX_EXAGGERATION
        cfg_weight = vocal_settings.CHATTERBOX_CFG_WEIGHT
        loop = asyncio.get_running_loop()
        audio_bytes, duration = await loop.run_in_executor(None, self._synthesize_sync, request.text, request.reference_audio_path, exaggeration, cfg_weight, request.language)
        return TTSResult(audio_data=audio_bytes, sample_rate=self.sample_rate, duration=duration, format=AudioFormat.WAV)

    def _synthesize_sync(
        self,
        text: str,
        audio_prompt_path: str | None,
        exaggeration: float,
        cfg_weight: float,
        language: str | None,
    ) -> tuple[bytes, float]:
        import soundfile as sf

        kwargs: dict = {"exaggeration": exaggeration, "cfg_weight": cfg_weight}
        if audio_prompt_path:
            kwargs["audio_prompt_path"] = audio_prompt_path
        if self._kind == "multilingual_v3":
            language_id = (language or "en").lower().split("-")[0]
            if language_id not in MULTILINGUAL_LANGUAGES:
                supported = ", ".join(sorted(MULTILINGUAL_LANGUAGES))
                raise ValueError(f"Unsupported Chatterbox Multilingual V3 language '{language_id}'. Supported languages: {supported}")
            kwargs["language_id"] = language_id

        wav = self.model.generate(text, **kwargs)
        duration = wav.shape[-1] / self.sample_rate

        buf = io.BytesIO()
        wav_np = wav.squeeze(0).cpu().numpy()
        sf.write(buf, wav_np, self.sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue(), duration

    async def get_voices(self) -> list[Voice]:
        return [Voice(id="default", name="Default", language=vocal_settings.DEFAULT_LANGUAGE)]
