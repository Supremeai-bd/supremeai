"""AUD-4 (P0) HITL approval state machine regression tests.

Covers the hardening of backend/models/pending_tasks.py:
- AUD-4.1 ownership/tenant binding persisted
- AUD-4.2 approval expiration (TTL)
- AUD-4.3 expired approval replay rejected
- AUD-4.4 payload tampering detected (canonical SHA-256)
- AUD-4.5 duplicate execution prevented (mark_executed)
- AUD-4.6 atomic compare-and-set transitions (no lost update)
- AUD-4.7 authoritative cancellation
"""

import uuid

import pytest

from models.pending_tasks import (
    DEFAULT_APPROVAL_TTL_SECONDS,
    ApprovalStateError,
    TaskAlreadyResolvedError,
    TaskExpiredError,
    TaskStatus,
    TaskType,
    cancel_task,
    create_pending_task,
    get_task,
    list_pending,
    mark_executed,
    update_task_status,
)


@pytest.fixture
def task_payload():
    return {"skill_name": f"t_{uuid.uuid4().hex[:8]}", "generated_code": "x = 1\n"}


def test_create_binds_owner_tenant_ttl_hash(task_payload):
    task = create_pending_task(
        TaskType.SKILL_GENERATION, task_payload, created_by="alice", tenant_id="tenant-a"
    )
    assert task.created_by == "alice"  # AUD-4.1
    assert task.tenant_id == "tenant-a"  # AUD-4.1
    assert task.expires_at is not None  # AUD-4.2
    assert task.payload_hash  # AUD-4.4
    assert len(task.payload_hash) == 64  # sha256 hex
    # default TTL ~ 24h
    assert DEFAULT_APPROVAL_TTL_SECONDS == 24 * 60 * 60


def test_replay_of_approved_task_rejected(task_payload):
    """AUD-4.3/4.5: approving an already-approved task must fail (replay guard)."""
    task = create_pending_task(TaskType.SKILL_GENERATION, task_payload, created_by="alice")
    resolved = update_task_status(task.task_id, TaskStatus.APPROVED, "admin-1")
    assert resolved is not None
    assert resolved.status == TaskStatus.APPROVED

    with pytest.raises(TaskAlreadyResolvedError):
        update_task_status(task.task_id, TaskStatus.APPROVED, "admin-2")
    with pytest.raises(TaskAlreadyResolvedError):
        update_task_status(task.task_id, TaskStatus.REJECTED, "admin-2")

    # state was not clobbered
    assert get_task(task.task_id).status == TaskStatus.APPROVED
    assert get_task(task.task_id).resolved_by == "admin-1"


def test_expired_approval_cannot_be_decided(task_payload):
    """AUD-4.2/4.3: expired approvals are rejected with TaskExpiredError."""
    task = create_pending_task(
        TaskType.SKILL_GENERATION, task_payload, created_by="alice", ttl_seconds=-10
    )
    with pytest.raises(TaskExpiredError):
        update_task_status(task.task_id, TaskStatus.APPROVED, "admin")
    # and it does not show up in the pending list anymore
    assert all(t.task_id != task.task_id for t in list_pending())


def test_payload_tampering_detected(task_payload):
    """AUD-4.4: mutating the stored payload breaks the integrity hash."""
    task = create_pending_task(TaskType.SKILL_GENERATION, task_payload, created_by="alice")

    # Simulate a DB-level tamper: rewrite payload without recomputing the hash.
    from models import pending_tasks as pt

    conn = pt._get_conn()
    conn.execute(
        "UPDATE pending_tasks SET payload = ? WHERE task_id = ?",
        ('{"skill_name": "evil", "generated_code": "import os"}', task.task_id),
    )
    conn.commit()
    conn.close()

    with pytest.raises(Exception) as excinfo:
        update_task_status(task.task_id, TaskStatus.APPROVED, "admin")
    assert "integrity" in str(excinfo.value).lower() or "hash" in str(excinfo.value).lower()
    # the task remains PENDING (decision did not go through)
    assert get_task(task.task_id).status == TaskStatus.PENDING


def test_supplied_hash_mismatch_rejected(task_payload):
    task = create_pending_task(TaskType.SKILL_GENERATION, task_payload, created_by="alice")
    with pytest.raises(Exception):
        update_task_status(
            task.task_id,
            TaskStatus.APPROVED,
            "admin",
            expected_payload_hash="0" * 64,
        )


def test_duplicate_execution_guard(task_payload):
    """AUD-4.5: EXECUTED can only be reached once from APPROVED."""
    task = create_pending_task(TaskType.SKILL_GENERATION, task_payload, created_by="alice")
    update_task_status(task.task_id, TaskStatus.APPROVED, "admin")

    done = mark_executed(task.task_id, "worker-1")
    assert done.status == TaskStatus.EXECUTED

    with pytest.raises(TaskAlreadyResolvedError):
        mark_executed(task.task_id, "worker-2")

    # approving again after execution is a replay → rejected
    with pytest.raises(TaskAlreadyResolvedError):
        update_task_status(task.task_id, TaskStatus.APPROVED, "admin")


def test_cannot_transition_directly_to_executed_or_pending(task_payload):
    task = create_pending_task(TaskType.SKILL_GENERATION, task_payload, created_by="alice")
    with pytest.raises(ApprovalStateError):
        update_task_status(task.task_id, TaskStatus.EXECUTED, "admin")
    with pytest.raises(ApprovalStateError):
        update_task_status(task.task_id, TaskStatus.PENDING, "admin")


def test_cancellation_is_authoritative(task_payload):
    """AUD-4.7: cancel works on PENDING, and a cancelled task cannot be approved."""
    task = create_pending_task(TaskType.SKILL_GENERATION, task_payload, created_by="alice")
    cancelled = cancel_task(task.task_id, "admin", reason="superseded")
    assert cancelled.status == TaskStatus.CANCELLED

    with pytest.raises(TaskAlreadyResolvedError):
        update_task_status(task.task_id, TaskStatus.APPROVED, "admin")


def test_concurrent_decisions_single_winner(task_payload):
    """AUD-4.6: two 'concurrent' decision attempts → exactly one wins."""
    task = create_pending_task(TaskType.SKILL_GENERATION, task_payload, created_by="alice")

    # First attempt takes the row out of PENDING via the CAS update.
    first = update_task_status(task.task_id, TaskStatus.APPROVED, "admin-1")
    assert first.status == TaskStatus.APPROVED
    # Second attempt arrives "simultaneously" — must be rejected.
    with pytest.raises(TaskAlreadyResolvedError):
        update_task_status(task.task_id, TaskStatus.REJECTED, "admin-2")


def test_cross_tenant_decision_rejected(task_payload):
    """#481: the CAS transition is tenant-scoped — a foreign tenant's decision loses."""
    task = create_pending_task(
        TaskType.SKILL_GENERATION, task_payload, created_by="alice", tenant_id="tenant-a"
    )
    with pytest.raises(TaskAlreadyResolvedError):
        update_task_status(task.task_id, TaskStatus.APPROVED, "admin-2", tenant_id="tenant-b")
    # fail-closed: the record is still decidable by its owning tenant
    assert get_task(task.task_id).status == TaskStatus.PENDING
    resolved = update_task_status(
        task.task_id, TaskStatus.APPROVED, "admin-1", tenant_id="tenant-a"
    )
    assert resolved.status == TaskStatus.APPROVED


def test_unknown_task_returns_none():
    assert update_task_status("no-such-task", TaskStatus.APPROVED, "admin") is None


def test_hash_is_canonical_and_stable():
    """AUD-4.4: hash independent of key order."""
    from models.pending_tasks import compute_payload_hash

    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert compute_payload_hash(a) == compute_payload_hash(b)
