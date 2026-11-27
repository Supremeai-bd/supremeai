"""The SSE stream must not duplicate or falsely complete failed responses."""
from unittest.mock import AsyncMock

import pytest

import core.api.routes.stream_chat_sse as sse
from core.memory.auto_rag_injector import auto_rag_injector


@pytest.fixture(autouse=True)
def mock_memory(monkeypatch):
    store = AsyncMock(return_value=True)
    monkeypatch.setattr(auto_rag_injector, 'store_session_memory', store)
    return store


def frame_types(events):
    return [e.split('\n', 1)[0] for e in events if e.startswith('event:')]


@pytest.mark.parametrize('path', ['/api/v1/stream/chat', '/api/chat/stream'])
def test_route_exposes_partial_failure_without_a_second_answer(monkeypatch, path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    async def chunks():
        yield 'partial'
        raise RuntimeError('secret-upstream-details')

    complete = AsyncMock(return_value=chunks())
    monkeypatch.setattr(sse.llm_gateway, 'acompletion', complete)
    monkeypatch.setattr(sse, '_authenticate_request', AsyncMock(return_value={'sub': 'u1', 'tenant_id': 't1'}))
    monkeypatch.setattr(sse, '_enforce_finops', AsyncMock())
    monkeypatch.setattr(sse.finops_guard, 'record', AsyncMock())
    app = FastAPI()
    app.include_router(sse.router)
    app.include_router(sse.legacy_router)
    with TestClient(app) as client:
        response = client.post(path, json={'prompt': 'hi'})
    assert response.status_code == 200
    assert 'event: token' in response.text
    assert 'event: error' in response.text
    assert 'event: done' not in response.text
    assert '[DONE]' not in response.text
    assert 'secret-upstream-details' not in response.text
    assert complete.await_count == 1


@pytest.mark.asyncio
async def test_partial_stream_failure_never_restarts_or_reports_success(monkeypatch, mock_memory):
    async def chunks():
        yield 'partial'
        raise RuntimeError('secret-upstream-details')

    complete = AsyncMock(return_value=chunks())
    monkeypatch.setattr(sse.llm_gateway, 'acompletion', complete)
    generator = sse.SafeSSEGenerator('hi', user_id='u1')
    events = [event async for event in generator()]

    assert frame_types(events) == ['event: connected', 'event: token', 'event: error']
    assert '[DONE]' not in ''.join(events)
    assert 'secret-upstream-details' not in ''.join(events)
    assert complete.await_count == 1
    assert generator.state == sse.StreamState.ERROR
    mock_memory.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_stream_fallback_success_is_allowed(monkeypatch):
    async def empty():
        if False:
            yield None

    complete = AsyncMock(side_effect=[empty(), {'text': 'complete'}])
    monkeypatch.setattr(sse.llm_gateway, 'acompletion', complete)
    generator = sse.SafeSSEGenerator('hi', user_id='u1')
    events = [event async for event in generator()]
    assert frame_types(events) == ['event: connected', 'event: token', 'event: done']
    assert 'complete' in ''.join(events)
    assert '[DONE]' in ''.join(events)
    assert complete.await_count == 2


@pytest.mark.asyncio
async def test_stream_failure_before_first_token_can_use_fallback(monkeypatch):
    async def broken():
        raise RuntimeError('stream unavailable')
        yield None  # pragma: no cover

    complete = AsyncMock(side_effect=[broken(), {'text': 'recovered'}])
    monkeypatch.setattr(sse.llm_gateway, 'acompletion', complete)
    generator = sse.SafeSSEGenerator('hi', user_id='u1')
    events = [event async for event in generator()]
    assert frame_types(events) == ['event: connected', 'event: token', 'event: done']
    assert 'recovered' in ''.join(events)
    assert complete.await_count == 2


@pytest.mark.asyncio
async def test_unexpected_internal_failure_does_not_expose_error(monkeypatch):
    generator = sse.SafeSSEGenerator('hi', user_id='u1')

    async def unexpected():
        raise RuntimeError('secret-internal-details')
        yield ''  # pragma: no cover

    monkeypatch.setattr(generator, '_try_streaming_path', unexpected)
    events = [event async for event in generator()]
    assert frame_types(events) == ['event: connected', 'event: error']
    assert 'secret-internal-details' not in ''.join(events)
    assert generator.state == sse.StreamState.ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize('fallback', [RuntimeError('secret-upstream-details'), {}, None, {'text': ''}])
async def test_failed_or_empty_fallback_never_reports_success(monkeypatch, mock_memory, fallback):
    async def empty():
        if False:
            yield None

    complete = AsyncMock(side_effect=[empty(), fallback])
    monkeypatch.setattr(sse.llm_gateway, 'acompletion', complete)
    generator = sse.SafeSSEGenerator('hi', user_id='u1')
    events = [event async for event in generator()]
    assert frame_types(events) == ['event: connected', 'event: error']
    assert '[DONE]' not in ''.join(events)
    assert 'secret-upstream-details' not in ''.join(events)
    assert generator.state == sse.StreamState.ERROR
    assert complete.await_count == 2
    mock_memory.assert_not_awaited()
