"""Tests for core SSE first-token timeout and legacy memory isolation."""

import asyncio
import time

import pytest
from unittest.mock import AsyncMock

from core.memory.auto_rag_injector import auto_rag_injector

import core.api.routes.stream_chat_sse as sse


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id,tenant_id", [("u1", "t1"), ("u2", "t2"), ("admin", None)])
async def test_sse_does_not_recall_or_store_without_consent_integration(monkeypatch, user_id, tenant_id):
    recall = AsyncMock(side_effect=AssertionError("legacy memory recall must stay disabled"))
    store = AsyncMock(side_effect=AssertionError("legacy memory write must stay disabled"))
    monkeypatch.setattr(auto_rag_injector, "enrich_system_prompt", recall)
    monkeypatch.setattr(auto_rag_injector, "store_session_memory", store)
    prompts = []

    async def fake_acompletion(**kwargs):
        prompts.append(kwargs["prompt"])
        async def gen():
            yield "answer"
        return gen()

    monkeypatch.setattr(sse.llm_gateway, "acompletion", fake_acompletion)
    prompt = "Please remember this preference for my next conversations."
    gen = sse.SafeSSEGenerator(prompt, user_id=user_id, tenant_id=tenant_id, session_id="s1")
    events = [e async for e in gen()]
    assert prompts == [prompt]
    assert any("event: token" in e for e in events)
    assert any("event: done" in e for e in events)
    recall.assert_not_awaited()
    store.assert_not_awaited()


@pytest.mark.asyncio
async def test_first_token_timeout_fails_fast(monkeypatch):
    monkeypatch.setattr(sse, "SSE_FIRST_TOKEN_TIMEOUT_S", 0.1)

    async def hanging_acompletion(**kwargs):
        async def gen():
            await asyncio.sleep(5)
            yield "late"  # pragma: no cover

        return gen()

    monkeypatch.setattr(sse.llm_gateway, "acompletion", hanging_acompletion)

    gen = sse.SafeSSEGenerator("hello", user_id="u1")
    start = time.monotonic()
    events = [e async for e in gen._try_streaming_path()]
    elapsed = time.monotonic() - start

    assert elapsed < 2.0, "first-token timeout did not fail fast"
    assert gen.state == sse.StreamState.ERROR
    assert events == [], "no token events should be emitted on first-token timeout"


@pytest.mark.asyncio
async def test_first_token_records_latency(monkeypatch):
    monkeypatch.setattr(sse, "SSE_FIRST_TOKEN_TIMEOUT_S", 5)

    async def fake_acompletion(**kwargs):
        async def gen():
            yield "hello"

        return gen()

    monkeypatch.setattr(sse.llm_gateway, "acompletion", fake_acompletion)

    gen = sse.SafeSSEGenerator("hi", user_id="u1")
    events = [e async for e in gen._try_streaming_path()]

    assert gen._emitted_tokens is True
    assert any("token" in e for e in events)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
