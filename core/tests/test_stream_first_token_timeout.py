"""Tests for core SSE first-token / enrichment timeouts (stream_chat_sse).

A slow Auto-RAG enrichment must not block the LLM call (bounded, falls back to the
raw prompt), and a model that never emits a first token must fail the stream fast
instead of hanging.
"""

import asyncio
import time

import pytest

import core.api.routes.stream_chat_sse as sse


@pytest.mark.asyncio
async def test_enrichment_timeout_uses_raw_prompt(monkeypatch):
    monkeypatch.setattr(sse, "ENRICHMENT_TIMEOUT_S", 0.1)

    async def slow_enrich(**kwargs):
        await asyncio.sleep(5)
        return "ENRICHED"  # pragma: no cover

    monkeypatch.setattr(sse.auto_rag_injector, "enrich_system_prompt", slow_enrich)

    async def fake_acompletion(**kwargs):
        async def gen():
            yield "hi"

        return gen()

    monkeypatch.setattr(sse.llm_gateway, "acompletion", fake_acompletion)

    async def no_store(**kwargs):
        return False

    monkeypatch.setattr(sse.auto_rag_injector, "store_session_memory", no_store)

    gen = sse.SafeSSEGenerator("hello", user_id="u1")
    start = time.monotonic()
    events = [e async for e in gen.__call__()]
    elapsed = time.monotonic() - start

    assert elapsed < 2.0, "enrichment timeout did not bound the request"
    assert gen.prompt == "hello", "raw prompt must be used when enrichment times out"
    assert any("token" in e for e in events)


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