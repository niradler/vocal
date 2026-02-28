import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from huggingface_hub import ModelCard, get_safetensors_metadata, snapshot_download
from huggingface_hub import model_info as hf_model_info
from huggingface_hub.hf_api import ModelInfo as HFModelInfo

from ..model_info import (
    ModelBackend,
    ModelInfo,
    ModelProvider,
    ModelStatus,
    ModelTask,
    format_bytes,
)
from .base import ModelProvider as BaseProvider


class HuggingFaceProvider(BaseProvider):
    KNOWN_STT_MODELS = {
        "Systran/faster-whisper-tiny": "whisper-tiny",
        "Systran/faster-whisper-base": "whisper-base",
        "Systran/faster-whisper-small": "whisper-small",
        "Systran/faster-whisper-medium": "whisper-medium",
        "Systran/faster-whisper-large-v2": "whisper-large-v2",
        "Systran/faster-whisper-large-v3": "whisper-large-v3",
    }

    KNOWN_TTS_MODELS = {
        "hexgrad/Kokoro-82M": "kokoro",
        "onnx-community/Kokoro-82M-ONNX": "kokoro-onnx",
        "Qwen/Qwen3-TTS-12Hz-0.6B-Base": "qwen3-tts-0.6b",
        "Qwen/Qwen3-TTS-12Hz-1.7B-Base": "qwen3-tts-1.7b",
        "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice": "qwen3-tts-0.6b-custom",
        "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice": "qwen3-tts-1.7b-custom",
        "fishaudio/fish-speech-1.5": "fish-speech",
        "coqui/XTTS-v2": "xtts-v2",
        "myshell-ai/MeloTTS-English": "melotts-en",
    }

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir
        self._supported_models: dict[str, dict] | None = None
        self._alias_to_id: dict[str, str] = {}

    def get_provider_name(self) -> str:
        return "huggingface"

    def _load_supported_models(self) -> dict[str, dict]:
        if self._supported_models is not None:
            return self._supported_models

        supported_models_path = Path(__file__).parent.parent / "supported_models.json"

        if not supported_models_path.exists():
            return {}

        try:
            with open(supported_models_path) as f:
                data = json.load(f)

            self._supported_models = {}
            for model in data.get("models", []):
                model_id = model["id"]
                self._supported_models[model_id] = model

                if alias := model.get("alias"):
                    self._alias_to_id[alias] = model_id

            return self._supported_models
        except Exception as e:
            print(f"Error loading supported models: {e}")
            return {}

    def _resolve_alias(self, model_or_alias: str) -> str:
        self._load_supported_models()
        if model_or_alias in self._alias_to_id:
            return self._alias_to_id[model_or_alias]
        return model_or_alias

    def _model_dict_to_info(
        self,
        model_dict: dict,
        status: ModelStatus = ModelStatus.NOT_DOWNLOADED,
        local_path: str | None = None,
    ) -> ModelInfo:
        return ModelInfo(
            id=model_dict["id"],
            name=model_dict["name"],
            provider=ModelProvider.HUGGINGFACE,
            description=model_dict.get("description"),
            size=model_dict.get("size", 0),
            size_readable=model_dict.get("size_readable", "Unknown"),
            parameters=model_dict.get("parameters", "Unknown"),
            languages=model_dict.get("languages", []),
            backend=ModelBackend(model_dict.get("backend", "transformers")),
            status=status,
            source_url=model_dict.get("source_url"),
            license=model_dict.get("license"),
            recommended_vram=model_dict.get("recommended_vram"),
            task=ModelTask(model_dict.get("task", "stt")),
            local_path=local_path,
            modified_at=model_dict.get("modified_at"),
            downloaded_at=model_dict.get("downloaded_at"),
            author=model_dict.get("author"),
            tags=model_dict.get("tags", []),
            downloads=model_dict.get("downloads"),
            likes=model_dict.get("likes"),
            sha=model_dict.get("sha"),
            files=model_dict.get("files"),
        )

    async def list_models(self, task: str | None = None) -> list[ModelInfo]:
        models = []
        supported = self._load_supported_models()

        for model_id, model_dict in supported.items():
            if task is None or model_dict.get("task") == task:
                models.append(self._model_dict_to_info(model_dict))

        return models

    async def get_model_info(self, model_id: str) -> ModelInfo | None:
        model_id = self._resolve_alias(model_id)
        supported = self._load_supported_models()

        if model_id in supported:
            return self._model_dict_to_info(supported[model_id])

        return None

    async def fetch_metadata_from_hf(self, model_id: str) -> dict | None:  # noqa: C901
        try:
            loop = asyncio.get_event_loop()
            info: HFModelInfo = await loop.run_in_executor(None, lambda: hf_model_info(model_id))

            total_size = 0
            files = []
            if info.siblings:
                for sibling in info.siblings:
                    if sibling.size:
                        total_size += sibling.size
                        files.append({"filename": sibling.rfilename, "size": sibling.size})

            actual_param_count = None
            try:
                st_meta = await loop.run_in_executor(None, get_safetensors_metadata, model_id)
                actual_param_count = sum(st_meta.parameter_count.values())
            except Exception:
                pass

            license_info = None
            languages = []
            tags = info.tags or []

            try:
                card = await loop.run_in_executor(None, ModelCard.load, model_id)
                card_data = card.data.to_dict()
                license_info = card_data.get("license")

                card_languages = card_data.get("language", [])
                if isinstance(card_languages, str):
                    languages = [card_languages]
                elif isinstance(card_languages, list):
                    languages = card_languages
            except Exception:
                pass

            for tag in tags:
                if tag.startswith("language:"):
                    lang = tag.replace("language:", "")
                    if lang not in languages:
                        languages.append(lang)

            return {
                "model_id": model_id,
                "size": total_size,
                "size_readable": format_bytes(total_size),
                "actual_parameter_count": actual_param_count,
                "license": license_info,
                "last_modified": str(info.last_modified) if info.last_modified else None,
                "sha": info.sha,
                "author": info.author,
                "downloads": info.downloads,
                "likes": info.likes,
                "tags": tags,
                "languages": languages,
                "files": files[:10],
                "downloaded": True,
                "downloaded_at": datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"Error fetching metadata from HF: {e}")
            return None

    async def download_model(self, model_id: str, destination: Path, quantization: str | None = None) -> AsyncIterator[tuple[int, int]]:
        model_id = self._resolve_alias(model_id)
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

            total_size = sum(f.stat().st_size for f in Path(model_path).rglob("*") if f.is_file())
            yield (total_size, total_size)

        except Exception as e:
            raise RuntimeError(f"Failed to download model {model_id}: {e}")

    async def verify_model(self, model_id: str, local_path: Path) -> bool:
        if not local_path.exists():
            return False

        required_files = ["config.json"]
        for file in required_files:
            if not (local_path / file).exists():
                return False

        return True
