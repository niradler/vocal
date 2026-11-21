"""Unit tests: realtime voice-agent turn handling (issues #16, #18)."""

import json
import time

import httpx
import pytest

from vocal_api.routes import realtime as rt


class _FakeWS:
    def __init__(self):
        self.events = []

    async def send_text(self, text):
        self.events.append(json.loads(text))


class _FakeTTS:
    async def get_sample_rate(self, model):
        return 24000

    async def synthesize_stream(self, **kwargs):
        yield b"\x00\x00" * 240


@pytest.mark.asyncio
async def test_current_utterance_is_in_llm_context(monkeypatch):
    """#16: the LLM must see the CURRENT user turn, not only past turns."""
    captured = {}

    async def fake_stream_llm(session, cancel):
        captured["messages"] = rt._llm_messages(session)
        yield "The sky is blue."

    monkeypatch.setattr(rt, "_stream_llm", fake_stream_llm)

    session = rt._Session()
    session.conversation_history.append({"role": "user", "content": "earlier question"})
    session.conversation_history.append({"role": "assistant", "content": "earlier answer"})
    ws = _FakeWS()

    await rt._run_voice_agent(ws, session, "what color is the sky?", _FakeTTS(), time.perf_counter())

    assert captured["messages"][-1] == {"role": "user", "content": "what color is the sky?"}
    assert session.conversation_history[-1] == {"role": "assistant", "content": "The sky is blue."}
    assert any(e["type"] == "response.done" for e in ws.events)


@pytest.mark.asyncio
async def test_two_turns_keep_alignment(monkeypatch):
    """#16 regression: turn N's request ends with turn N's user text."""
    seen = []

    async def fake_stream_llm(session, cancel):
        seen.append([m for m in rt._llm_messages(session) if m["role"] == "user"])
        yield f"answer {len(seen)}"

    monkeypatch.setattr(rt, "_stream_llm", fake_stream_llm)

    session = rt._Session()
    ws = _FakeWS()
    await rt._run_voice_agent(ws, session, "first question", _FakeTTS(), time.perf_counter())
    await rt._run_voice_agent(ws, session, "second question", _FakeTTS(), time.perf_counter())

    assert seen[0][-1]["content"] == "first question"
    assert seen[1][-1]["content"] == "second question"
    assert len(seen[1]) == 2  # both user turns present, in order


@pytest.mark.asyncio
async def test_unreachable_llm_yields_empty_not_exception(monkeypatch):
    """#18: a connection failure must complete the turn, not abort the pipeline."""

    class _DeadClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, *args, **kwargs):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(rt.httpx, "AsyncClient", lambda *a, **k: _DeadClient())

    session = rt._Session()
    deltas = [d async for d in rt._stream_llm(session, __import__("asyncio").Event())]
    assert deltas == [""]


def test_llm_messages_includes_system_prompt():
    session = rt._Session()
    session.system_prompt = "be brief"
    session.conversation_history.append({"role": "user", "content": "hi"})
    messages = rt._llm_messages(session)
    assert messages[0] == {"role": "system", "content": "be brief"}
    assert messages[-1] == {"role": "user", "content": "hi"}
