import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from huggingface_hub import (
    ModelCard,
    get_safetensors_metadata,
    snapshot_download,
)
from huggingface_hub import (
    model_info as hf_model_info,
)
from huggingface_hub.hf_api import ModelInfo as HFModelInfo

from ..capabilities import (
    HuggingFaceCardRecord,
    HuggingFaceSnapshot,
    StoredModelRecord,
    huggingface_card_record_from_mapping,
    huggingface_snapshot_from_info,
    infer_model_capabilities,
    model_record_from_mapping,
    supported_model_records_from_mapping,
)
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
        self._supported_models: dict[str, StoredModelRecord] | None = None
        self._alias_to_id: dict[str, str] = {}

    def get_provider_name(self) -> str:
        return "huggingface"

    def _load_supported_models(self) -> dict[str, StoredModelRecord]:
        if self._supported_models is not None:
            return self._supported_models

        supported_models_path = Path(__file__).parent.parent / "supported_models.json"

        if not supported_models_path.exists():
            return {}

        try:
            with open(supported_models_path, encoding="utf-8") as f:
                models = supported_model_records_from_mapping(json.load(f))

            self._supported_models = {}
            self._alias_to_id = {}
            for model in models:
                self._supported_models[model.id] = model

                if model.alias:
                    self._alias_to_id[model.alias] = model.id

            return self._supported_models
        except Exception as e:
            print(f"Error loading supported models: {e}")
            return {}

    def _resolve_alias(self, model_or_alias: str) -> str:
        self._load_supported_models()
        if model_or_alias in self._alias_to_id:
            return self._alias_to_id[model_or_alias]
        return model_or_alias

    def resolve_alias(self, model_or_alias: str) -> str:
        return self._resolve_alias(model_or_alias)

    def _model_dict_to_info(
        self,
        model_dict: StoredModelRecord,
        status: ModelStatus = ModelStatus.NOT_DOWNLOADED,
        local_path: str | None = None,
    ) -> ModelInfo:
        record = model_dict
        capabilities = infer_model_capabilities(
            task=record.task,
            backend=record.backend,
            model_id=record.id,
            tags=record.tags,
            overrides=record,
        )
        return ModelInfo(
            id=record.id,
            name=record.name,
            provider=ModelProvider.HUGGINGFACE,
            description=record.description,
            size=record.size,
            size_readable=record.size_readable,
            parameters=record.parameters,
            languages=record.languages,
            backend=ModelBackend(record.backend),
            status=status,
            source_url=record.source_url,
            license=record.license,
            recommended_vram=record.recommended_vram,
            task=ModelTask(record.task),
            local_path=local_path,
            modified_at=record.modified_at,
            downloaded_at=record.downloaded_at,
            author=record.author,
            tags=record.tags,
            downloads=record.downloads,
            likes=record.likes,
            sha=record.sha,
            files=[file.model_dump() for file in record.files] if record.files else None,
            **capabilities,
        )

    async def list_models(self, task: str | None = None) -> list[ModelInfo]:
        models = []
        supported = self._load_supported_models()

        for model_id, model_dict in supported.items():
            if task is None or model_dict.task == task:
                models.append(self._model_dict_to_info(model_dict))

        return models

    async def get_model_info(self, model_id: str) -> ModelInfo | None:
        model_id = self._resolve_alias(model_id)
        supported = self._load_supported_models()

        if model_id in supported:
            return self._model_dict_to_info(supported[model_id])

        if "/" not in model_id:
            return None

        try:
            loop = asyncio.get_running_loop()
            info: HFModelInfo = await loop.run_in_executor(None, lambda: hf_model_info(model_id))
            tags = info.tags or []
            task = "tts" if any(t in tags for t in ("text-to-speech", "tts")) else "stt"
            backend = "transformers"
            caps = infer_model_capabilities(task=task, backend=backend, model_id=model_id, tags=tags)
            return ModelInfo(
                id=model_id,
                name=model_id.split("/")[-1],
                provider=ModelProvider.HUGGINGFACE,
                size=0,
                size_readable="Unknown",
                parameters="Unknown",
                languages=[t.replace("language:", "") for t in tags if t.startswith("language:")],
                backend=ModelBackend(backend),
                status=ModelStatus.NOT_DOWNLOADED,
                task=ModelTask(task),
                source_url=f"https://huggingface.co/{model_id}",
                **caps,
            )
        except Exception:
            return None

    async def fetch_metadata_from_hf(self, model_id: str) -> dict | None:  # noqa: C901
        try:
            supported = self._load_supported_models()
            supported_entry = supported.get(model_id)
            loop = asyncio.get_running_loop()
            info: HFModelInfo = await loop.run_in_executor(None, lambda: hf_model_info(model_id))
            snapshot: HuggingFaceSnapshot = huggingface_snapshot_from_info(info)

            actual_parameter_count = None
            try:
                st_meta = await loop.run_in_executor(None, get_safetensors_metadata, model_id)
                actual_parameter_count = sum(st_meta.parameter_count.values())
            except Exception:
                pass

            card_record = HuggingFaceCardRecord()

            try:
                card = await loop.run_in_executor(None, ModelCard.load, model_id)
                card_record = huggingface_card_record_from_mapping(card.data.to_dict())
            except Exception:
                pass

            languages = list(card_record.languages)
            for tag in snapshot.tags:
                if tag.startswith("language:"):
                    lang = tag.replace("language:", "")
                    if lang not in languages:
                        languages.append(lang)

            payload = {
                "id": model_id,
                "name": supported_entry.name if supported_entry else model_id.split("/")[-1],
                "provider": supported_entry.provider if supported_entry else "huggingface",
                "task": supported_entry.task if supported_entry else ("tts" if "text-to-speech" in snapshot.tags or "tts" in snapshot.tags else "stt"),
                "backend": supported_entry.backend if supported_entry else "transformers",
                "size": snapshot.size,
                "size_readable": format_bytes(snapshot.size),
                "license": card_record.license or (supported_entry.license if supported_entry else None),
                "modified_at": snapshot.last_modified.isoformat() if snapshot.last_modified else None,
                "sha": snapshot.sha,
                "author": snapshot.author,
                "downloads": snapshot.downloads,
                "likes": snapshot.likes,
                "tags": snapshot.tags,
                "languages": languages,
                "files": [file.model_dump() for file in snapshot.files[:10]],
                "downloaded_at": datetime.now().isoformat(),
                "description": supported_entry.description if supported_entry else None,
                "parameters": f"{actual_parameter_count:,}" if actual_parameter_count else (supported_entry.parameters if supported_entry else "Unknown"),
                "recommended_vram": supported_entry.recommended_vram if supported_entry else None,
                "source_url": supported_entry.source_url if supported_entry else f"https://huggingface.co/{model_id}",
            }
            record = model_record_from_mapping(payload)
            return record.model_dump(exclude_none=True)
        except Exception as e:
            print(f"Error fetching metadata from HF: {e}")
            return None

    async def download_model(self, model_id: str, destination: Path, quantization: str | None = None) -> AsyncIterator[tuple[int, int]]:
        model_id = self._resolve_alias(model_id)
        destination.mkdir(parents=True, exist_ok=True)

        supported = self._load_supported_models()
        record = supported.get(model_id)
        hf_repo_id = (record.hf_repo_id if record and record.hf_repo_id else None) or model_id

        loop = asyncio.get_running_loop()

        try:
            if await self.verify_model(model_id, destination):
                final_size = sum(f.stat().st_size for f in destination.rglob("*") if f.is_file())
                yield (final_size, final_size)
                return

            await loop.run_in_executor(
                None,
                lambda: snapshot_download(
                    hf_repo_id,
                    local_dir=str(destination),
                    cache_dir=str(self.cache_dir) if self.cache_dir else None,
                ),
            )

            final_size = sum(f.stat().st_size for f in destination.rglob("*") if f.is_file())
            yield (final_size, final_size)

        except Exception as e:
            raise RuntimeError(f"Failed to download model {model_id}: {e}")

    async def verify_model(self, model_id: str, local_path: Path) -> bool:
        if not local_path.exists():
            return False

        if not (local_path / "config.json").exists():
            return False

        all_files = [f for f in local_path.rglob("*") if f.is_file()]

        if any(".incomplete" in f.name or f.suffix == ".lock" for f in all_files):
            return False

        weight_names = {"model.safetensors", "pytorch_model.bin", "model.bin", "model.gguf", "model.pt"}
        has_weights = any(f.name in weight_names or (f.name.startswith("model-") and f.suffix == ".safetensors") for f in all_files)
        return has_weights
