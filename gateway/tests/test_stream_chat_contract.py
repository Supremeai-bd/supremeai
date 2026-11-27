"""Unit tests verifying AI Chat Streaming dual contract and backwards compatibility.

Tests both /api/chat/stream and /api/v1/stream/chat with both 'prompt' and 'message' payloads.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from brain.model_router import ModelRouter
from fastapi.testclient import TestClient

from core.app import app

client = TestClient(app)


@pytest.fixture
def auth_header(monkeypatch):
    """Use a real signed token; isolate external revocation and quota services."""
    from core.config import settings
    from core.security import JWT_AUDIENCE, JWT_ISSUER
    import core.security
    from core.finops import guard

    monkeypatch.setenv("SUPREMEAI_JWT_SECRET", "local-stream-contract-test-secret-" * 3)
    monkeypatch.setattr(core.security, "is_token_revoked", AsyncMock(return_value=False))
    monkeypatch.setattr(guard, "check", AsyncMock(return_value=SimpleNamespace(allowed=True)))
    monkeypatch.setattr(guard, "record", AsyncMock())
    token = jwt.encode(
        {"sub": "stream-test-user", "role": "viewer", "tenant_id": "stream-test-tenant",
         "jti": "stream-contract-jti", "iss": JWT_ISSUER, "aud": JWT_AUDIENCE,
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.jwt_secret, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_async_route_and_stream_consumes_direct_async_iterator(monkeypatch):
    """A direct async iterator must not be awaited before token consumption."""
    router = ModelRouter.__new__(ModelRouter)

    async def token_stream():
        for token in ("Hello", " world"):
            yield token

    class Gateway:
        def acompletion(self, **kwargs):
            return token_stream()

    monkeypatch.setattr("brain.model_router.get_llm_gateway", lambda: Gateway())
    tokens = [token async for token in router.async_route_and_stream("hello")]
    assert tokens == ["Hello", " world"]


@pytest.mark.asyncio
async def test_model_router_partial_failure_does_not_call_fallback(monkeypatch):
    router = ModelRouter.__new__(ModelRouter)

    async def chunks():
        yield "partial"
        raise RuntimeError("provider interrupted")

    gateway = MagicMock()
    gateway.acompletion = MagicMock(return_value=chunks())
    monkeypatch.setattr("brain.model_router.get_llm_gateway", lambda: gateway)
    fallback = MagicMock(side_effect=AssertionError("must not append a second answer"))
    monkeypatch.setattr(router, "route_and_stream", fallback)
    tokens = []
    with pytest.raises(RuntimeError, match="provider interrupted"):
        async for token in router.async_route_and_stream("hello"):
            tokens.append(token)
    assert tokens == ["partial"]
    fallback.assert_not_called()


@pytest.mark.asyncio
async def test_model_router_can_fallback_before_first_token(monkeypatch):
    router = ModelRouter.__new__(ModelRouter)
    gateway = MagicMock()
    gateway.acompletion = MagicMock(side_effect=RuntimeError("provider unavailable"))
    monkeypatch.setattr("brain.model_router.get_llm_gateway", lambda: gateway)
    fallback = MagicMock(return_value=iter(["recovered"]))
    monkeypatch.setattr(router, "route_and_stream", fallback)
    assert [token async for token in router.async_route_and_stream("hello")] == ["recovered"]
    fallback.assert_called_once()


@pytest.fixture
def mock_streaming_gateway():
    import core.services as services_mod
    from core.llm.llm_gateway import llm_gateway

    # #2558 (order-dependence): model_router-এর প্রাথমিক মান None হতে পারে
    # (core.services import-এ সেট করা) — None একটি বৈধ পূর্ববর্তী state, তাই
    # restore-ও শর্তহীনভাবে হতে হবে। আগের `if previous_router:` গার্ডের কারণে
    # fake MagicMock চিরকালের জন্য leak হয়ে tests/core/test_agent_factory.py-কে
    # ভাঙত ("object MagicMock can't be used in 'await' expression")।
    previous_router = getattr(services_mod, "model_router", None)
    fake_router = MagicMock()

    async def fake_stream(*args, **kwargs):
        for token in ["Hello", " world", "!"]:
            yield token.encode("utf-8")

    fake_router.async_route_and_stream = fake_stream
    services_mod.model_router = fake_router

    async def fake_gateway_stream(*args, **kwargs):
        if kwargs.get("context") and kwargs["context"].stream:

            async def _gen():
                for token in ["Hello", " from", " SSE", "!"]:
                    yield token

            return _gen()
        return {"text": "Hello fallback"}

    # #2558: llm_gateway.acompletion-এ instance-level অ্যাসাইনমেন্ট class
    # attribute-কে shadow করে রাখে — teardown-এ শুধু পুরনো bound-method বসালে
    # shadow-টি থেকে যায়, ফলে পরবর্তী টেস্টের CLASS-level patch
    # (LLMGateway.acompletion) অকার্যকর হয়ে যায়। Shadow-টি মুছে দিলে class
    # attribute আবার দৃশ্যমান হয়।
    had_instance_acompletion = "acompletion" in vars(llm_gateway)
    orig_acompletion = llm_gateway.acompletion
    llm_gateway.acompletion = AsyncMock(side_effect=fake_gateway_stream)

    yield

    services_mod.model_router = previous_router  # None-সহ সব state-এ শর্তহীন restore
    if had_instance_acompletion:
        llm_gateway.acompletion = orig_acompletion
    else:
        del llm_gateway.acompletion  # instance-shadow অপসারণ — class attr আবার দৃশ্যমান


def test_post_chat_stream_legacy_payload(mock_streaming_gateway, auth_header):
    """Verify POST /api/chat/stream handles legacy {message: '...'} and yields token + delta."""
    response = client.post(
        "/api/chat/stream",
        json={"message": "test message", "sessionId": "sess-123"},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "data: " in body
    assert "token" in body
    assert "delta" in body
    assert "[DONE]" in body


def test_post_stream_chat_sse_with_prompt(mock_streaming_gateway, auth_header):
    """Verify POST /api/v1/stream/chat handles modern {prompt: '...'} without 422 error."""
    response = client.post(
        "/api/v1/stream/chat",
        json={"prompt": "test prompt", "session_id": "sess-456"},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "event: connected" in body
    assert "event: token" in body
    assert "token" in body
    assert "delta" in body
    assert "event: done" in body
    assert "[DONE]" in body


def test_post_stream_chat_sse_with_message_alias(mock_streaming_gateway, auth_header):
    """Verify POST /api/v1/stream/chat handles UI {message: '...'} without 422 error."""
    response = client.post(
        "/api/v1/stream/chat",
        json={"message": "hello UI message", "sessionId": "sess-789"},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "event: token" in body
    assert "delta" in body
    assert "token" in body


@pytest.mark.parametrize("path", ["/api/chat/stream", "/api/v1/stream/chat"])
def test_invalid_bearer_is_rejected(path):
    response = client.post(path, json={"prompt": "hello"}, headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/api/chat/stream", "/api/v1/stream/chat"])
def test_authenticated_stream_does_not_use_legacy_auto_rag(path, auth_header, monkeypatch):
    from core.memory.auto_rag_injector import auto_rag_injector
    from core.llm.llm_gateway import llm_gateway
    import core.services as services

    recall = AsyncMock(side_effect=AssertionError("unexpected legacy recall"))
    store = AsyncMock(side_effect=AssertionError("unexpected legacy memory write"))
    monkeypatch.setattr(auto_rag_injector, "enrich_system_prompt", recall)
    monkeypatch.setattr(auto_rag_injector, "store_session_memory", store)

    async def chunks(*args, **kwargs):
        yield "answer"

    if path == "/api/chat/stream":
        router = MagicMock()
        router.async_route_and_stream = chunks
        monkeypatch.setattr(services, "model_router", router)
    else:
        monkeypatch.setattr(llm_gateway, "acompletion", AsyncMock(return_value=chunks()))
    response = client.post(path, json={"prompt": "Please remember my language preference", "task_type": "general"}, headers=auth_header)
    assert response.status_code == 200
    assert "answer" in response.text
    assert "[DONE]" in response.text
    recall.assert_not_awaited()
    store.assert_not_awaited()


@pytest.mark.parametrize("path", ["/api/chat/stream", "/api/v1/stream/chat"])
def test_authenticated_partial_stream_failure_is_terminal(path, auth_header, monkeypatch):
    from core.llm.llm_gateway import llm_gateway

    async def chunks():
        yield "partial answer"
        raise RuntimeError("secret-upstream-details")

    complete = AsyncMock(return_value=chunks())
    if path == "/api/chat/stream":
        import core.services as services
        router = MagicMock()
        router.async_route_and_stream = MagicMock(side_effect=lambda **kwargs: chunks())
        monkeypatch.setattr(services, "model_router", router)
    else:
        monkeypatch.setattr(llm_gateway, "acompletion", complete)
    response = client.post(path, json={"prompt": "test prompt", "task_type": "general"}, headers=auth_header)
    assert response.status_code == 200
    assert "partial answer" in response.text
    assert "event: error" in response.text
    assert "event: done" not in response.text
    assert "[DONE]" not in response.text
    assert "secret-upstream-details" not in response.text
    if path == "/api/chat/stream":
        router.async_route_and_stream.assert_called_once()
    else:
        assert complete.await_count == 1


def test_legacy_empty_stream_does_not_report_success(auth_header, monkeypatch):
    import core.services as services

    async def empty(**kwargs):
        if False:
            yield ""  # pragma: no cover

    router = MagicMock()
    router.async_route_and_stream = empty
    monkeypatch.setattr(services, "model_router", router)
    response = client.post("/api/chat/stream", json={"prompt": "hi", "task_type": "general"}, headers=auth_header)
    assert response.status_code == 200
    assert "event: error" in response.text
    assert "[DONE]" not in response.text


def test_validation_error_when_neither_prompt_nor_message(auth_header):
    """Verify 422 validation error when neither prompt nor message is provided."""
    response = client.post(
        "/api/v1/stream/chat",
        json={"task_type": "chat"},
        headers=auth_header,
    )
    assert response.status_code == 422
