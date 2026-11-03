"""Unit tests verifying AI Chat Streaming dual contract and backwards compatibility.

Tests both /api/chat/stream and /api/v1/stream/chat with both 'prompt' and 'message' payloads.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from brain.model_router import ModelRouter
from core.app import app

client = TestClient(app)


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
        if kwargs.get("stream"):

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


def test_post_chat_stream_legacy_payload(mock_streaming_gateway):
    """Verify POST /api/chat/stream handles legacy {message: '...'} and yields token + delta."""
    response = client.post(
        "/api/chat/stream",
        json={"message": "test message", "sessionId": "sess-123"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "data: " in body
    assert "token" in body
    assert "delta" in body
    assert "[DONE]" in body


def test_post_stream_chat_sse_with_prompt(mock_streaming_gateway):
    """Verify POST /api/v1/stream/chat handles modern {prompt: '...'} without 422 error."""
    response = client.post(
        "/api/v1/stream/chat",
        json={"prompt": "test prompt", "session_id": "sess-456"},
        headers={"Authorization": "Bearer test-token"},
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


def test_post_stream_chat_sse_with_message_alias(mock_streaming_gateway):
    """Verify POST /api/v1/stream/chat handles UI {message: '...'} without 422 error."""
    response = client.post(
        "/api/v1/stream/chat",
        json={"message": "hello UI message", "sessionId": "sess-789"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "event: token" in body
    assert "delta" in body
    assert "token" in body


def test_validation_error_when_neither_prompt_nor_message():
    """Verify 422 validation error when neither prompt nor message is provided."""
    response = client.post(
        "/api/v1/stream/chat",
        json={"task_type": "chat"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 422
