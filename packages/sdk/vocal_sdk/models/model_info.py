from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, TYPE_CHECKING

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.model_backend import ModelBackend
from ..models.model_provider import ModelProvider
from ..models.model_status import ModelStatus
from ..models.model_task import ModelTask
from typing import cast

if TYPE_CHECKING:
    from ..models.model_info_files_type_0_item import ModelInfoFilesType0Item


T = TypeVar("T", bound="ModelInfo")


@_attrs_define
class ModelInfo:
    """Model information schema

    Attributes:
        id (str): Unique model identifier
        name (str): Human-readable model name
        provider (ModelProvider): Model provider/source
        backend (ModelBackend): Model inference backend
        status (ModelStatus): Model download/availability status
        task (ModelTask): Model task type
        description (None | str | Unset): Model description from HuggingFace
        size (int | Unset): Model size in bytes Default: 0.
        size_readable (str | Unset): Human-readable size Default: 'Unknown'.
        parameters (str | Unset): Number of parameters Default: 'Unknown'.
        languages (list[str] | Unset): Supported languages
        source_url (None | str | Unset):
        license_ (None | str | Unset):
        recommended_vram (None | str | Unset):
        local_path (None | str | Unset):
        modified_at (None | str | Unset): Last modified date on HuggingFace
        downloaded_at (None | str | Unset): Date when model was downloaded locally
        author (None | str | Unset): Model author/organization
        tags (list[str] | Unset): HuggingFace tags
        downloads (int | None | Unset): Download count on HuggingFace
        likes (int | None | Unset): Likes on HuggingFace
        sha (None | str | Unset): Git commit SHA
        files (list[ModelInfoFilesType0Item] | None | Unset): List of model files
    """

    id: str
    name: str
    provider: ModelProvider
    backend: ModelBackend
    status: ModelStatus
    task: ModelTask
    description: None | str | Unset = UNSET
    size: int | Unset = 0
    size_readable: str | Unset = "Unknown"
    parameters: str | Unset = "Unknown"
    languages: list[str] | Unset = UNSET
    source_url: None | str | Unset = UNSET
    license_: None | str | Unset = UNSET
    recommended_vram: None | str | Unset = UNSET
    local_path: None | str | Unset = UNSET
    modified_at: None | str | Unset = UNSET
    downloaded_at: None | str | Unset = UNSET
    author: None | str | Unset = UNSET
    tags: list[str] | Unset = UNSET
    downloads: int | None | Unset = UNSET
    likes: int | None | Unset = UNSET
    sha: None | str | Unset = UNSET
    files: list[ModelInfoFilesType0Item] | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        provider = self.provider.value

        backend = self.backend.value

        status = self.status.value

        task = self.task.value

        description: None | str | Unset
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        size = self.size

        size_readable = self.size_readable

        parameters = self.parameters

        languages: list[str] | Unset = UNSET
        if not isinstance(self.languages, Unset):
            languages = self.languages

        source_url: None | str | Unset
        if isinstance(self.source_url, Unset):
            source_url = UNSET
        else:
            source_url = self.source_url

        license_: None | str | Unset
        if isinstance(self.license_, Unset):
            license_ = UNSET
        else:
            license_ = self.license_

        recommended_vram: None | str | Unset
        if isinstance(self.recommended_vram, Unset):
            recommended_vram = UNSET
        else:
            recommended_vram = self.recommended_vram

        local_path: None | str | Unset
        if isinstance(self.local_path, Unset):
            local_path = UNSET
        else:
            local_path = self.local_path

        modified_at: None | str | Unset
        if isinstance(self.modified_at, Unset):
            modified_at = UNSET
        else:
            modified_at = self.modified_at

        downloaded_at: None | str | Unset
        if isinstance(self.downloaded_at, Unset):
            downloaded_at = UNSET
        else:
            downloaded_at = self.downloaded_at

        author: None | str | Unset
        if isinstance(self.author, Unset):
            author = UNSET
        else:
            author = self.author

        tags: list[str] | Unset = UNSET
        if not isinstance(self.tags, Unset):
            tags = self.tags

        downloads: int | None | Unset
        if isinstance(self.downloads, Unset):
            downloads = UNSET
        else:
            downloads = self.downloads

        likes: int | None | Unset
        if isinstance(self.likes, Unset):
            likes = UNSET
        else:
            likes = self.likes

        sha: None | str | Unset
        if isinstance(self.sha, Unset):
            sha = UNSET
        else:
            sha = self.sha

        files: list[dict[str, Any]] | None | Unset
        if isinstance(self.files, Unset):
            files = UNSET
        elif isinstance(self.files, list):
            files = []
            for files_type_0_item_data in self.files:
                files_type_0_item = files_type_0_item_data.to_dict()
                files.append(files_type_0_item)

        else:
            files = self.files

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "provider": provider,
                "backend": backend,
                "status": status,
                "task": task,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if size is not UNSET:
            field_dict["size"] = size
        if size_readable is not UNSET:
            field_dict["size_readable"] = size_readable
        if parameters is not UNSET:
            field_dict["parameters"] = parameters
        if languages is not UNSET:
            field_dict["languages"] = languages
        if source_url is not UNSET:
            field_dict["source_url"] = source_url
        if license_ is not UNSET:
            field_dict["license"] = license_
        if recommended_vram is not UNSET:
            field_dict["recommended_vram"] = recommended_vram
        if local_path is not UNSET:
            field_dict["local_path"] = local_path
        if modified_at is not UNSET:
            field_dict["modified_at"] = modified_at
        if downloaded_at is not UNSET:
            field_dict["downloaded_at"] = downloaded_at
        if author is not UNSET:
            field_dict["author"] = author
        if tags is not UNSET:
            field_dict["tags"] = tags
        if downloads is not UNSET:
            field_dict["downloads"] = downloads
        if likes is not UNSET:
            field_dict["likes"] = likes
        if sha is not UNSET:
            field_dict["sha"] = sha
        if files is not UNSET:
            field_dict["files"] = files

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.model_info_files_type_0_item import ModelInfoFilesType0Item

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        provider = ModelProvider(d.pop("provider"))

        backend = ModelBackend(d.pop("backend"))

        status = ModelStatus(d.pop("status"))

        task = ModelTask(d.pop("task"))

        def _parse_description(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        size = d.pop("size", UNSET)

        size_readable = d.pop("size_readable", UNSET)

        parameters = d.pop("parameters", UNSET)

        languages = cast(list[str], d.pop("languages", UNSET))

        def _parse_source_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        source_url = _parse_source_url(d.pop("source_url", UNSET))

        def _parse_license_(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        license_ = _parse_license_(d.pop("license", UNSET))

        def _parse_recommended_vram(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        recommended_vram = _parse_recommended_vram(d.pop("recommended_vram", UNSET))

        def _parse_local_path(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        local_path = _parse_local_path(d.pop("local_path", UNSET))

        def _parse_modified_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        modified_at = _parse_modified_at(d.pop("modified_at", UNSET))

        def _parse_downloaded_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        downloaded_at = _parse_downloaded_at(d.pop("downloaded_at", UNSET))

        def _parse_author(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        author = _parse_author(d.pop("author", UNSET))

        tags = cast(list[str], d.pop("tags", UNSET))

        def _parse_downloads(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        downloads = _parse_downloads(d.pop("downloads", UNSET))

        def _parse_likes(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        likes = _parse_likes(d.pop("likes", UNSET))

        def _parse_sha(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        sha = _parse_sha(d.pop("sha", UNSET))

        def _parse_files(data: object) -> list[ModelInfoFilesType0Item] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                files_type_0 = []
                _files_type_0 = data
                for files_type_0_item_data in _files_type_0:
                    files_type_0_item = ModelInfoFilesType0Item.from_dict(
                        files_type_0_item_data
                    )

                    files_type_0.append(files_type_0_item)

                return files_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[ModelInfoFilesType0Item] | None | Unset, data)

        files = _parse_files(d.pop("files", UNSET))

        model_info = cls(
            id=id,
            name=name,
            provider=provider,
            backend=backend,
            status=status,
            task=task,
            description=description,
            size=size,
            size_readable=size_readable,
            parameters=parameters,
            languages=languages,
            source_url=source_url,
            license_=license_,
            recommended_vram=recommended_vram,
            local_path=local_path,
            modified_at=modified_at,
            downloaded_at=downloaded_at,
            author=author,
            tags=tags,
            downloads=downloads,
            likes=likes,
            sha=sha,
            files=files,
        )

        model_info.additional_properties = d
        return model_info

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
