"""Offline chat contract for the ASGI app selected by gateway/Dockerfile."""

import json
from contextlib import asynccontextmanager
from importlib import import_module
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from gateway.service import app as edge
from gateway.service import free_model_discovery
from gateway.service.pool import FederationSquad, KeySlot
from gateway.service.route_arbiter import route_arbiter

_HEADERS = {"Authorization": "Bearer fixture-client-key"}
_CHAT = {"model": "supremeai-api", "messages": [{"role": "user", "content": "Hello"}]}


def _sse(data):
    return f"data: {json.dumps(data)}\n\n".encode()


class _ProviderStream(httpx.AsyncByteStream):
    def __init__(self, *parts):
        self.parts = parts
        self.closed = False

    async def __aiter__(self):
        for part in self.parts:
            if isinstance(part, Exception):
                raise part
            yield part

    async def aclose(self):
        self.closed = True


@pytest.fixture
def gateway(monkeypatch):
    upstream = Mock()

    @asynccontextmanager
    async def http_client(_timeout):
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
            yield client

    # Patch the adapter module actually used by the Docker entrypoint, including
    # under the repo test harness's legacy `service.*` import path.
    adapters = import_module(edge.stream_chat_completion_events.__module__)
    monkeypatch.setattr(adapters, "_pooled_http_client", http_client)
    monkeypatch.setattr(free_model_discovery, "validate_slot", AsyncMock())
    monkeypatch.setattr(free_model_discovery, "persist_slot", AsyncMock())
    monkeypatch.setattr(FederationSquad, "PREFIX_MAP", {"groq": []})
    squad = FederationSquad()
    squad.pools["groq"].slots = [
        KeySlot(
            "fixture-slot", "fixture-provider-key", "groq", ewma_latency_ms=10, discovered_models=["first", "second"]
        ),
        KeySlot("backup-slot", "fixture-backup-key", "groq", ewma_latency_ms=100, discovered_models=["backup"]),
    ]
    monkeypatch.setattr(edge, "squad", squad)
    monkeypatch.setattr(route_arbiter, "squad", None)
    monkeypatch.setattr(edge, "_adaptive_routes", {name: edge.RouteState(name) for name in edge._adaptive_routes})
    monkeypatch.setenv("SUPREMEAI_API_KEY", "fixture-client-key")
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "")
    monkeypatch.setattr(edge, "compile_chat_context", None)
    monkeypatch.setattr(edge, "response_cache", None)
    monkeypatch.setattr(edge, "add_message", None)
    monkeypatch.setattr(edge, "append_canonical_message", Mock())

    # Do not run the real startup probes/secret hydration in this offline test.
    client = TestClient(edge.app)
    try:
        yield client, upstream
    finally:
        client.close()


def _stream_frames(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    data = [line[6:] for line in response.text.splitlines() if line.startswith("data: ")]
    assert data[-1] == "[DONE]" and data.count("[DONE]") == 1
    return [json.loads(item) for item in data[:-1]]


def test_docker_app_serves_models_release_and_authenticated_completion(gateway, monkeypatch):
    client, upstream = gateway
    monkeypatch.setenv("RENDER_GIT_COMMIT", "a" * 40)
    assert "supremeai-api" in {item["id"] for item in client.get("/v1/models").json()["data"]}
    assert client.get("/release").json()["commit"] == "a" * 40
    assert client.post("/v1/chat/completions", json=_CHAT).status_code == 401
    upstream.assert_not_called()

    upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": "Fixture reply"}}]})
    response = client.post("/v1/chat/completions", json=_CHAT, headers=_HEADERS)
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Fixture reply"
    upstream.assert_called_once()


@pytest.mark.parametrize("terminal", [b"data: [DONE]\n\n", _sse({"choices": [{"finish_reason": "stop"}]})])
def test_stream_can_try_another_model_before_output(gateway, terminal):
    client, upstream = gateway
    stream = _ProviderStream(_sse({"choices": [{"delta": {"content": "Hello"}}]}), terminal)
    upstream.side_effect = [httpx.Response(429), httpx.Response(200, stream=stream)]
    frames = _stream_frames(
        client.post("/v1/chat/completions", json={**_CHAT, "stream": True, "session_id": "fixture"}, headers=_HEADERS)
    )
    assert [json.loads(call.args[0].content)["model"] for call in upstream.call_args_list] == ["first", "second"]
    assert frames[0]["choices"][0]["delta"]["content"] == "Hello"
    assert [frame["choices"][0]["finish_reason"] for frame in frames] == [None, "stop"]
    assert stream.closed
    assert [call.args[1:3] for call in edge.append_canonical_message.call_args_list] == [
        ("user", "Hello"), ("assistant", "Hello")
    ]


def test_stream_can_try_another_slot_before_output(gateway):
    client, upstream = gateway
    stream = _ProviderStream(_sse({"choices": [{"delta": {"content": "Backup"}}]}), b"data: [DONE]\n\n")
    upstream.side_effect = [httpx.Response(403), httpx.Response(200, stream=stream)]

    frames = _stream_frames(client.post("/v1/chat/completions", json={**_CHAT, "stream": True}, headers=_HEADERS))
    assert [json.loads(call.args[0].content)["model"] for call in upstream.call_args_list] == ["first", "backup"]
    assert frames[0]["choices"][0]["delta"]["content"] == "Backup"
    assert frames[-1]["choices"][0]["finish_reason"] == "stop"
    assert stream.closed


@pytest.mark.parametrize(
    ("failure", "first_finish"),
    [
        (httpx.ReadError("fixture detail"), None),
        (httpx.ReadTimeout("fixture detail"), None),
        (_sse({"error": "fixture detail"}), None),
        (_sse({"choices": [{"finish_reason": "error"}]}), None),
        (b"", None),
        (httpx.ReadError("fixture detail"), "stop"),
    ],
    ids=["read-error", "read-timeout", "error-frame", "error-finish", "incomplete-eof", "error-after-finish"],
)
def test_interrupted_stream_has_no_success_frame_or_retry(gateway, failure, first_finish):
    client, upstream = gateway
    stream = _ProviderStream(
        _sse({"choices": [{"delta": {"content": "Partial"}, "finish_reason": first_finish}]}), failure
    )
    upstream.side_effect = [httpx.Response(200, stream=stream), httpx.Response(503)]

    frames = _stream_frames(client.post("/api/v1/stream/chat", json={**_CHAT, "session_id": "fixture"}, headers=_HEADERS))
    assert frames[0]["choices"][0]["delta"]["content"] == "Partial"
    assert frames[0]["choices"][0]["finish_reason"] is None
    assert frames[1].get("error") == "Stream interrupted"
    assert len(frames) == 2
    upstream.assert_called_once()
    assert stream.closed
    assert [call.args[1] for call in edge.append_canonical_message.call_args_list] == ["user"]


@pytest.mark.parametrize("interrupt", [False, True])
def test_tool_call_is_finished_only_after_clean_end(gateway, interrupt):
    client, upstream = gateway
    tool_calls = [{"index": 0, "id": "fixture-tool", "function": {"name": "fixture", "arguments": "{}"}}]
    terminal = httpx.ReadTimeout("fixture detail") if interrupt else b"data: [DONE]\n\n"
    stream = _ProviderStream(_sse({"choices": [{"delta": {"tool_calls": tool_calls}}]}), terminal)
    upstream.side_effect = [httpx.Response(200, stream=stream), httpx.Response(503)]

    frames = _stream_frames(client.post("/v1/chat/completions", json={**_CHAT, "stream": True}, headers=_HEADERS))
    assert frames[0]["choices"][0]["delta"]["tool_calls"] == tool_calls
    assert frames[0]["choices"][0]["finish_reason"] is None
    assert len(frames) == 2
    if interrupt:
        assert frames[1].get("error") == "Stream interrupted"
    else:
        assert frames[1]["choices"][0]["finish_reason"] == "tool_calls"
    upstream.assert_called_once()
    assert stream.closed
