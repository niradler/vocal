from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, TYPE_CHECKING

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast

if TYPE_CHECKING:
    from ..models.transcription_segment import TranscriptionSegment
    from ..models.transcription_word import TranscriptionWord


T = TypeVar("T", bound="TranscriptionResponse")


@_attrs_define
class TranscriptionResponse:
    """Response schema for transcription

    Example:
        {'duration': 2.5, 'language': 'en', 'segments': [{'end': 2.5, 'id': 0, 'start': 0.0, 'text': 'Hello, how are you
            today?'}], 'text': 'Hello, how are you today?'}

    Attributes:
        text (str): Full transcribed text
        language (str): Detected or specified language
        duration (float): Audio duration in seconds
        segments (list[TranscriptionSegment] | None | Unset):
        words (list[TranscriptionWord] | None | Unset):
    """

    text: str
    language: str
    duration: float
    segments: list[TranscriptionSegment] | None | Unset = UNSET
    words: list[TranscriptionWord] | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        text = self.text

        language = self.language

        duration = self.duration

        segments: list[dict[str, Any]] | None | Unset
        if isinstance(self.segments, Unset):
            segments = UNSET
        elif isinstance(self.segments, list):
            segments = []
            for segments_type_0_item_data in self.segments:
                segments_type_0_item = segments_type_0_item_data.to_dict()
                segments.append(segments_type_0_item)

        else:
            segments = self.segments

        words: list[dict[str, Any]] | None | Unset
        if isinstance(self.words, Unset):
            words = UNSET
        elif isinstance(self.words, list):
            words = []
            for words_type_0_item_data in self.words:
                words_type_0_item = words_type_0_item_data.to_dict()
                words.append(words_type_0_item)

        else:
            words = self.words

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "text": text,
                "language": language,
                "duration": duration,
            }
        )
        if segments is not UNSET:
            field_dict["segments"] = segments
        if words is not UNSET:
            field_dict["words"] = words

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.transcription_segment import TranscriptionSegment
        from ..models.transcription_word import TranscriptionWord

        d = dict(src_dict)
        text = d.pop("text")

        language = d.pop("language")

        duration = d.pop("duration")

        def _parse_segments(data: object) -> list[TranscriptionSegment] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                segments_type_0 = []
                _segments_type_0 = data
                for segments_type_0_item_data in _segments_type_0:
                    segments_type_0_item = TranscriptionSegment.from_dict(
                        segments_type_0_item_data
                    )

                    segments_type_0.append(segments_type_0_item)

                return segments_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[TranscriptionSegment] | None | Unset, data)

        segments = _parse_segments(d.pop("segments", UNSET))

        def _parse_words(data: object) -> list[TranscriptionWord] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                words_type_0 = []
                _words_type_0 = data
                for words_type_0_item_data in _words_type_0:
                    words_type_0_item = TranscriptionWord.from_dict(
                        words_type_0_item_data
                    )

                    words_type_0.append(words_type_0_item)

                return words_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[TranscriptionWord] | None | Unset, data)

        words = _parse_words(d.pop("words", UNSET))

        transcription_response = cls(
            text=text,
            language=language,
            duration=duration,
            segments=segments,
            words=words,
        )

        transcription_response.additional_properties = d
        return transcription_response

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
