"""The relay must answer a `stream: true` request with SSE, not with silence.

The defect these tests exist for: the gateway asks every provider for
`stream: true` and reads the answer as SSE (`data:` frames). The relay accepted
the flag, ignored it, and returned one JSON body — so the gateway's line loop
found no frames, concluded "Upstream stream ended before completion", and threw
away an answer the relay had already produced. A slow answer became no answer,
and it looked like a provider failure instead of a protocol mismatch.

The fix has to stay honest in both directions:

* the frames are real `chat.completion.chunk` objects terminated by `[DONE]`,
  because that is what the gateway parses;
* only the Duck.ai tier actually arrives incrementally. The zero-auth tier and
  the cookie engine answer whole, so the final chunk says
  `delivery: "buffered"` instead of advertising token streaming for a
  single-shot body;
* a failure after the first byte cannot become a 502 — the headers are already
  sent — so it becomes an error frame the gateway already understands;
* a silent engine produces a keep-alive *comment*, never a fake content delta.

Nothing here asserts anything about latency: streaming fixes the protocol, not
the engine.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

BROWSER_ROOT = Path(__file__).resolve().parents[1]
if str(BROWSER_ROOT) not in sys.path:
    sys.path.insert(0, str(BROWSER_ROOT))

import server  # noqa: E402

CHAT_BODY = {"messages": [{"role": "user", "content": "hello"}], "model": "duck-claude"}


@pytest.fixture(autouse=True)
def _clean_state():
    """Each test starts from an empty session table and neutral latency ranking."""
    server._session_state.clear()
    saved_latency = dict(server._engine_latency)
    server._engine_latency.clear()
    yield
    server._session_state.clear()
    server._engine_latency.clear()
    server._engine_latency.update(saved_latency)


def _deltas(*parts):
    async def gen(*_args, **_kwargs):
        for part in parts:
            await asyncio.sleep(0)
            yield part

    return gen


def _fails(exc, *parts):
    async def gen(*_args, **_kwargs):
        for part in parts:
            yield part
        raise exc

    return gen


def _frames(body: str) -> list:
    """`data:` payloads of an SSE body, `[DONE]` included as a literal string."""
    out = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            out.append(payload if payload == "[DONE]" else json.loads(payload))
    return out


def _patch_engines(monkeypatch, *, duck=None, gemini=None):
    if duck is not None:
        monkeypatch.setattr(server.duck_engine, "ask_stream", duck)
    if gemini is not None:
        monkeypatch.setattr(server.relay_engine, "ask", gemini)


def test_stream_true_is_answered_with_sse(monkeypatch):
    _patch_engines(monkeypatch, duck=_deltas("He", "llo"))
    resp = TestClient(server.app).post("/v1/chat/completions", json=CHAT_BODY | {"stream": True})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["x-accel-buffering"] == "no", "a buffering proxy would undo the stream"

    frames = _frames(resp.text)
    assert frames[-1] == "[DONE]"
    chunks = [frame for frame in frames if isinstance(frame, dict)]
    assert "".join(
        chunk["choices"][0]["delta"].get("content", "") for chunk in chunks
    ) == "Hello"


def test_frames_keep_the_openai_chunk_shape(monkeypatch):
    _patch_engines(monkeypatch, duck=_deltas("ok"))
    body = TestClient(server.app).post(
        "/v1/chat/completions", json=CHAT_BODY | {"stream": True}
    ).text
    first = next(frame for frame in _frames(body) if isinstance(frame, dict))

    assert first["object"] == "chat.completion.chunk"
    assert first["model"] == "supremeai-fast"
    assert first["choices"][0]["delta"]["role"] == "assistant"
    assert first["supremeai"]["engine"] == "dk"
    assert first["supremeai"]["stream"] == "sse"


def test_incremental_answer_says_incremental(monkeypatch):
    _patch_engines(monkeypatch, duck=_deltas("a", "b", "c"))
    body = TestClient(server.app).post(
        "/v1/chat/completions", json=CHAT_BODY | {"stream": True}
    ).text
    final = [frame for frame in _frames(body) if isinstance(frame, dict)][-1]

    assert final["choices"][0]["finish_reason"] == "stop"
    assert final["supremeai"]["delivery"] == "incremental"
    assert final["supremeai"]["deltas"] == 3


def test_a_whole_answer_is_labelled_buffered(monkeypatch):
    """The cookie engine answers in one piece; the label must not claim otherwise."""
    _patch_engines(
        monkeypatch,
        duck=_fails(HTTPException(status_code=502, detail="duck down")),
        gemini=_returns("gemini says hi"),
    )
    body = TestClient(server.app).post(
        "/v1/chat/completions", json=CHAT_BODY | {"stream": True}
    ).text
    final = [frame for frame in _frames(body) if isinstance(frame, dict)][-1]

    assert final["supremeai"]["engine"] == "ge"
    assert final["supremeai"]["delivery"] == "buffered"
    assert final["supremeai"]["deltas"] == 1


def test_a_silent_engine_produces_a_comment_not_a_fake_delta(monkeypatch):
    monkeypatch.setattr(server, "STREAM_HEARTBEAT_S", 0.01)
    _patch_engines(monkeypatch, duck=_slow_deltas(0.05, "late"))
    resp = TestClient(server.app).post("/v1/chat/completions", json=CHAT_BODY | {"stream": True})

    assert ": waiting" in resp.text, "the gateway reads these to extend its first-token window"
    content = "".join(
        frame["choices"][0]["delta"].get("content", "")
        for frame in _frames(resp.text)
        if isinstance(frame, dict)
    )
    assert content == "late", "a keep-alive must never masquerade as content"


def test_failure_before_the_first_delta_falls_back_to_the_next_engine(monkeypatch):
    _patch_engines(
        monkeypatch,
        duck=_fails(HTTPException(status_code=502, detail="duck down")),
        gemini=_returns("gemini answers"),
    )
    body = TestClient(server.app).post(
        "/v1/chat/completions", json=CHAT_BODY | {"stream": True}
    ).text
    content = "".join(
        frame["choices"][0]["delta"].get("content", "")
        for frame in _frames(body)
        if isinstance(frame, dict)
    )
    assert content == "gemini answers"


def test_failure_after_the_first_delta_is_an_error_frame_not_a_502(monkeypatch):
    """Headers are already sent; the only honest signal left is an SSE error."""
    _patch_engines(monkeypatch, duck=_fails(HTTPException(status_code=502, detail="mid"), "par"))
    resp = TestClient(server.app).post("/v1/chat/completions", json=CHAT_BODY | {"stream": True})

    assert resp.status_code == 200, "a 502 here would drop the bytes already sent"
    frames = _frames(resp.text)
    assert frames[-1] == "[DONE]"
    errors = [frame for frame in frames if isinstance(frame, dict) and frame.get("error")]
    assert errors and errors[0]["error"]["type"] == "upstream_error"


def test_both_engines_dead_is_one_error_frame(monkeypatch):
    _patch_engines(
        monkeypatch,
        duck=_fails(HTTPException(status_code=502, detail="duck")),
        gemini=_raises(HTTPException(status_code=502, detail="gemini")),
    )
    frames = _frames(
        TestClient(server.app)
        .post("/v1/chat/completions", json=CHAT_BODY | {"stream": True})
        .text
    )
    assert frames[-1] == "[DONE]"
    assert isinstance(frames[0], dict) and frames[0]["error"]["type"] == "upstream_error"


def test_non_stream_requests_are_untouched(monkeypatch):
    """The regression this branch could most easily cause."""
    _patch_engines(monkeypatch, duck=_deltas("whole answer"))
    resp = TestClient(server.app).post("/v1/chat/completions", json=CHAT_BODY)

    assert resp.headers["content-type"].startswith("application/json")
    payload = resp.json()
    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["message"]["content"] == "whole answer"


# --- the delta parser, on its own -------------------------------------------


def _lines(*items):
    async def gen():
        for item in items:
            yield item

    return gen()


@pytest.mark.asyncio
async def test_duck_frames_become_deltas():
    lines = _lines(
        'data: {"message": "Hel"}',
        "",
        'data: {"message": "lo"}',
        'data: {"action": "success"}',
        "data: [DONE]",
        'data: {"message": "never read"}',
    )
    assert [delta async for delta in server.iter_duck_deltas(lines)] == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_duck_parser_skips_junk_and_keep_alives():
    lines = _lines(": ping", "event: message", "data: not-json", 'data: {"message": "ok"}')
    assert [delta async for delta in server.iter_duck_deltas(lines)] == ["ok"]


# --- session evidence from a stream ----------------------------------------


@pytest.mark.asyncio
async def test_a_complete_stream_is_recorded_as_ok(monkeypatch):
    monkeypatch.setattr(server.duck_engine, "ask_stream", _deltas("a", "b"))
    collected = [delta async for delta in server.engine_deltas("duck", "hi", "duck-claude")]

    assert collected == ["a", "b"]
    assert server._session_state["duck"]["state"] == "OK"


@pytest.mark.asyncio
async def test_an_abandoned_stream_is_not_recorded_as_ok(monkeypatch):
    """A client hanging up must not be evidence that the cookie works."""
    monkeypatch.setattr(server.duck_engine, "ask_stream", _deltas("a", "b", "c"))
    stream = server.engine_deltas("duck", "hi", "duck-claude")
    assert await stream.__anext__() == "a"
    await stream.aclose()

    assert server._session_state.get("duck", {}).get("state") != "OK"


@pytest.mark.asyncio
async def test_a_mid_stream_403_is_recorded_as_expired(monkeypatch):
    monkeypatch.setattr(
        server.duck_engine,
        "ask_stream",
        _fails(HTTPException(status_code=403, detail="session expired"), "partial"),
    )
    with pytest.raises(HTTPException):
        async for _delta in server.engine_deltas("duck", "hi", "duck-claude"):
            pass

    assert server._session_state["duck"]["state"] == "EXPIRED"


def _returns(value):
    async def ask(*_args, **_kwargs):
        return value

    return ask


def _raises(exc):
    async def ask(*_args, **_kwargs):
        raise exc

    return ask


def _slow_deltas(delay: float, *parts):
    async def gen(*_args, **_kwargs):
        await asyncio.sleep(delay)
        for part in parts:
            yield part

    return gen
