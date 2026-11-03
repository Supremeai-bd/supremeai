# tests/test_core_retry_handler.py
"""Tests for the core retry_handler decorator (sync + async, backoff, callbacks)."""

import pytest

from core.retry_handler import retry_handler, retry_with_budget


def test_sync_success_first_try():
    calls = []

    @retry_handler(max_retries=3, delay=0, backoff=1, use_jitter=False)
    def f():
        calls.append(1)
        return "ok"

    assert f() == "ok"
    assert len(calls) == 1


def test_sync_retry_then_success():
    state = {"n": 0}

    @retry_handler(max_retries=3, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False)
    def f():
        state["n"] += 1
        if state["n"] < 3:
            raise ValueError("x")
        return "ok"

    assert f() == "ok"
    assert state["n"] == 3


def test_sync_exhaust_retries_raises():
    state = {"n": 0}

    @retry_handler(max_retries=2, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False)
    def f():
        state["n"] += 1
        raise ValueError("x")

    with pytest.raises(ValueError):
        f()
    # initial attempt + 2 retries
    assert state["n"] == 3


def test_sync_non_matching_exception_propagates_immediately():
    @retry_handler(max_retries=3, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False)
    def f():
        raise KeyError("nope")

    with pytest.raises(KeyError):
        f()


def test_sync_callbacks_invoked():
    retries = []
    maxed = []

    @retry_handler(
        max_retries=2,
        delay=0,
        backoff=1,
        exceptions=(ValueError,),
        use_jitter=False,
        on_retry_callback=lambda attempt, exc: retries.append(attempt),
        on_max_retries_callback=lambda exc: maxed.append(exc),
    )
    def f():
        raise ValueError("x")

    with pytest.raises(ValueError):
        f()

    assert retries == [1, 2]
    assert len(maxed) == 1


async def test_async_success_after_retry():
    state = {"n": 0}

    @retry_handler(max_retries=3, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False)
    async def f():
        state["n"] += 1
        if state["n"] < 2:
            raise ValueError()
        return "ok"

    assert await f() == "ok"
    assert state["n"] == 2


async def test_async_exhaust_retries_raises():
    state = {"n": 0}

    @retry_handler(max_retries=1, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False)
    async def f():
        state["n"] += 1
        raise ValueError()

    with pytest.raises(ValueError):
        await f()
    assert state["n"] == 2


def test_retry_with_budget_sync_success():
    @retry_with_budget(max_retries=2, delay=0, use_jitter=False)
    def f():
        return 42

    assert f() == 42
