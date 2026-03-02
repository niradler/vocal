from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from .. import types

from ..types import UNSET, Unset

from ..models.transcription_format import TranscriptionFormat
from ..types import File
from io import BytesIO
from typing import cast


T = TypeVar("T", bound="BodyCreateTranscriptionV1AudioTranscriptionsPost")


@_attrs_define
class BodyCreateTranscriptionV1AudioTranscriptionsPost:
    """
    Attributes:
        file (File): Audio file to transcribe
        model (str | Unset): Model ID Default: 'Systran/faster-whisper-tiny'.
        language (None | str | Unset): Language code
        prompt (None | str | Unset): Style prompt
        response_format (TranscriptionFormat | Unset): Output format for transcription
        temperature (float | Unset):  Default: 0.0.
    """

    file: File
    model: str | Unset = "Systran/faster-whisper-tiny"
    language: None | str | Unset = UNSET
    prompt: None | str | Unset = UNSET
    response_format: TranscriptionFormat | Unset = UNSET
    temperature: float | Unset = 0.0
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        file = self.file.to_tuple()

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

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("file", self.file.to_tuple()))

        if not isinstance(self.model, Unset):
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

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        file = File(payload=BytesIO(d.pop("file")))

        model = d.pop("model", UNSET)

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

        body_create_transcription_v1_audio_transcriptions_post = cls(
            file=file,
            model=model,
            language=language,
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
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
