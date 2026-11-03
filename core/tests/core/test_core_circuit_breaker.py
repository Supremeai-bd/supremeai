# tests/test_core_circuit_breaker.py
"""Tests for the core circuit breaker resilience pattern."""

import time
from unittest.mock import AsyncMock, patch

import pytest

# Issue #2250: legacy core.circuit_breaker retired — tests re-pointed to the
# canonical resilience module. `AsyncCircuitBreaker as CircuitBreaker` keeps
# every assertion byte-identical so the suite proves behavior parity of the
# ported async state machine.
from core.resilience.circuit_breaker import (
    AsyncCircuitBreaker as CircuitBreaker,
)
from core.resilience.circuit_breaker import (
    CircuitBreakerError,
    CircuitState,
    RedisCircuitBreaker,
    get_circuit,
)


async def _fail():
    async with CircuitBreaker(name="t").protect():
        raise RuntimeError("boom")


def test_initial_state_is_closed():
    cb = CircuitBreaker(name="svc")
    assert cb.state == CircuitState.CLOSED
    assert cb.stats.current_state == CircuitState.CLOSED


def test_default_parameters():
    cb = CircuitBreaker(name="svc")
    assert cb.failure_threshold == 5
    assert cb.success_threshold == 3
    assert cb.recovery_timeout == 30.0


def test_stats_initial_counts_zero():
    cb = CircuitBreaker(name="svc")
    assert cb.stats.total_requests == 0
    assert cb.stats.total_successes == 0
    assert cb.stats.total_failures == 0
    assert cb.stats.total_rejections == 0


async def test_protect_success_stays_closed():
    cb = CircuitBreaker(name="svc", failure_threshold=2, success_threshold=2)

    async with cb.protect():
        pass

    assert cb.state == CircuitState.CLOSED
    assert cb.stats.total_requests == 1
    assert cb.stats.total_successes == 1
    assert cb.stats.total_failures == 0


async def test_protect_failure_opens_circuit():
    cb = CircuitBreaker(name="svc", failure_threshold=2, success_threshold=2)

    for _ in range(2):
        with pytest.raises(RuntimeError):
            async with cb.protect():
                raise RuntimeError("boom")

    assert cb.state == CircuitState.OPEN
    assert cb.stats.total_failures == 2
    assert cb.stats.total_rejections == 0


async def test_open_circuit_rejects_and_records_rejection():
    cb = CircuitBreaker(name="svc", failure_threshold=1, recovery_timeout=30)

    with pytest.raises(RuntimeError):
        async with cb.protect():
            raise RuntimeError("boom")

    assert cb.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerError):
        async with cb.protect():
            pass

    assert cb.stats.total_rejections == 1


async def test_half_open_recovers_to_closed():
    cb = CircuitBreaker(name="svc", failure_threshold=1, success_threshold=1, recovery_timeout=30)

    with pytest.raises(RuntimeError):
        async with cb.protect():
            raise RuntimeError("boom")

    assert cb.state == CircuitState.OPEN

    # Pretend enough time has elapsed to allow a recovery attempt.
    cb._last_failure_time = time.time() - 100

    async with cb.protect():
        pass

    assert cb.state == CircuitState.CLOSED


async def test_half_open_failure_returns_to_open():
    cb = CircuitBreaker(name="svc", failure_threshold=1, success_threshold=1, recovery_timeout=30)

    with pytest.raises(RuntimeError):
        async with cb.protect():
            raise RuntimeError("boom")

    cb._last_failure_time = time.time() - 100

    with pytest.raises(RuntimeError):
        async with cb.protect():
            raise RuntimeError("boom")

    assert cb.state == CircuitState.OPEN


def test_get_recovery_time_when_not_open():
    cb = CircuitBreaker(name="svc")
    assert cb.get_recovery_time() == 0.0


def test_get_recovery_time_when_open():
    cb = CircuitBreaker(name="svc", recovery_timeout=30)
    cb._state = CircuitState.OPEN
    cb._last_failure_time = time.time() - 10
    recovery = cb.get_recovery_time()
    assert 0 < recovery <= 30


def test_reset_returns_to_closed():
    cb = CircuitBreaker(name="svc")
    cb._state = CircuitState.OPEN
    cb.reset()
    assert cb.state == CircuitState.CLOSED


def test_get_circuit_returns_breaker():
    cb = get_circuit("database")
    assert isinstance(cb, CircuitBreaker)
    assert cb.name == "database"


async def test_redis_circuit_breaker_should_attempt_closed():
    rc = RedisCircuitBreaker(name="r", failure_threshold=1)
    assert await rc.should_attempt_external() is True


async def test_redis_circuit_breaker_should_attempt_open_false():
    rc = RedisCircuitBreaker(name="r", failure_threshold=1)

    with pytest.raises(RuntimeError):
        async with rc.protect():
            raise RuntimeError("boom")

    assert rc.state == CircuitState.OPEN
    assert await rc.should_attempt_external() is False


async def test_redis_circuit_breaker_record_failure_no_redis():
    rc = RedisCircuitBreaker(name="r", failure_threshold=1)

    with patch.object(rc, "_get_redis_client", new=AsyncMock(return_value=None)):
        with pytest.raises(RuntimeError):
            async with rc.protect():
                raise RuntimeError("boom")
        await rc.record_failure()

    assert rc.state == CircuitState.OPEN


async def test_redis_circuit_breaker_record_success_no_redis():
    rc = RedisCircuitBreaker(name="r")

    with patch.object(rc, "_get_redis_client", new=AsyncMock(return_value=None)):
        async with rc.protect():
            pass
        await rc.record_success()

    assert rc.state == CircuitState.CLOSED
