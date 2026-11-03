"""Tests for CircuitBreaker pattern.

Tests cover:
- CLOSED state: requests pass through
- OPEN state: requests fail-fast after threshold reached
- HALF_OPEN state: allows one probe after recovery timeout
- State normalization (normalize_circuit_state)
- Auto-recovery after timeout
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    normalize_circuit_state,
)


class TestCircuitBreakerStates:
    """Test the three-state FSM: CLOSED → OPEN → HALF_OPEN → CLOSED."""

    def test_starts_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30)
        assert cb.state == CircuitBreakerState.CLOSED

    def test_closed_passes_through_success(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitBreakerState.CLOSED

    def test_closed_counts_failures(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30)

        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.state == CircuitBreakerState.CLOSED  # Not yet at threshold

    def test_opens_after_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30)

        def fail_fn():
            raise ValueError("fail")

        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(fail_fn)

        assert cb.state == CircuitBreakerState.OPEN

    def test_open_fails_fast(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=30)

        def fail_fn():
            raise ValueError("fail")

        # Trip the breaker
        with pytest.raises(ValueError):
            cb.call(fail_fn)
        assert cb.state == CircuitBreakerState.OPEN

        # Next call should fail fast with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "should-not-reach")

    def test_open_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0)

        def fail_fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            cb.call(fail_fn)
        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout (0 = instant)
        time.sleep(0.01)

        # Next call should transition to HALF_OPEN
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitBreakerState.CLOSED  # Success → CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0)

        def fail_fn():
            raise ValueError("fail")

        # Trip
        with pytest.raises(ValueError):
            cb.call(fail_fn)
        assert cb.state == CircuitBreakerState.OPEN

        time.sleep(0.01)

        # Probe fails → back to OPEN
        with pytest.raises(ValueError):
            cb.call(fail_fn)
        assert cb.state == CircuitBreakerState.OPEN


class TestNormalizeCircuitState:
    """Test the normalize_circuit_state() helper for cross-implementation vocabulary."""

    def test_normalizes_string_open(self):
        assert normalize_circuit_state("open") == CircuitBreakerState.OPEN

    def test_normalizes_string_closed(self):
        assert normalize_circuit_state("closed") == CircuitBreakerState.CLOSED

    def test_normalizes_string_half_open_variants(self):
        assert normalize_circuit_state("half-open") == CircuitBreakerState.HALF_OPEN
        assert normalize_circuit_state("half_open") == CircuitBreakerState.HALF_OPEN
        assert normalize_circuit_state("HALF-OPEN") == CircuitBreakerState.HALF_OPEN

    def test_normalizes_enum(self):
        assert normalize_circuit_state(CircuitBreakerState.OPEN) == CircuitBreakerState.OPEN
        assert normalize_circuit_state(CircuitBreakerState.CLOSED) == CircuitBreakerState.CLOSED
        assert (
            normalize_circuit_state(CircuitBreakerState.HALF_OPEN) == CircuitBreakerState.HALF_OPEN
        )

    def test_unknown_returns_closed(self):
        assert normalize_circuit_state("unknown") == CircuitBreakerState.CLOSED
        assert normalize_circuit_state(None) == CircuitBreakerState.CLOSED


class TestCircuitBreakerAsync:
    """Test async call support."""

    @pytest.mark.asyncio
    async def test_async_success(self):
        cb = CircuitBreaker("test-async", failure_threshold=3, recovery_timeout=30)

        async def async_ok():
            return "async-ok"

        result = await cb.call_async(async_ok)
        assert result == "async-ok"
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_async_failure_trips(self):
        cb = CircuitBreaker("test-async", failure_threshold=2, recovery_timeout=30)

        async def async_fail():
            raise ValueError("async-fail")

        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call_async(async_fail)

        assert cb.state == CircuitBreakerState.OPEN
