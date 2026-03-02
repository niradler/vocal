from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast


T = TypeVar("T", bound="ModelDownloadProgress")


@_attrs_define
class ModelDownloadProgress:
    """Model download progress

    Attributes:
        model_id (str):
        status (str):
        progress (float | Unset):  Default: 0.0.
        downloaded_bytes (int | Unset):  Default: 0.
        total_bytes (int | Unset):  Default: 0.
        message (None | str | Unset):
    """

    model_id: str
    status: str
    progress: float | Unset = 0.0
    downloaded_bytes: int | Unset = 0
    total_bytes: int | Unset = 0
    message: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        model_id = self.model_id

        status = self.status

        progress = self.progress

        downloaded_bytes = self.downloaded_bytes

        total_bytes = self.total_bytes

        message: None | str | Unset
        if isinstance(self.message, Unset):
            message = UNSET
        else:
            message = self.message

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "model_id": model_id,
                "status": status,
            }
        )
        if progress is not UNSET:
            field_dict["progress"] = progress
        if downloaded_bytes is not UNSET:
            field_dict["downloaded_bytes"] = downloaded_bytes
        if total_bytes is not UNSET:
            field_dict["total_bytes"] = total_bytes
        if message is not UNSET:
            field_dict["message"] = message

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        model_id = d.pop("model_id")

        status = d.pop("status")

        progress = d.pop("progress", UNSET)

        downloaded_bytes = d.pop("downloaded_bytes", UNSET)

        total_bytes = d.pop("total_bytes", UNSET)

        def _parse_message(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        message = _parse_message(d.pop("message", UNSET))

        model_download_progress = cls(
            model_id=model_id,
            status=status,
            progress=progress,
            downloaded_bytes=downloaded_bytes,
            total_bytes=total_bytes,
            message=message,
        )

        model_download_progress.additional_properties = d
        return model_download_progress

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
