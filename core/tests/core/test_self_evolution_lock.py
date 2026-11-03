"""Issue #1685 (CRITICAL) — self-evolution distributed lock fail-safe tests.

Old contract: `_acquire_lock()` returned True ("fail open") whenever Redis was
unreachable — every instance then evolved simultaneously → concurrent writes to
production code (corrupted deploys, last-write-wins over validated skills).

New contract (fail-closed):
1. Redis unreachable / unconfigured → False + CRITICAL log, evolution skipped
2. NX-locked by another instance → False
3. Free lock → True
4. ORPHAN lock (key present, TTL == -1, i.e. no expiry — impossible via our
   SET NX EX path) → stale-lock breaker deletes it and retries once
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.self_evolution.self_evolution_agent import SelfEvolutionAgent


def contextlib_suppress_task():
    """Suppress CancelledError/loop-end when awaiting a cancelled _loop task."""
    return contextlib.suppress(asyncio.CancelledError)


def _agent() -> SelfEvolutionAgent:
    return SelfEvolutionAgent(
        fitness_engine=MagicMock(metrics={}),
        auto_skill_creator=MagicMock(),
        interval_seconds=300,
    )


def _redis_ok(nx_result=True, ttl_value=299, retry_nx_result=True):
    redis = MagicMock()
    redis.set = AsyncMock(side_effect=[nx_result, retry_nx_result])
    redis.ttl = AsyncMock(return_value=ttl_value)
    redis.delete = AsyncMock(return_value=1)
    return redis


class TestAcquireLockFailClosed:
    async def test_redis_unreachable_fails_closed(self):
        agent = _agent()

        async def broken_redis():
            raise ConnectionError("redis down")

        agent._get_redis = broken_redis
        assert await agent._acquire_lock() is False  # was True (fail-open) — #1685

    async def test_unconfigured_redis_fails_closed(self):
        agent = _agent()
        agent._redis = None

        async def honest_error():
            raise RuntimeError("Redis URL not configured")

        agent._get_redis = honest_error
        assert await agent._acquire_lock() is False

    async def test_lock_held_by_other_instance_fails_closed(self):
        agent = _agent()
        agent._redis = _redis_ok(nx_result=False, ttl_value=120)
        assert await agent._acquire_lock() is False

    async def test_free_lock_acquired(self):
        agent = _agent()
        agent._redis = _redis_ok(nx_result=True)
        assert await agent._acquire_lock() is True

    async def test_orphan_lock_broken_and_retried(self):
        agent = _agent()
        # first NX fails (key exists), TTL == -1 (no expiry → orphan),
        # delete runs, second NX succeeds
        agent._redis = _redis_ok(nx_result=False, ttl_value=-1, retry_nx_result=True)
        assert await agent._acquire_lock() is True
        agent._redis.delete.assert_awaited_once_with("lock:self_evolution_agent")
        assert agent._redis.set.await_count == 2

    async def test_client_is_cached_not_rebuilt_per_tick(self):
        agent = _agent()
        fake = MagicMock()
        agent._redis = fake
        r = await agent._get_redis()
        assert r is fake  # same instance — no per-call client churn


class TestLoopSkipsEvolutionWithoutLock:
    async def test_tick_not_called_when_lock_denied(self, monkeypatch):
        agent = _agent()
        agent._acquire_lock = AsyncMock(return_value=False)
        agent._tick = AsyncMock()

        monkeypatch.setattr(
            "core.memory_manager.get_memory_manager",
            lambda: MagicMock(is_safe_for_heavy_task=lambda: True),
        )
        agent._running = True
        task = asyncio.create_task(agent._loop())
        await asyncio.sleep(0.2)
        agent._running = False
        task.cancel()
        # _loop() suppresses CancelledError internally (by design) — it just ends
        with contextlib_suppress_task():
            await task
        agent._tick.assert_not_awaited()  # evolution must not run without the lock
