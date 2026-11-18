"""Unit tests for the streaming VAD gate (turn boundaries, not probabilities)."""

import numpy as np

from vocal_core.audio.vad_gate import StreamingVADGate, SyntheticVAD

FRAME_MS = 32
SR = 16000
FRAME = b"\x00\x00" * int(SR * FRAME_MS / 1000)


def scripted(probabilities: list[float], default: float = 0.0) -> SyntheticVAD:
    return SyntheticVAD(script=probabilities, default=default)


def feed_seconds(gate: StreamingVADGate, seconds: float) -> list:
    """Feed whole frames for ``seconds`` and collect emitted boundaries."""
    events = []
    for _ in range(int(seconds * 1000 / FRAME_MS)):
        events.extend(gate.feed(FRAME))
    return events


def test_onset_debounce_ignores_single_blip():
    # One loud frame is not enough: onset requires 180 ms of continuous speech.
    gate = StreamingVADGate(scripted([0.9, 0.0, 0.0, 0.0]), onset_ms=180, silence_ms=300)
    events = feed_seconds(gate, 0.2)
    assert events == []
    assert gate.is_speaking is False


def test_speech_started_includes_preroll():
    # 300 ms of preroll + 180 ms of onset must be kept, so the first phoneme
    # is not clipped.
    vad = scripted([0.0] * 10 + [0.9] * 10)  # ~320 ms silence, then speech
    gate = StreamingVADGate(vad, onset_ms=180, silence_ms=300, preroll_ms=300)
    started = None
    for _ in range(int(0.75 * 1000 / FRAME_MS)):
        for event in gate.feed(FRAME):
            if event.kind == "speech_started":
                started = event
                # Snapshot at the moment the turn opens.
                assert len(gate.utterance_pcm) == event.audio_ms * 2 * SR // 1000
                break
        if started:
            break

    assert started is not None
    # preroll (<=300 ms) plus onset (180 ms) worth of audio
    assert 400 <= started.audio_ms <= 600


def test_hangover_keeps_turn_open_through_short_pause():
    # 1 s of speech, 200 ms pause, 1 s more speech, then long silence.
    pattern = [0.9] * 31 + [0.0] * 6 + [0.9] * 31 + [0.0] * 40
    gate = StreamingVADGate(scripted(pattern), onset_ms=180, silence_ms=500)
    events = feed_seconds(gate, len(pattern) * FRAME_MS / 1000)

    kinds = [e.kind for e in events]
    assert kinds.count("speech_started") == 1
    assert kinds.count("speech_stopped") == 1
    assert kinds.index("speech_stopped") > kinds.index("speech_started")


def test_commit_grace_merges_natural_pause():
    # ~1 s pause mid-sentence: with the agent defaults (700 ms + 400 ms grace)
    # the turn must not split.
    pattern = [0.9] * 31 + [0.0] * 31 + [0.9] * 31 + [0.0] * 40
    gate = StreamingVADGate(
        scripted(pattern),
        onset_ms=180,
        silence_ms=700,
        commit_grace_ms=400,
    )
    events = feed_seconds(gate, len(pattern) * FRAME_MS / 1000)

    kinds = [e.kind for e in events]
    assert kinds == ["speech_started", "speech_stopped"]


def test_without_grace_a_one_second_pause_splits():
    """Documents the tradeoff: dictation mode commits at 600 ms and splits."""
    pattern = [0.9] * 31 + [0.0] * 31 + [0.9] * 31 + [0.0] * 40
    gate = StreamingVADGate(scripted(pattern), onset_ms=180, silence_ms=600, commit_grace_ms=0)
    events = feed_seconds(gate, len(pattern) * FRAME_MS / 1000)

    kinds = [e.kind for e in events]
    assert kinds.count("speech_started") == 2
    assert kinds.count("speech_stopped") == 2


def test_commit_grace_expires_and_commits():
    pattern = [0.9] * 31 + [0.0] * 60
    gate = StreamingVADGate(scripted(pattern), onset_ms=180, silence_ms=300, commit_grace_ms=400)
    events = feed_seconds(gate, len(pattern) * FRAME_MS / 1000)

    stopped = [e for e in events if e.kind == "speech_stopped"]
    assert len(stopped) == 1
    # silence budget (300) plus grace (400), with frame granularity
    assert stopped[0].audio_ms > 0


def test_max_utterance_forces_commit():
    gate = StreamingVADGate(
        scripted([], default=0.9),
        onset_ms=180,
        silence_ms=1000,
        max_utterance_s=0.5,
    )
    events = feed_seconds(gate, 1.0)

    stopped = [e for e in events if e.kind == "speech_stopped"]
    assert len(stopped) == 1
    assert stopped[0].audio_ms >= 450


def test_trailing_silence_is_trimmed_but_a_tail_remains():
    pattern = [0.9] * 31 + [0.0] * 200
    gate = StreamingVADGate(scripted(pattern), onset_ms=180, silence_ms=400)
    events = feed_seconds(gate, len(pattern) * FRAME_MS / 1000)
    stopped = next(e for e in events if e.kind == "speech_stopped")

    # 400 ms silence budget, keep at most 200 ms of it (one frame of rounding).
    assert stopped.audio_ms <= 31 * FRAME_MS + 200 + FRAME_MS
    assert len(gate.utterance_pcm) == stopped.audio_ms * 2 * SR // 1000
    assert stopped.audio_ms >= 31 * FRAME_MS


def test_flush_closes_open_turn():
    gate = StreamingVADGate(scripted([], default=0.9), onset_ms=180, silence_ms=1000)
    feed_seconds(gate, 0.5)
    assert gate.is_speaking is True

    events = gate.flush()
    assert [e.kind for e in events] == ["speech_stopped"]
    assert gate.is_speaking is False


def test_flush_is_noop_when_idle():
    gate = StreamingVADGate(scripted([], default=0.0))
    assert gate.flush() == []


def test_partial_frames_are_buffered_until_complete():
    # 32 ms frames at 16 kHz = 1024 bytes; onset of 96 ms needs three frames.
    gate = StreamingVADGate(scripted([], default=0.9), onset_ms=96, min_speech_ms=0, silence_ms=1000)
    half = FRAME[: len(FRAME) // 2]
    events = []
    for _ in range(6):
        events.extend(gate.feed(half))
    assert [e.kind for e in events] == ["speech_started"]


def test_min_speech_is_folded_into_onset():
    gate = StreamingVADGate(scripted([], default=0.9), onset_ms=32, min_speech_ms=160)
    assert gate.onset_ms == 160


def test_adapter_failure_is_treated_as_silence():
    class Broken:
        def get_probability(self, pcm_bytes, sample_rate):
            raise RuntimeError("boom")

        def reset(self):
            pass

    gate = StreamingVADGate(Broken(), onset_ms=32, silence_ms=100)
    assert feed_seconds(gate, 0.3) == []


def test_configure_updates_threshold_and_timing():
    gate = StreamingVADGate(scripted([0.4], default=0.0), threshold=0.5)
    gate.configure(threshold=0.3, silence_ms=250, commit_grace_ms=100, preroll_ms=160)
    assert gate.threshold == 0.3
    assert gate.continue_threshold == 0.3 * 0.6
    assert gate.silence_ms == 250
    assert gate.commit_grace_ms == 100
    assert gate._preroll_frames == 5


def test_utterance_ms_is_frame_accurate():
    gate = StreamingVADGate(scripted([], default=0.9), onset_ms=32, silence_ms=1000)
    started = None
    for _ in range(10):
        for event in gate.feed(FRAME):
            if event.kind == "speech_started":
                started = event
                break
        if started:
            break

    assert started is not None
    assert started.audio_ms % FRAME_MS == 0
    assert started.audio_ms <= 10 * FRAME_MS


def test_synthetic_vad_script_is_consumed_in_order():
    vad = scripted([0.1, 0.2, 0.3], default=0.9)
    values = [vad.get_probability(FRAME, SR) for _ in range(4)]
    assert values == [0.1, 0.2, 0.3, 0.9]
    vad.reset()
    assert vad.get_probability(FRAME, SR) == 0.1
    assert vad.resets == 1


def test_rms_probability_scales_with_energy():
    from vocal_core.audio.vad_gate import rms_probability

    quiet = np.zeros(512, dtype=np.int16)
    loud = np.full(512, 2000, dtype=np.int16)
    assert rms_probability(quiet, threshold=400) == 0.0
    assert 0.0 < rms_probability(loud, threshold=400) <= 1.0
