"""Streaming WAV headers must stay valid uint32 RIFF chunks."""

import struct

import numpy as np
import pytest
import torch

from vocal_core.adapters.tts.kokoro import _to_pcm16 as kokoro_pcm16
from vocal_core.adapters.tts.kokoro import _wav_header_open_ended as kokoro_header
from vocal_core.adapters.tts.phonon import _to_pcm16 as phonon_pcm16
from vocal_core.adapters.tts.phonon import _wav_header_open_ended as phonon_header


@pytest.mark.parametrize("header_factory", [phonon_header, kokoro_header])
def test_open_ended_wav_header_is_packable_and_streaming_sized(header_factory):
    header = header_factory(24000)

    assert len(header) == 44
    assert header[:4] == b"RIFF"
    assert header[8:12] == b"WAVE"
    assert header[36:40] == b"data"

    riff_size = struct.unpack("<I", header[4:8])[0]
    data_size = struct.unpack("<I", header[40:44])[0]
    # Streaming headers declare "unknown length"; 36 + 0xFFFFFFFF would overflow uint32.
    assert riff_size == 0xFFFFFFFF
    assert data_size == 0xFFFFFFFF


@pytest.mark.parametrize("header_factory", [phonon_header, kokoro_header])
def test_open_ended_wav_header_respects_sample_rate(header_factory):
    header = header_factory(16000)
    sample_rate, byte_rate, block_align, bits = struct.unpack("<IIHH", header[24:36])

    assert sample_rate == 16000
    assert byte_rate == 16000 * 2
    assert block_align == 2
    assert bits == 16


@pytest.mark.parametrize("convert", [phonon_pcm16, kokoro_pcm16])
def test_streaming_chunks_accept_numpy_and_torch(convert):
    """Kokoro's pipeline yields torch tensors; both adapters must emit int16 PCM."""
    samples = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
    expected = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

    assert convert(samples) == expected
    assert convert(torch.from_numpy(samples)) == expected


@pytest.mark.parametrize("convert", [phonon_pcm16, kokoro_pcm16])
def test_streaming_chunks_clip_out_of_range_samples(convert):
    loud = np.array([1.5, -1.5], dtype=np.float32)
    pcm = np.frombuffer(convert(loud), dtype=np.int16)

    assert pcm.tolist() == [32767, -32767]
