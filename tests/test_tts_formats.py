"""Tests for TTS multi-format audio conversion."""

import struct
import wave

import pytest


def _make_wav(path: str, duration: float = 0.5, sample_rate: int = 22050) -> None:
    """Create a minimal valid WAV file with a sine tone."""
    import math

    n_samples = int(sample_rate * duration)
    samples = [int(32767 * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(n_samples)]
    raw = struct.pack(f"<{n_samples}h", *samples)

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)


class TestConvertAudio:
    """Test the _convert_audio function."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.wav_path = str(tmp_path / "test.wav")
        _make_wav(self.wav_path)

    def _convert(self, path, fmt):
        from vocal_core.adapters.tts.piper import _convert_audio

        return _convert_audio(path, fmt)

    def test_wav_passthrough(self):
        """WAV input with WAV target should skip ffmpeg (fast path)."""
        data, sr, dur = self._convert(self.wav_path, "wav")
        assert data[:4] == b"RIFF"
        assert sr == 22050
        assert dur > 0

    def test_convert_to_mp3(self):
        """Convert WAV to MP3."""
        data, sr, dur = self._convert(self.wav_path, "mp3")
        assert len(data) > 0
        # MP3 files start with ID3 tag or sync word 0xFF 0xFB
        assert data[:3] == b"ID3" or data[0] == 0xFF
        assert sr == 22050

    def test_convert_to_flac(self):
        """Convert WAV to FLAC."""
        data, sr, dur = self._convert(self.wav_path, "flac")
        assert len(data) > 0
        assert data[:4] == b"fLaC"

    def test_convert_to_opus(self):
        """Convert WAV to Opus."""
        data, sr, dur = self._convert(self.wav_path, "opus")
        assert len(data) > 0
        # Opus in Ogg container starts with OggS
        assert data[:4] == b"OggS"

    def test_convert_to_aac(self):
        """Convert WAV to AAC (ADTS)."""
        data, sr, dur = self._convert(self.wav_path, "aac")
        assert len(data) > 0

    def test_convert_to_pcm(self):
        """Convert WAV to raw PCM (headerless s16le)."""
        data, sr, dur = self._convert(self.wav_path, "pcm")
        assert len(data) > 0
        # PCM should be roughly n_samples * 2 bytes (16-bit)
        expected = int(22050 * 0.5) * 2
        assert abs(len(data) - expected) < 100  # allow small tolerance

    def test_unsupported_format_raises(self):
        """Unsupported format should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported format"):
            self._convert(self.wav_path, "wma")

    def test_mp3_smaller_than_wav(self):
        """MP3 should be significantly smaller than WAV."""
        wav_data, _, _ = self._convert(self.wav_path, "wav")
        mp3_data, _, _ = self._convert(self.wav_path, "mp3")
        assert len(mp3_data) < len(wav_data)


class TestSupportedFormats:
    """Test SUPPORTED_FORMATS constant and API schema alignment."""

    def test_supported_formats_set(self):
        from vocal_core.adapters.tts.piper import SUPPORTED_FORMATS

        assert SUPPORTED_FORMATS == {"mp3", "opus", "aac", "flac", "wav", "pcm"}

    def test_api_schema_matches(self):
        """API AudioFormat literal should match SUPPORTED_FORMATS."""
        from typing import get_args

        from vocal_api.routes.tts import AudioFormat
        from vocal_core.adapters.tts.piper import SUPPORTED_FORMATS

        api_formats = set(get_args(AudioFormat))
        assert api_formats == SUPPORTED_FORMATS

    def test_default_format_is_mp3(self):
        """Default response_format in API should be mp3."""
        from vocal_api.routes.tts import TTSRequest

        req = TTSRequest(model="test", input="hello")
        assert req.response_format == "mp3"

    def test_invalid_format_rejected_by_schema(self):
        """API schema should reject invalid formats."""
        from pydantic import ValidationError

        from vocal_api.routes.tts import TTSRequest

        with pytest.raises(ValidationError):
            TTSRequest(model="test", input="hello", response_format="wma")


class TestMediaTypes:
    """Test Content-Type mapping."""

    def test_media_types_complete(self):
        from vocal_api.routes.tts import _MEDIA_TYPES
        from vocal_core.adapters.tts.piper import SUPPORTED_FORMATS

        for fmt in SUPPORTED_FORMATS:
            assert fmt in _MEDIA_TYPES, f"Missing media type for {fmt}"

    def test_mp3_content_type(self):
        from vocal_api.routes.tts import _MEDIA_TYPES

        assert _MEDIA_TYPES["mp3"] == "audio/mpeg"

    def test_wav_content_type(self):
        from vocal_api.routes.tts import _MEDIA_TYPES

        assert _MEDIA_TYPES["wav"] == "audio/wav"
