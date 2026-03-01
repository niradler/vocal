from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast


T = TypeVar("T", bound="TranscriptionSegment")


@_attrs_define
class TranscriptionSegment:
    """A segment of transcribed text with timing

    Attributes:
        id (int):
        start (float): Start time in seconds
        end (float): End time in seconds
        text (str): Transcribed text
        tokens (list[int] | None | Unset):
        temperature (float | None | Unset):
        avg_logprob (float | None | Unset):
        compression_ratio (float | None | Unset):
        no_speech_prob (float | None | Unset):
    """

    id: int
    start: float
    end: float
    text: str
    tokens: list[int] | None | Unset = UNSET
    temperature: float | None | Unset = UNSET
    avg_logprob: float | None | Unset = UNSET
    compression_ratio: float | None | Unset = UNSET
    no_speech_prob: float | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        start = self.start

        end = self.end

        text = self.text

        tokens: list[int] | None | Unset
        if isinstance(self.tokens, Unset):
            tokens = UNSET
        elif isinstance(self.tokens, list):
            tokens = self.tokens

        else:
            tokens = self.tokens

        temperature: float | None | Unset
        if isinstance(self.temperature, Unset):
            temperature = UNSET
        else:
            temperature = self.temperature

        avg_logprob: float | None | Unset
        if isinstance(self.avg_logprob, Unset):
            avg_logprob = UNSET
        else:
            avg_logprob = self.avg_logprob

        compression_ratio: float | None | Unset
        if isinstance(self.compression_ratio, Unset):
            compression_ratio = UNSET
        else:
            compression_ratio = self.compression_ratio

        no_speech_prob: float | None | Unset
        if isinstance(self.no_speech_prob, Unset):
            no_speech_prob = UNSET
        else:
            no_speech_prob = self.no_speech_prob

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "start": start,
                "end": end,
                "text": text,
            }
        )
        if tokens is not UNSET:
            field_dict["tokens"] = tokens
        if temperature is not UNSET:
            field_dict["temperature"] = temperature
        if avg_logprob is not UNSET:
            field_dict["avg_logprob"] = avg_logprob
        if compression_ratio is not UNSET:
            field_dict["compression_ratio"] = compression_ratio
        if no_speech_prob is not UNSET:
            field_dict["no_speech_prob"] = no_speech_prob

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        start = d.pop("start")

        end = d.pop("end")

        text = d.pop("text")

        def _parse_tokens(data: object) -> list[int] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                tokens_type_0 = cast(list[int], data)

                return tokens_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[int] | None | Unset, data)

        tokens = _parse_tokens(d.pop("tokens", UNSET))

        def _parse_temperature(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        temperature = _parse_temperature(d.pop("temperature", UNSET))

        def _parse_avg_logprob(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        avg_logprob = _parse_avg_logprob(d.pop("avg_logprob", UNSET))

        def _parse_compression_ratio(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        compression_ratio = _parse_compression_ratio(d.pop("compression_ratio", UNSET))

        def _parse_no_speech_prob(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        no_speech_prob = _parse_no_speech_prob(d.pop("no_speech_prob", UNSET))

        transcription_segment = cls(
            id=id,
            start=start,
            end=end,
            text=text,
            tokens=tokens,
            temperature=temperature,
            avg_logprob=avg_logprob,
            compression_ratio=compression_ratio,
            no_speech_prob=no_speech_prob,
        )

        transcription_segment.additional_properties = d
        return transcription_segment

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
