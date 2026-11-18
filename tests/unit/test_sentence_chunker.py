"""Unit tests for incremental sentence chunking used by pipelined TTS."""

from vocal_core.audio.sentences import SentenceChunker


def test_splits_complete_sentences_across_tokens():
    chunker = SentenceChunker(min_chars=8)
    out: list[str] = []
    for token in ["Hello", " there,", " how", " are", " you?", " I", " am", " fine."]:
        out.extend(chunker.push(token))
    assert out == ["Hello there, how are you?", "I am fine."]
    assert chunker.flush() is None


def test_holds_incomplete_sentence_until_flush():
    chunker = SentenceChunker(min_chars=10)
    assert chunker.push("This is a partial") == []
    assert chunker.flush() == "This is a partial"


def test_short_fragment_is_not_emitted_alone():
    chunker = SentenceChunker(min_chars=12)
    # "Hi." is below min_chars, so it must not start its own TTS request.
    assert chunker.push("Hi. ") == []
    chunks = chunker.push("This is a real sentence.")
    assert chunks == ["Hi. This is a real sentence."]


def test_abbreviation_does_not_end_sentence():
    chunker = SentenceChunker(min_chars=10)
    out = chunker.push("Dr. Smith arrived early. He was late.")
    assert out == ["Dr. Smith arrived early.", "He was late."]


def test_newlines_end_sentences():
    chunker = SentenceChunker(min_chars=5)
    out = chunker.push("First line\nSecond line\n")
    assert out == ["First line", "Second line"]


def test_long_text_is_soft_cut_at_word_boundary():
    chunker = SentenceChunker(min_chars=10, max_chars=40)
    text = "word " * 20  # 100 chars with no terminating punctuation
    chunks = chunker.push(text)
    assert chunks, "expected at least one soft cut"
    assert all(len(c) <= 40 for c in chunks)
    assert all(not c.endswith(" ") for c in chunks)


def test_empty_tokens_are_ignored():
    chunker = SentenceChunker()
    assert chunker.push("") == []
    assert chunker.flush() is None


def test_flush_clears_buffer():
    chunker = SentenceChunker(min_chars=100)
    chunker.push("still going")
    assert chunker.flush() == "still going"
    assert chunker.flush() is None
