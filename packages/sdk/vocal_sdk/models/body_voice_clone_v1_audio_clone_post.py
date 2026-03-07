from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from .. import types

from ..types import UNSET, Unset

from ..models.body_voice_clone_v1_audio_clone_post_response_format import (
    BodyVoiceCloneV1AudioClonePostResponseFormat,
)
from ..types import File
from io import BytesIO
from typing import cast


T = TypeVar("T", bound="BodyVoiceCloneV1AudioClonePost")


@_attrs_define
class BodyVoiceCloneV1AudioClonePost:
    """
    Attributes:
        reference_audio (File): Reference audio recording for voice cloning (wav/mp3/m4a, 3-30s recommended)
        text (str): Text to synthesize in the cloned voice
        model (str | Unset): TTS model to use for voice cloning (must support cloning, e.g. Qwen3-TTS base variants)
            Default: 'Qwen/Qwen3-TTS-12Hz-0.6B-Base'.
        reference_text (None | str | Unset): Optional transcript of the reference audio
        language (str | Unset): Target language code (e.g. 'en', 'zh') Default: 'en'.
        response_format (BodyVoiceCloneV1AudioClonePostResponseFormat | Unset): Output format Default:
            BodyVoiceCloneV1AudioClonePostResponseFormat.WAV.
    """

    reference_audio: File
    text: str
    model: str | Unset = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    reference_text: None | str | Unset = UNSET
    language: str | Unset = "en"
    response_format: BodyVoiceCloneV1AudioClonePostResponseFormat | Unset = (
        BodyVoiceCloneV1AudioClonePostResponseFormat.WAV
    )
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        reference_audio = self.reference_audio.to_tuple()

        text = self.text

        model = self.model

        reference_text: None | str | Unset
        if isinstance(self.reference_text, Unset):
            reference_text = UNSET
        else:
            reference_text = self.reference_text

        language = self.language

        response_format: str | Unset = UNSET
        if not isinstance(self.response_format, Unset):
            response_format = self.response_format.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "reference_audio": reference_audio,
                "text": text,
            }
        )
        if model is not UNSET:
            field_dict["model"] = model
        if reference_text is not UNSET:
            field_dict["reference_text"] = reference_text
        if language is not UNSET:
            field_dict["language"] = language
        if response_format is not UNSET:
            field_dict["response_format"] = response_format

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("reference_audio", self.reference_audio.to_tuple()))

        files.append(("text", (None, str(self.text).encode(), "text/plain")))

        if not isinstance(self.model, Unset):
            files.append(("model", (None, str(self.model).encode(), "text/plain")))

        if not isinstance(self.reference_text, Unset):
            if isinstance(self.reference_text, str):
                files.append(
                    (
                        "reference_text",
                        (None, str(self.reference_text).encode(), "text/plain"),
                    )
                )
            else:
                files.append(
                    (
                        "reference_text",
                        (None, str(self.reference_text).encode(), "text/plain"),
                    )
                )

        if not isinstance(self.language, Unset):
            files.append(
                ("language", (None, str(self.language).encode(), "text/plain"))
            )

        if not isinstance(self.response_format, Unset):
            files.append(
                (
                    "response_format",
                    (None, str(self.response_format.value).encode(), "text/plain"),
                )
            )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        reference_audio = File(payload=BytesIO(d.pop("reference_audio")))

        text = d.pop("text")

        model = d.pop("model", UNSET)

        def _parse_reference_text(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        reference_text = _parse_reference_text(d.pop("reference_text", UNSET))

        language = d.pop("language", UNSET)

        _response_format = d.pop("response_format", UNSET)
        response_format: BodyVoiceCloneV1AudioClonePostResponseFormat | Unset
        if isinstance(_response_format, Unset):
            response_format = UNSET
        else:
            response_format = BodyVoiceCloneV1AudioClonePostResponseFormat(
                _response_format
            )

        body_voice_clone_v1_audio_clone_post = cls(
            reference_audio=reference_audio,
            text=text,
            model=model,
            reference_text=reference_text,
            language=language,
            response_format=response_format,
        )

        body_voice_clone_v1_audio_clone_post.additional_properties = d
        return body_voice_clone_v1_audio_clone_post

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
