from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="SettingsResponse")


@_attrs_define
class SettingsResponse:
    """Current effective settings. Plain types on purpose: constraints belong to
    the request (SettingsPayload); the response reports reality, and a typed
    schema gives the generated SDK real attributes instead of a dict.

        Attributes:
            llm_base_url (str):
            llm_model (str):
            llm_api_key (None | str):
            stt_default_model (str):
            stt_default_language (None | str):
            tts_default_model (str):
            tts_default_voice (None | str):
            tts_default_clone_model (str):
            default_language (str):
            vad_speech_threshold (float):
            vad_threshold (float):
            vad_onset_ms (int):
            vad_silence_ms (int):
            vad_commit_grace_ms (int):
            vad_min_speech_ms (int):
            vad_preroll_ms (int):
            realtime_agent_silence_ms (int):
            realtime_agent_commit_grace_ms (int):
            realtime_partial_interval_s (float):
            realtime_max_utterance_s (float):
            chat_system_prompt (str):
            log_level (str):
            llm_api_key_set (bool):
    """

    llm_base_url: str
    llm_model: str
    llm_api_key: None | str
    stt_default_model: str
    stt_default_language: None | str
    tts_default_model: str
    tts_default_voice: None | str
    tts_default_clone_model: str
    default_language: str
    vad_speech_threshold: float
    vad_threshold: float
    vad_onset_ms: int
    vad_silence_ms: int
    vad_commit_grace_ms: int
    vad_min_speech_ms: int
    vad_preroll_ms: int
    realtime_agent_silence_ms: int
    realtime_agent_commit_grace_ms: int
    realtime_partial_interval_s: float
    realtime_max_utterance_s: float
    chat_system_prompt: str
    log_level: str
    llm_api_key_set: bool
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        llm_base_url = self.llm_base_url

        llm_model = self.llm_model

        llm_api_key: None | str
        llm_api_key = self.llm_api_key

        stt_default_model = self.stt_default_model

        stt_default_language: None | str
        stt_default_language = self.stt_default_language

        tts_default_model = self.tts_default_model

        tts_default_voice: None | str
        tts_default_voice = self.tts_default_voice

        tts_default_clone_model = self.tts_default_clone_model

        default_language = self.default_language

        vad_speech_threshold = self.vad_speech_threshold

        vad_threshold = self.vad_threshold

        vad_onset_ms = self.vad_onset_ms

        vad_silence_ms = self.vad_silence_ms

        vad_commit_grace_ms = self.vad_commit_grace_ms

        vad_min_speech_ms = self.vad_min_speech_ms

        vad_preroll_ms = self.vad_preroll_ms

        realtime_agent_silence_ms = self.realtime_agent_silence_ms

        realtime_agent_commit_grace_ms = self.realtime_agent_commit_grace_ms

        realtime_partial_interval_s = self.realtime_partial_interval_s

        realtime_max_utterance_s = self.realtime_max_utterance_s

        chat_system_prompt = self.chat_system_prompt

        log_level = self.log_level

        llm_api_key_set = self.llm_api_key_set

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "LLM_BASE_URL": llm_base_url,
                "LLM_MODEL": llm_model,
                "LLM_API_KEY": llm_api_key,
                "STT_DEFAULT_MODEL": stt_default_model,
                "STT_DEFAULT_LANGUAGE": stt_default_language,
                "TTS_DEFAULT_MODEL": tts_default_model,
                "TTS_DEFAULT_VOICE": tts_default_voice,
                "TTS_DEFAULT_CLONE_MODEL": tts_default_clone_model,
                "DEFAULT_LANGUAGE": default_language,
                "VAD_SPEECH_THRESHOLD": vad_speech_threshold,
                "VAD_THRESHOLD": vad_threshold,
                "VAD_ONSET_MS": vad_onset_ms,
                "VAD_SILENCE_MS": vad_silence_ms,
                "VAD_COMMIT_GRACE_MS": vad_commit_grace_ms,
                "VAD_MIN_SPEECH_MS": vad_min_speech_ms,
                "VAD_PREROLL_MS": vad_preroll_ms,
                "REALTIME_AGENT_SILENCE_MS": realtime_agent_silence_ms,
                "REALTIME_AGENT_COMMIT_GRACE_MS": realtime_agent_commit_grace_ms,
                "REALTIME_PARTIAL_INTERVAL_S": realtime_partial_interval_s,
                "REALTIME_MAX_UTTERANCE_S": realtime_max_utterance_s,
                "CHAT_SYSTEM_PROMPT": chat_system_prompt,
                "LOG_LEVEL": log_level,
                "llm_api_key_set": llm_api_key_set,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        llm_base_url = d.pop("LLM_BASE_URL")

        llm_model = d.pop("LLM_MODEL")

        def _parse_llm_api_key(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        llm_api_key = _parse_llm_api_key(d.pop("LLM_API_KEY"))

        stt_default_model = d.pop("STT_DEFAULT_MODEL")

        def _parse_stt_default_language(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        stt_default_language = _parse_stt_default_language(
            d.pop("STT_DEFAULT_LANGUAGE")
        )

        tts_default_model = d.pop("TTS_DEFAULT_MODEL")

        def _parse_tts_default_voice(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        tts_default_voice = _parse_tts_default_voice(d.pop("TTS_DEFAULT_VOICE"))

        tts_default_clone_model = d.pop("TTS_DEFAULT_CLONE_MODEL")

        default_language = d.pop("DEFAULT_LANGUAGE")

        vad_speech_threshold = d.pop("VAD_SPEECH_THRESHOLD")

        vad_threshold = d.pop("VAD_THRESHOLD")

        vad_onset_ms = d.pop("VAD_ONSET_MS")

        vad_silence_ms = d.pop("VAD_SILENCE_MS")

        vad_commit_grace_ms = d.pop("VAD_COMMIT_GRACE_MS")

        vad_min_speech_ms = d.pop("VAD_MIN_SPEECH_MS")

        vad_preroll_ms = d.pop("VAD_PREROLL_MS")

        realtime_agent_silence_ms = d.pop("REALTIME_AGENT_SILENCE_MS")

        realtime_agent_commit_grace_ms = d.pop("REALTIME_AGENT_COMMIT_GRACE_MS")

        realtime_partial_interval_s = d.pop("REALTIME_PARTIAL_INTERVAL_S")

        realtime_max_utterance_s = d.pop("REALTIME_MAX_UTTERANCE_S")

        chat_system_prompt = d.pop("CHAT_SYSTEM_PROMPT")

        log_level = d.pop("LOG_LEVEL")

        llm_api_key_set = d.pop("llm_api_key_set")

        settings_response = cls(
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
            llm_api_key_set=llm_api_key_set,
        )

        settings_response.additional_properties = d
        return settings_response

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
