"""Regression tests for OpenAI-compatibility bugs (#13, #14)."""

import struct

import pytest

from vocal_api.models.transcription import TranscriptionFormat, TranscriptionResponse, TranscriptionSegment
from vocal_api.routes.transcription import _render_subtitles, _srt_timestamp, _vtt_timestamp
from vocal_core.adapters.tts.kokoro import (
    KOKORO_VOICE_DATA,
    OPENAI_VOICE_ALIASES,
    _wav_header_open_ended,
    resolve_voice_name,
)


class TestStreamingWavHeader:
    """#13: `36 + 0xFFFFFFFF` overflowed the RIFF size field."""

    def test_header_is_valid_riff(self):
        header = _wav_header_open_ended(24000)
        assert len(header) == 44
        assert header[:4] == b"RIFF"
        assert header[8:12] == b"WAVE"
        assert header[36:40] == b"data"

    def test_unknown_sizes_are_ffffffff(self):
        header = _wav_header_open_ended(24000)
        riff_size = struct.unpack("<I", header[4:8])[0]
        data_size = struct.unpack("<I", header[40:44])[0]
        assert riff_size == 0xFFFFFFFF
        assert data_size == 0xFFFFFFFF

    def test_format_fields_match_sample_rate(self):
        header = _wav_header_open_ended(16000, num_channels=1, bits_per_sample=16)
        channels, rate, _byte_rate, _align, bits = struct.unpack("<HHIIH", header[22:36])
        assert (channels, rate, bits) == (1, 16000, 16)


class TestVoiceNames:
    """#13: OpenAI voice names must not 500."""

    @pytest.mark.parametrize("alias", sorted(OPENAI_VOICE_ALIASES))
    def test_openai_alias_maps_to_a_real_kokoro_voice(self, alias):
        resolved = resolve_voice_name(alias)
        assert resolved in KOKORO_VOICE_DATA

    def test_unknown_name_is_passed_through(self):
        assert resolve_voice_name("af_bella") == "af_bella"

    def test_alias_is_case_insensitive(self):
        assert resolve_voice_name("Alloy") == "af_alloy"
        assert resolve_voice_name("  ONYX ") == "am_onyx"


class TestSubtitleRendering:
    """#14: response_format=srt/vtt must produce real subtitle text."""

    def _result(self) -> TranscriptionResponse:
        return TranscriptionResponse(
            text="Hello there. General Kenobi.",
            language="en",
            duration=4.0,
            segments=[
                TranscriptionSegment(id=0, start=0.0, end=1.5, text="Hello there."),
                TranscriptionSegment(id=1, start=1.5, end=4.0, text="General Kenobi."),
            ],
        )

    def test_timestamps(self):
        assert _srt_timestamp(0) == "00:00:00,000"
        assert _srt_timestamp(3661.5) == "01:01:01,500"
        assert _vtt_timestamp(1.25) == "00:00:01.250"

    def test_srt(self):
        out = _render_subtitles(self._result(), TranscriptionFormat.SRT)
        lines = out.splitlines()
        assert lines[0] == "1"
        assert lines[1] == "00:00:00,000 --> 00:00:01,500"
        assert lines[2] == "Hello there."
        assert lines[4] == "2"

    def test_vtt(self):
        out = _render_subtitles(self._result(), TranscriptionFormat.VTT)
        lines = out.splitlines()
        assert lines[0] == "WEBVTT"
        assert "00:00:01.500 --> 00:00:04.000" in out
        assert "General Kenobi." in out

    def test_falls_back_to_one_cue(self):
        result = TranscriptionResponse(text="Only line", language="en", duration=2.0, segments=None)
        out = _render_subtitles(result, TranscriptionFormat.SRT)
        assert "00:00:00,000 --> 00:00:02,000" in out
        assert "Only line" in out
