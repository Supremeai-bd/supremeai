"""Root acceptance tests for issue #1572 — Part 3: External Agents State Manager
& Asynchronous Job API.

Covers:
* Strict state flow: QUEUED → CLAIMED → RUNNING → CHECKPOINT → VERIFYING → COMPLETED.
* Illegal transitions rejected (InvalidTransitionError).
* Durability: state survives a simulated process restart (new manager on the
  same JsonFileStore directory).
* Stale run resumption: disconnect → WAITING_FOR_CHANNEL → safe resume to RUNNING.
* Asynchronous Job API: delegate_web_agent returns INSTANTLY (non-blocking),
  get/cancel behave per contract.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import pytest
from external_agents.contracts.task_contract import (
    AgentProvider,
    TaskContract,
    TaskState,
)
from external_agents.control.job_api import ExternalAgentJobAPI
from external_agents.control.state_manager import (
    AgentStateManager,
    InMemoryStore,
    InvalidTransitionError,
    JsonFileStore,
)


@pytest.fixture()
def tmp_store(tmp_path):
    return JsonFileStore(base_dir=tmp_path / "agent-state")


def _contract(goal="ship it") -> TaskContract:
    return TaskContract(goal=goal, allowed_providers=[AgentProvider.ZCODE])


# ---------------------------------------------------------------------------
# 1. Happy-path state flow
# ---------------------------------------------------------------------------
def test_full_happy_path_transitions(tmp_store):
    sm = AgentStateManager(store=tmp_store)
    task = _contract()
    sm.create_task(task)

    assert sm.get(task.task_id).state is TaskState.QUEUED
    sm.claim(task.task_id, worker_id="zcode-1")
    sm.start(task.task_id)
    sm.checkpoint(task.task_id, {"step": 1, "note": "contracts written"})
    sm.resume_from_checkpoint(task.task_id)
    sm.checkpoint(task.task_id, {"step": 2}, note="tests added")
    sm.resume_from_checkpoint(task.task_id)
    sm.begin_verification(task.task_id)
    sm.complete(task.task_id, result={"ok": True})

    record = sm.get(task.task_id)
    assert record.state is TaskState.COMPLETED
    assert record.attempt == 1
    assert record.result == {"ok": True}
    assert len(sm.checkpoints(task.task_id)) == 2


def test_illegal_transitions_rejected(tmp_store):
    sm = AgentStateManager(store=tmp_store)
    task = _contract()
    sm.create_task(task)
    with pytest.raises(InvalidTransitionError):
        sm.complete(task.task_id)  # QUEUED → COMPLETED is illegal
    with pytest.raises(InvalidTransitionError):
        sm.begin_verification(task.task_id)  # QUEUED → VERIFYING is illegal


def test_unknown_task_raises(tmp_store):
    sm = AgentStateManager(store=tmp_store)
    with pytest.raises(KeyError):
        sm.claim("task-does-not-exist", worker_id="w")


# ---------------------------------------------------------------------------
# 2. Durability across process restarts
# ---------------------------------------------------------------------------
def test_state_persists_across_process_restart(tmp_path):
    store_dir = tmp_path / "durable"
    task = _contract("durable mission")

    # "process 1": create + advance halfway, then die
    sm1 = AgentStateManager(store=JsonFileStore(base_dir=store_dir))
    sm1.create_task(task)
    sm1.claim(task.task_id, worker_id="zcode-1")
    sm1.start(task.task_id)
    sm1.checkpoint(task.task_id, {"progress": "50%"})

    # "process 2": a fresh manager on the same directory sees everything
    sm2 = AgentStateManager(store=JsonFileStore(base_dir=store_dir))
    record = sm2.get(task.task_id)
    assert record is not None
    assert record.state is TaskState.CHECKPOINT
    assert record.worker_id == "zcode-1"
    assert sm2.checkpoints(task.task_id)[0].payload == {"progress": "50%"}

    # and it can continue the flow from where process 1 stopped
    sm2.resume_from_checkpoint(task.task_id)
    sm2.begin_verification(task.task_id)
    assert sm2.get(task.task_id).state is TaskState.VERIFYING


# ---------------------------------------------------------------------------
# 3. Stale run resumption (WAITING_FOR_CHANNEL)
# ---------------------------------------------------------------------------
def test_disconnect_parks_run_and_reconnection_resumes(tmp_store):
    sm = AgentStateManager(store=tmp_store)
    task = _contract()
    sm.create_task(task)
    sm.claim(task.task_id, "zcode-1")
    sm.start(task.task_id)
    sm.checkpoint(task.task_id, {"progress": "30%"})

    # local PC / browser disconnects mid-run
    parked = sm.mark_waiting_for_channel(task.task_id, reason="browser disconnected")
    assert parked.state is TaskState.WAITING_FOR_CHANNEL

    # reconnect → resume; the recorded checkpoints are intact
    resumed = sm.resume_from_channel(task.task_id)
    assert resumed.state is TaskState.RUNNING
    assert sm.checkpoints(task.task_id)[0].payload == {"progress": "30%"}


def test_waiting_for_channel_rejected_from_terminal_states(tmp_store):
    sm = AgentStateManager(store=tmp_store)
    task = _contract()
    sm.create_task(task)
    with pytest.raises(InvalidTransitionError):
        sm.mark_waiting_for_channel(task.task_id)  # QUEUED is not resumable


def test_failed_and_cancelled_terminal(tmp_store):
    sm = AgentStateManager(store=tmp_store)
    t1 = _contract("a")
    sm.create_task(t1)
    sm.claim(t1.task_id, "w")
    sm.fail(t1.task_id, error="boom")
    assert sm.get(t1.task_id).state is TaskState.FAILED
    with pytest.raises(InvalidTransitionError):
        sm.start(t1.task_id)

    t2 = _contract("b")
    sm.create_task(t2)
    sm.cancel(t2.task_id, reason="no longer needed")
    assert sm.get(t2.task_id).state is TaskState.CANCELLED


def test_runs_recorded(tmp_store):
    sm = AgentStateManager(store=tmp_store)
    task = _contract()
    sm.create_task(task)
    run = sm.record_run(task.task_id, worker_id="zcode-1", detail={"round": 1})
    sm.finish_run(run, status="completed")
    runs = sm.runs(task.task_id)
    assert (
        len(runs) == 1
        and runs[0].status == "completed"
        and runs[0].ended_at is not None
    )


def test_list_by_state(tmp_store):
    sm = AgentStateManager(store=tmp_store)
    t1, t2 = _contract("a"), _contract("b")
    sm.create_task(t1)
    sm.create_task(t2)
    sm.claim(t1.task_id, "w")
    queued = sm.list_by_state(TaskState.QUEUED)
    claimed = sm.list_by_state(TaskState.CLAIMED)
    assert {t.task_id for t in queued} == {t2.task_id}
    assert {t.task_id for t in claimed} == {t1.task_id}


# ---------------------------------------------------------------------------
# 4. Asynchronous Job API — instant delegation
# ---------------------------------------------------------------------------
SLOW_WORKER_DELAY = 1.5


async def slow_worker(task: TaskContract, record) -> dict | None:
    await asyncio.sleep(SLOW_WORKER_DELAY)
    return {"ok": True, "goal": task.goal}


async def failing_worker(task: TaskContract, record) -> dict | None:
    raise RuntimeError("worker exploded")


def test_delegate_returns_instantly_without_blocking():
    api = ExternalAgentJobAPI(
        state_manager=AgentStateManager(store=InMemoryStore()), worker=slow_worker
    )
    task = _contract("non-blocking delegation")

    started = time.monotonic()
    job = asyncio.run(api.delegate_web_agent(task))
    elapsed = time.monotonic() - started

    assert job.job_id.startswith("job-")
    assert job.task_id == task.task_id
    assert elapsed < 0.5, (
        f"delegate_web_agent must return instantly (took {elapsed:.2f}s)"
    )
    api.shutdown()


def test_get_job_reflects_eventual_completion():
    api = ExternalAgentJobAPI(
        state_manager=AgentStateManager(store=InMemoryStore()), worker=slow_worker
    )
    task = _contract("eventual success")

    async def scenario():
        job = await api.delegate_web_agent(task)
        early = await api.get_web_agent_job(job.job_id)
        assert early is not None
        assert early.state in {TaskState.QUEUED, TaskState.CLAIMED, TaskState.RUNNING}
        await asyncio.sleep(SLOW_WORKER_DELAY + 0.3)
        final = await api.get_web_agent_job(job.job_id)
        return job, early, final

    _, _, final = asyncio.run(scenario())
    assert final.state is TaskState.COMPLETED
    assert final.result == {"ok": True, "goal": "eventual success"}


def test_worker_failure_marks_task_failed():
    api = ExternalAgentJobAPI(
        state_manager=AgentStateManager(store=InMemoryStore()), worker=failing_worker
    )
    task = _contract("will fail")

    async def scenario():
        job = await api.delegate_web_agent(task)
        await asyncio.sleep(0.3)
        return await api.get_web_agent_job(job.job_id)

    final = asyncio.run(scenario())
    assert final.state is TaskState.FAILED
    assert "worker exploded" in final.last_error


def test_cancel_web_agent_job(tmp_store):
    sm = AgentStateManager(store=tmp_store)

    async def park_forever(task, record):
        # simulate a stuck worker: park the durable run in WAITING_FOR_CHANNEL
        sm.mark_waiting_for_channel(task.task_id, reason="stuck")
        await asyncio.sleep(30)  # would block forever if delegate wasn't async
        return None

    api = ExternalAgentJobAPI(state_manager=sm, worker=park_forever)
    task = _contract("cancellable")

    async def scenario():
        job = await api.delegate_web_agent(task)
        await asyncio.sleep(0.2)  # let the worker park the run
        cancelled = await api.cancel_web_agent_job(job.job_id)
        after = await api.get_web_agent_job(job.job_id)
        missing = await api.cancel_web_agent_job("job-nope")
        return cancelled, after, missing

    cancelled, after, missing = asyncio.run(scenario())
    assert cancelled is True
    assert after.state is TaskState.CANCELLED
    assert missing is False
    api.shutdown()


def test_get_unknown_job_returns_none():
    api = ExternalAgentJobAPI(state_manager=AgentStateManager(store=InMemoryStore()))
    assert asyncio.run(api.get_web_agent_job("job-ghost")) is None


def test_delegate_without_worker_stays_queued():
    api = ExternalAgentJobAPI(
        state_manager=AgentStateManager(store=InMemoryStore()), worker=None
    )
    task = _contract("no worker yet")

    async def scenario():
        job = await api.delegate_web_agent(task)
        return await api.get_web_agent_job(job.job_id)

    job = asyncio.run(scenario())
    assert job.state is TaskState.QUEUED
