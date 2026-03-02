from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.tts_request_response_format import TTSRequestResponseFormat
from typing import cast


T = TypeVar("T", bound="TTSRequest")


@_attrs_define
class TTSRequest:
    """Text-to-Speech request (OpenAI-compatible)

    Attributes:
        model (str): TTS model to use (e.g., 'hexgrad/Kokoro-82M')
        input_ (str): The text to synthesize
        voice (None | str | Unset): Voice ID to use
        speed (float | Unset): Speech speed multiplier Default: 1.0.
        response_format (TTSRequestResponseFormat | Unset): Audio format: mp3, opus, aac, flac, wav, pcm Default:
            TTSRequestResponseFormat.MP3.
        stream (bool | Unset): Stream audio chunks as they are generated (wav/pcm yield true chunks; other formats send
            one chunk after full generation) Default: False.
    """

    model: str
    input_: str
    voice: None | str | Unset = UNSET
    speed: float | Unset = 1.0
    response_format: TTSRequestResponseFormat | Unset = TTSRequestResponseFormat.MP3
    stream: bool | Unset = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        model = self.model

        input_ = self.input_

        voice: None | str | Unset
        if isinstance(self.voice, Unset):
            voice = UNSET
        else:
            voice = self.voice

        speed = self.speed

        response_format: str | Unset = UNSET
        if not isinstance(self.response_format, Unset):
            response_format = self.response_format.value

        stream = self.stream

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "model": model,
                "input": input_,
            }
        )
        if voice is not UNSET:
            field_dict["voice"] = voice
        if speed is not UNSET:
            field_dict["speed"] = speed
        if response_format is not UNSET:
            field_dict["response_format"] = response_format
        if stream is not UNSET:
            field_dict["stream"] = stream

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        model = d.pop("model")

        input_ = d.pop("input")

        def _parse_voice(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        voice = _parse_voice(d.pop("voice", UNSET))

        speed = d.pop("speed", UNSET)

        _response_format = d.pop("response_format", UNSET)
        response_format: TTSRequestResponseFormat | Unset
        if isinstance(_response_format, Unset):
            response_format = UNSET
        else:
            response_format = TTSRequestResponseFormat(_response_format)

        stream = d.pop("stream", UNSET)

        tts_request = cls(
            model=model,
            input_=input_,
            voice=voice,
            speed=speed,
            response_format=response_format,
            stream=stream,
        )

        tts_request.additional_properties = d
        return tts_request

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
