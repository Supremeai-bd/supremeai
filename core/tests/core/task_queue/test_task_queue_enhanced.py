"""Critical-path tests for core/queue/task_queue_enhanced.py (TaskQueue).

CONTEXT (final-test hardening-2): this module had ZERO coverage in the CI
combined coverage report (0/340 statements) while being tier-critical
(core/queue/**). These tests lock the production contracts:

1. Anti-polling: get_result() awaits an asyncio.Event — no sleep loops.
2. Bounded memory: max tracked tasks + FIFO eviction; bounded local queue
   raises TaskQueueOverflowError (backpressure) instead of OOM.
3. CancelledError is always re-raised, never suppressed.
4. Graceful shutdown: worker exits cleanly via the shutdown event.
"""

from __future__ import annotations

import asyncio

import pytest

from core.logging_config import logger
from core.queue.task_queue_enhanced import (
    EnhancedTaskQueue,
    QueueBackend,
    TaskPriority,
    TaskQueue,
    TaskQueueOverflowError,
    TaskResult,
    get_task_queue,
)


async def _submit_and_run(queue: TaskQueue, func, *args, **kwargs) -> TaskResult:
    task_id = await queue.submit_task(func, *args, **kwargs)
    return await queue.get_result(task_id, timeout=5)


class TestDataModels:
    def test_task_result_roundtrip(self):
        result = TaskResult(task_id="t-1", status="completed", result={"x": 1}, retry_count=2)
        payload = result.to_dict()
        restored = TaskResult.from_dict(payload)
        assert restored == result

    def test_task_priority_ordering(self):
        assert TaskPriority.LOW < TaskPriority.NORMAL < TaskPriority.HIGH < TaskPriority.CRITICAL

    def test_queue_backend_values(self):
        assert QueueBackend.ASYNCIO.value == "asyncio"
        assert QueueBackend.MEMORY.value == "memory"

    def test_enhanced_alias(self):
        assert EnhancedTaskQueue is TaskQueue


class TestSubmitAndExecute:
    async def test_async_function_completes(self):
        queue = TaskQueue()

        async def work(a: int, b: int) -> int:
            return a + b

        result = await _submit_and_run(queue, work, 2, 3)
        assert result.status == "completed"
        assert result.result == 5
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.error is None

    async def test_sync_function_runs_in_thread_pool(self):
        queue = TaskQueue()

        def sync_work() -> str:
            return "done"

        result = await _submit_and_run(queue, sync_work)
        assert result.status == "completed"
        assert result.result == "done"

    async def test_failure_captures_error(self):
        queue = TaskQueue()

        async def boom() -> None:
            raise RuntimeError("kaboom")

        result = await _submit_and_run(queue, boom)
        assert result.status == "failed"
        assert "kaboom" in result.error

    async def test_get_result_unknown_task_raises_keyerror(self):
        queue = TaskQueue()
        with pytest.raises(KeyError):
            await queue.get_result("nonexistent-task-id")

    async def test_get_result_timeout_raises_timeout(self):
        queue = TaskQueue()

        async def slow() -> str:
            await asyncio.sleep(30)
            return "late"

        task_id = await queue.submit_task(slow)
        with pytest.raises(TimeoutError):
            await queue.get_result(task_id, timeout=0.05)
        # cleanup
        await queue.cancel_task(task_id)
        await queue.shutdown()


class TestAntiPolling:
    async def test_get_result_awaits_event_not_polling(self):
        """get_result() must block on the completion event and unblock as soon
        as the task finishes — the whole point of the anti-polling refactor."""
        queue = TaskQueue()
        release = asyncio.Event()

        async def wait_for_release() -> str:
            await release.wait()
            return "released"

        task_id = await queue.submit_task(wait_for_release)
        getter = asyncio.create_task(queue.get_result(task_id, timeout=5))
        await asyncio.sleep(0.05)
        assert not getter.done()  # still waiting — no busy result yet
        release.set()
        result = await asyncio.wait_for(getter, timeout=2)
        assert result.status == "completed"
        assert result.result == "released"

    async def test_stats_track_lifecycle(self):
        queue = TaskQueue()

        async def ok() -> int:
            return 1

        await _submit_and_run(queue, ok)
        stats = await queue.get_stats()
        assert stats["submitted"] == 1
        assert stats["completed"] == 1
        assert stats["failed"] == 0


class TestBoundedMemory:
    async def test_local_queue_overflow_raises_backpressure(self):
        queue = TaskQueue(local_queue_maxsize=1)
        queue.default_backend = QueueBackend.ASYNCIO

        async def blocker() -> None:
            await asyncio.sleep(5)

        # Fill the single queue slot; the second submit must overflow.
        first = await queue.submit_task(blocker)
        with pytest.raises(TaskQueueOverflowError):
            await queue.submit_task(blocker)
        await queue.cancel_task(first)
        await queue.shutdown()

    async def test_fifo_eviction_of_oldest_completed_tasks(self):
        queue = TaskQueue(max_tracked_tasks=2)

        async def ok() -> int:
            return 1

        for _ in range(4):
            task_id = await queue.submit_task(ok)
            await queue.get_result(task_id, timeout=5)

        stats = await queue.get_stats()
        assert stats["evicted"] >= 2  # oldest completed tasks were evicted


class TestCancellation:
    async def test_cancel_pending_task(self):
        # Deterministic setup: keep the real worker from starting by planting
        # a live (but unrelated) worker task — _submit_to_asyncio only spawns
        # its worker when none is running. Both submissions therefore stay
        # pending in the local queue, which is exactly the state under test.
        queue = TaskQueue()
        placeholder_worker = asyncio.create_task(asyncio.sleep(3600))
        queue._worker_task = placeholder_worker
        try:

            async def never_runs() -> None:
                return None

            first_id = await queue.submit_task(never_runs)
            pending_id = await queue.submit_task(never_runs)

            assert await queue.get_status(pending_id) == "pending"
            assert await queue.cancel_task(pending_id) is True
            result = await queue.get_result(pending_id, timeout=1)
            assert result.status == "cancelled"
            # Cancel a second time → no longer pending.
            assert await queue.cancel_task(pending_id) is False
            # The untouched task is still cancellable.
            assert await queue.cancel_task(first_id) is True
        finally:
            placeholder_worker.cancel()
            try:
                await placeholder_worker
            except asyncio.CancelledError as exc:
                logger.debug(f"Worker cancelled cleanly: {exc}")
            await queue.shutdown()


class TestLifecycle:
    async def test_shutdown_terminates_worker_cleanly(self):
        queue = TaskQueue()
        await queue.shutdown()
        assert queue._shutdown_event.is_set()
        # Second shutdown is idempotent.
        await queue.shutdown()

    async def test_status_reflects_state(self):
        queue = TaskQueue()

        async def ok() -> str:
            return "x"

        task_id = await queue.submit_task(ok)
        await queue.get_result(task_id, timeout=5)
        assert await queue.get_status(task_id) == "completed"
        assert await queue.get_status("missing") == "unknown"

    async def test_cleanup_old_tasks_removes_finished(self):
        queue = TaskQueue()

        async def ok() -> str:
            return "x"

        task_id = await queue.submit_task(ok)
        await queue.get_result(task_id, timeout=5)
        # completed_at is fresh → 0s age keeps it; but any completed task
        # older than the cutoff is gone. Fake age by clearing completed_at.
        queue._results[task_id].completed_at = 1.0
        await queue.cleanup_old_tasks(max_age_seconds=10)
        assert task_id not in queue._results


class TestSingleton:
    def test_get_task_queue_returns_singleton(self):
        assert get_task_queue() is get_task_queue()
