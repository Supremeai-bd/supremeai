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

@pytest.mark.asyncio
async def test_api_deadline_caps_first_token_wait():
    import time

    async def blocked():
        yield ("status", {"status": 200})
        await asyncio.Future()

    with pytest.raises(TimeoutError):
        _ = [item async for item in _aiter_stream_first_token(
            blocked(), connect_timeout_s=8, first_token_timeout_s=8, route_deadline=time.monotonic() + 0.05,
        )]


# --- keep-alives: "slow but alive" is not "dead" ----------------------------
# The first-token window exists to detect an upstream that has gone quiet. A
# buffered web engine (the relay's cookie tier) is quiet for 10-25s and then
# sends everything at once, so the 8s window used to kill a request that was
# working the whole time. An SSE keep-alive is proof of life, so it extends the
# window — but only up to a ceiling, because a chatty-but-stuck upstream is
# exactly what the timeout is for.

import asyncio  # noqa: E402

import pytest  # noqa: E402


async def _slow_stream(plan):
    """Yield items, sleeping the given seconds before each one."""
    for delay, item in plan:
        await asyncio.sleep(delay)
        yield item


@pytest.mark.asyncio
async def test_a_keep_alive_extends_the_first_token_window():
    stream = _slow_stream(
        [
            (0.0, ("status", {"status": 200})),
            (0.10, ("heartbeat", {"comment": "waiting"})),
            (0.10, ("event", {"delta": "finally"})),
        ]
    )
    out = [
        item
        async for item in _aiter_stream_first_token(
            stream, connect_timeout_s=5, first_token_timeout_s=0.15, heartbeat_ceiling_s=5
        )
    ]
    assert [kind for kind, _ in out] == ["status", "event"]


@pytest.mark.asyncio
async def test_a_keep_alive_does_not_push_past_the_ceiling():
    stream = _slow_stream(
        [
            (0.0, ("status", {"status": 200})),
            (0.05, ("heartbeat", {"comment": "waiting"})),
            (0.20, ("event", {"delta": "too late"})),
        ]
    )
    with pytest.raises(asyncio.TimeoutError):
        async for _item in _aiter_stream_first_token(
            stream, connect_timeout_s=5, first_token_timeout_s=0.15, heartbeat_ceiling_s=0.12
        ):
            pass


@pytest.mark.asyncio
async def test_keep_alives_are_not_forwarded_downstream():
    """They exist to keep the upstream honest, not to reach the client as events."""
    stream = _slow_stream(
        [
            (0.0, ("status", {"status": 200})),
            (0.0, ("heartbeat", {"comment": "waiting"})),
            (0.0, ("event", {"delta": "hi"})),
        ]
    )
    out = [
        item
        async for item in _aiter_stream_first_token(
            stream, connect_timeout_s=5, first_token_timeout_s=5
        )
    ]
    assert [kind for kind, _ in out] == ["status", "event"]


@pytest.mark.asyncio
async def test_a_stream_with_no_keep_alives_still_times_out():
    """The extension only ever comes from evidence of life; silence still fails."""
    stream = _slow_stream(
        [
            (0.0, ("status", {"status": 200})),
            (0.20, ("event", {"delta": "late"})),
        ]
    )
    with pytest.raises(asyncio.TimeoutError):
        async for _item in _aiter_stream_first_token(
            stream, connect_timeout_s=5, first_token_timeout_s=0.15
        ):
            pass
