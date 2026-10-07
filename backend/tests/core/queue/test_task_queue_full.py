"""Full-coverage tests for core/queue/task_queue.py (RedisTaskQueue + redis_configured).

Task 7-b (critical-tier queue coverage campaign).

Rules honoured here:
- ALL Redis I/O is mocked (AsyncMock / plain async functions) — no real network.
- Worker loops are kept short via instance-level IDLE_SHUTDOWN_SECONDS /
  MAX_BLPOP_TIMEOUT tuning; no sleep > 1s anywhere.
- Module-level singleton is never touched (fresh RedisTaskQueue instances only).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import settings
from core.queue import task_queue as tq_module
from core.queue.task_queue import RedisTaskQueue, redis_configured


def _patch_redis_url(monkeypatch, value: str) -> None:
    """settings.redis_url is a read-only property (secret-vault backed);
    patch it on the Settings class instead."""
    monkeypatch.setattr(type(settings), "redis_url", value, raising=False)


# ---------------------------------------------------------------------------
# redis_configured (R2-03 guard)
# ---------------------------------------------------------------------------
class TestRedisConfigured:
    def test_placeholder_urls_rejected(self, monkeypatch):
        for bad in (
            "redis://<your-redis-url>",
            "https://example.com:6379",
            "redis://localhost_placeholder/0",
        ):
            _patch_redis_url(monkeypatch, bad)
            assert redis_configured() is False, bad

    def test_empty_url_rejected(self, monkeypatch):
        _patch_redis_url(monkeypatch, "")
        monkeypatch.delenv("REDIS_URL", raising=False)
        assert redis_configured() is False

    def test_real_url_accepted(self, monkeypatch):
        _patch_redis_url(monkeypatch, "redis://real-host:6379/0")
        assert redis_configured() is True

    def test_settings_import_failure_falls_back_to_env(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.config", None)
        monkeypatch.setenv("REDIS_URL", "https://example.com")  # placeholder → rejected
        assert redis_configured() is False
        monkeypatch.setenv("REDIS_URL", "redis://env-host:6379/2")
        assert redis_configured() is True


# ---------------------------------------------------------------------------
# _get_redis
# ---------------------------------------------------------------------------
class TestGetRedis:
    async def test_creates_and_caches_client(self, monkeypatch):
        # বাংলা (#4169): task_queue now uses redis_manager.get_managed_client()
        # instead of direct redis.from_url(). Test uses mock redis_manager.
        fake_client = MagicMock(name="redis-client")

        # Mock redis_manager.get_managed_client to return fake_client
        rm_module = __import__("core.cache.redis_manager", fromlist=["redis_manager"])
        monkeypatch.setattr(
            rm_module.redis_manager, "get_managed_client",
            lambda: fake_client,  # sync mock — _get_redis awaits it but get_managed_client is async
        )
        # Need async version
        async def fake_get_managed():
            return fake_client
        monkeypatch.setattr(
            rm_module.redis_manager, "get_managed_client",
            fake_get_managed,
        )

        q = RedisTaskQueue()
        assert q.redis is None
        c1 = await q._get_redis()
        c2 = await q._get_redis()
        assert c1 is fake_client
        assert c2 is fake_client  # cached — get_managed_client called exactly once


# ---------------------------------------------------------------------------
# ensure_worker_started
# ---------------------------------------------------------------------------
class TestEnsureWorkerStarted:
    async def test_noop_when_worker_already_running(self):
        q = RedisTaskQueue()
        sentinel = asyncio.create_task(asyncio.sleep(3600), name="sentinel-worker")
        q._worker_task = sentinel
        try:
            q.ensure_worker_started()
            assert q._worker_task is sentinel
        finally:
            sentinel.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sentinel

    async def test_noop_when_redis_not_configured(self, monkeypatch):
        monkeypatch.setattr(tq_module, "redis_configured", lambda: False)
        q = RedisTaskQueue()
        q.ensure_worker_started()
        assert q._worker_task is None

    async def test_noop_without_running_loop(self, monkeypatch):
        monkeypatch.setattr(tq_module, "redis_configured", lambda: True)

        def raise_no_loop():
            raise RuntimeError("no running loop")

        monkeypatch.setattr(asyncio, "get_running_loop", raise_no_loop)
        q = RedisTaskQueue()
        q.ensure_worker_started()
        assert q._worker_task is None

    async def test_starts_worker_lazily(self, monkeypatch):
        monkeypatch.setattr(tq_module, "redis_configured", lambda: True)
        q = RedisTaskQueue()
        # Keep the worker loop fully mocked so it exits on its own idle budget.
        q._get_redis = AsyncMock(return_value=MagicMock(blpop=AsyncMock(return_value=None)))
        q.ensure_worker_started()
        assert q._worker_task is not None
        assert not q._worker_task.done()
        q._worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await q._worker_task


# ---------------------------------------------------------------------------
# enqueue
# ---------------------------------------------------------------------------
class TestEnqueue:
    async def test_rejects_without_redis_configured(self, monkeypatch):
        monkeypatch.setattr(tq_module, "redis_configured", lambda: False)
        q = RedisTaskQueue()
        task_id = await q.enqueue("email", {"a": 1}, "user-1")
        # Fail-soft: an id is still returned so callers keep working.
        assert isinstance(task_id, str) and len(task_id) == 36
        assert q._worker_task is None

    async def test_enqueues_and_starts_worker(self, monkeypatch):
        monkeypatch.setattr(tq_module, "redis_configured", lambda: True)
        q = RedisTaskQueue()
        redis = AsyncMock()
        redis.rpush = AsyncMock()
        redis.set = AsyncMock()
        q.redis = redis  # pre-seeded → _get_redis skips from_url

        task_id = await q.enqueue("email", {"x": 1}, "user-1")

        assert redis.rpush.await_count == 1
        queue_name, raw = redis.rpush.await_args.args
        assert queue_name == q.queue_name
        pushed = json.loads(raw)
        assert pushed["task_id"] == task_id
        assert pushed["task_type"] == "email"
        assert pushed["user_id"] == "user-1"
        assert pushed["status"] == "pending"

        redis.set.assert_awaited_once()
        meta_key = redis.set.await_args.args[0]
        assert meta_key == f"task:{task_id}"

        # Worker auto-started on demand.
        worker = q._worker_task
        assert worker is not None and not worker.done()
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
        q._worker_task = None


# ---------------------------------------------------------------------------
# worker_loop
# ---------------------------------------------------------------------------
class TestWorkerLoop:
    async def test_returns_immediately_when_redis_unavailable(self):
        q = RedisTaskQueue()
        q._get_redis = AsyncMock(side_effect=RuntimeError("redis down"))
        await q.worker_loop()
        assert q._worker_task is None

    async def test_processes_task_then_idle_shutdown(self):
        q = RedisTaskQueue()
        q.MAX_BLPOP_TIMEOUT = 1  # instance-level tuning (short loop)
        q.IDLE_SHUTDOWN_SECONDS = 2.5

        processed: list[dict] = []

        async def handler(data: dict) -> dict:
            processed.append(data)
            return {"ok": True}

        q.register_handler("email", handler)

        task_payload = {
            "task_id": "tid-1",
            "task_type": "email",
            "user_id": "user-1",
            "payload": {"x": 1},
            "status": "pending",
        }
        responses = iter([(q.queue_name, json.dumps(task_payload))])

        async def blpop(name, timeout=None):
            return next(responses, None)

        redis = MagicMock()
        redis.blpop = blpop
        redis.set = AsyncMock()
        q.redis = redis

        await q.worker_loop()
        # give the scheduled background _process_task a chance to finish
        await asyncio.sleep(0.1)

        assert processed and processed[0]["task_id"] == "tid-1"
        statuses = [json.loads(c.args[1])["status"] for c in redis.set.await_args_list]
        assert statuses == ["processing", "completed"]
        assert q._worker_task is None  # idle shutdown cleared the task handle

    async def test_error_backoff_then_idle_exit(self, monkeypatch):
        # Make the exponential-backoff sleep instantaneous (it starts at 1.0s).
        async def fast_sleep(delay, *args, **kwargs):
            return None

        monkeypatch.setattr(asyncio, "sleep", fast_sleep)

        q = RedisTaskQueue()
        q.MAX_BLPOP_TIMEOUT = 1
        q.IDLE_SHUTDOWN_SECONDS = 3  # error adds backoff*2=2s idle → one more poll

        attempts = {"n": 0}

        async def blpop(name, timeout=None):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("redis connection lost")
            return None

        redis = MagicMock()
        redis.blpop = blpop
        q.redis = redis

        await q.worker_loop()
        assert attempts["n"] == 2  # one error + exactly one idle poll
        assert q._worker_task is None

    async def test_blpop_timeout_counts_as_idle(self):
        q = RedisTaskQueue()
        q.MAX_BLPOP_TIMEOUT = 1
        q.IDLE_SHUTDOWN_SECONDS = 2

        calls = {"n": 0}

        async def blpop(name, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise TimeoutError()
            return None

        redis = MagicMock()
        redis.blpop = blpop
        q.redis = redis

        await q.worker_loop()
        assert q._worker_task is None

    async def test_cancelled_error_is_reraised(self):
        q = RedisTaskQueue()

        async def blpop(name, timeout=None):
            raise asyncio.CancelledError()

        redis = MagicMock()
        redis.blpop = blpop
        q.redis = redis

        with pytest.raises(asyncio.CancelledError):
            await q.worker_loop()


# ---------------------------------------------------------------------------
# _process_task
# ---------------------------------------------------------------------------
def _install_fake_pubsub(monkeypatch, publish: AsyncMock) -> MagicMock:
    # #1832: task completion now broadcasts via core.messaging.pubsub.global_pubsub
    # (live SSE dashboard_events channel) — the old websocket_agent.manager was
    # an unmounted orphan with zero possible subscribers.
    from core.messaging import pubsub as pubsub_mod

    fake_pubsub = MagicMock()
    fake_pubsub.publish = publish
    monkeypatch.setattr(pubsub_mod, "global_pubsub", fake_pubsub)
    return fake_pubsub


class TestProcessTask:
    async def test_unknown_task_type_marks_failed(self):
        q = RedisTaskQueue()
        redis = MagicMock()
        redis.set = AsyncMock()
        q.redis = redis

        await q._process_task(
            {"task_id": "t1", "task_type": "ghost", "user_id": "u", "payload": {}}
        )

        saved = json.loads(redis.set.await_args.args[1])
        assert saved["status"] == "failed"
        assert saved["error"] == "No handler"

    async def test_success_persists_and_broadcasts(self, monkeypatch):
        q = RedisTaskQueue()
        publish = AsyncMock()
        _install_fake_pubsub(monkeypatch, publish)

        async def handler(data: dict) -> dict:
            return {"done": True}

        q.register_handler("email", handler)
        redis = MagicMock()
        redis.set = AsyncMock()
        q.redis = redis

        await q._process_task(
            {"task_id": "t2", "task_type": "email", "user_id": "user-9", "payload": {}}
        )

        statuses = [json.loads(c.args[1])["status"] for c in redis.set.await_args_list]
        assert statuses == ["processing", "completed"]
        completed = json.loads(redis.set.await_args_list[-1].args[1])
        assert completed["result"] == {"done": True}

        publish.assert_awaited_once()
        args = publish.await_args.args
        assert args[0] == "dashboard_events"
        msg = args[1]
        assert msg["type"] == "task_completed"
        assert msg["task_id"] == "t2"
        assert msg["user_id"] == "user-9"
        assert msg["result"] == {"done": True}

    async def test_broadcast_failure_is_silenced(self, monkeypatch):
        q = RedisTaskQueue()
        publish = AsyncMock(side_effect=RuntimeError("pubsub down"))
        _install_fake_pubsub(monkeypatch, publish)

        async def handler(data: dict) -> str:
            return "ok"

        q.register_handler("email", handler)
        redis = MagicMock()
        redis.set = AsyncMock()
        q.redis = redis

        # Must NOT raise even though the broadcast blew up.
        await q._process_task(
            {"task_id": "t3", "task_type": "email", "user_id": "u", "payload": {}}
        )
        statuses = [json.loads(c.args[1])["status"] for c in redis.set.await_args_list]
        assert statuses == ["processing", "completed"]

    async def test_handler_failure_marks_failed(self):
        q = RedisTaskQueue()

        async def handler(data: dict) -> None:
            raise ValueError("bad payload")

        q.register_handler("email", handler)
        redis = MagicMock()
        redis.set = AsyncMock()
        q.redis = redis

        await q._process_task(
            {"task_id": "t4", "task_type": "email", "user_id": "u", "payload": {}}
        )
        saved = json.loads(redis.set.await_args.args[1])
        assert saved["status"] == "failed"
        assert "bad payload" in saved["error"]

    async def test_register_handler_overwrites(self):
        q = RedisTaskQueue()

        async def h1(data):
            return 1

        async def h2(data):
            return 2

        q.register_handler("kind", h1)
        q.register_handler("kind", h2)
        assert q._handlers["kind"] is h2
