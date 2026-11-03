# tests/test_core_retry_budget.py
"""Tests for the core retry budget (token-bucket) rate limiter."""

import time

import pytest

from core.retry_budget import RetryBudget, global_retry_budget


async def test_consume_with_available_tokens():
    rb = RetryBudget(max_tokens=2, refill_rate_per_sec=1.0)
    assert await rb.consume() is True
    assert rb.tokens == pytest.approx(1.0)


async def test_consume_exhaustion_returns_false():
    rb = RetryBudget(max_tokens=1, refill_rate_per_sec=0.0)
    assert await rb.consume() is True
    assert await rb.consume() is False


async def test_consume_refills_over_time():
    rb = RetryBudget(max_tokens=2, refill_rate_per_sec=1.0)
    await rb.consume()  # tokens: 2 -> 1
    rb.last_refill = time.monotonic() - 3  # simulate 3s elapsed

    assert await rb.consume() is True
    # Refill would bring it to 1 + 3 = 4, capped at 2, then -1 on consume.
    assert rb.tokens == pytest.approx(1.0)


async def test_consume_never_exceeds_max_tokens():
    rb = RetryBudget(max_tokens=2, refill_rate_per_sec=100.0)
    rb.last_refill = time.monotonic() - 100  # huge elapsed window

    assert await rb.consume() is True
    assert rb.tokens <= rb.max_tokens


async def test_global_retry_budget_instance():
    assert isinstance(global_retry_budget, RetryBudget)
    assert global_retry_budget.max_tokens == 20
