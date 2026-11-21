"""Frame-accurate streaming VAD gate.

The VAD *adapter* answers "is this frame speech?". This gate turns that raw
signal into utterance boundaries that a realtime API can act on:

* **Pre-roll** - keeps the audio just before onset so the first phoneme is not
  clipped from the utterance sent to STT.
* **Onset confirmation** - short debounce so a click does not open a turn.
* **Hangover (silence)** - waits a configurable amount of silence before it
  closes the turn, so natural pauses do not split one sentence.
* **Hysteresis** - continuing speech uses a lower threshold than starting it,
  which stops word tails from being treated as silence.
* **Max utterance** - hard cap for runaway audio.

All durations are milliseconds, independent of the client's chunk size, and
all emitted audio is at the gate's sample rate.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_FRAME_MS = 32


class SupportsProbability(Protocol):
    def get_probability(self, pcm_bytes: bytes, sample_rate: int) -> float: ...

    def reset(self) -> None: ...


@dataclass(frozen=True)
class VADEvent:
    """A boundary emitted by :class:`StreamingVADGate`."""

    kind: Literal["speech_started", "speech_stopped"]
    audio_ms: int
    probability: float


class StreamingVADGate:
    """Stateful VAD gate. One instance per realtime session."""

    def __init__(
        self,
        adapter: SupportsProbability,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        *,
        threshold: float = 0.5,
        onset_ms: int = 180,
        silence_ms: int = 700,
        min_speech_ms: int = 180,
        preroll_ms: int = 300,
        max_utterance_s: float = 30.0,
        frame_ms: int = DEFAULT_FRAME_MS,
        continue_threshold_ratio: float = 0.6,
        commit_grace_ms: int = 0,
    ) -> None:
        if frame_ms <= 0:
            raise ValueError("frame_ms must be positive")
        self.adapter = adapter
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.onset_ms = max(0, onset_ms)
        self.silence_ms = max(0, silence_ms)
        # A turn must be preceded by this much continuous speech; it is folded
        # into the onset debounce instead of being a separate post-hoc filter.
        self.min_speech_ms = max(0, min_speech_ms)
        self.onset_ms = max(self.onset_ms, self.min_speech_ms)
        self.max_utterance_s = max_utterance_s
        self.frame_ms = frame_ms
        self.continue_threshold = threshold * continue_threshold_ratio
        # Extra wait after the silence threshold before the turn is committed.
        # A pause shorter than this resumes the same utterance instead of
        # splitting it into two turns (natural pauses in continuous speech are
        # routinely 0.8-1.2 s).
        self.commit_grace_ms = max(0, commit_grace_ms)

        self._frame_bytes = max(2, int(sample_rate * frame_ms / 1000) * 2)
        self._preroll_frames = max(1, int(round(preroll_ms / frame_ms))) if preroll_ms else 0
        self._pending = bytearray()
        self._preroll: deque[bytes] = deque(maxlen=self._preroll_frames or 1)
        self._onset_frames: list[bytes] = []
        self._utterance = bytearray()
        # A single chunk can contain the end of one turn and the start of the
        # next. Committed audio is queued here so the caller can still fetch it
        # after the gate has begun collecting the following turn.
        self._committed: deque[bytes] = deque()
        self._speech_ms = 0
        self._silence_ms = 0
        self._utterance_ms = 0
        self._state: Literal["idle", "speech", "closing"] = "idle"
        self._last_probability = 0.0
        self._grace_started_ms = 0

    # ------------------------------------------------------------------ state
    @property
    def is_speaking(self) -> bool:
        return self._state == "speech"

    @property
    def is_active(self) -> bool:
        """True while audio is still being collected for the current turn."""
        return self._state != "idle"

    @property
    def utterance_ms(self) -> int:
        return self._utterance_ms

    @property
    def utterance_pcm(self) -> bytes:
        """Audio captured for the current (or just finished) utterance."""
        return bytes(self._utterance)

    def take_utterance(self) -> bytes:
        """Return the oldest committed utterance, or the in-progress audio.

        A chunk may close one turn and open the next; the committed audio is
        queued at commit time so it cannot be overwritten by the new onset.
        """
        if self._committed:
            return self._committed.popleft()
        pcm = bytes(self._utterance)
        self._utterance.clear()
        self._utterance_ms = 0
        self._speech_ms = 0
        self._silence_ms = 0
        self._onset_frames.clear()
        self._grace_started_ms = 0
        return pcm

    def reset(self) -> None:
        """Drop all buffered state, keeping the adapter's model warm."""
        self._pending.clear()
        self._preroll.clear()
        self._onset_frames.clear()
        self._utterance.clear()
        self._committed.clear()
        self._speech_ms = 0
        self._silence_ms = 0
        self._utterance_ms = 0
        self._state = "idle"
        self._last_probability = 0.0
        self._grace_started_ms = 0
        try:
            self.adapter.reset()
        except Exception:  # pragma: no cover - adapter specific
            logger.debug("VAD adapter reset failed", exc_info=True)

    def configure(
        self,
        *,
        threshold: float | None = None,
        onset_ms: int | None = None,
        silence_ms: int | None = None,
        min_speech_ms: int | None = None,
        preroll_ms: int | None = None,
        commit_grace_ms: int | None = None,
    ) -> None:
        """Apply session-level turn-detection overrides."""
        if threshold is not None:
            self.threshold = float(threshold)
            self.continue_threshold = self.threshold * 0.6
        if onset_ms is not None:
            self.onset_ms = max(0, int(onset_ms))
            # Keep the same invariant as the constructor: a turn needs at
            # least `min_speech_ms` of speech to open.
            self.onset_ms = max(self.onset_ms, self.min_speech_ms)
        if silence_ms is not None:
            self.silence_ms = max(0, int(silence_ms))
        if min_speech_ms is not None:
            self.min_speech_ms = max(0, int(min_speech_ms))
            self.onset_ms = max(self.onset_ms, self.min_speech_ms)
        if preroll_ms is not None:
            self._preroll_frames = max(1, int(round(int(preroll_ms) / self.frame_ms))) if preroll_ms else 0
            self._preroll = deque(maxlen=self._preroll_frames or 1)
        if commit_grace_ms is not None:
            self.commit_grace_ms = max(0, int(commit_grace_ms))

    # ------------------------------------------------------------------- feed
    def feed(self, pcm: bytes) -> list[VADEvent]:
        """Consume PCM at ``sample_rate`` and return boundaries found in it."""
        if pcm:
            self._pending.extend(pcm)
        events: list[VADEvent] = []
        frame_bytes = self._frame_bytes
        while len(self._pending) >= frame_bytes:
            frame = bytes(self._pending[:frame_bytes])
            del self._pending[:frame_bytes]
            event = self._process_frame(frame)
            if event is not None:
                events.append(event)
        return events

    def flush(self) -> list[VADEvent]:
        """Close an open turn at end-of-stream.

        Trailing sub-frame audio is folded into the utterance first; otherwise
        ``take_utterance()`` would silently lose the last few milliseconds.
        """
        if self._state == "idle":
            return []
        if self._pending:
            self._utterance.extend(self._pending)
            self._utterance_ms += len(self._pending) // 2 * 1000 // self.sample_rate
            self._pending.clear()
        return [self._commit(self._last_probability)]

    def _process_frame(self, frame: bytes) -> VADEvent | None:  # noqa: C901
        try:
            probability = float(self.adapter.get_probability(frame, self.sample_rate))
        except Exception:  # pragma: no cover - adapter failure should not kill the call
            logger.warning("VAD adapter failed on a frame; treating it as silence", exc_info=True)
            probability = 0.0
        self._last_probability = probability
        is_speech = probability >= (self.threshold if self._state == "idle" else self.continue_threshold)

        if self._state == "idle":
            self._utterance_ms = 0
            if is_speech:
                self._onset_frames.append(frame)
                if len(self._onset_frames) * self.frame_ms >= self.onset_ms:
                    self._state = "speech"
                    buffered = list(self._preroll) + self._onset_frames
                    self._preroll.clear()
                    self._onset_frames.clear()
                    self._utterance = bytearray(b"".join(buffered))
                    self._utterance_ms = len(buffered) * self.frame_ms
                    self._speech_ms = len(buffered) * self.frame_ms
                    self._silence_ms = 0
                    return VADEvent("speech_started", self._utterance_ms, probability)
            else:
                self._onset_frames.clear()
                if self._preroll_frames:
                    self._preroll.append(frame)
            return None

        # Collecting for an open turn (``speech`` or ``closing``).
        self._utterance.extend(frame)
        self._utterance_ms += self.frame_ms
        resumed = False
        if is_speech:
            self._speech_ms += self.frame_ms
            self._silence_ms = 0
            if self._state == "closing":
                # Speech resumed inside the grace window: keep the same turn
                # instead of committing a fragment.
                self._state = "speech"
                resumed = True
        else:
            self._silence_ms += self.frame_ms

        if self._utterance_ms >= self.max_utterance_s * 1000:
            return self._commit(probability)
        if resumed or is_speech:
            return None

        if self._silence_ms < self.silence_ms:
            return None

        if self._state == "speech":
            if self.commit_grace_ms > 0:
                self._state = "closing"
                self._grace_started_ms = self._silence_ms
                return None
            return self._commit(probability)

        # closing
        if self._silence_ms - self._grace_started_ms < self.commit_grace_ms:
            return None
        return self._commit(probability)

    def _commit(self, probability: float) -> VADEvent:
        """End the turn, trim most of the hangover silence, queue the audio."""
        self._state = "idle"
        keep_ms = min(self.silence_ms, 200)
        drop_bytes = max(0, int((self._silence_ms - keep_ms) / self.frame_ms) * self._frame_bytes)
        if drop_bytes and drop_bytes < len(self._utterance):
            del self._utterance[-drop_bytes:]
            self._utterance_ms -= int(drop_bytes / 2 / self.sample_rate * 1000)
        audio_ms = self._utterance_ms
        if self._utterance:
            self._committed.append(bytes(self._utterance))
        self._utterance.clear()
        self._utterance_ms = 0
        self._speech_ms = 0
        self._silence_ms = 0
        self._grace_started_ms = 0
        return VADEvent("speech_stopped", audio_ms, probability)


class SyntheticVAD:
    """Test/benchmark adapter driven by an explicit probability script."""

    def __init__(self, script: list[float] | None = None, default: float = 0.0) -> None:
        self.script = list(script or [])
        self.default = default
        self.index = 0
        self.resets = 0

    def get_probability(self, pcm_bytes: bytes, sample_rate: int) -> float:
        if self.index < len(self.script):
            value = self.script[self.index]
            self.index += 1
            return value
        return self.default

    def reset(self) -> None:
        self.index = 0
        self.resets += 1


def rms_probability(pcm: np.ndarray | bytes, threshold: float) -> float:
    """Cheap energy fallback used by tests and the RMS adapter."""
    if isinstance(pcm, bytes):
        arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    else:
        arr = pcm.astype(np.float32)
    if arr.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(arr**2)))
    return min(1.0, rms / threshold) if threshold > 0 else 0.0
