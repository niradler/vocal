from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast


T = TypeVar("T", bound="TranscriptionWord")


@_attrs_define
class TranscriptionWord:
    """Word-level timestamp

    Attributes:
        word (str):
        start (float):
        end (float):
        probability (float | None | Unset):
    """

    word: str
    start: float
    end: float
    probability: float | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        word = self.word

        start = self.start

        end = self.end

        probability: float | None | Unset
        if isinstance(self.probability, Unset):
            probability = UNSET
        else:
            probability = self.probability

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "word": word,
                "start": start,
                "end": end,
            }
        )
        if probability is not UNSET:
            field_dict["probability"] = probability

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        word = d.pop("word")

        start = d.pop("start")

        end = d.pop("end")

        def _parse_probability(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        probability = _parse_probability(d.pop("probability", UNSET))

        transcription_word = cls(
            word=word,
            start=start,
            end=end,
            probability=probability,
        )

        transcription_word.additional_properties = d
        return transcription_word

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
