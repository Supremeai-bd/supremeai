"""Coverage tests for core/retry_handler.py (sync + async retry, jitter, callbacks, retry_with_budget)."""

from unittest.mock import AsyncMock

import pytest

from core.retry_handler import retry_handler, retry_with_budget


def test_sync_success_first_try(monkeypatch):
    monkeypatch.setattr("core.retry_handler.time.sleep", lambda s: None)

    @retry_handler(max_retries=3, delay=0, backoff=1, use_jitter=False)
    def f():
        return "ok"

    assert f() == "ok"


def test_sync_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("core.retry_handler.time.sleep", lambda s: None)
    state = {"n": 0}

    @retry_handler(max_retries=3, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False)
    def f():
        state["n"] += 1
        if state["n"] < 3:
            raise ValueError("x")
        return "ok"

    assert f() == "ok"
    assert state["n"] == 3


def test_sync_exhausts_retries_and_calls_callbacks(monkeypatch):
    monkeypatch.setattr("core.retry_handler.time.sleep", lambda s: None)
    retries, maxed = [], []

    @retry_handler(
        max_retries=2,
        delay=0,
        backoff=1,
        exceptions=(ValueError,),
        use_jitter=False,
        on_retry_callback=lambda a, e: retries.append(a),
        on_max_retries_callback=lambda e: maxed.append(e),
    )
    def f():
        raise ValueError("x")

    with pytest.raises(ValueError):
        f()
    assert retries == [1, 2]
    assert len(maxed) == 1


def test_sync_non_matching_exception_propagates(monkeypatch):
    monkeypatch.setattr("core.retry_handler.time.sleep", lambda s: None)

    @retry_handler(max_retries=3, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False)
    def f():
        raise KeyError("nope")

    with pytest.raises(KeyError):
        f()


def test_sync_jitter_patch_sleep_and_random(monkeypatch):
    calls = []
    monkeypatch.setattr("core.retry_handler.time.sleep", calls.append)
    # uniform(0.1, 0.3) -> lower bound 0.1
    monkeypatch.setattr("core.retry_handler.random.uniform", lambda a, b: a)

    @retry_handler(max_retries=1, delay=1.0, backoff=2.0, exceptions=(ValueError,), use_jitter=True)
    def f():
        raise ValueError("x")

    with pytest.raises(ValueError):
        f()


# ---------------------------------------------------------------------------
# async retry_handler
# ---------------------------------------------------------------------------


async def test_async_success_after_retry(monkeypatch):
    monkeypatch.setattr("core.retry_handler.asyncio.sleep", AsyncMock())
    state = {"n": 0}

    @retry_handler(max_retries=3, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False)
    async def f():
        state["n"] += 1
        if state["n"] < 2:
            raise ValueError("x")
        return "ok"

    assert await f() == "ok"
    assert state["n"] == 2


async def test_async_exhausts_retries(monkeypatch):
    monkeypatch.setattr("core.retry_handler.asyncio.sleep", AsyncMock())

    @retry_handler(max_retries=1, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False)
    async def f():
        raise ValueError("x")

    with pytest.raises(ValueError):
        await f()


async def test_async_jitter_uses_asyncio_sleep(monkeypatch):
    monkeypatch.setattr("core.retry_handler.random.uniform", lambda a, b: a)
    sleep_mock = AsyncMock()
    monkeypatch.setattr("core.retry_handler.asyncio.sleep", sleep_mock)

    @retry_handler(max_retries=1, delay=1.0, backoff=1.0, exceptions=(ValueError,), use_jitter=True)
    async def f():
        raise ValueError("x")

    with pytest.raises(ValueError):
        await f()
    sleep_mock.assert_awaited_with(1.1)


async def test_async_non_matching_exception(monkeypatch):
    monkeypatch.setattr("core.retry_handler.asyncio.sleep", AsyncMock())

    @retry_handler(max_retries=3, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False)
    async def f():
        raise KeyError("nope")

    with pytest.raises(KeyError):
        await f()


def test_retry_with_budget_sync_success(monkeypatch):
    import core.retry_budget as rb
    from core.retry_budget import RetryBudget

    fake_budget = RetryBudget()
    consumed = {"n": 0}

    async def fake_consume():
        consumed["n"] += 1
        return True

    fake_budget.consume = fake_consume
    monkeypatch.setattr(rb, "global_retry_budget", fake_budget)
    monkeypatch.setattr("core.retry_handler.time.sleep", lambda s: None)

    state = {"n": 0}

    @retry_with_budget(
        max_retries=1, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False
    )
    def f(state):
        state["n"] += 1
        if state["n"] < 2:
            raise ValueError("x")
        return "ok"

    assert f(state) == "ok"
    assert consumed["n"] == 1


def test_retry_with_budget_sync_exhausted(monkeypatch):
    import asyncio

    import core.retry_budget as rb
    from core.retry_budget import RetryBudget

    fake_budget = RetryBudget()

    async def _consume_false():
        return False

    fake_budget.consume = _consume_false
    monkeypatch.setattr(rb, "global_retry_budget", fake_budget)
    monkeypatch.setattr("core.retry_handler.time.sleep", lambda s: None)
    calls = {"n": 0}

    @retry_with_budget(
        max_retries=2, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False
    )
    def f():
        calls["n"] += 1
        raise ValueError("x")

    with pytest.raises(ValueError):
        f()
    assert calls["n"] == 1


async def test_retry_with_budget_async_success(monkeypatch):
    import core.retry_budget as rb

    fake_budget = AsyncMock(return_value=True)
    monkeypatch.setattr(rb, "global_retry_budget", fake_budget)
    monkeypatch.setattr("core.retry_handler.asyncio.sleep", AsyncMock())
    state = {"n": 0}

    @retry_with_budget(
        max_retries=1, delay=0, backoff=1, exceptions=(ValueError,), use_jitter=False
    )
    async def f():
        state["n"] += 1
        if state["n"] < 2:
            raise ValueError("x")
        return "ok"

    assert await f() == "ok"
    assert fake_budget.consume.call_count == 1
