import asyncio
import time
from collections.abc import AsyncGenerator
from pathlib import Path

from vocal_core import ModelRegistry
from vocal_core.adapters.tts import (
    CHATTERBOX_AVAILABLE,
    FASTER_QWEN3_TTS_AVAILABLE,
    KOKORO_AVAILABLE,
    OMNIVOICE_AVAILABLE,
    VOXTRAL_TTS_AVAILABLE,
    ChatterboxTTSAdapter,
    FasterQwen3TTSAdapter,
    KokoroTTSAdapter,
    OmniVoiceTTSAdapter,
    PiperTTSAdapter,
    SimpleTTSAdapter,
    TTSAdapter,
    TTSCapabilities,
    TTSResult,
    Voice,
    VoiceCloneRequest,
    VoxtralTTSAdapter,
)
from vocal_core.config import optional_dependency_install_hint

try:
    from piper import PiperVoice as _piper_check  # noqa: F401

    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False


class TTSService:
    """Service for handling TTS operations with Ollama-style keep-alive"""

    def __init__(self, registry: ModelRegistry, keep_alive_seconds: int = 300):
        self.registry = registry
        self.adapters: dict[str, TTSAdapter] = {}
        self.last_used: dict[str, float] = {}
        self.keep_alive_seconds = keep_alive_seconds
        self._cleanup_task = None

    async def start_cleanup_task(self):
        """Start background task to cleanup unused models"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """Background task to unload models after keep_alive expires"""
        while True:
            try:
                await asyncio.sleep(60)
                current_time = time.time()
                models_to_unload = []

                for model_id, last_used_time in self.last_used.items():
                    if current_time - last_used_time > self.keep_alive_seconds:
                        models_to_unload.append(model_id)

                for model_id in models_to_unload:
                    if model_id in self.adapters:
                        adapter = self.adapters[model_id]
                        if hasattr(adapter, "unload_model"):
                            await adapter.unload_model()
                        del self.adapters[model_id]
                        del self.last_used[model_id]

            except Exception:
                pass

    async def synthesize(
        self,
        model_id: str,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        output_format: str = "mp3",
        language: str | None = None,
        **kwargs,
    ) -> TTSResult:
        """
        Synthesize text to speech using specified model

        Args:
            model_id: TTS model identifier (use "pyttsx3" for system TTS)
            text: Text to convert to speech
            voice: Voice ID to use
            speed: Speech speed multiplier
            output_format: Output audio format

        Returns:
            TTSResult with audio data
        """
        extra = {k: v for k, v in ({"language": language} | kwargs).items() if v is not None}

        if model_id == "pyttsx3":
            adapter = await self._get_or_create_simple_adapter()
            self.last_used[model_id] = time.time()
            return await adapter.synthesize(text=text, voice=voice, speed=speed, output_format=output_format, **extra)

        model_info = await self.registry.get_model(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found in registry")

        if model_info.task.value != "tts":
            raise ValueError(f"Model {model_id} is not a TTS model (task: {model_info.task})")

        model_path = self.registry.get_model_path(model_id)

        if not model_path:
            raise ValueError(f"Model {model_id} not downloaded. Download it first: POST /v1/models/{model_id}/download")

        adapter = await self._get_or_create_adapter(model_id, model_path, model_info.backend.value)
        self.last_used[model_id] = time.time()

        return await adapter.synthesize(text=text, voice=voice, speed=speed, output_format=output_format, **extra)

    async def clone_synthesize(
        self,
        model_id: str,
        text: str,
        reference_audio_path: str,
        reference_text: str | None = None,
        output_format: str = "wav",
        language: str | None = None,
        speed: float = 1.0,
    ) -> TTSResult:
        if model_id == "pyttsx3":
            raise ValueError("System TTS does not support voice cloning.")

        model_info = await self.registry.get_model(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found in registry")

        if model_info.task.value != "tts":
            raise ValueError(f"Model {model_id} is not a TTS model (task: {model_info.task})")

        model_path = self.registry.get_model_path(model_id)
        if not model_path:
            raise ValueError(f"Model {model_id} not downloaded. Download it first: POST /v1/models/{model_id}/download")

        adapter = await self._get_or_create_adapter(model_id, model_path, model_info.backend.value)
        capabilities = adapter.get_capabilities()
        if not capabilities.supports_voice_clone:
            raise ValueError(f"Model {model_id} does not support reference-audio voice cloning.")

        self.last_used[model_id] = time.time()
        request = VoiceCloneRequest(
            text=text,
            reference_audio_path=reference_audio_path,
            reference_text=reference_text,
            language=language,
            speed=speed,
            output_format=output_format,
        )
        return await adapter.clone_synthesize(request)

    async def synthesize_stream(
        self,
        model_id: str,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        output_format: str = "pcm",
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream audio bytes as they are generated.

        Args:
            model_id: TTS model identifier (use "pyttsx3" for system TTS)
            text: Text to convert to speech
            voice: Voice ID to use
            speed: Speech speed multiplier
            output_format: Output audio format

        Yields:
            bytes chunks of audio data
        """
        if model_id == "pyttsx3":
            adapter = await self._get_or_create_simple_adapter()
            self.last_used[model_id] = time.time()
            async for chunk in adapter.synthesize_stream(text=text, voice=voice, speed=speed, output_format=output_format):
                yield chunk
            return

        model_info = await self.registry.get_model(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found in registry")

        if model_info.task.value != "tts":
            raise ValueError(f"Model {model_id} is not a TTS model (task: {model_info.task})")

        model_path = self.registry.get_model_path(model_id)
        if not model_path:
            raise ValueError(f"Model {model_id} not downloaded. Download it first: POST /v1/models/{model_id}/download")

        adapter = await self._get_or_create_adapter(model_id, model_path, model_info.backend.value)
        self.last_used[model_id] = time.time()

        async for chunk in adapter.synthesize_stream(text=text, voice=voice, speed=speed, output_format=output_format):
            yield chunk

    async def get_voices(self, model_id: str | None = None) -> list[Voice]:
        """
        Get list of available voices

        Args:
            model_id: Optional model ID to get voices for specific model

        Returns:
            List of Voice objects
        """
        if not model_id or model_id == "pyttsx3":
            adapter = await self._get_or_create_simple_adapter()
            self.last_used["pyttsx3"] = time.time()
            return await adapter.get_voices()

        model_path = self.registry.get_model_path(model_id)
        if not model_path:
            raise ValueError(f"Model {model_id} not downloaded")

        model_info = await self.registry.get_model(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found")

        adapter = await self._get_or_create_adapter(model_id, model_path, model_info.backend.value)
        self.last_used[model_id] = time.time()
        return await adapter.get_voices()

    async def get_capabilities(self, model_id: str | None = None) -> TTSCapabilities:
        if not model_id or model_id == "pyttsx3":
            adapter = await self._get_or_create_simple_adapter()
            self.last_used["pyttsx3"] = time.time()
            return adapter.get_capabilities()

        model_path = self.registry.get_model_path(model_id)
        if not model_path:
            raise ValueError(f"Model {model_id} not downloaded")

        model_info = await self.registry.get_model(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found")

        adapter = await self._get_or_create_adapter(model_id, model_path, model_info.backend.value)
        self.last_used[model_id] = time.time()
        return adapter.get_capabilities()

    async def _get_or_create_simple_adapter(self) -> SimpleTTSAdapter:
        """Get or create the simple system TTS adapter"""
        if "pyttsx3" not in self.adapters:
            adapter = SimpleTTSAdapter()
            await adapter.load_model(Path("."))
            self.adapters["pyttsx3"] = adapter
        return self.adapters["pyttsx3"]

    async def _get_or_create_adapter(self, model_id: str, model_path: Path, backend: str) -> TTSAdapter:
        """Get or create TTS adapter for model"""
        if model_id not in self.adapters:
            adapter = self._create_adapter(backend)
            await adapter.load_model(model_path)
            self.adapters[model_id] = adapter

        return self.adapters[model_id]

    def _create_adapter(self, backend: str) -> TTSAdapter:  # noqa: C901
        if backend == "kokoro":
            if not KOKORO_AVAILABLE:
                raise ImportError(optional_dependency_install_hint("kokoro"))
            return KokoroTTSAdapter()
        if backend == "faster_qwen3_tts":
            if not FASTER_QWEN3_TTS_AVAILABLE:
                raise ImportError(optional_dependency_install_hint("qwen3-tts", "faster-qwen3-tts"))
            return FasterQwen3TTSAdapter()
        if backend == "piper":
            if not PIPER_AVAILABLE:
                raise ImportError(optional_dependency_install_hint("piper", "piper-tts"))
            return PiperTTSAdapter()
        if backend == "chatterbox":
            if not CHATTERBOX_AVAILABLE:
                raise ImportError(optional_dependency_install_hint("chatterbox", "chatterbox-tts"))
            return ChatterboxTTSAdapter()
        if backend == "voxtral_tts":
            if not VOXTRAL_TTS_AVAILABLE:
                raise ImportError(optional_dependency_install_hint("voxtral", "httpx"))
            return VoxtralTTSAdapter()
        if backend == "omnivoice":
            if not OMNIVOICE_AVAILABLE:
                raise ImportError(optional_dependency_install_hint("omnivoice"))
            return OmniVoiceTTSAdapter()
        raise ValueError(f"Unsupported TTS backend: '{backend}'. Supported backends: kokoro, faster_qwen3_tts, piper, chatterbox, voxtral_tts, omnivoice")
