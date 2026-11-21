from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..models.body_create_transcription_v1_audio_transcriptions_post_timestamp_granularities_type_0_item import (
    BodyCreateTranscriptionV1AudioTranscriptionsPostTimestampGranularitiesType0Item,
)
from ..models.transcription_format import TranscriptionFormat
from ..types import UNSET, File, Unset

T = TypeVar("T", bound="BodyCreateTranscriptionV1AudioTranscriptionsPost")


@_attrs_define
class BodyCreateTranscriptionV1AudioTranscriptionsPost:
    """
    Attributes:
        file (File): Audio file to transcribe
        model (None | str | Unset): Model ID (defaults to the server STT default)
        language (None | str | Unset): Language code
        prompt (None | str | Unset): Style prompt
        response_format (TranscriptionFormat | Unset): Output format for transcription
        temperature (float | Unset):  Default: 0.0.
        timestamp_granularities (list[BodyCreateTranscriptionV1AudioTranscriptionsPostTimestampGranularitiesType0Item] |
            None | Unset): Timestamp granularities (verbose_json only)
    """

    file: File
    model: None | str | Unset = UNSET
    language: None | str | Unset = UNSET
    prompt: None | str | Unset = UNSET
    response_format: TranscriptionFormat | Unset = UNSET
    temperature: float | Unset = 0.0
    timestamp_granularities: (
        list[
            BodyCreateTranscriptionV1AudioTranscriptionsPostTimestampGranularitiesType0Item
        ]
        | None
        | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        file = self.file.to_tuple()

        model: None | str | Unset
        if isinstance(self.model, Unset):
            model = UNSET
        else:
            model = self.model

        language: None | str | Unset
        if isinstance(self.language, Unset):
            language = UNSET
        else:
            language = self.language

        prompt: None | str | Unset
        if isinstance(self.prompt, Unset):
            prompt = UNSET
        else:
            prompt = self.prompt

        response_format: str | Unset = UNSET
        if not isinstance(self.response_format, Unset):
            response_format = self.response_format.value

        temperature = self.temperature

        timestamp_granularities: list[str] | None | Unset
        if isinstance(self.timestamp_granularities, Unset):
            timestamp_granularities = UNSET
        elif isinstance(self.timestamp_granularities, list):
            timestamp_granularities = []
            for (
                timestamp_granularities_type_0_item_data
            ) in self.timestamp_granularities:
                timestamp_granularities_type_0_item = (
                    timestamp_granularities_type_0_item_data.value
                )
                timestamp_granularities.append(timestamp_granularities_type_0_item)

        else:
            timestamp_granularities = self.timestamp_granularities

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "file": file,
            }
        )
        if model is not UNSET:
            field_dict["model"] = model
        if language is not UNSET:
            field_dict["language"] = language
        if prompt is not UNSET:
            field_dict["prompt"] = prompt
        if response_format is not UNSET:
            field_dict["response_format"] = response_format
        if temperature is not UNSET:
            field_dict["temperature"] = temperature
        if timestamp_granularities is not UNSET:
            field_dict["timestamp_granularities[]"] = timestamp_granularities

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("file", self.file.to_tuple()))

        if not isinstance(self.model, Unset):
            if isinstance(self.model, str):
                files.append(("model", (None, str(self.model).encode(), "text/plain")))
            else:
                files.append(("model", (None, str(self.model).encode(), "text/plain")))

        if not isinstance(self.language, Unset):
            if isinstance(self.language, str):
                files.append(
                    ("language", (None, str(self.language).encode(), "text/plain"))
                )
            else:
                files.append(
                    ("language", (None, str(self.language).encode(), "text/plain"))
                )

        if not isinstance(self.prompt, Unset):
            if isinstance(self.prompt, str):
                files.append(
                    ("prompt", (None, str(self.prompt).encode(), "text/plain"))
                )
            else:
                files.append(
                    ("prompt", (None, str(self.prompt).encode(), "text/plain"))
                )

        if not isinstance(self.response_format, Unset):
            files.append(
                (
                    "response_format",
                    (None, str(self.response_format.value).encode(), "text/plain"),
                )
            )

        if not isinstance(self.temperature, Unset):
            files.append(
                ("temperature", (None, str(self.temperature).encode(), "text/plain"))
            )

        if not isinstance(self.timestamp_granularities, Unset):
            if isinstance(self.timestamp_granularities, list):
                for (
                    timestamp_granularities_type_0_item_element
                ) in self.timestamp_granularities:
                    files.append(
                        (
                            "timestamp_granularities[]",
                            (
                                None,
                                str(
                                    timestamp_granularities_type_0_item_element.value
                                ).encode(),
                                "text/plain",
                            ),
                        )
                    )
            else:
                files.append(
                    (
                        "timestamp_granularities[]",
                        (
                            None,
                            str(self.timestamp_granularities).encode(),
                            "text/plain",
                        ),
                    )
                )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        file = File(payload=BytesIO(d.pop("file")))

        def _parse_model(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        model = _parse_model(d.pop("model", UNSET))

        def _parse_language(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        language = _parse_language(d.pop("language", UNSET))

        def _parse_prompt(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        prompt = _parse_prompt(d.pop("prompt", UNSET))

        _response_format = d.pop("response_format", UNSET)
        response_format: TranscriptionFormat | Unset
        if isinstance(_response_format, Unset):
            response_format = UNSET
        else:
            response_format = TranscriptionFormat(_response_format)

        temperature = d.pop("temperature", UNSET)

        def _parse_timestamp_granularities(
            data: object,
        ) -> (
            list[
                BodyCreateTranscriptionV1AudioTranscriptionsPostTimestampGranularitiesType0Item
            ]
            | None
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                timestamp_granularities_type_0 = []
                _timestamp_granularities_type_0 = data
                for (
                    timestamp_granularities_type_0_item_data
                ) in _timestamp_granularities_type_0:
                    timestamp_granularities_type_0_item = BodyCreateTranscriptionV1AudioTranscriptionsPostTimestampGranularitiesType0Item(
                        timestamp_granularities_type_0_item_data
                    )

                    timestamp_granularities_type_0.append(
                        timestamp_granularities_type_0_item
                    )

                return timestamp_granularities_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                list[
                    BodyCreateTranscriptionV1AudioTranscriptionsPostTimestampGranularitiesType0Item
                ]
                | None
                | Unset,
                data,
            )

        timestamp_granularities = _parse_timestamp_granularities(
            d.pop("timestamp_granularities[]", UNSET)
        )

        body_create_transcription_v1_audio_transcriptions_post = cls(
            file=file,
            model=model,
            language=language,
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
            timestamp_granularities=timestamp_granularities,
        )

        body_create_transcription_v1_audio_transcriptions_post.additional_properties = d
        return body_create_transcription_v1_audio_transcriptions_post

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
