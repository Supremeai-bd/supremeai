"""A streaming request must survive an upstream that answers in one piece.

The web engines are relayed through `browser/server.py`, which used to accept
`stream: true` and answer with a single JSON body. The gateway's stream reader
only understands `data:` frames, so it found nothing, fell through to
"Upstream stream ended before completion" and discarded an answer that had
already been generated. The user saw a provider failure; the provider had
answered.

Three properties are pinned here:

* a non-SSE 2xx body is buffered into one event instead of being thrown away
  (slow answer beats no answer, and the shape of the answer is not our choice);
* SSE still parses as before, and an SSE keep-alive (`: comment`) is surfaced as
  a `heartbeat` item rather than silently dropped — the first-token window uses
  it to tell "slow but alive" from "dead";
* an upstream that ends without a finish reason is still an error, so this does
  not turn truncation into success.
"""

from __future__ import annotations

import json

from contextlib import asynccontextmanager

import httpx
import pytest

from gateway.service.free_route_policy import ApprovedRoute
from gateway.service.providers import adapters

PAYLOAD = {"model": "duck-claude", "messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture(autouse=True)
def _one_approved_model(monkeypatch):
    monkeypatch.setattr(
        adapters,
        "approved_route",
        lambda provider, url, _key, **_kw: ApprovedRoute((provider, url, "tag"), ("duck-claude",)),
    )


def _client_returning(monkeypatch, *, content=b"", headers=None, json_body=None, status=200):
    def handler(request):  # noqa: ARG001 - the request body is not under test here
        if json_body is not None:
            return httpx.Response(status, json=json_body)
        return httpx.Response(status, content=content, headers=headers or {})

    @asynccontextmanager
    async def client(_timeout):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as made:
            yield made

    monkeypatch.setattr(adapters, "_pooled_http_client", client)


async def _events():
    return [item async for item in adapters.stream_chat_completion_events("claude_web", "cookie", PAYLOAD)]


# --- a whole-body answer on a streaming request ----------------------------


@pytest.mark.asyncio
async def test_json_body_on_a_stream_request_becomes_one_event(monkeypatch):
    _client_returning(
        monkeypatch,
        json_body={"choices": [{"message": {"role": "assistant", "content": "buffered hello"}}]},
    )
    events = await _events()

    assert [kind for kind, _ in events] == ["status", "event", "done"]
    assert events[1][1]["delta"] == "buffered hello"
    assert events[1][1]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_a_json_error_body_is_an_error_not_an_empty_answer(monkeypatch):
    _client_returning(monkeypatch, json_body={"error": {"message": "upstream sad"}})
    events = await _events()

    assert events[-1][0] == "error"
    assert "error" in events[-1][1]


@pytest.mark.asyncio
async def test_an_error_body_with_a_generic_reason_still_fails(monkeypatch):
    _client_returning(monkeypatch, json_body={"detail": "not json shaped like a completion"})
    events = await _events()

    assert events[-1][0] == "error"


@pytest.mark.asyncio
async def test_a_non_json_body_is_reported_not_crashed(monkeypatch):
    _client_returning(monkeypatch, content=b"<html>gateway timeout</html>")
    events = await _events()

    assert events[0][0] == "status"
    assert events[-1][0] == "error"


# --- SSE, unchanged --------------------------------------------------------


def _sse(*frames: str) -> bytes:
    return "".join(f"{frame}\n\n" for frame in frames).encode()


@pytest.mark.asyncio
async def test_sse_frames_are_parsed_into_deltas(monkeypatch):
    _client_returning(
        monkeypatch,
        content=_sse(
            'data: {"choices": [{"delta": {"content": "He"}}]}',
            'data: {"choices": [{"delta": {"content": "llo"}}]}',
            'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}',
            "data: [DONE]",
        ),
        headers={"content-type": "text/event-stream"},
    )
    events = await _events()

    deltas = [data.get("delta") for kind, data in events if kind == "event"]
    assert deltas == ["He", "llo", ""]
    assert events[-1] == ("done", None)


@pytest.mark.asyncio
async def test_sse_keep_alives_become_heartbeats(monkeypatch):
    _client_returning(
        monkeypatch,
        content=_sse(
            ": waiting",
            'data: {"choices": [{"delta": {"content": "late"}}]}',
            'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}',
            "data: [DONE]",
        ),
        headers={"content-type": "text/event-stream"},
    )
    events = await _events()

    assert events[1] == ("heartbeat", {"comment": "waiting"})
    assert events[2][1]["delta"] == "late"


@pytest.mark.asyncio
async def test_an_sse_error_chunk_is_an_error(monkeypatch):
    _client_returning(
        monkeypatch,
        content=_sse("data: " + json.dumps({"error": {"message": "dead"}})),
        headers={"content-type": "text/event-stream"},
    )
    events = await _events()

    assert events[-1][0] == "error"


@pytest.mark.asyncio
async def test_a_truncated_sse_stream_is_still_an_error(monkeypatch):
    """Finish reason or nothing: this fix must not launder truncation into success."""
    _client_returning(
        monkeypatch,
        content=_sse('data: {"choices": [{"delta": {"content": "half an ans"}}]}'),
        headers={"content-type": "text/event-stream"},
    )
    events = await _events()

    assert events[-1][0] == "error"
    assert "before completion" in events[-1][1]["error"]


# --- the interpreter itself ------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "kind", "content"),
    [
        (b'{"choices": [{"message": {"content": "x"}}]}', "event", "x"),
        (
            b'{"choices": [{"message": {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}}]}',
            "event",
            "ab",
        ),
        (b'{"choices": [{"message": {"content": ""}}]}', "error", None),
        (b'{"choices": []}', "error", None),
        (b"not json", "error", None),
        (b"[]", "error", None),
    ],
)
def test_single_shot_interpreter(raw, kind, content):
    interpreted, payload = adapters._single_shot_event(raw, "duck-claude")
    assert interpreted == kind
    if content is not None:
        assert payload["delta"] == content
