"""Incremental text -> speakable-sentence chunking for pipelined TTS."""

from __future__ import annotations

import re

_SENTENCE_END = re.compile(r"(?<=[.!?\u2026])\s+|(?<=[.!?\u2026])$|\n+")
_ABBREVIATIONS = {
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "sr.",
    "jr.",
    "st.",
    "vs.",
    "etc.",
    "e.g.",
    "i.e.",
    "a.m.",
    "p.m.",
}


class SentenceChunker:
    """Splits a token stream into sentences without waiting for the whole reply.

    ``push`` accepts arbitrary token fragments and returns every complete
    sentence. ``flush`` returns whatever is left so the last fragment is spoken.
    """

    def __init__(self, min_chars: int = 12, max_chars: int = 220) -> None:
        self.min_chars = max(1, min_chars)
        self.max_chars = max(self.min_chars, max_chars)
        self._buffer = ""

    def push(self, token: str) -> list[str]:
        if not token:
            return []
        self._buffer += token
        chunks: list[str] = []
        while True:
            sentence = self._next_sentence()
            if sentence is None:
                break
            chunks.append(sentence)
        return chunks

    def flush(self) -> str | None:
        rest = self._buffer.strip()
        self._buffer = ""
        if not rest:
            return None
        return rest

    def _next_sentence(self) -> str | None:
        buffer = self._buffer
        for match in _SENTENCE_END.finditer(buffer):
            end = match.end()
            candidate = buffer[:end].strip()
            if len(candidate) < self.min_chars:
                continue
            if self._is_abbreviation(candidate):
                continue
            self._buffer = buffer[end:]
            return candidate
        if len(buffer) >= self.max_chars:
            cut = _soft_cut(buffer, self.max_chars)
            if cut > 0:
                candidate = buffer[:cut].strip()
                self._buffer = buffer[cut:]
                return candidate or None
        return None

    @staticmethod
    def _is_abbreviation(candidate: str) -> bool:
        tail = candidate.rsplit(" ", 1)[-1].lower()
        return tail in _ABBREVIATIONS


def _soft_cut(text: str, limit: int) -> int:
    """Find a word boundary at or before ``limit``; fall back to a hard cut."""
    window = text[:limit]
    for separator in (" ", ",", ";", ":"):
        cut = window.rfind(separator)
        if cut > limit // 2:
            return cut + 1
    return limit
