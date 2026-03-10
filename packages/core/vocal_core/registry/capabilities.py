from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CapabilityOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supports_streaming: bool | None = None
    supports_voice_list: bool | None = None
    supports_voice_clone: bool | None = None
    supports_voice_design: bool | None = None
    requires_gpu: bool | None = None
    voice_mode: str | None = None
    clone_mode: str | None = None
    reference_audio_min_seconds: float | None = None
    reference_audio_max_seconds: float | None = None


class RepoFileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    size: int | None = None


class StoredModelRecord(CapabilityOverrides):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    provider: str
    task: str
    backend: str
    description: str | None = None
    size: int = 0
    size_readable: str = "Unknown"
    parameters: str = "Unknown"
    languages: list[str] = Field(default_factory=list)
    recommended_vram: str | None = None
    source_url: str | None = None
    license: str | None = None
    modified_at: str | None = None
    downloaded_at: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    downloads: int | None = None
    likes: int | None = None
    sha: str | None = None
    files: list[RepoFileRecord] | None = None
    alias: str | None = None
    actual_parameter_count: int | None = None


class HuggingFaceCardRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license: str | None = None
    languages: list[str] = Field(default_factory=list)


class HuggingFaceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author: str | None = None
    downloads: int | None = None
    files: list[RepoFileRecord] = Field(default_factory=list)
    last_modified: datetime | None = None
    likes: int | None = None
    sha: str | None = None
    size: int = 0
    tags: list[str] = Field(default_factory=list)


def capability_overrides_from_mapping(data: Mapping[str, Any]) -> CapabilityOverrides:
    payload = {}
    for field_name in CapabilityOverrides.model_fields:
        if field_name in data:
            payload[field_name] = data[field_name]
    return CapabilityOverrides.model_validate(payload)


def _get_required_or_default(
    data: Mapping[str, Any],
    field_name: str,
    *,
    default: str | None = None,
    record_id: str | None = None,
) -> str:
    if field_name in data:
        return data[field_name]
    if default is not None:
        return default
    if record_id is None:
        raise ValueError(f"Model record is missing required field '{field_name}'.")
    raise ValueError(f"Model record '{record_id}' is missing required field '{field_name}'.")


def model_record_from_mapping(
    data: Mapping[str, Any],
    *,
    default_id: str | None = None,
    default_name: str | None = None,
    default_provider: str | None = None,
    default_task: str | None = None,
    default_backend: str | None = None,
) -> StoredModelRecord:
    record_id = _get_required_or_default(data, "id", default=default_id)
    payload: dict[str, Any] = {
        "id": record_id,
        "name": _get_required_or_default(data, "name", default=default_name, record_id=record_id),
        "provider": _get_required_or_default(data, "provider", default=default_provider, record_id=record_id),
        "task": _get_required_or_default(data, "task", default=default_task, record_id=record_id),
        "backend": _get_required_or_default(data, "backend", default=default_backend, record_id=record_id),
    }

    optional_fields = (
        "description",
        "size",
        "size_readable",
        "parameters",
        "languages",
        "recommended_vram",
        "source_url",
        "license",
        "modified_at",
        "downloaded_at",
        "author",
        "tags",
        "downloads",
        "likes",
        "sha",
        "files",
        "alias",
        "actual_parameter_count",
        "supports_streaming",
        "supports_voice_list",
        "supports_voice_clone",
        "supports_voice_design",
        "requires_gpu",
        "voice_mode",
        "clone_mode",
        "reference_audio_min_seconds",
        "reference_audio_max_seconds",
    )
    for field_name in optional_fields:
        if field_name in data:
            payload[field_name] = data[field_name]

    return StoredModelRecord.model_validate(payload)


def supported_model_records_from_mapping(data: Mapping[str, Any]) -> list[StoredModelRecord]:
    if "generated_at" in data:
        datetime.fromisoformat(str(data["generated_at"]).replace("Z", "+00:00"))

    models_raw = data["models"] if "models" in data else []
    if not isinstance(models_raw, list):
        raise ValueError("Supported models document must contain a 'models' list.")

    return [model_record_from_mapping(model) for model in models_raw if isinstance(model, Mapping)]


def huggingface_card_record_from_mapping(data: Mapping[str, Any]) -> HuggingFaceCardRecord:
    payload: dict[str, Any] = {}
    if "license" in data:
        payload["license"] = data["license"]

    if "language" in data:
        raw_languages = data["language"]
        if isinstance(raw_languages, str):
            payload["languages"] = [raw_languages]
        elif isinstance(raw_languages, list):
            payload["languages"] = [language for language in raw_languages if isinstance(language, str)]

    return HuggingFaceCardRecord.model_validate(payload)


def huggingface_snapshot_from_info(info: Any) -> HuggingFaceSnapshot:
    total_size = 0
    files: list[RepoFileRecord] = []

    siblings = getattr(info, "siblings", None)
    if isinstance(siblings, list):
        for sibling in siblings:
            filename = getattr(sibling, "rfilename", None)
            size = getattr(sibling, "size", None)
            if not isinstance(filename, str):
                continue
            file_payload: dict[str, Any] = {"filename": filename}
            if isinstance(size, int):
                file_payload["size"] = size
                total_size += size
            files.append(RepoFileRecord.model_validate(file_payload))

    tags = getattr(info, "tags", None)
    payload = {
        "author": getattr(info, "author", None),
        "downloads": getattr(info, "downloads", None),
        "files": files,
        "last_modified": getattr(info, "last_modified", None),
        "likes": getattr(info, "likes", None),
        "sha": getattr(info, "sha", None),
        "size": total_size,
        "tags": [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else [],
    }
    return HuggingFaceSnapshot.model_validate(payload)


def infer_model_capabilities(
    *,
    task: str,
    backend: str,
    model_id: str,
    tags: list[str] | None = None,
    overrides: CapabilityOverrides | None = None,
) -> dict[str, Any]:
    tags = tags or []
    task = task or "stt"
    backend = backend or "transformers"
    model_id_lower = model_id.lower()
    overrides = overrides or CapabilityOverrides()
    inferred_voice_mode = overrides.voice_mode
    inferred_clone_mode = overrides.clone_mode
    _streaming_default = backend == "faster_whisper"
    inferred_supports_streaming = overrides.supports_streaming if overrides.supports_streaming is not None else _streaming_default
    inferred_supports_voice_list = overrides.supports_voice_list if overrides.supports_voice_list is not None else False
    inferred_supports_voice_clone = overrides.supports_voice_clone if overrides.supports_voice_clone is not None else False
    inferred_supports_voice_design = overrides.supports_voice_design if overrides.supports_voice_design is not None else False
    inferred_requires_gpu = overrides.requires_gpu if overrides.requires_gpu is not None else False
    inferred_min_seconds = overrides.reference_audio_min_seconds
    inferred_max_seconds = overrides.reference_audio_max_seconds

    if task == "tts":
        if backend == "kokoro":
            inferred_supports_streaming = overrides.supports_streaming if overrides.supports_streaming is not None else True
            inferred_supports_voice_list = overrides.supports_voice_list if overrides.supports_voice_list is not None else True
            inferred_voice_mode = overrides.voice_mode or "voice_id"
        elif backend == "piper":
            inferred_supports_voice_list = overrides.supports_voice_list if overrides.supports_voice_list is not None else True
            inferred_voice_mode = overrides.voice_mode or "voice_id"
        elif backend == "faster_qwen3_tts":
            inferred_requires_gpu = overrides.requires_gpu if overrides.requires_gpu is not None else True
            if "voicedesign" in model_id_lower or "voice-design" in model_id_lower:
                inferred_supports_voice_design = overrides.supports_voice_design if overrides.supports_voice_design is not None else True
                inferred_voice_mode = overrides.voice_mode or "instruction"
            elif "customvoice" in model_id_lower or "custom-voice" in model_id_lower or "customvoice" in "".join(tags).lower():
                inferred_supports_voice_list = overrides.supports_voice_list if overrides.supports_voice_list is not None else True
                inferred_voice_mode = overrides.voice_mode or "voice_id"
            else:
                inferred_supports_voice_clone = overrides.supports_voice_clone if overrides.supports_voice_clone is not None else True
                inferred_clone_mode = overrides.clone_mode or "reference_audio"
                inferred_min_seconds = overrides.reference_audio_min_seconds if overrides.reference_audio_min_seconds is not None else 3.0
                inferred_max_seconds = overrides.reference_audio_max_seconds if overrides.reference_audio_max_seconds is not None else 30.0

    return {
        "supports_streaming": inferred_supports_streaming,
        "supports_voice_list": inferred_supports_voice_list,
        "supports_voice_clone": inferred_supports_voice_clone,
        "supports_voice_design": inferred_supports_voice_design,
        "requires_gpu": inferred_requires_gpu,
        "voice_mode": inferred_voice_mode,
        "clone_mode": inferred_clone_mode,
        "reference_audio_min_seconds": inferred_min_seconds,
        "reference_audio_max_seconds": inferred_max_seconds,
    }
