from typing import Optional, AsyncIterator
from pathlib import Path
import asyncio
from huggingface_hub import snapshot_download, model_info as hf_model_info
from huggingface_hub.utils import HfHubHTTPError

from .base import ModelProvider as BaseProvider
from ..model_info import (
    ModelInfo,
    ModelStatus,
    ModelBackend,
    ModelProvider,
    ModelTask,
    format_bytes,
)


class HuggingFaceProvider(BaseProvider):
    """HuggingFace model provider implementation"""

    KNOWN_STT_MODELS = {
        "Systran/faster-whisper-tiny": {
            "name": "Faster Whisper Tiny",
            "parameters": "39M",
            "backend": ModelBackend.FASTER_WHISPER,
            "recommended_vram": "1GB+",
            "alias": "whisper-tiny",
        },
        "Systran/faster-whisper-base": {
            "name": "Faster Whisper Base",
            "parameters": "74M",
            "backend": ModelBackend.FASTER_WHISPER,
            "recommended_vram": "1GB+",
            "alias": "whisper-base",
        },
        "Systran/faster-whisper-small": {
            "name": "Faster Whisper Small",
            "parameters": "244M",
            "backend": ModelBackend.FASTER_WHISPER,
            "recommended_vram": "2GB+",
            "alias": "whisper-small",
        },
        "Systran/faster-whisper-medium": {
            "name": "Faster Whisper Medium",
            "parameters": "769M",
            "backend": ModelBackend.FASTER_WHISPER,
            "recommended_vram": "5GB+",
            "alias": "whisper-medium",
        },
        "Systran/faster-whisper-large-v3": {
            "name": "Faster Whisper Large V3",
            "parameters": "1.5B",
            "backend": ModelBackend.FASTER_WHISPER,
            "recommended_vram": "10GB+",
            "alias": "whisper-large-v3",
        },
        "Systran/faster-distil-whisper-large-v3": {
            "name": "Faster Distil Whisper Large V3",
            "parameters": "809M",
            "backend": ModelBackend.FASTER_WHISPER,
            "recommended_vram": "6GB+",
            "alias": "whisper-large-v3-turbo",
        },
    }

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize HuggingFace provider

        Args:
            cache_dir: Optional custom cache directory
        """
        self.cache_dir = cache_dir

    def get_provider_name(self) -> str:
        return "huggingface"

    async def list_models(self, task: Optional[str] = None) -> list[ModelInfo]:
        """List available models from HuggingFace"""
        models = []

        for model_id, meta in self.KNOWN_STT_MODELS.items():
            if task and task != "stt":
                continue

            try:
                info = await self.get_model_info(model_id)
                if info:
                    models.append(info)
            except Exception:
                models.append(
                    ModelInfo(
                        id=model_id,
                        name=meta["name"],
                        provider=ModelProvider.HUGGINGFACE,
                        backend=meta["backend"],
                        task=ModelTask.STT,
                        status=ModelStatus.NOT_DOWNLOADED,
                        parameters=meta["parameters"],
                        recommended_vram=meta["recommended_vram"],
                        languages=self._get_whisper_languages(),
                    )
                )

        return models

    async def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """Get model info from HuggingFace"""
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, hf_model_info, model_id)

            meta = self.KNOWN_STT_MODELS.get(model_id, {})

            size = getattr(info, "size", 0) or 0

            return ModelInfo(
                id=model_id,
                name=meta.get("name", info.modelId),
                provider=ModelProvider.HUGGINGFACE,
                description=getattr(info, "description", None),
                size=size,
                size_readable=format_bytes(size) if size > 0 else "Unknown",
                parameters=meta.get("parameters", "Unknown"),
                languages=self._get_whisper_languages()
                if "whisper" in model_id.lower()
                else [],
                backend=meta.get("backend", ModelBackend.TRANSFORMERS),
                status=ModelStatus.NOT_DOWNLOADED,
                source_url=f"https://huggingface.co/{model_id}",
                license=getattr(info, "license", None),
                recommended_vram=meta.get("recommended_vram"),
                task=ModelTask.STT
                if model_id in self.KNOWN_STT_MODELS
                else ModelTask.STT,
            )
        except HfHubHTTPError:
            return None
        except Exception as e:
            print(f"Error fetching model info for {model_id}: {e}")
            return None

    async def download_model(
        self, model_id: str, destination: Path, quantization: Optional[str] = None
    ) -> AsyncIterator[tuple[int, int]]:
        """Download model from HuggingFace"""
        destination.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()

        try:
            model_path = await loop.run_in_executor(
                None,
                lambda: snapshot_download(
                    model_id,
                    local_dir=str(destination),
                    cache_dir=str(self.cache_dir) if self.cache_dir else None,
                    local_dir_use_symlinks=False,
                ),
            )

            total_size = sum(
                f.stat().st_size for f in Path(model_path).rglob("*") if f.is_file()
            )
            yield (total_size, total_size)

        except Exception as e:
            raise RuntimeError(f"Failed to download model {model_id}: {e}")

    async def verify_model(self, model_id: str, local_path: Path) -> bool:
        """Verify downloaded model"""
        if not local_path.exists():
            return False

        required_files = ["config.json"]
        for file in required_files:
            if not (local_path / file).exists():
                return False

        return True

    def _get_whisper_languages(self) -> list[str]:
        """Get list of languages supported by Whisper"""
        return [
            "en",
            "zh",
            "de",
            "es",
            "ru",
            "ko",
            "fr",
            "ja",
            "pt",
            "tr",
            "pl",
            "ca",
            "nl",
            "ar",
            "sv",
            "it",
            "id",
            "hi",
            "fi",
            "vi",
            "he",
            "uk",
            "el",
            "ms",
            "cs",
            "ro",
            "da",
            "hu",
            "ta",
            "no",
            "th",
            "ur",
            "hr",
            "bg",
            "lt",
            "la",
            "mi",
            "ml",
            "cy",
            "sk",
            "te",
            "fa",
            "lv",
            "bn",
            "sr",
            "az",
            "sl",
            "kn",
            "et",
            "mk",
            "br",
            "eu",
            "is",
            "hy",
            "ne",
            "mn",
            "bs",
            "kk",
            "sq",
            "sw",
            "gl",
            "mr",
            "pa",
            "si",
            "km",
            "sn",
            "yo",
            "so",
            "af",
            "oc",
            "ka",
            "be",
            "tg",
            "sd",
            "gu",
            "am",
            "yi",
            "lo",
            "uz",
            "fo",
            "ht",
            "ps",
            "tk",
            "nn",
            "mt",
            "sa",
            "lb",
            "my",
            "bo",
            "tl",
            "mg",
            "as",
            "tt",
            "haw",
            "ln",
            "ha",
            "ba",
            "jw",
            "su",
        ]
