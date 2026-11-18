from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.settings_payload_loglevel_type_0 import SettingsPayloadLOGLEVELType0
from ..types import UNSET, Unset

T = TypeVar("T", bound="SettingsPayload")


@_attrs_define
class SettingsPayload:
    """Editable Vocal settings. Omitted (null) fields are left unchanged on update.

    Attributes:
        llm_base_url (None | str | Unset): OpenAI-compatible LLM base URL for the voice agent
        llm_model (None | str | Unset): LLM model used by the voice agent
        llm_api_key (None | str | Unset): LLM API key; the masked value or an empty string keeps the current key
        stt_default_model (None | str | Unset): Default speech-to-text model
        stt_default_language (None | str | Unset): Default STT language code; empty string means auto-detect
        tts_default_model (None | str | Unset): Default text-to-speech model
        tts_default_voice (None | str | Unset): Default TTS voice; empty string means model default
        tts_default_clone_model (None | str | Unset): Default model for voice cloning
        default_language (None | str | Unset): Default language code
        vad_speech_threshold (float | None | Unset): Silero speech probability threshold
        vad_threshold (float | None | Unset): RMS energy threshold (fallback VAD)
        vad_onset_ms (int | None | Unset): Speech onset confirmation window
        vad_silence_ms (int | None | Unset): Dictation: silence before a turn commits
        vad_commit_grace_ms (int | None | Unset): Dictation: extra grace after silence
        vad_min_speech_ms (int | None | Unset): Minimum speech duration to count as a turn
        vad_preroll_ms (int | None | Unset): Audio kept before speech onset
        realtime_agent_silence_ms (int | None | Unset): Voice agent: silence before a turn commits
        realtime_agent_commit_grace_ms (int | None | Unset): Voice agent: extra grace after silence
        realtime_partial_interval_s (float | None | Unset): Live partial transcript interval; 0 disables partials
        realtime_max_utterance_s (float | None | Unset): Maximum single utterance length
        chat_system_prompt (None | str | Unset): Voice agent system prompt; empty string disables it
        log_level (None | SettingsPayloadLOGLEVELType0 | Unset): Server log level (applies to new log records)
    """

    llm_base_url: None | str | Unset = UNSET
    llm_model: None | str | Unset = UNSET
    llm_api_key: None | str | Unset = UNSET
    stt_default_model: None | str | Unset = UNSET
    stt_default_language: None | str | Unset = UNSET
    tts_default_model: None | str | Unset = UNSET
    tts_default_voice: None | str | Unset = UNSET
    tts_default_clone_model: None | str | Unset = UNSET
    default_language: None | str | Unset = UNSET
    vad_speech_threshold: float | None | Unset = UNSET
    vad_threshold: float | None | Unset = UNSET
    vad_onset_ms: int | None | Unset = UNSET
    vad_silence_ms: int | None | Unset = UNSET
    vad_commit_grace_ms: int | None | Unset = UNSET
    vad_min_speech_ms: int | None | Unset = UNSET
    vad_preroll_ms: int | None | Unset = UNSET
    realtime_agent_silence_ms: int | None | Unset = UNSET
    realtime_agent_commit_grace_ms: int | None | Unset = UNSET
    realtime_partial_interval_s: float | None | Unset = UNSET
    realtime_max_utterance_s: float | None | Unset = UNSET
    chat_system_prompt: None | str | Unset = UNSET
    log_level: None | SettingsPayloadLOGLEVELType0 | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        llm_base_url: None | str | Unset
        if isinstance(self.llm_base_url, Unset):
            llm_base_url = UNSET
        else:
            llm_base_url = self.llm_base_url

        llm_model: None | str | Unset
        if isinstance(self.llm_model, Unset):
            llm_model = UNSET
        else:
            llm_model = self.llm_model

        llm_api_key: None | str | Unset
        if isinstance(self.llm_api_key, Unset):
            llm_api_key = UNSET
        else:
            llm_api_key = self.llm_api_key

        stt_default_model: None | str | Unset
        if isinstance(self.stt_default_model, Unset):
            stt_default_model = UNSET
        else:
            stt_default_model = self.stt_default_model

        stt_default_language: None | str | Unset
        if isinstance(self.stt_default_language, Unset):
            stt_default_language = UNSET
        else:
            stt_default_language = self.stt_default_language

        tts_default_model: None | str | Unset
        if isinstance(self.tts_default_model, Unset):
            tts_default_model = UNSET
        else:
            tts_default_model = self.tts_default_model

        tts_default_voice: None | str | Unset
        if isinstance(self.tts_default_voice, Unset):
            tts_default_voice = UNSET
        else:
            tts_default_voice = self.tts_default_voice

        tts_default_clone_model: None | str | Unset
        if isinstance(self.tts_default_clone_model, Unset):
            tts_default_clone_model = UNSET
        else:
            tts_default_clone_model = self.tts_default_clone_model

        default_language: None | str | Unset
        if isinstance(self.default_language, Unset):
            default_language = UNSET
        else:
            default_language = self.default_language

        vad_speech_threshold: float | None | Unset
        if isinstance(self.vad_speech_threshold, Unset):
            vad_speech_threshold = UNSET
        else:
            vad_speech_threshold = self.vad_speech_threshold

        vad_threshold: float | None | Unset
        if isinstance(self.vad_threshold, Unset):
            vad_threshold = UNSET
        else:
            vad_threshold = self.vad_threshold

        vad_onset_ms: int | None | Unset
        if isinstance(self.vad_onset_ms, Unset):
            vad_onset_ms = UNSET
        else:
            vad_onset_ms = self.vad_onset_ms

        vad_silence_ms: int | None | Unset
        if isinstance(self.vad_silence_ms, Unset):
            vad_silence_ms = UNSET
        else:
            vad_silence_ms = self.vad_silence_ms

        vad_commit_grace_ms: int | None | Unset
        if isinstance(self.vad_commit_grace_ms, Unset):
            vad_commit_grace_ms = UNSET
        else:
            vad_commit_grace_ms = self.vad_commit_grace_ms

        vad_min_speech_ms: int | None | Unset
        if isinstance(self.vad_min_speech_ms, Unset):
            vad_min_speech_ms = UNSET
        else:
            vad_min_speech_ms = self.vad_min_speech_ms

        vad_preroll_ms: int | None | Unset
        if isinstance(self.vad_preroll_ms, Unset):
            vad_preroll_ms = UNSET
        else:
            vad_preroll_ms = self.vad_preroll_ms

        realtime_agent_silence_ms: int | None | Unset
        if isinstance(self.realtime_agent_silence_ms, Unset):
            realtime_agent_silence_ms = UNSET
        else:
            realtime_agent_silence_ms = self.realtime_agent_silence_ms

        realtime_agent_commit_grace_ms: int | None | Unset
        if isinstance(self.realtime_agent_commit_grace_ms, Unset):
            realtime_agent_commit_grace_ms = UNSET
        else:
            realtime_agent_commit_grace_ms = self.realtime_agent_commit_grace_ms

        realtime_partial_interval_s: float | None | Unset
        if isinstance(self.realtime_partial_interval_s, Unset):
            realtime_partial_interval_s = UNSET
        else:
            realtime_partial_interval_s = self.realtime_partial_interval_s

        realtime_max_utterance_s: float | None | Unset
        if isinstance(self.realtime_max_utterance_s, Unset):
            realtime_max_utterance_s = UNSET
        else:
            realtime_max_utterance_s = self.realtime_max_utterance_s

        chat_system_prompt: None | str | Unset
        if isinstance(self.chat_system_prompt, Unset):
            chat_system_prompt = UNSET
        else:
            chat_system_prompt = self.chat_system_prompt

        log_level: None | str | Unset
        if isinstance(self.log_level, Unset):
            log_level = UNSET
        elif isinstance(self.log_level, SettingsPayloadLOGLEVELType0):
            log_level = self.log_level.value
        else:
            log_level = self.log_level

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if llm_base_url is not UNSET:
            field_dict["LLM_BASE_URL"] = llm_base_url
        if llm_model is not UNSET:
            field_dict["LLM_MODEL"] = llm_model
        if llm_api_key is not UNSET:
            field_dict["LLM_API_KEY"] = llm_api_key
        if stt_default_model is not UNSET:
            field_dict["STT_DEFAULT_MODEL"] = stt_default_model
        if stt_default_language is not UNSET:
            field_dict["STT_DEFAULT_LANGUAGE"] = stt_default_language
        if tts_default_model is not UNSET:
            field_dict["TTS_DEFAULT_MODEL"] = tts_default_model
        if tts_default_voice is not UNSET:
            field_dict["TTS_DEFAULT_VOICE"] = tts_default_voice
        if tts_default_clone_model is not UNSET:
            field_dict["TTS_DEFAULT_CLONE_MODEL"] = tts_default_clone_model
        if default_language is not UNSET:
            field_dict["DEFAULT_LANGUAGE"] = default_language
        if vad_speech_threshold is not UNSET:
            field_dict["VAD_SPEECH_THRESHOLD"] = vad_speech_threshold
        if vad_threshold is not UNSET:
            field_dict["VAD_THRESHOLD"] = vad_threshold
        if vad_onset_ms is not UNSET:
            field_dict["VAD_ONSET_MS"] = vad_onset_ms
        if vad_silence_ms is not UNSET:
            field_dict["VAD_SILENCE_MS"] = vad_silence_ms
        if vad_commit_grace_ms is not UNSET:
            field_dict["VAD_COMMIT_GRACE_MS"] = vad_commit_grace_ms
        if vad_min_speech_ms is not UNSET:
            field_dict["VAD_MIN_SPEECH_MS"] = vad_min_speech_ms
        if vad_preroll_ms is not UNSET:
            field_dict["VAD_PREROLL_MS"] = vad_preroll_ms
        if realtime_agent_silence_ms is not UNSET:
            field_dict["REALTIME_AGENT_SILENCE_MS"] = realtime_agent_silence_ms
        if realtime_agent_commit_grace_ms is not UNSET:
            field_dict["REALTIME_AGENT_COMMIT_GRACE_MS"] = (
                realtime_agent_commit_grace_ms
            )
        if realtime_partial_interval_s is not UNSET:
            field_dict["REALTIME_PARTIAL_INTERVAL_S"] = realtime_partial_interval_s
        if realtime_max_utterance_s is not UNSET:
            field_dict["REALTIME_MAX_UTTERANCE_S"] = realtime_max_utterance_s
        if chat_system_prompt is not UNSET:
            field_dict["CHAT_SYSTEM_PROMPT"] = chat_system_prompt
        if log_level is not UNSET:
            field_dict["LOG_LEVEL"] = log_level

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)

        def _parse_llm_base_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        llm_base_url = _parse_llm_base_url(d.pop("LLM_BASE_URL", UNSET))

        def _parse_llm_model(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        llm_model = _parse_llm_model(d.pop("LLM_MODEL", UNSET))

        def _parse_llm_api_key(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        llm_api_key = _parse_llm_api_key(d.pop("LLM_API_KEY", UNSET))

        def _parse_stt_default_model(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        stt_default_model = _parse_stt_default_model(d.pop("STT_DEFAULT_MODEL", UNSET))

        def _parse_stt_default_language(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        stt_default_language = _parse_stt_default_language(
            d.pop("STT_DEFAULT_LANGUAGE", UNSET)
        )

        def _parse_tts_default_model(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        tts_default_model = _parse_tts_default_model(d.pop("TTS_DEFAULT_MODEL", UNSET))

        def _parse_tts_default_voice(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        tts_default_voice = _parse_tts_default_voice(d.pop("TTS_DEFAULT_VOICE", UNSET))

        def _parse_tts_default_clone_model(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        tts_default_clone_model = _parse_tts_default_clone_model(
            d.pop("TTS_DEFAULT_CLONE_MODEL", UNSET)
        )

        def _parse_default_language(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        default_language = _parse_default_language(d.pop("DEFAULT_LANGUAGE", UNSET))

        def _parse_vad_speech_threshold(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        vad_speech_threshold = _parse_vad_speech_threshold(
            d.pop("VAD_SPEECH_THRESHOLD", UNSET)
        )

        def _parse_vad_threshold(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        vad_threshold = _parse_vad_threshold(d.pop("VAD_THRESHOLD", UNSET))

        def _parse_vad_onset_ms(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        vad_onset_ms = _parse_vad_onset_ms(d.pop("VAD_ONSET_MS", UNSET))

        def _parse_vad_silence_ms(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        vad_silence_ms = _parse_vad_silence_ms(d.pop("VAD_SILENCE_MS", UNSET))

        def _parse_vad_commit_grace_ms(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        vad_commit_grace_ms = _parse_vad_commit_grace_ms(
            d.pop("VAD_COMMIT_GRACE_MS", UNSET)
        )

        def _parse_vad_min_speech_ms(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        vad_min_speech_ms = _parse_vad_min_speech_ms(d.pop("VAD_MIN_SPEECH_MS", UNSET))

        def _parse_vad_preroll_ms(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        vad_preroll_ms = _parse_vad_preroll_ms(d.pop("VAD_PREROLL_MS", UNSET))

        def _parse_realtime_agent_silence_ms(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        realtime_agent_silence_ms = _parse_realtime_agent_silence_ms(
            d.pop("REALTIME_AGENT_SILENCE_MS", UNSET)
        )

        def _parse_realtime_agent_commit_grace_ms(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        realtime_agent_commit_grace_ms = _parse_realtime_agent_commit_grace_ms(
            d.pop("REALTIME_AGENT_COMMIT_GRACE_MS", UNSET)
        )

        def _parse_realtime_partial_interval_s(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        realtime_partial_interval_s = _parse_realtime_partial_interval_s(
            d.pop("REALTIME_PARTIAL_INTERVAL_S", UNSET)
        )

        def _parse_realtime_max_utterance_s(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        realtime_max_utterance_s = _parse_realtime_max_utterance_s(
            d.pop("REALTIME_MAX_UTTERANCE_S", UNSET)
        )

        def _parse_chat_system_prompt(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        chat_system_prompt = _parse_chat_system_prompt(
            d.pop("CHAT_SYSTEM_PROMPT", UNSET)
        )

        def _parse_log_level(
            data: object,
        ) -> None | SettingsPayloadLOGLEVELType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                log_level_type_0 = SettingsPayloadLOGLEVELType0(data)

                return log_level_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SettingsPayloadLOGLEVELType0 | Unset, data)

        log_level = _parse_log_level(d.pop("LOG_LEVEL", UNSET))

        settings_payload = cls(
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            stt_default_model=stt_default_model,
            stt_default_language=stt_default_language,
            tts_default_model=tts_default_model,
            tts_default_voice=tts_default_voice,
            tts_default_clone_model=tts_default_clone_model,
            default_language=default_language,
            vad_speech_threshold=vad_speech_threshold,
            vad_threshold=vad_threshold,
            vad_onset_ms=vad_onset_ms,
            vad_silence_ms=vad_silence_ms,
            vad_commit_grace_ms=vad_commit_grace_ms,
            vad_min_speech_ms=vad_min_speech_ms,
            vad_preroll_ms=vad_preroll_ms,
            realtime_agent_silence_ms=realtime_agent_silence_ms,
            realtime_agent_commit_grace_ms=realtime_agent_commit_grace_ms,
            realtime_partial_interval_s=realtime_partial_interval_s,
            realtime_max_utterance_s=realtime_max_utterance_s,
            chat_system_prompt=chat_system_prompt,
            log_level=log_level,
        )

        settings_payload.additional_properties = d
        return settings_payload

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
