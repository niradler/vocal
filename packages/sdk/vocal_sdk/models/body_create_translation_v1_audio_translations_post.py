from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from .. import types

from ..types import UNSET, Unset

from ..types import File
from io import BytesIO


T = TypeVar("T", bound="BodyCreateTranslationV1AudioTranslationsPost")


@_attrs_define
class BodyCreateTranslationV1AudioTranslationsPost:
    """
    Attributes:
        file (File):
        model (str | Unset):  Default: 'Systran/faster-whisper-tiny'.
    """

    file: File
    model: str | Unset = "Systran/faster-whisper-tiny"
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        file = self.file.to_tuple()

        model = self.model

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "file": file,
            }
        )
        if model is not UNSET:
            field_dict["model"] = model

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("file", self.file.to_tuple()))

        if not isinstance(self.model, Unset):
            files.append(("model", (None, str(self.model).encode(), "text/plain")))

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        file = File(payload=BytesIO(d.pop("file")))

        model = d.pop("model", UNSET)

        body_create_translation_v1_audio_translations_post = cls(
            file=file,
            model=model,
        )

        body_create_translation_v1_audio_translations_post.additional_properties = d
        return body_create_translation_v1_audio_translations_post

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
