"""Tests for core/zero_cost_architecture/zero_cost_patch_phase1_4.py — Round A.

Scope (Phase 1 queue subsystem + config + module utilities):
- ZeroCostConfig / get_zero_cost_config (env-driven defaults + singleton)
- TaskPriority / TaskStatus / QueuedTask (priority ordering)
- InProcessAsyncQueue (enqueue/backpressure/worker/retry/cancel/metrics/status)
- QueueMetrics (durations, percentiles, success rate, trim)
- the four queue exceptions
- utilities: generate_correlation_id, sanitize_for_logging,
  measure_coroutine_performance, resilient_execute, CircuitBreakerOpenError

Round B (next): UpstashRedisClient, AdaptiveCircuitBreaker,
PerformanceLearningEngine, ZeroCostOrchestrator, lifespan_manager.

CI-safe by construction (g50b): the only external I/O in this scope lives in
Round B classes; every sleep that makes retry/backoff slow is patched at the
module's own seam (asyncio.sleep) and restored by monkeypatch.
"""

from __future__ import annotations

import asyncio
import re
import time

import pytest

import core.zero_cost_architecture.zero_cost_patch_phase1_4 as zc
from core.zero_cost_architecture.zero_cost_patch_phase1_4 import (
    AdaptiveCircuitBreakerState,
    CircuitBreakerOpenError,
    InProcessAsyncQueue,
    QueuedTask,
    QueueFullError,
    QueueMetrics,
    TaskCancelledError,
    TaskFailedError,
    TaskPriority,
    TaskStatus,
    TaskTimeoutError,
    ZeroCostConfig,
    generate_correlation_id,
    get_zero_cost_config,
    measure_coroutine_performance,
    resilient_execute,
    sanitize_for_logging,
)


def small_config(**over) -> ZeroCostConfig:
    base = dict(
        QUEUE_MAX_CONCURRENT_TASKS=2,
        QUEUE_TASK_TIMEOUT_SECONDS=5.0,
        QUEUE_MAX_QUEUE_SIZE=100,
        QUEUE_PRIORITY_LEVELS=5,
        QUEUE_BACKPRESSURE_THRESHOLD=0.8,
        GRACEFUL_SHUTDOWN_TIMEOUT=1.0,
    )
    base.update(over)
    return ZeroCostConfig(**base)


def make_task(coro_func=None, priority: TaskPriority = TaskPriority.NORMAL, **kw) -> QueuedTask:
    async def default_coro():
        return "ok"

    return QueuedTask(
        priority=priority,
        created_at=time.monotonic(),
        task_id=kw.pop("task_id", "t1"),
        coro_func=coro_func or default_coro,
        **kw,
    )


# ───────────────────────── Configuration layer ─────────────────────────


def test_config_defaults_all_phases():
    cfg = ZeroCostConfig()
    assert cfg.QUEUE_MAX_CONCURRENT_TASKS == 5
    assert cfg.QUEUE_TASK_TIMEOUT_SECONDS == 300.0
    assert cfg.QUEUE_PRIORITY_LEVELS == 5
    assert cfg.QUEUE_MAX_QUEUE_SIZE == 100
    assert cfg.QUEUE_BACKPRESSURE_THRESHOLD == 0.8
    assert cfg.UPSTASH_REDIS_URL is None and cfg.UPSTASH_REDIS_TOKEN is None
    assert cfg.REDIS_CACHE_TTL_SECONDS == 3600
    assert cfg.REDIS_COORDINATION_PREFIX == "supremeai:zca:"
    assert cfg.RATE_LIMIT_REDIS_CALLS_PER_DAY == 10000
    assert cfg.CIRCUIT_BREAKER_FAILURE_THRESHOLD == 5
    assert cfg.CIRCUIT_BREAKER_COOLDOWN_SECONDS == 30.0
    assert cfg.CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS == 3
    assert cfg.CIRCUIT_BREAKER_ADAPTIVE_ENABLED is True
    assert cfg.CIRCUIT_BREAKER_MIN_THRESHOLD == 2
    assert cfg.CIRCUIT_BREAKER_MAX_THRESHOLD == 20
    assert cfg.LEARNING_ENABLED is True
    assert cfg.LEARNING_SAMPLE_WINDOW == 100
    assert cfg.LEARNING_CONFIDENCE_THRESHOLD == 0.8
    assert cfg.LEARNING_DECAY_FACTOR == 0.95
    assert cfg.LEARNING_AUTO_TUNING_INTERVAL == 300
    assert cfg.SELF_HEALING_ENABLED is True
    assert cfg.OBSERVABILITY_DETAILED is False
    assert cfg.GRACEFUL_SHUTDOWN_TIMEOUT == 30.0


def test_config_env_driven_overrides(monkeypatch):
    monkeypatch.setenv("ZERO_COST_MAX_CONCURRENT", "7")
    monkeypatch.setenv("ZERO_COST_TASK_TIMEOUT", "12.5")
    monkeypatch.setenv("UPSTASH_DAILY_LIMIT", "500")
    monkeypatch.setenv("CB_ADAPTIVE", "false")
    monkeypatch.setenv("LEARNING_ENABLED", "false")
    monkeypatch.setenv("OBSERVABILITY_DETAILED", "true")
    monkeypatch.setenv("REDIS_KEY_PREFIX", "custom:prefix:")
    cfg = ZeroCostConfig()
    assert cfg.QUEUE_MAX_CONCURRENT_TASKS == 7
    assert cfg.QUEUE_TASK_TIMEOUT_SECONDS == 12.5
    assert cfg.RATE_LIMIT_REDIS_CALLS_PER_DAY == 500
    assert cfg.CIRCUIT_BREAKER_ADAPTIVE_ENABLED is False
    assert cfg.LEARNING_ENABLED is False
    assert cfg.OBSERVABILITY_DETAILED is True
    assert cfg.REDIS_COORDINATION_PREFIX == "custom:prefix:"


def test_config_singleton(monkeypatch):
    monkeypatch.setattr(zc, "_zero_cost_config", None)
    cfg = get_zero_cost_config()
    assert isinstance(cfg, ZeroCostConfig)
    assert get_zero_cost_config() is cfg  # cached singleton arm


def test_config_ignores_extra_fields():
    cfg = ZeroCostConfig(UNKNOWN_FIELD=123)  # extra="ignore"
    assert cfg.QUEUE_MAX_QUEUE_SIZE == 100


# ───────────────────────── Enums + QueuedTask ─────────────────────────


def test_priority_levels_ordered():
    values = [p.value for p in TaskPriority]
    assert values == [0, 1, 2, 3, 4]
    assert [p.name for p in TaskPriority] == [
        "CRITICAL",
        "HIGH",
        "NORMAL",
        "LOW",
        "DEFERRED",
    ]


def test_status_lifecycle_values():
    assert {s.value for s in TaskStatus} == {
        "pending",
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
        "timeout",
    }


def test_queuedtask_orders_by_priority_only():
    """Heapq ordering works via the (priority.value, created_at, task) tuple;
    the dataclass's own order=True comparison is broken across DIFFERENT
    priorities because TaskPriority is a plain (non-IntEnum) Enum — a
    documented owner quirk (direct task<task comparison raises TypeError)."""

    async def coro():
        return None

    critical = QueuedTask(
        priority=TaskPriority.CRITICAL, created_at=1.0, task_id="c", coro_func=coro
    )
    normal = QueuedTask(priority=TaskPriority.NORMAL, created_at=2.0, task_id="n", coro_func=coro)
    same_a = QueuedTask(priority=TaskPriority.LOW, created_at=1.0, task_id="a", coro_func=coro)
    same_b = QueuedTask(priority=TaskPriority.LOW, created_at=9.0, task_id="b", coro_func=coro)
    # The mechanism the queue actually relies on (tuple comparison):
    assert (TaskPriority.CRITICAL.value, 1.0, critical) < (TaskPriority.NORMAL.value, 2.0, normal)
    # Same priority → dataclass compare is equality-only, no crash:
    assert not (same_a < same_b) and not (same_b < same_a)
    # Owner quirk: direct cross-priority comparison crashes (documented only):
    with pytest.raises(TypeError):
        _ = critical < normal


# ───────────────────────── QueueMetrics ─────────────────────────


def test_metrics_initial_state():
    m = QueueMetrics()
    assert m.tasks_enqueued == 0 and m.tasks_started == 0
    assert m.avg_duration == 0.0 and m.p95_duration == 0.0
    assert m.success_rate == 1.0  # zero total → 1.0 arm
    d = m.to_dict()
    assert d["tasks_enqueued"] == 0 and d["success_rate"] == 1.0
    assert d["avg_duration_s"] == 0.0 and d["p95_duration_s"] == 0.0


def test_metrics_avg_and_p95_small_sample():
    m = QueueMetrics()
    for d in (1.0, 2.0, 3.0):
        m.record_execution_duration(d)
    assert m.avg_duration == pytest.approx(2.0)
    assert m.p95_duration == pytest.approx(3.0)  # idx = int(3*0.95) = 2


def test_metrics_p95_indexing():
    m = QueueMetrics()
    for i in range(100):
        m.record_execution_duration(float(i))
    assert m.p95_duration == pytest.approx(95.0)  # idx = int(100*0.95) = 95


def test_metrics_duration_trim_keeps_half():
    m = QueueMetrics()
    for i in range(1001):
        m.record_execution_duration(float(i))
    assert len(m._durations) == 500  # trimmed to max//2
    assert m._durations[-1] == 1000.0


def test_metrics_success_rate_and_rounding():
    m = QueueMetrics()
    m.tasks_completed = 3
    m.tasks_failed = 1
    assert m.success_rate == pytest.approx(0.75)
    m.record_execution_duration(1.23456)
    d = m.to_dict()
    assert d["success_rate"] == 0.75
    assert d["avg_duration_s"] == 1.235 and d["p95_duration_s"] == 1.235


# ───────────────────────── Queue init / registry / status ─────────────────────────


def test_queue_init_shape():
    q = InProcessAsyncQueue(small_config())
    assert set(q._queues) == set(TaskPriority)
    assert all(queue.maxsize == 20 for queue in q._queues.values())  # 100//5
    assert q._semaphore._value == 2
    assert q._task_registry == {} and q._running_count == 0
    assert q._worker_task is None
    assert q.get_metrics()["registered_tasks"] == 0


def test_get_metrics_shape():
    q = InProcessAsyncQueue(small_config())
    m = q.get_metrics()
    assert set(m) == {
        "tasks_enqueued",
        "tasks_started",
        "tasks_completed",
        "tasks_failed",
        "tasks_cancelled",
        "tasks_timed_out",
        "tasks_retried",
        "tasks_rejected",
        "success_rate",
        "avg_duration_s",
        "p95_duration_s",
        "queues",
        "active_tasks",
        "running_count",
        "registered_tasks",
        "is_shutdown_requested",
    }
    assert set(m["queues"]) == {p.name for p in TaskPriority}
    assert m["queues"]["CRITICAL"]["maxsize"] == 20
    assert m["is_shutdown_requested"] is False


def test_get_status_unknown_returns_none():
    assert InProcessAsyncQueue(small_config()).get_status("nope") is None


def test_get_status_known_task_clean():
    q = InProcessAsyncQueue(small_config())
    task = make_task(metadata={"src": "test"})
    q._task_registry[task.task_id] = task
    s = q.get_status("t1")
    assert s["task_id"] == "t1"
    assert s["status"] == "pending"
    assert s["priority"] == "NORMAL"
    assert s["has_error"] is False and s["error_type"] is None
    assert s["metadata"] == {"src": "test"}
    assert s["retries"] == 0 and s["max_retries"] == 2


def test_get_status_with_error():
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    task.error = ValueError("boom")
    q._task_registry[task.task_id] = task
    s = q.get_status("t1")
    assert s["has_error"] is True and s["error_type"] == "ValueError"


# ───────────────────────── enqueue / backpressure ─────────────────────────


async def test_enqueue_custom_and_auto_ids():
    q = InProcessAsyncQueue(small_config())
    tid = await q.enqueue(make_task().coro_func, task_id="custom-1")
    assert tid == "custom-1"
    auto = await q.enqueue(make_task().coro_func)
    assert auto != "custom-1" and len(auto) == 36  # uuid4


async def test_enqueue_registers_marks_queued_and_counts():
    q = InProcessAsyncQueue(small_config())

    async def work():
        return 1

    tid = await q.enqueue(work, priority=TaskPriority.HIGH, metadata={"k": "v"})
    task = q._task_registry[tid]
    assert task.status == TaskStatus.QUEUED
    assert task.priority == TaskPriority.HIGH
    assert q._queues[TaskPriority.HIGH].qsize() == 1
    assert q._metrics.tasks_enqueued == 1
    assert q.get_metrics()["registered_tasks"] == 1


async def test_enqueue_rejects_when_full_and_keeps_registry_entry():
    q = InProcessAsyncQueue(small_config(QUEUE_MAX_QUEUE_SIZE=5))

    async def work():
        return 1

    await q.enqueue(work, task_id="first")
    with pytest.raises(QueueFullError, match="at capacity"):
        await q.enqueue(work, task_id="second")  # per-queue maxsize = 5//5 = 1
    assert q._metrics.tasks_rejected == 1
    # Owner-code quirk (documented, not patched): registry entry is created
    # BEFORE the put_nowait, so a rejected task stays registered as PENDING.
    assert q._task_registry["second"].status == TaskStatus.PENDING


async def test_enqueue_registers_callback():
    q = InProcessAsyncQueue(small_config())

    async def work():
        return 1

    async def cb(task):
        pass

    tid = await q.enqueue(work, callback=cb)
    assert cb in q._completion_callbacks[tid]


async def test_backpressure_no_wait_below_threshold():
    q = InProcessAsyncQueue(small_config())
    await q._check_backpressure()  # empty queues → ratio 0 → no sleep arm


async def test_backpressure_sleeps_at_threshold(monkeypatch):
    q = InProcessAsyncQueue(small_config(QUEUE_BACKPRESSURE_THRESHOLD=0.1))
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(zc.asyncio, "sleep", fake_sleep)

    async def work():
        return 1

    for _ in range(10):  # 10/100 = 0.1 → below arm on first 10
        await q.enqueue(work)
    assert slept == []
    await q.enqueue(work)  # 11th: ratio 0.1 ≥ 0.1 → backpressure arm
    assert len(slept) == 1
    assert slept[0] == pytest.approx(min(0.1 * 0.5, 2.0))


# ───────────────────────── get_result ─────────────────────────


async def test_get_result_unknown_task_raises():
    q = InProcessAsyncQueue(small_config())
    with pytest.raises(KeyError):
        await q.get_result("ghost")


async def test_get_result_completed_returns_value():
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    task.status = TaskStatus.COMPLETED
    task.result = "value"
    q._task_registry["t1"] = task
    assert await q.get_result("t1") == "value"


async def test_get_result_failed_raises_with_cause():
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    task.status = TaskStatus.FAILED
    task.error = ValueError("boom")
    q._task_registry["t1"] = task
    with pytest.raises(TaskFailedError, match="boom") as exc_info:
        await q.get_result("t1")
    assert isinstance(exc_info.value.__cause__, ValueError)


async def test_get_result_cancelled_raises():
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    task.status = TaskStatus.CANCELLED
    q._task_registry["t1"] = task
    with pytest.raises(TaskCancelledError):
        await q.get_result("t1")


async def test_get_result_timeout_status_without_error():
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    task.status = TaskStatus.TIMEOUT
    task.error = None
    q._task_registry["t1"] = task
    with pytest.raises(TaskTimeoutError, match="timed out"):
        await q.get_result("t1")


async def test_get_result_poll_timeout_on_pending_task():
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    task.status = TaskStatus.RUNNING  # never becomes terminal
    q._task_registry["t1"] = task
    with pytest.raises(TaskTimeoutError, match="did not complete within 0.15"):
        await q.get_result("t1", timeout=0.15)


# ───────────────────────── cancel ─────────────────────────


async def test_cancel_unknown_task_false():
    q = InProcessAsyncQueue(small_config())
    assert await q.cancel("ghost") is False


@pytest.mark.parametrize(
    "terminal", [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
)
async def test_cancel_terminal_task_false(terminal):
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    task.status = terminal
    q._task_registry["t1"] = task
    assert await q.cancel("t1") is False


async def test_cancel_queued_task():
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    task.status = TaskStatus.QUEUED
    q._task_registry["t1"] = task
    assert await q.cancel("t1") is True
    assert task.status == TaskStatus.CANCELLED
    assert q._metrics.tasks_cancelled == 1


async def test_cancel_running_task_cancels_async_task():
    q = InProcessAsyncQueue(small_config())

    async def sleeper():
        await asyncio.sleep(5)

    task = make_task(coro_func=sleeper)
    task.status = TaskStatus.RUNNING
    q._task_registry["t1"] = task
    dummy = asyncio.create_task(sleeper())
    q._active_tasks["t1"] = dummy
    assert await q.cancel("t1") is True
    await asyncio.sleep(0.01)  # let cancellation settle
    assert dummy.cancelled()
    assert task.status == TaskStatus.CANCELLED


# ───────────────────────── worker integration ─────────────────────────


async def test_worker_executes_task_end_to_end():
    q = InProcessAsyncQueue(small_config())
    await q.start()
    tid = await q.enqueue(make_task().coro_func)
    result = await q.get_result(tid, timeout=5)
    assert result == "ok"
    task = q._task_registry[tid]
    assert task.status == TaskStatus.COMPLETED
    assert task.started_at is not None and task.completed_at is not None
    assert q._metrics.tasks_started == 1 and q._metrics.tasks_completed == 1
    assert q.get_status(tid)["status"] == "completed"
    await q.stop()


async def test_worker_respects_priority_order():
    q = InProcessAsyncQueue(small_config(QUEUE_MAX_CONCURRENT_TASKS=1))
    order: list[str] = []

    async def work(name):
        order.append(name)
        return name

    await q.enqueue(work, "normal-first", priority=TaskPriority.NORMAL, task_id="normal-first")
    await q.enqueue(
        work, "critical-second", priority=TaskPriority.CRITICAL, task_id="critical-second"
    )
    await q.start()
    await q.get_result("critical-second", timeout=5)
    assert order == ["critical-second", "normal-first"]
    await q.stop()


async def test_start_twice_keeps_same_worker():
    q = InProcessAsyncQueue(small_config())
    await q.start()
    first = q._worker_task
    await q.start()  # already-running arm
    assert q._worker_task is first
    await q.stop()


async def test_worker_survives_permanent_failure():
    q = InProcessAsyncQueue(small_config())

    async def broken():
        raise RuntimeError("kaput")

    tid = await q.enqueue(broken, max_retries=0)
    done: list[QueuedTask] = []

    async def on_done(task):
        done.append(task)

    q._completion_callbacks[tid].append(on_done)
    await q.start()
    with pytest.raises(TaskFailedError, match="kaput"):
        await q.get_result(tid, timeout=5)
    assert q._metrics.tasks_failed == 1
    # Worker still healthy — a follow-up task completes
    tid2 = await q.enqueue(make_task().coro_func)
    assert await q.get_result(tid2, timeout=5) == "ok"
    assert done and done[0].task_id == tid  # permanent-fail callback invoked
    await q.stop()


async def test_worker_loop_continues_after_internal_error(monkeypatch):
    q = InProcessAsyncQueue(small_config())

    async def boom(task):
        raise RuntimeError("internal")

    monkeypatch.setattr(q, "_execute_task", boom)
    await q.enqueue(make_task().coro_func)
    await q.start()
    await asyncio.sleep(0.3)  # worker hits the error, logs, keeps looping
    await q.stop()
    assert q._worker_task.done()
    assert q._worker_task.cancelled() is False  # exited via shutdown, not cancel


async def test_stop_without_worker_sets_shutdown():
    q = InProcessAsyncQueue(small_config())
    await q.stop()
    assert q.get_metrics()["is_shutdown_requested"] is True
    assert q._worker_task is None


async def test_stop_timeout_force_cancels_worker(monkeypatch):
    q = InProcessAsyncQueue(small_config())

    async def hang():
        await asyncio.sleep(100)

    monkeypatch.setattr(q, "_get_next_task", hang)
    await q.start()
    await q.stop(timeout=0.05)  # wait_for times out → force-cancel arm
    assert q._worker_task.done()
    # Owner behavior (documented): _worker_loop catches its own CancelledError
    # (worker-loop handler) and breaks, so the task ends NORMALLY, not cancelled.
    assert q._worker_task.cancelled() is False


async def test_stop_with_already_cancelled_worker_silences_await():
    q = InProcessAsyncQueue(small_config())

    async def sleeper():
        await asyncio.sleep(100)

    ghost = asyncio.create_task(sleeper())
    await asyncio.sleep(0)
    ghost.cancel()
    with pytest.raises(asyncio.CancelledError):
        await ghost  # bare coroutine → propagates (no internal handler)
    q._worker_task = ghost
    await q.stop(timeout=0.05)  # shield raises CancelledError → silenced-await arm
    assert q.get_metrics()["is_shutdown_requested"] is True


async def test_stop_cancels_active_tasks_and_marks_them():
    q = InProcessAsyncQueue(small_config())

    async def sleeper():
        await asyncio.sleep(100)

    task = make_task(coro_func=sleeper)
    task.status = TaskStatus.RUNNING
    q._task_registry["t1"] = task
    active = asyncio.create_task(sleeper())
    q._active_tasks["t1"] = active
    await q.stop()  # active-task cancellation block
    await asyncio.sleep(0.01)
    assert active.cancelled()
    assert task.status == TaskStatus.CANCELLED
    assert q._active_tasks == {}


async def test_stop_cancels_orphan_active_task_without_registry_entry():
    """Active task whose id is absent from the registry — cancel still runs,
    the status-lookup arm is skipped (owner arc 339->... false arm)."""
    q = InProcessAsyncQueue(small_config())

    async def sleeper():
        await asyncio.sleep(100)

    orphan = asyncio.create_task(sleeper())
    q._active_tasks["ghost"] = orphan  # deliberately NOT in _task_registry
    await q.stop()
    await asyncio.sleep(0.01)
    assert orphan.cancelled()
    assert q._active_tasks == {}


async def test_cancel_running_task_with_finished_async_entry():
    """cancel() when the RUNNING task's async entry is already done — skips the
    inner await arm (481->490) and still marks the task cancelled."""
    q = InProcessAsyncQueue(small_config())

    async def quick():
        return 1

    task = make_task(coro_func=quick)
    task.status = TaskStatus.RUNNING
    q._task_registry["t1"] = task
    finished = asyncio.create_task(quick())
    await finished  # done before cancel arrives
    q._active_tasks["t1"] = finished
    assert await q.cancel("t1") is True
    assert task.status == TaskStatus.CANCELLED
    assert q._metrics.tasks_cancelled == 1


async def test_worker_loop_cancelled_error_handler_breaks():
    q = InProcessAsyncQueue(small_config())
    await q.start()
    await asyncio.sleep(0.05)  # worker inside its idle poll
    q._worker_task.cancel()
    await q._worker_task  # worker-loop handler catches → "Worker loop cancelled" → break
    assert q._worker_task.done() and not q._worker_task.cancelled()
    await q.stop()


# ───────────────────────── _execute_task direct ─────────────────────────


async def test_execute_task_success_records_everything():
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    q._task_registry["t1"] = task
    await q._execute_task(task)
    assert task.status == TaskStatus.COMPLETED
    assert task.result == "ok"
    assert q._metrics.tasks_started == 1 and q._metrics.tasks_completed == 1
    assert len(q._metrics._durations) == 1
    assert q._running_count == 0  # finally decrement
    assert task.task_id not in q._active_tasks  # finally cleanup


async def test_execute_task_timeout_then_permanent_fail():
    q = InProcessAsyncQueue(small_config())

    async def slow():
        await asyncio.sleep(1)

    task = make_task(coro_func=slow, max_retries=0)
    task.timeout_seconds = 0.05
    q._task_registry["t1"] = task
    await q._execute_task(task)
    assert q._metrics.tasks_timed_out == 1
    assert task.status == TaskStatus.FAILED  # retry-or-fail with max_retries=0
    assert isinstance(task.error, TaskTimeoutError)


async def test_execute_task_cancelled_midway():
    q = InProcessAsyncQueue(small_config())

    async def slow():
        await asyncio.sleep(5)

    task = make_task(coro_func=slow)
    q._task_registry["t1"] = task
    runner = asyncio.create_task(q._execute_task(task))
    await asyncio.sleep(0.05)  # reach RUNNING
    runner.cancel()
    with pytest.raises(asyncio.CancelledError):
        await runner
    assert task.status == TaskStatus.CANCELLED
    assert q._metrics.tasks_cancelled == 1
    assert q._running_count == 0 and task.task_id not in q._active_tasks


async def test_execute_task_retry_requeues_then_second_attempt_succeeds(monkeypatch):
    q = InProcessAsyncQueue(small_config())
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(zc.asyncio, "sleep", fake_sleep)
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("first attempt fails")
        return "recovered"

    task = make_task(coro_func=flaky, max_retries=1)
    q._task_registry["t1"] = task
    await q._execute_task(task)  # attempt 1 fails → retry path
    assert task.status == TaskStatus.QUEUED
    assert task.retries == 1
    assert q._metrics.tasks_retried == 1
    assert slept == [2.0]  # exponential backoff 2**1
    assert q._queues[TaskPriority.NORMAL].qsize() == 1  # re-enqueued
    await q._execute_task(task)  # attempt 2 (worker would re-pick)
    assert task.status == TaskStatus.COMPLETED
    assert task.result == "recovered"
    assert calls["n"] == 2


# ───────────────────────── _handle_retry_or_fail direct ─────────────────────────


async def test_retry_requeues_with_exponential_backoff(monkeypatch):
    q = InProcessAsyncQueue(small_config())
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(zc.asyncio, "sleep", fake_sleep)
    task = make_task(max_retries=2)
    task.retries = 1
    await q._handle_retry_or_fail(task)
    assert task.retries == 2 and task.status == TaskStatus.QUEUED
    assert slept == [4.0]  # 2**2, capped at 10
    assert q._metrics.tasks_retried == 1


async def test_retry_backoff_capped_at_ten(monkeypatch):
    q = InProcessAsyncQueue(small_config())
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(zc.asyncio, "sleep", fake_sleep)
    task = make_task(max_retries=5)
    task.retries = 4
    await q._handle_retry_or_fail(task)
    assert slept == [10.0]  # min(2**5, 10.0)


async def test_retry_queue_full_marks_failed():
    q = InProcessAsyncQueue(small_config(QUEUE_MAX_QUEUE_SIZE=5))
    task = make_task(max_retries=2)
    # Pre-fill the task's own priority queue (maxsize 5//5 = 1)
    filler = make_task(task_id="filler")
    q._queues[TaskPriority.NORMAL].put_nowait((TaskPriority.NORMAL.value, 0.0, filler))
    await q._handle_retry_or_fail(task)
    assert task.status == TaskStatus.FAILED
    assert q._metrics.tasks_retried == 0


async def test_permanent_fail_sets_timestamp_and_invokes_async_callback():
    q = InProcessAsyncQueue(small_config())
    task = make_task(max_retries=1)
    task.retries = 1
    seen: list[QueuedTask] = []

    async def cb(t):
        seen.append(t)

    q._completion_callbacks["t1"].append(cb)
    await q._handle_retry_or_fail(task)
    assert task.status == TaskStatus.FAILED
    assert task.completed_at is not None
    assert seen == [task]
    assert "t1" not in q._completion_callbacks  # popped


# ───────────────────────── _invoke_callbacks direct ─────────────────────────


async def test_invoke_callbacks_sync_and_async():
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    q._task_registry["t1"] = task
    sync_seen: list[QueuedTask] = []
    async_seen: list[QueuedTask] = []

    def sync_cb(t):
        sync_seen.append(t)

    async def async_cb(t):
        async_seen.append(t)

    q._completion_callbacks["t1"].extend([sync_cb, async_cb])
    await q._invoke_callbacks(task)
    assert sync_seen == [task] and async_seen == [task]
    assert "t1" not in q._completion_callbacks


async def test_invoke_callback_error_contained():
    q = InProcessAsyncQueue(small_config())
    task = make_task()
    q._task_registry["t1"] = task

    def bad_cb(t):
        raise RuntimeError("cb exploded")

    after: list[QueuedTask] = []

    def good_cb(t):
        after.append(t)

    q._completion_callbacks["t1"].extend([bad_cb, good_cb])
    await q._invoke_callbacks(task)  # no propagation
    assert after == [task]  # second callback still ran


# ───────────────────────── _get_next_task ─────────────────────────


async def test_get_next_task_empty_queues_returns_none():
    q = InProcessAsyncQueue(small_config())
    assert await q._get_next_task() is None


async def test_get_next_task_highest_priority_first():
    q = InProcessAsyncQueue(small_config())
    low = make_task(priority=TaskPriority.LOW, task_id="low")
    critical = make_task(priority=TaskPriority.CRITICAL, task_id="critical")
    q._queues[TaskPriority.LOW].put_nowait((TaskPriority.LOW.value, 0.0, low))
    q._queues[TaskPriority.CRITICAL].put_nowait((TaskPriority.CRITICAL.value, 0.0, critical))
    got = await q._get_next_task()
    assert got.task_id == "critical"


async def test_get_next_task_queueempty_race_continues():
    q = InProcessAsyncQueue(small_config())

    class RacyQueue:
        def empty(self):
            return False

        def get_nowait(self):
            raise asyncio.QueueEmpty()

    q._queues[TaskPriority.CRITICAL] = RacyQueue()
    assert await q._get_next_task() is None  # racy CRITICAL → continue → rest empty


# ───────────────────────── Utilities ─────────────────────────


def test_generate_correlation_id_format():
    cid = generate_correlation_id()
    assert re.fullmatch(r"[0-9a-f]{12}-\d{13}", cid), cid
    assert generate_correlation_id() != cid


def test_sanitize_passthrough():
    assert sanitize_for_logging("hello world") == "hello world"
    assert sanitize_for_logging(42) == "42"


def test_sanitize_truncates_long_data():
    out = sanitize_for_logging("x" * 300, max_length=200)
    assert out == "x" * 200 + "..."
    assert len(out) == 203


def test_sanitize_redacts_sensitive_patterns():
    text = "config token: abc123 and api_key=xyz789 PASSWORD: hunter2 secret=q1w2 api-key: k-9"
    out = sanitize_for_logging(text)
    assert "abc123" not in out and "xyz789" not in out
    assert "hunter2" not in out and "q1w2" not in out and "k-9" not in out
    assert out.count("[REDACTED]") == 5


async def test_measure_coroutine_performance_returns_result_and_duration():
    async def work(a, b):
        await asyncio.sleep(0.01)
        return a + b

    result, duration = await measure_coroutine_performance(work, 40, b=2)
    assert result == 42
    assert duration >= 0.0


def test_circuit_breaker_open_error_carries_context():
    err = CircuitBreakerOpenError("llm_api", AdaptiveCircuitBreakerState.OPEN)
    assert err.name == "llm_api"
    assert err.state == AdaptiveCircuitBreakerState.OPEN
    assert "llm_api" in str(err) and "open" in str(err)
    assert isinstance(err, RuntimeError)


async def test_resilient_execute_decorator_wires_orchestrator(monkeypatch):
    captured: dict = {}

    class FakeOrchestrator:
        async def execute_with_resilience(self, **kwargs):
            captured.update(kwargs)
            return "resilient-result"

    monkeypatch.setattr(zc, "get_orchestrator", lambda: FakeOrchestrator())

    @resilient_execute(circuit_breaker="llm", priority=TaskPriority.HIGH, fallback=None)
    async def call_llm(prompt: str) -> str:
        return prompt

    assert call_llm.__name__ == "call_llm"  # functools.wraps
    result = await call_llm("hi", extra=1)
    assert result == "resilient-result"
    assert captured["circuit_breaker"] == "llm"
    assert captured["priority"] == TaskPriority.HIGH
    assert captured["args"] == ("hi",)
    assert captured["kwargs"] == {"extra": 1}
    assert captured["coro_func"].__name__ == "call_llm"
