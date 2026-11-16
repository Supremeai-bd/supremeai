"""Regression tests for time-to-first-token enforcement in the streaming path.

These lock the Phase-1 behaviour: a provider is only treated as started once the
first *text/tool_calls* token arrives, and a slow first token (or slow headers)
raises ``asyncio.TimeoutError`` so the caller can fail over before forwarding
anything downstream.
"""

import asyncio

import pytest

from gateway.service.app import _aiter_stream_first_token


async def _agen(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_normal_stream_passes_through():
    stream = _agen(
        [
            ("status", {"status": 200}),
            ("event", {"delta": "Hello"}),
            ("event", {"delta": " world"}),
        ]
    )
    out = [
        item
        async for item in _aiter_stream_first_token(
            stream, connect_timeout_s=5, first_token_timeout_s=5
        )
    ]
    assert out == [
        ("status", {"status": 200}),
        ("event", {"delta": "Hello"}),
        ("event", {"delta": " world"}),
    ]


@pytest.mark.asyncio
async def test_tool_calls_count_as_first_token():
    stream = _agen(
        [
            ("status", {"status": 200}),
            ("event", {"tool_calls": [{"id": "call_1"}]}),
        ]
    )
    out = [
        item
        async for item in _aiter_stream_first_token(
            stream, connect_timeout_s=5, first_token_timeout_s=5
        )
    ]
    assert out[-1][0] == "event"
    assert out[-1][1]["tool_calls"]


@pytest.mark.asyncio
async def test_slow_first_token_raises_timeout():
    async def slow():
        yield ("status", {"status": 200})
        await asyncio.sleep(10)  # headers arrive, but no token
        yield ("event", {"delta": "late"})  # pragma: no cover

    stream = slow()
    with pytest.raises(asyncio.TimeoutError):
        async for _ in _aiter_stream_first_token(
            stream, connect_timeout_s=5, first_token_timeout_s=0.2
        ):
            pass


@pytest.mark.asyncio
async def test_slow_headers_raise_connect_timeout():
    async def no_status():
        await asyncio.sleep(10)
        yield ("status", {"status": 200})  # pragma: no cover

    stream = no_status()
    with pytest.raises(asyncio.TimeoutError):
        async for _ in _aiter_stream_first_token(
            stream, connect_timeout_s=0.2, first_token_timeout_s=5
        ):
            pass


@pytest.mark.asyncio
async def test_committed_stream_is_not_cut():
    # After the first token the stream is committed: a slow gap must NOT time out.
    async def committed():
        yield ("status", {"status": 200})
        yield ("event", {"delta": "Hi"})
        await asyncio.sleep(0.3)
        yield ("event", {"delta": "!"})

    stream = committed()
    out = [
        item
        async for item in _aiter_stream_first_token(
            stream, connect_timeout_s=5, first_token_timeout_s=0.1
        )
    ]
    assert out[-1] == ("event", {"delta": "!"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])