import time

import pytest

from core.circuit_breaker import CircuitBreaker


@pytest.fixture
def cb():
    return CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=1.0)


def test_initial_state_closed(cb):
    assert cb.state == "CLOSED"
    assert cb.allow_request() is True


def test_success_keeps_closed(cb):
    cb.mark_success()
    assert cb.state == "CLOSED"
    assert cb.allow_request() is True
    assert cb.failures == 0


def test_open_after_threshold(cb):
    for _ in range(2):
        cb.mark_failure()
    assert cb.state == "CLOSED"
    cb.mark_failure()
    assert cb.state == "OPEN"
    assert cb.allow_request() is False


def test_half_open_after_recovery_timeout(cb):
    for _ in range(3):
        cb.mark_failure()
    assert cb.state == "OPEN"
    cb.opened_at = time.time() - 1.5
    assert cb.allow_request() is True
    assert cb.state == "HALF_OPEN"


def test_mark_success_closes_from_half_open(cb):
    for _ in range(3):
        cb.mark_failure()
    cb.opened_at = time.time() - 1.5
    cb.allow_request()
    assert cb.state == "HALF_OPEN"
    cb.mark_success()
    assert cb.state == "CLOSED"
    assert cb.failures == 0


def test_call_success(anyio_backend):
    cb = CircuitBreaker(name="async-test", failure_threshold=2)

    async def good():
        return "ok"

    async def run():
        return await cb.call(good)

    import asyncio
    result = asyncio.get_event_loop().run_until_complete(run())
    assert result == "ok"
    assert cb.state == "CLOSED"


def test_call_raises_when_open(anyio_backend):
    cb = CircuitBreaker(name="async-open", failure_threshold=1)

    async def bad():
        raise ValueError("fail")

    async def run():
        await cb.call(bad)

    import asyncio
    with pytest.raises(ValueError):
        asyncio.get_event_loop().run_until_complete(run())
    assert cb.state == "OPEN"


def test_call_blocks_when_open(anyio_backend):
    cb = CircuitBreaker(name="async-blocked", failure_threshold=1)

    async def good():
        return "ok"

    async def run():
        return await cb.call(good)

    import asyncio
    cb.mark_failure()
    assert cb.state == "OPEN"
    with pytest.raises(RuntimeError, match="open"):
        asyncio.get_event_loop().run_until_complete(run())
