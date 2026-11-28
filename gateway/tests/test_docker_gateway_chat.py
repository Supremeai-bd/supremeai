"""Offline chat contract for the ASGI app selected by gateway/Dockerfile."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from importlib import import_module
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from gateway.service import app as edge
from gateway.service.free_route_policy import HMAC_KEY_ENV, POLICY_ENV, credential_identity
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

    # Patch the HTTP boundary of the adapter used by the Docker entrypoint.
    adapters = import_module(edge.stream_chat_completion_events.__module__)
    monkeypatch.setattr(adapters, "_pooled_http_client", http_client)
    monkeypatch.setattr(adapters, "_PAID_MODELS", set())
    monkeypatch.setenv(HMAC_KEY_ENV, bytes(range(32)).hex())
    monkeypatch.setenv(POLICY_ENV, json.dumps([
        {
            "provider": "groq", "base_url": adapters.PROVIDER_CONFIGS["groq"]["base_url"],
            "key_hmac_sha256": credential_identity("groq", adapters.PROVIDER_CONFIGS["groq"]["base_url"], key)[2],
            "models": models,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
        for key, models in (("fixture-provider-key", ["first", "second"]), ("fixture-backup-key", ["backup"]))
    ]))
    monkeypatch.setattr(FederationSquad, "PREFIX_MAP", {"groq": [], "gemini": [], "v0": []})
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
    monkeypatch.setenv("SUPREMEAI_MASTER_KEY", "fixture-signing-secret-for-routing-tests")
    from gateway.service.keygen import generate_key
    monkeypatch.setitem(_HEADERS, "Authorization", "Bearer " + generate_key("routing-test"))
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "")
    # This suite isolates provider routing; the real compiler has separate tests.
    monkeypatch.setattr(edge, "compile_chat_context", lambda **kwargs: kwargs["messages"])
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


@pytest.mark.parametrize("model", ["supremeai-web", "supremeai/web", "supremeai-webhook", "supremeai/ghost_gemini"])
@pytest.mark.parametrize("stream", [False, True])
def test_webhook_only_alias_never_crosses_into_api_pool(gateway, monkeypatch, model, stream):
    client, upstream = gateway
    relay = AsyncMock(return_value=(503, {"error": "fixture outage"}))
    monkeypatch.setattr(edge, "forward_stealth_webhook", relay)
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "https://relay.example.invalid")
    result = client.post("/v1/chat/completions", json={**_CHAT, "model": model, "stream": stream}, headers=_HEADERS)
    assert result.status_code == 502
    relay.assert_awaited_once()
    upstream.assert_not_called()


def test_relay_only_api_fallback_is_opt_in(gateway, monkeypatch):
    client, upstream = gateway
    monkeypatch.setenv("ENABLE_API_FALLBACK", "true")
    relay = AsyncMock(return_value=(503, {"error": "fixture relay outage"}))
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "https://relay.example.invalid")
    monkeypatch.setattr(edge, "forward_stealth_webhook", relay)
    upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": "API fallback"}}]})

    response = client.post(
        "/v1/chat/completions",
        json={**_CHAT, "model": "supremeai-web"},
        headers=_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "API fallback"
    relay.assert_awaited_once()
    upstream.assert_called_once()


def test_relay_only_fallback_disabled_stays_fail_closed(gateway, monkeypatch):
    client, upstream = gateway
    monkeypatch.setenv("ENABLE_API_FALLBACK", "false")
    relay = AsyncMock(return_value=(503, {"error": "fixture relay outage"}))
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "https://relay.example.invalid")
    monkeypatch.setattr(edge, "forward_stealth_webhook", relay)

    response = client.post(
        "/v1/chat/completions",
        json={**_CHAT, "model": "supremeai-web"},
        headers=_HEADERS,
    )
    assert response.status_code == 502
    relay.assert_awaited_once()
    upstream.assert_not_called()


@pytest.mark.parametrize("stream", [False, True])
def test_missing_approval_does_not_use_configured_keys_or_relay_for_api_alias(gateway, monkeypatch, stream):
    client, upstream = gateway
    monkeypatch.delenv(POLICY_ENV)
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "https://relay.example.invalid")
    relay = AsyncMock()
    monkeypatch.setattr(edge, "forward_stealth_webhook", relay)
    result = client.post("/v1/chat/completions", json={**_CHAT, "stream": stream}, headers=_HEADERS)
    assert result.status_code == 503
    relay.assert_not_called()
    upstream.assert_not_called()


def test_payload_cannot_select_unapproved_model_or_paid_extension(gateway):
    client, upstream = gateway
    upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": "Safe route"}}]})
    body = {**_CHAT, "model": "not-approved", "models": ["not-approved"], "plugins": [{"id": "web"}],
            "web_search_options": {}, "service_tier": "priority"}
    result = client.post("/v1/chat/completions", json=body, headers=_HEADERS)
    assert result.status_code == 200
    sent = json.loads(upstream.call_args.args[0].content)
    assert sent["model"] == "first"
    assert not any(field in sent for field in ("models", "plugins", "web_search_options", "service_tier"))


def test_402_withdraws_model_even_if_it_was_preferred(gateway):
    client, upstream = gateway
    upstream.side_effect = [
        httpx.Response(402),
        httpx.Response(200, json={"choices": [{"message": {"content": "Approved alternate"}}]}),
        httpx.Response(200, json={"choices": [{"message": {"content": "Approved alternate"}}]}),
    ]
    for _ in range(2):
        assert client.post("/v1/chat/completions", json={**_CHAT, "model": "first"}, headers=_HEADERS).status_code == 200
    assert [json.loads(call.args[0].content)["model"] for call in upstream.call_args_list] == ["first", "second", "second"]


@pytest.mark.parametrize("approval", [
    "expired", "wrong-base", "wrong-credential", "invalid-json", "missing-binding-key", "rotated-binding-key",
])
@pytest.mark.parametrize("stream", [False, True])
def test_unproven_route_never_dispatches(gateway, monkeypatch, approval, stream):
    client, upstream = gateway
    if approval == "missing-binding-key":
        monkeypatch.delenv(HMAC_KEY_ENV)
    elif approval == "rotated-binding-key":
        monkeypatch.setenv(HMAC_KEY_ENV, "f0" * 32)
    else:
        policy = json.loads(os.environ[POLICY_ENV])
        override = {
            "expired": {"expires_at": "2000-01-01T00:00:00Z"},
            "wrong-base": {"base_url": "https://other.example.invalid/v1"},
            "wrong-credential": {"key_hmac_sha256": "f" * 64},
            "invalid-json": {},
        }[approval]
        updated = "{" if approval == "invalid-json" else json.dumps([{**entry, **override} for entry in policy])
        monkeypatch.setenv(POLICY_ENV, updated)
    assert client.get("/readyz").status_code == 503
    response = client.post("/v1/chat/completions", json={**_CHAT, "stream": stream}, headers=_HEADERS)
    assert response.status_code == 503
    upstream.assert_not_called()


@pytest.mark.parametrize("model", ["supremeai-api", "supremeai-web", "auto"])
def test_unapproved_image_never_uses_text_api_or_relay(gateway, monkeypatch, model):
    client, upstream = gateway
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "https://relay.example.invalid")
    relay = AsyncMock()
    monkeypatch.setattr(edge, "forward_stealth_webhook", relay)
    body = {"model": model, "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "https://image.example.invalid/photo.png"}},
    ]}]}
    assert client.post("/v1/chat/completions", json=body, headers=_HEADERS).status_code == 503
    upstream.assert_not_called()
    relay.assert_not_awaited()


def test_api_only_image_uses_only_the_approved_multimodal_model(gateway, monkeypatch):
    client, upstream = gateway
    slot = KeySlot("vision-slot", "fixture-vision-key", "gemini", preferred_model="text-only")
    edge.squad.pools["gemini"].slots = [slot]
    policy = json.loads(os.environ[POLICY_ENV])
    policy.append({
        "provider": "gemini", "base_url": edge.PROVIDER_CONFIGS["gemini"]["base_url"],
        "key_hmac_sha256": credential_identity("gemini", edge.PROVIDER_CONFIGS["gemini"]["base_url"], slot.key)[2],
        "models": ["text-only", "vision-fixture"], "vision_models": ["vision-fixture"],
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    })
    monkeypatch.setenv(POLICY_ENV, json.dumps(policy))
    upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": "Image result"}}]})
    body = {**_CHAT, "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "https://image.example.invalid/photo.png"}},
    ]}]}
    assert client.post("/v1/chat/completions", json=body, headers=_HEADERS).status_code == 200
    upstream.assert_called_once()
    request = upstream.call_args.args[0]
    assert str(request.url).startswith(policy[-1]["base_url"])
    assert json.loads(request.content)["model"] == "vision-fixture"


@pytest.mark.parametrize("approved", [False, True])
def test_v0_uses_only_its_approved_slot(gateway, monkeypatch, approved):
    client, upstream = gateway
    slot = KeySlot("v0-slot", "fixture-v0-key", "v0")
    edge.squad.pools["v0"].slots = [slot]
    relay = AsyncMock()
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "https://relay.example.invalid")
    monkeypatch.setattr(edge, "forward_stealth_webhook", relay)
    if approved:
        policy = json.loads(os.environ[POLICY_ENV])
        policy.append({
            "provider": "v0", "base_url": edge.PROVIDER_CONFIGS["v0"]["base_url"],
            "key_hmac_sha256": credential_identity("v0", edge.PROVIDER_CONFIGS["v0"]["base_url"], slot.key)[2],
            "models": ["ui-fixture"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        })
        monkeypatch.setenv(POLICY_ENV, json.dumps(policy))
        upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": "fixture UI"}}]})
    response = client.post("/v1/ui/generate", json={"prompt": "fixture UI"}, headers=_HEADERS)
    relay.assert_not_awaited()
    if approved:
        assert response.status_code == 200
        upstream.assert_called_once()
        request = upstream.call_args.args[0]
        assert request.headers["authorization"] == "Bearer fixture-v0-key"
        assert json.loads(request.content)["model"] == "ui-fixture"
    else:
        assert response.status_code == 503
        upstream.assert_not_called()


def test_response_is_not_reused_across_caller_keys(gateway, monkeypatch):
    client, upstream = gateway
    upstream.side_effect = [
        httpx.Response(200, json={"choices": [{"message": {"content": value}}]})
        for value in ("first result", "second result")
    ]
    body = {**_CHAT, "temperature": 0}
    first = client.post("/v1/chat/completions", json=body, headers=_HEADERS)
    monkeypatch.setenv("SUPREMEAI_API_KEY", "second-fixture-client-key")
    second = client.post("/v1/chat/completions", json=body, headers={"Authorization": "Bearer second-fixture-client-key"})
    assert first.status_code == second.status_code == 200
    assert first.json()["choices"][0]["message"]["content"] == "first result"
    assert second.json()["choices"][0]["message"]["content"] == "second result"
    assert upstream.call_count == 2


def test_api_attempt_is_cancelled_at_the_route_deadline(gateway, monkeypatch):
    client, upstream = gateway
    cancelled = Mock()

    async def slow(*_args, **_kwargs):
        try:
            await asyncio.Future()
        finally:
            cancelled()

    adapter = AsyncMock(side_effect=slow)
    monkeypatch.setattr(edge, "forward_chat_completion", adapter)
    monkeypatch.setattr(edge, "CHAT_ROUTE_DEADLINE_S", 0.05)
    response = client.post("/v1/chat/completions", json=_CHAT, headers=_HEADERS)
    assert response.status_code == 502
    cancelled.assert_called_once()
    adapter.assert_awaited_once()
    upstream.assert_not_called()


def test_consented_personal_memory_reaches_only_owners_provider_context(gateway, monkeypatch, tmp_path):
    from gateway.service import context_compiler, memory_store
    from gateway.service.keygen import generate_key

    client, upstream = gateway
    store = memory_store.CanonicalMemoryStore(str(tmp_path / "private.db"))
    monkeypatch.setattr(memory_store, "_DEFAULT_STORE", store)
    monkeypatch.setattr(edge, "ingest_consented_personal_memory", store.ingest_consented_personal_memory)
    monkeypatch.setattr(edge, "compile_chat_context", context_compiler.compile_chat_context)
    a = {"Authorization": "Bearer " + generate_key("usr-usr-aaaaaaaaaaaa")}
    b = {"Authorization": "Bearer " + generate_key("usr-usr-bbbbbbbbbbbb")}
    store.set_personal_memory_consent("usr-aaaaaaaaaaaa", True)
    upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": "Fixture reply"}}]})
    payload = {"model": "supremeai-api", "messages": [{"role": "user", "content": "My name is Alice."}]}
    assert client.post("/v1/chat/completions", json=payload, headers=a).status_code == 200
    own = json.loads(upstream.call_args.args[0].content)
    assert "Alice" in str(own["messages"])
    assert any("Alice" in str(m) and "durable_user_memory" in str(m) and m["role"] == "user" for m in own["messages"])
    assert client.post("/v1/chat/completions", json={"model": "supremeai-api", "messages": [{"role": "user", "content": "Hello"}]}, headers=b).status_code == 200
    other = json.loads(upstream.call_args.args[0].content)
    assert "Alice" not in str(other["messages"])
    store.set_personal_memory_consent("usr-aaaaaaaaaaaa", False)
    assert client.post("/v1/chat/completions", json={"model": "supremeai-api", "messages": [{"role": "user", "content": "Hello"}]}, headers=a).status_code == 200
    disabled = json.loads(upstream.call_args.args[0].content)
    assert "Alice" not in str(disabled["messages"])


def test_sanitizer_failure_rejects_response_and_assistant_persistence(gateway, monkeypatch):
    client, upstream = gateway
    upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": "unsafe fixture"}}]})
    monkeypatch.setattr(edge, "validate_and_sanitize", Mock(side_effect=ValueError("sensitive detail")))
    response = client.post("/v1/chat/completions", json={**_CHAT, "session_id": "fixture"}, headers=_HEADERS)
    assert response.status_code == 500
    assert "unsafe fixture" not in response.text and "sensitive detail" not in response.text
    assert not any(call.args[1] == "assistant" for call in edge.append_canonical_message.call_args_list)


def test_ring_log_handler_discards_failed_subscriber_without_recursion(monkeypatch):
    import logging
    failing = Mock()
    failing.put_nowait.side_effect = RuntimeError("broken")
    handler = edge.RingBufferLogHandler()
    handler.subscribers.add(failing)
    monkeypatch.setattr(edge.logger, "handlers", [handler])
    monkeypatch.setattr(edge.logger, "propagate", False)
    monkeypatch.setattr(edge.logger, "level", logging.DEBUG)
    edge.logger.warning("one fixture event")
    assert failing.put_nowait.call_count == 1
    assert failing not in handler.subscribers
    assert len(handler.buffer) == 1


def test_missing_sanitizer_rejects_non_streaming_response(gateway, monkeypatch):
    client, upstream = gateway
    upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": "unsafe fixture"}}]})
    monkeypatch.setattr(edge, "validate_and_sanitize", None)
    response = client.post("/v1/chat/completions", json={**_CHAT, "session_id": "fixture"}, headers=_HEADERS)
    assert response.status_code == 503
    assert "unsafe fixture" not in response.text
    assert not any(call.args[1] == "assistant" for call in edge.append_canonical_message.call_args_list)


@pytest.mark.parametrize("stream", [False, True])
def test_webhook_missing_guard_cannot_serve_buffered_reply(gateway, monkeypatch, stream):
    client, upstream = gateway
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "https://relay.example.invalid")
    relay = AsyncMock(return_value=(200, {"choices": [{"message": {"content": "unsafe fixture"}}]}))
    monkeypatch.setattr(edge, "forward_stealth_webhook", relay)
    monkeypatch.setattr(edge, "validate_and_sanitize", None)
    response = client.post("/v1/chat/completions", json={**_CHAT, "model": "supremeai-web", "stream": stream}, headers=_HEADERS)
    assert response.status_code == 503
    assert "unsafe fixture" not in response.text
    relay.assert_awaited_once()
    upstream.assert_not_called()


@pytest.mark.parametrize("stream", [False, True])
def test_assistant_persistence_failure_is_not_reported_as_success(gateway, monkeypatch, stream):
    client, upstream = gateway

    def persist(_conv, role, *_args, **_kwargs):
        if role == "assistant":
            raise RuntimeError("sensitive database detail")
        return {"id": "user-message"}

    monkeypatch.setattr(edge, "append_canonical_message", Mock(side_effect=persist))
    if stream:
        upstream.return_value = httpx.Response(200, stream=_ProviderStream(
            _sse({"choices": [{"delta": {"content": "Partial visible reply"}}]}), b"data: [DONE]\n\n"))
    else:
        upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": "Fixture reply"}}]})
    response = client.post("/v1/chat/completions", json={**_CHAT, "stream": stream, "session_id": "fixture"}, headers=_HEADERS)
    assert "sensitive database detail" not in response.text
    if stream:
        frames = _stream_frames(response)
        assert frames[-1]["error"] == "Conversation storage unavailable"
        assert not any(frame.get("choices", [{}])[0].get("finish_reason") == "stop" for frame in frames)
    else:
        assert response.status_code == 503
        assert "Fixture reply" not in response.text


@pytest.mark.parametrize("stream", [False, True])
def test_relay_assistant_persistence_failure_never_sends_reply(gateway, monkeypatch, stream):
    client, upstream = gateway

    def persist(_conv, role, *_args, **_kwargs):
        if role == "assistant":
            raise RuntimeError("private detail")
        return {"id": "user-message"}

    monkeypatch.setattr(edge, "append_canonical_message", Mock(side_effect=persist))
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "https://relay.example.invalid")
    monkeypatch.setattr(edge, "forward_stealth_webhook", AsyncMock(return_value=(200, {"choices": [{"message": {"content": "Fixture reply"}}]})))
    response = client.post("/v1/chat/completions", json={**_CHAT, "model": "supremeai-web", "session_id": "fixture", "stream": stream}, headers=_HEADERS)
    assert response.status_code == 503
    assert "private detail" not in response.text and "Fixture reply" not in response.text
    upstream.assert_not_called()


def test_upstream_errors_do_not_leak_into_chat_response(gateway):
    client, upstream = gateway
    upstream.return_value = httpx.Response(503, json={"error": "private-upstream-token"})
    response = client.post("/v1/chat/completions", json=_CHAT, headers=_HEADERS)
    assert response.status_code == 502
    assert "private-upstream-token" not in response.text


def test_upstream_stream_errors_do_not_leak_into_sse(gateway, monkeypatch):
    client, _ = gateway

    async def failing_stream(*_args, **_kwargs):
        yield "error", {"status": 503, "error": "private-upstream-token"}

    monkeypatch.setattr(edge, "stream_chat_completion_events", failing_stream)
    response = client.post("/v1/chat/completions", json={**_CHAT, "stream": True}, headers=_HEADERS)
    assert "private-upstream-token" not in response.text
    assert _stream_frames(response)[-1]["error"] == "Upstream stream failed"


def test_relay_legacy_assistant_storage_failure_is_reported(gateway, monkeypatch):
    client, upstream = gateway
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "https://relay.example.invalid")
    monkeypatch.setattr(edge, "forward_stealth_webhook", AsyncMock(return_value=(200, {"choices": [{"message": {"content": "Fixture reply"}}]})))

    def legacy(_conv, role, *_args, **_kwargs):
        if role == "assistant":
            raise RuntimeError("private detail")

    monkeypatch.setattr(edge, "add_message", Mock(side_effect=legacy))
    response = client.post("/v1/chat/completions", json={**_CHAT, "model": "supremeai-web", "session_id": "fixture"}, headers=_HEADERS)
    assert response.status_code == 503
    assert "private detail" not in response.text and "Fixture reply" not in response.text
    upstream.assert_not_called()


def test_tool_only_nonstream_response_is_not_rejected_or_persisted_as_none(gateway):
    client, upstream = gateway
    upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": "{}"}}]}, "finish_reason": "tool_calls"}]})
    response = client.post("/v1/chat/completions", json={**_CHAT, "session_id": "fixture"}, headers=_HEADERS)
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "lookup"
    assert not any(call.args[1] == "assistant" for call in edge.append_canonical_message.call_args_list)


@pytest.mark.parametrize("calls", [[], [{}], [{"id": "x", "type": "function", "function": {"name": "", "arguments": "{}"}}]])
def test_malformed_nonstream_tool_calls_are_rejected(gateway, calls):
    client, upstream = gateway
    upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": calls}}]})
    assert client.post("/v1/chat/completions", json=_CHAT, headers=_HEADERS).status_code == 500


@pytest.mark.parametrize("stream", [False, True])
def test_provider_receives_owner_scoped_context_for_banglish_news_followup(gateway, monkeypatch, tmp_path, stream):
    """Gateway→owner store→compiler→mock provider: প্রসঙ্গ হারানো বা cross-user নয়।"""
    from gateway.service import context_compiler, memory_store

    client, upstream = gateway
    store = memory_store.CanonicalMemoryStore(str(tmp_path / "chat.db"))
    store.append_canonical_message("alice-chat", "user", "ajker bangladesher kono khobor jana ache?", user_id="alice")
    store.append_canonical_message("alice-chat", "assistant", "লাইভ খবর এখন জানা নেই।", user_id="alice")
    store.append_canonical_message("bob-chat", "user", "private other user fixture", user_id="bob")
    monkeypatch.setattr(memory_store, "_DEFAULT_STORE", store)
    monkeypatch.setattr(edge, "_extract_user_id", lambda *_: "alice")
    monkeypatch.setattr(edge, "_extract_registered_user_id", lambda *_: None)
    monkeypatch.setattr(edge, "append_canonical_message", store.append_canonical_message)
    monkeypatch.setattr(edge, "compile_chat_context", context_compiler.compile_chat_context)
    answer = "এই মুহূর্তে লাইভ খোঁজ করতে পারছি না।"
    if stream:
        upstream.return_value = httpx.Response(200, stream=_ProviderStream(_sse({"choices": [{"delta": {"content": answer}}]}), b"data: [DONE]\n\n"))
    else:
        upstream.return_value = httpx.Response(200, json={"choices": [{"message": {"content": answer}}]})
    response = client.post("/v1/chat/completions", json={**_CHAT, "stream": stream, "session_id": "alice-chat", "messages": [{"role": "user", "content": "google theke khuje dao"}]}, headers=_HEADERS)
    assert response.status_code == 200
    sent = json.loads(upstream.call_args.args[0].content)
    assert [(m["role"], m["content"]) for m in sent["messages"][-3:]] == [
        ("user", "ajker bangladesher kono khobor jana ache?"),
        ("assistant", "লাইভ খবর এখন জানা নেই।"),
        ("user", "google theke khuje dao"),
    ]
    assert "private other user fixture" not in json.dumps(sent)
    assert "Never claim to have searched" in sent["messages"][0]["content"]
    history = store.get_recent_history("alice-chat", user_id="alice")
    assert history[-1]["content"] == answer
    if stream:
        assert _stream_frames(response)[0]["choices"][0]["delta"]["content"] == answer
    else:
        assert response.json()["choices"][0]["message"]["content"] == answer


@pytest.mark.parametrize("stream", [False, True])
def test_explicit_source_discovery_chat_returns_real_metadata_without_calling_model(gateway, monkeypatch, stream):
    client, upstream = gateway
    result = {"status": "ok", "executed": True, "source": "Crossref", "results": [{
        "title": "Study fixture", "url": "https://doi.org/10.1234/example", "published": "2025", "publisher": "Fixture"}]}
    forward = AsyncMock(return_value=result)
    monkeypatch.setattr(edge, "_forward_agent_request", forward)
    spec = {"query": "dengue research", "kind": "research", "consent": True}
    resp = client.post("/v1/chat/completions", json={**_CHAT, "stream": stream, "source_search": spec,
        "messages": [{"role": "user", "content": "ডেঙ্গু নিয়ে গবেষণা খুঁজে দাও"}]}, headers=_HEADERS)
    assert resp.status_code == 200
    if stream:
        frames = _stream_frames(resp)
        answer = frames[0]["choices"][0]["delta"]["content"]
        assert frames[-1]["choices"][0]["finish_reason"] == "stop"
    else:
        answer = resp.json()["choices"][0]["message"]["content"]
        assert resp.json()["source_search"] == {"status": "ok", "executed": True}
    assert "Study fixture" in answer and "https://doi.org/10.1234/example" in answer
    assert "স্বাধীনভাবে যাচাই করিনি" in answer
    assert forward.await_args.args[3] == spec
    upstream.assert_not_called()


def test_source_discovery_chat_consent_and_clarification_are_honest(gateway, monkeypatch):
    client, upstream = gateway
    forward = AsyncMock(side_effect=[
        {"status": "consent_required", "executed": False, "source": "Bing News", "results": []},
        {"status": "needs_clarification", "executed": False, "options": ["news", "research"], "results": []},
    ])
    monkeypatch.setattr(edge, "_forward_agent_request", forward)
    body = {**_CHAT, "source_search": {"query": "news", "consent": False}, "messages": [{"role": "user", "content": "আজকের খবর"}]}
    first = client.post("/v1/chat/completions", json=body, headers=_HEADERS)
    second = client.post("/v1/chat/completions", json=body, headers=_HEADERS)
    assert "অনুমতি" in first.json()["choices"][0]["message"]["content"]
    assert first.json()["source_search"]["executed"] is False
    assert "কোন ধরনের তথ্য" in second.json()["choices"][0]["message"]["content"]
    upstream.assert_not_called()


def test_invalid_source_search_and_missing_guard_cannot_report_success(gateway, monkeypatch):
    client, upstream = gateway
    forward = AsyncMock(return_value={"status": "ok", "executed": True, "source": "Fixture", "results": [{"title": "x", "url": "https://example.org"}]})
    monkeypatch.setattr(edge, "_forward_agent_request", forward)
    resp = client.post("/v1/chat/completions", json={**_CHAT, "source_search": "bad"}, headers=_HEADERS)
    assert resp.status_code == 400
    forward.assert_not_awaited()
    monkeypatch.setattr(edge, "validate_and_sanitize", None)
    resp = client.post("/v1/chat/completions", json={**_CHAT, "source_search": {"query": "fixture", "consent": True}}, headers=_HEADERS)
    assert resp.status_code == 503
    upstream.assert_not_called()
