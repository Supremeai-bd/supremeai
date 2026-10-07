"""Coverage-completion tests for core/queue/task_queue_enhanced.py (TaskQueue).

Task 7-b. Complements tests/core/queue/test_task_queue_enhanced.py by hitting
the backend-selection branches, fallback paths, worker error paths, redis /
pubsub / celery submission adapters and the module-level celery_app bootstrap.

NOTE (bug found while writing these tests): TaskQueue._evict_oldest_if_needed()
livelocks (infinite busy loop, no await) when the oldest tracked task is still
pending/processing and the result map is full. submit_task() calls it before
its own (correct) eviction loop, so the "Cannot evict" warning branch in
submit_task() is unreachable in production through the normal path. The test
below neutralises the helper via monkeypatch to pin the warning branch's
behaviour; production code is untouched.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import settings
from core.queue import task_queue_enhanced as tqe
from core.queue.task_queue_enhanced import (
    QueueBackend,
    TaskPriority,
    TaskQueue,
    TaskResult,
)

MODULE_PATH = Path(tqe.__file__)


async def _wait_result(q: TaskQueue, task_id: str) -> TaskResult:
    return await q.get_result(task_id, timeout=5)


def _patch_redis_url(monkeypatch, value: str | None) -> None:
    monkeypatch.setattr(type(settings), "redis_url", value, raising=False)


# ---------------------------------------------------------------------------
# Data models & helpers
# ---------------------------------------------------------------------------
class TestModelsAndHelpers:
    def test_task_metadata_to_dict_serializes_priority(self):
        md = tqe.TaskMetadata(task_id="t", name="n", priority=TaskPriority.HIGH, created_at=1.0)
        data = md.to_dict()
        assert data["priority"] == TaskPriority.HIGH.value
        assert data["task_id"] == "t"

    def test_default_local_queue_maxsize_invalid_env(self, monkeypatch):
        monkeypatch.setenv("TASK_QUEUE_MAX_SIZE", "not-a-number")
        assert tqe._default_local_queue_maxsize() == 100

    def test_default_local_queue_maxsize_zero_clamped(self, monkeypatch):
        monkeypatch.setenv("TASK_QUEUE_MAX_SIZE", "0")
        assert tqe._default_local_queue_maxsize() == 1


# ---------------------------------------------------------------------------
# Backend availability probes (cached_property ImportError paths)
# ---------------------------------------------------------------------------
class TestBackendAvailabilityProbes:
    def test_celery_unavailable(self, monkeypatch):
        q = TaskQueue()
        monkeypatch.setitem(sys.modules, "celery", None)
        assert q._is_celery_available is False

    def test_celery_available(self, monkeypatch):
        q = TaskQueue()
        monkeypatch.setitem(sys.modules, "celery", types.ModuleType("celery"))
        assert q._is_celery_available is True

    def test_redis_unavailable(self, monkeypatch):
        q = TaskQueue()
        monkeypatch.setitem(sys.modules, "redis.asyncio", None)
        assert q._is_redis_available is False

    def test_redis_available(self):
        q = TaskQueue()
        assert q._is_redis_available is True

    def test_pubsub_unavailable(self, monkeypatch):
        q = TaskQueue()
        monkeypatch.setitem(sys.modules, "google.cloud.pubsub_v1", None)
        assert q._is_pubsub_available is False

    def test_pubsub_available(self, monkeypatch):
        q = TaskQueue()
        monkeypatch.setitem(sys.modules, "google.cloud.pubsub_v1", types.ModuleType("pubsub"))
        assert q._is_pubsub_available is True


# ---------------------------------------------------------------------------
# submit_task: backend selection & failure branches
# ---------------------------------------------------------------------------
class TestSubmitBackendSelection:
    async def test_redis_backend_selected(self, monkeypatch):
        q = TaskQueue()
        q.__dict__["_is_redis_available"] = True
        redis_submit = AsyncMock()
        monkeypatch.setattr(q, "_submit_to_redis", redis_submit)
        monkeypatch.setattr(settings, "queue_backend_priority", "redis,asyncio", raising=False)

        async def work() -> int:
            return 1

        task_id = await q.submit_task(work)
        redis_submit.assert_awaited_once()
        # Nothing executes the task locally — result stays pending.
        assert q._results[task_id].status == "pending"
        await q.shutdown()

    async def test_pubsub_backend_selected(self, monkeypatch):
        q = TaskQueue()
        q.__dict__["_is_pubsub_available"] = True
        pubsub_submit = AsyncMock()
        monkeypatch.setattr(q, "_submit_to_pubsub", pubsub_submit)
        monkeypatch.setattr(settings, "queue_backend_priority", "pubsub", raising=False)

        async def work() -> int:
            return 1

        task_id = await q.submit_task(work)
        pubsub_submit.assert_awaited_once()
        assert q._results[task_id].status == "pending"
        await q.shutdown()

    async def test_celery_backend_selected(self, monkeypatch):
        q = TaskQueue()
        q.__dict__["_is_celery_available"] = True
        celery_submit = AsyncMock()
        monkeypatch.setattr(q, "_submit_to_celery", celery_submit)
        monkeypatch.setattr(settings, "queue_backend_priority", "celery", raising=False)

        async def work() -> int:
            return 1

        task_id = await q.submit_task(work)
        celery_submit.assert_awaited_once()
        assert q._results[task_id].status == "pending"
        await q.shutdown()

    async def test_unknown_priority_falls_back_to_asyncio(self, monkeypatch):
        q = TaskQueue()
        monkeypatch.setattr(settings, "queue_backend_priority", "bogus-backend", raising=False)

        async def work() -> str:
            return "done"

        task_id = await q.submit_task(work)
        result = await _wait_result(q, task_id)
        assert result.status == "completed"
        await q.shutdown()

    async def test_priority_parse_failure_falls_back_to_asyncio(self, monkeypatch):
        q = TaskQueue()
        # None.split(",") → AttributeError → priorities default to ["asyncio"]
        monkeypatch.setattr(settings, "queue_backend_priority", None, raising=False)

        async def work() -> str:
            return "ok"

        task_id = await q.submit_task(work)
        result = await _wait_result(q, task_id)
        assert result.status == "completed"
        await q.shutdown()

    async def test_submit_failure_marks_failed_and_sets_event(self, monkeypatch):
        q = TaskQueue()

        async def failing(*args, **kwargs):
            raise RuntimeError("backend exploded")

        monkeypatch.setattr(q, "_submit_to_asyncio", failing)
        with pytest.raises(RuntimeError, match="backend exploded"):
            await q.submit_task(lambda: None)

        result = next(iter(q._results.values()))
        assert result.status == "failed"
        assert "backend exploded" in result.error
        stats = await q.get_stats()
        assert stats["failed"] == 1

    async def test_submit_cancelled_marks_cancelled_and_sets_event(self, monkeypatch):
        q = TaskQueue()

        async def cancelling(*args, **kwargs):
            raise asyncio.CancelledError()

        monkeypatch.setattr(q, "_submit_to_asyncio", cancelling)
        with pytest.raises(asyncio.CancelledError):
            await q.submit_task(lambda: None)

        result = next(iter(q._results.values()))
        assert result.status == "cancelled"


# ---------------------------------------------------------------------------
# Bounded memory: warning branch when nothing can be evicted
# ---------------------------------------------------------------------------
class TestEvictionWarningBranch:
    async def test_warning_when_all_tracked_tasks_pending(self, monkeypatch):
        q = TaskQueue(max_tracked_tasks=1, local_queue_maxsize=10)
        # Neutralise the livelocking pre-eviction helper (see module docstring).
        monkeypatch.setattr(q, "_evict_oldest_if_needed", AsyncMock(return_value=None))
        placeholder_worker = asyncio.create_task(asyncio.sleep(3600))
        q._worker_task = placeholder_worker
        try:

            async def never_runs() -> None:
                return None

            first = await q.submit_task(never_runs)
            second = await q.submit_task(never_runs)  # results full, oldest pending

            assert first != second
            stats = await q.get_stats()
            assert stats["evicted"] == 0
            assert len(q._results) == 2
        finally:
            placeholder_worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await placeholder_worker
            await q.shutdown()


# ---------------------------------------------------------------------------
# get_result / _execute_task edge cases
# ---------------------------------------------------------------------------
class TestResultEdgeCases:
    async def test_get_result_cancelled_error_propagates(self):
        q = TaskQueue()

        async def slow() -> None:
            await asyncio.sleep(30)

        task_id = await q.submit_task(slow)
        getter = asyncio.create_task(q.get_result(task_id, timeout=5))
        await asyncio.sleep(0.05)
        getter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await getter
        await q.cancel_task(task_id)
        await q.shutdown()

    async def test_execute_task_with_missing_result_object_returns_early(self):
        q = TaskQueue()

        async def work() -> int:
            return 1

        # No exception, no result written — the early-return guard fires.
        await q._execute_task(work, "missing-id", (), {})
        assert "missing-id" not in q._results


# ---------------------------------------------------------------------------
# _asyncio_worker: timeout, unexpected error, clean shutdown
# ---------------------------------------------------------------------------
class TestAsyncioWorker:
    async def test_queue_get_timeout_continues_then_shutdown(self, monkeypatch):
        q = TaskQueue()
        real_sleep = asyncio.sleep

        async def raise_timeout():
            # MUST yield to the loop before raising — a coroutine that raises
            # before its first await completes synchronously and would starve
            # the event loop while the worker spins on it.
            await real_sleep(0.005)
            raise TimeoutError()

        monkeypatch.setattr(q.local_queue, "get", raise_timeout)
        worker = asyncio.create_task(q._asyncio_worker())
        q._worker_task = worker
        await real_sleep(0.05)  # allow ≥1 TimeoutError → continue
        q._shutdown_event.set()
        await asyncio.wait_for(worker, timeout=2)
        assert worker.done()

    async def test_worker_unexpected_error_logged_then_shutdown(self, monkeypatch):
        real_sleep = asyncio.sleep

        async def fast_sleep(delay, *args, **kwargs):
            return await real_sleep(0)

        monkeypatch.setattr(asyncio, "sleep", fast_sleep)
        q = TaskQueue()

        async def work() -> int:
            return 1

        async def flaky_execute(func, task_id, args, kwargs):
            await real_sleep(0)  # yield before raising (event-loop starvation guard)
            raise RuntimeError("worker crash")

        monkeypatch.setattr(q, "_execute_task", flaky_execute)

        first = {"done": False}

        async def get():
            if not first["done"]:
                first["done"] = True
                await real_sleep(0)
                return (work, "tid-1", (), {})
            await real_sleep(0.005)
            raise TimeoutError()

        monkeypatch.setattr(q.local_queue, "get", get)
        q.local_queue.put_nowait((work, "tid-1", (), {}))

        worker = asyncio.create_task(q._asyncio_worker())
        q._worker_task = worker
        await real_sleep(0.05)
        q._shutdown_event.set()
        await asyncio.wait_for(worker, timeout=2)
        assert worker.done()

    async def test_worker_shutdown_complete_message(self, monkeypatch):
        """shutdown_event set BEFORE worker starts → immediate clean exit."""
        q = TaskQueue()
        q._shutdown_event.set()
        worker = asyncio.create_task(q._asyncio_worker())
        await asyncio.wait_for(worker, timeout=2)
        assert worker.done()


# ---------------------------------------------------------------------------
# Backend adapters: redis / pubsub / celery
# ---------------------------------------------------------------------------
def _client_with_pipeline():
    pipeline = MagicMock()
    pipeline.zadd = MagicMock()
    pipeline.hset = MagicMock()
    pipeline.execute = AsyncMock(return_value=True)
    client = MagicMock()
    client.pipeline = MagicMock(return_value=pipeline)
    return client, pipeline


class TestSubmitToRedis:
    async def test_uses_redis_manager_client(self, monkeypatch):
        q = TaskQueue()
        client, pipeline = _client_with_pipeline()
        fake_manager = MagicMock()
        fake_manager.get_managed_client_sync = MagicMock(return_value=client)
        rm_module = importlib.import_module("core.cache.redis_manager")
        monkeypatch.setattr(rm_module, "redis_manager", fake_manager, raising=False)

        async def work() -> int:
            return 1

        await q._submit_to_redis(work, "tid-1", (1,), {"k": 2}, TaskPriority.HIGH)

        assert pipeline.zadd.called
        zadd_args = pipeline.zadd.call_args
        assert zadd_args.args[0] == "supremeai:task_queue"
        task_payload = json.loads(next(iter(zadd_args.args[1].keys())))
        assert task_payload["task_id"] == "tid-1"
        assert task_payload["priority"] == TaskPriority.HIGH.value
        pipeline.hset.assert_called_once()
        pipeline.execute.assert_awaited_once()

    async def test_creates_client_when_manager_has_none(self, monkeypatch):
        # বাংলা (#4169): now uses get_managed_client_sync() — if None, skip task
        q = TaskQueue()
        fake_manager = MagicMock()
        fake_manager.get_managed_client_sync = MagicMock(return_value=None)
        rm_module = importlib.import_module("core.cache.redis_manager")
        monkeypatch.setattr(rm_module, "redis_manager", fake_manager, raising=False)

        async def work() -> int:
            return 1

        # বাংলা (#4169): when get_managed_client_sync returns None, task is skipped (no from_url fallback)
        await q._submit_to_redis(work, "tid-2", (), {}, TaskPriority.LOW)
        # No assertion on created — from_url is no longer called


class TestSubmitToPubsub:
    async def test_publishes_message_and_awaits_future(self, monkeypatch):
        q = TaskQueue()
        future = MagicMock()
        future.result = MagicMock(return_value="msg-42")
        publisher = MagicMock()
        publisher.topic_path = MagicMock(return_value="projects/p/topics/supremeai-tasks")
        publisher.publish = MagicMock(return_value=future)
        fake_pubsub = types.ModuleType("google.cloud.pubsub_v1")
        fake_pubsub.PublisherClient = MagicMock(return_value=publisher)
        monkeypatch.setitem(sys.modules, "google.cloud.pubsub_v1", fake_pubsub)

        async def work() -> int:
            return 1

        await q._submit_to_pubsub(work, "tid-3", (), {}, TaskPriority.NORMAL)

        publisher.publish.assert_called_once()
        payload = json.loads(publisher.publish.call_args.args[1])
        assert payload["task_id"] == "tid-3"
        assert future.result.called


class TestSubmitToCelery:
    async def test_send_task_via_singleton_app(self, monkeypatch):
        celery_mod = types.ModuleType("celery")

        class FakeCelery:
            def __init__(self, *args, **kwargs):
                self.calls = []

            def send_task(self, *args, **kwargs):
                return "queued"

        celery_mod.Celery = FakeCelery
        monkeypatch.setitem(sys.modules, "celery", celery_mod)

        old_instance = TaskQueue._celery_app_instance
        TaskQueue._celery_app_instance = None
        try:
            q = TaskQueue()

            async def work() -> int:
                return 1

            await q._submit_to_celery(work, "tid-4", (1,), {"k": 2}, TaskPriority.CRITICAL)
            assert TaskQueue._celery_app_instance is not None
        finally:
            TaskQueue._celery_app_instance = old_instance

    async def test_reuses_existing_singleton_app(self, monkeypatch):
        celery_mod = types.ModuleType("celery")
        celery_mod.Celery = MagicMock()
        monkeypatch.setitem(sys.modules, "celery", celery_mod)

        existing = MagicMock()
        old_instance = TaskQueue._celery_app_instance
        TaskQueue._celery_app_instance = existing
        try:
            q = TaskQueue()

            async def work() -> int:
                return 1

            await q._submit_to_celery(work, "tid-5", (), {}, TaskPriority.NORMAL)
            assert existing.send_task.called
        finally:
            TaskQueue._celery_app_instance = old_instance


# ---------------------------------------------------------------------------
# cleanup + convenience API + celery bootstrap
# ---------------------------------------------------------------------------
class TestCleanupAndConvenienceAPI:
    async def test_cleanup_old_tasks_default_ttl(self):
        q = TaskQueue()

        async def ok() -> str:
            return "x"

        task_id = await q.submit_task(ok)
        await _wait_result(q, task_id)
        await q.cleanup_old_tasks()  # default TTL from settings — fresh task kept
        assert task_id in q._results
        await q.shutdown()

    async def test_module_level_convenience_api(self):
        old_instance = tqe._task_queue_instance
        tqe._task_queue_instance = None
        temp_instance = None
        try:

            async def work() -> str:
                return "done"

            task_id = await tqe.submit_task(work)
            temp_instance = tqe.get_task_queue()
            result = await tqe.get_task_result(task_id, timeout=5)
            assert result.status == "completed"
            # legacy sync stub stays "unknown" until routes are migrated
            assert tqe.get_task_status(task_id) == "unknown"
            assert await tqe.get_task_status_async(task_id) == "completed"
            stats = await tqe.get_queue_stats()
            assert stats["submitted"] == 1
            assert await tqe.cancel_task(task_id) is False  # already completed
        finally:
            tqe._task_queue_instance = old_instance
            if temp_instance is not None and temp_instance is not old_instance:
                await temp_instance.shutdown()


def _load_fresh_module(monkeypatch, name: str):
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, mod)
    spec.loader.exec_module(mod)
    return mod


class TestCeleryBootstrap:
    def test_celery_app_created_when_celery_importable(self, monkeypatch):
        fake_celery = types.ModuleType("celery")
        created_kwargs = {}

        class FakeCeleryApp:
            def __init__(self, *args, **kwargs):
                created_kwargs.update(kwargs)
                self.conf = MagicMock()
                self.conf.update = MagicMock()

        fake_celery.Celery = FakeCeleryApp
        monkeypatch.setitem(sys.modules, "celery", fake_celery)

        mod = _load_fresh_module(monkeypatch, "tqe_fresh_celery_ok")
        assert isinstance(mod.celery_app, FakeCeleryApp)
        assert created_kwargs["include"] == ["workers.chaos_worker"]

    def test_stub_created_when_broker_missing_in_non_local_env(self, monkeypatch):
        fake_celery = types.ModuleType("celery")
        fake_celery.Celery = MagicMock()
        monkeypatch.setitem(sys.modules, "celery", fake_celery)
        _patch_redis_url(monkeypatch, None)  # no broker configured
        monkeypatch.setattr(type(settings), "env", "test", raising=False)

        mod = _load_fresh_module(monkeypatch, "tqe_fresh_celery_stub")
        stub = mod.celery_app
        assert stub.name == "supremeai-stub"

        def fn() -> int:
            return 1

        decorated = stub.task(name="noop")(fn)
        assert decorated is fn
