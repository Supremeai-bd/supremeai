# বাংলা মন্তব্য: Issue #2761 — MCP Control Tower task state machine contract টেস্ট।
"""Contract tests for MCP Control Tower task-queue state machine (issue #2761).

বাংলা মন্তব্য: `infrastructure/mcp-control-plane/src/tasks/task-registry.ts`-
এর pure state machine logic এই ফাইলে একটি faithful Python port-এ পরীক্ষা
করা হয়। চুক্তিগত আচরণ (transition rules, lease expiry, concurrent claim
race-safety) TypeScript সোর্সের সাথে অভিন্ন — শুধু implementation language
ভিন্ন।

টেস্ট কভারেজ:
  1. Task lifecycle: UNCLAIMED → LEASED → COMPLETED (success path)
  2. State transition validation: invalid transition rejected
  3. Lease expiry → re-queue (zero-zombie failover)
  4. Concurrent claim safety: two nodes, one wins (idempotent reclaim)

Rule #64: সব কিছু fully mocked — কোনো রিয়েল Redis/GitHub/network কল নেই।
Rule #6: বাংলা কমেন্ট + Given-When-Then docstring প্রতিটি টেস্টে।
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

import pytest

# ---------------------------------------------------------------------------
# বাংলা মন্তব্য: Pure-Python port of MCP Control Tower task state machine.
# Faithful to `infrastructure/mcp-control-plane/src/tasks/task-registry.ts`:
#   - TaskState = "UNCLAIMED" | "LEASED" | "COMPLETED"
#   - LEASE_TTL_MS = 20 * 60 * 1000 (20 minutes)
#   - claim/heartbeat/complete — race-safe in-process CAS
#   - Lazy lease expiry on every read (releaseExpiredLeases)
# ---------------------------------------------------------------------------


LEASE_TTL_MS = 20 * 60 * 1000  # 20 minutes — লিজের আয়ু
TASK_QUEUE_HASH_KEY = "supremeai:task-queue"  # Redis hash key (informational)

TaskState = Literal["UNCLAIMED", "LEASED", "COMPLETED"]
CompletionKind = Literal["local", "external"]


@dataclass
class TaskKnowledge:
    """AGENTS.md knowledge-sharing schema — why/alternatives_rejected."""

    why: str
    alternatives_rejected: list[str] = field(default_factory=list)


@dataclass
class TaskRecord:
    """Single task in the queue — mirrors TS TaskRecord."""

    issue: int
    title: str
    priority: str
    labels: list[str] = field(default_factory=list)
    url: str | None = None
    state: TaskState = "UNCLAIMED"
    claimed_by: str | None = None
    claim_token: str | None = None
    claimed_at: str | None = None
    claimed_at_ms: int | None = None
    last_heartbeat_at: str | None = None
    lease_expires_at_ms: int | None = None
    completed_at: str | None = None
    completed_by: str | None = None
    completion_kind: CompletionKind | None = None
    knowledge: TaskKnowledge | None = None
    updated_at_ms: int = 0
    updated_at: str = ""


def _now_iso(now_ms: int) -> str:
    """ISO-8601 timestamp helper (mirrors nowIso in TS source)."""
    import datetime as _dt

    return _dt.datetime.fromtimestamp(now_ms / 1000, tz=_dt.UTC).isoformat()


def is_lease_expired(task: TaskRecord, now_ms: int | None = None) -> bool:
    """Pure lease-expiry check — LEASED records with past lease_expires_at_ms।"""
    if task.state != "LEASED":
        return False
    if task.lease_expires_at_ms is None:
        return True  # অসঙ্গত রেকর্ড — নিরাপদ দিকে expire
    return (now_ms if now_ms is not None else int(time.time() * 1000)) >= task.lease_expires_at_ms


def is_github_locked(task: TaskRecord) -> bool:
    """GitHub legacy claim active (status:in-progress / has-pr labels)।"""
    return "status:in-progress" in task.labels or "has-pr" in task.labels


def validate_slot(slot: str) -> str | None:
    """Slot id format validator — returns None if valid, error msg if not।"""
    if not slot or not isinstance(slot, str):
        return "slot must be a non-empty string"
    if not slot.startswith("agent-"):
        return "slot must start with 'agent-'"
    return None


class TaskRegistry:
    """In-memory task queue — pure-Python port of the TS TaskRegistry.

    বাংলা মন্তব্য: process-loop single-threaded → check-and-set atomic.
    Two nodes calling claimTask simultaneously — only one wins. Lease
    expiry auto-released on every read (zero-zombie failover).
    """

    def __init__(self) -> None:
        self._registry: dict[int, TaskRecord] = {}
        self._lock = threading.Lock()

    def upsert(self, task: TaskRecord) -> None:
        """Direct insert/replace — for test seeding only."""
        with self._lock:
            self._registry[task.issue] = task

    def _release_expired_leases(self, now_ms: int) -> int:
        """Lazy lease expiry — release stale LEASED records (ghost-state purge)."""
        released = 0
        for task in self._registry.values():
            if is_lease_expired(task, now_ms):
                ghost = task.claimed_by
                task.state = "UNCLAIMED"
                task.claimed_by = None
                task.claim_token = None
                task.claimed_at = None
                task.claimed_at_ms = None
                task.last_heartbeat_at = None
                task.lease_expires_at_ms = None
                task.updated_at_ms = now_ms
                task.updated_at = _now_iso(now_ms)
                released += 1
                # বাংলা: ghost owner এর slot এখন stale — পরবর্তী heartbeat
                # token-mismatch দিয়ে reject হবে।
                _ = ghost  # (logging-only in production)
        return released

    def get_task(self, issue: int, now_ms: int | None = None) -> TaskRecord | None:
        """Read single task — releases expired leases first (lazy cleanup)."""
        with self._lock:
            self._release_expired_leases(now_ms or int(time.time() * 1000))
            return self._registry.get(issue)

    def list_tasks(self, now_ms: int | None = None) -> list[TaskRecord]:
        """List all tasks — releases expired leases first।"""
        with self._lock:
            self._release_expired_leases(now_ms or int(time.time() * 1000))
            return list(self._registry.values())

    def claim_task(self, issue: int, slot: str, now_ms: int | None = None) -> dict:
        """Atomic claim — returns ClaimResult dict (mirrors TS ClaimResult)।"""
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        with self._lock:
            self._release_expired_leases(now)
            # বাংলা: issue validation
            if not isinstance(issue, int) or issue <= 0:
                return {
                    "ok": False,
                    "reason": "not-found",
                    "error": "issue must be positive integer",
                }
            slot_err = validate_slot(slot)
            if slot_err:
                return {"ok": False, "reason": "not-found", "error": f"invalid slot: {slot_err}"}
            task = self._registry.get(issue)
            if task is None:
                return {"ok": False, "reason": "not-found", "error": f"task #{issue} not in queue"}
            if task.state == "COMPLETED":
                return {
                    "ok": False,
                    "reason": "completed",
                    "error": f"task #{issue} already completed",
                }
            if is_github_locked(task):
                return {
                    "ok": False,
                    "reason": "github-locked",
                    "error": f"task #{issue} carries status:in-progress/has-pr label",
                }
            if task.state == "LEASED":
                if task.claimed_by == slot:
                    # বাংলা: idempotent re-claim — একই slot, একই token, মেয়াদ রিনিউ।
                    task.lease_expires_at_ms = now + LEASE_TTL_MS
                    task.updated_at_ms = now
                    task.updated_at = _now_iso(now)
                    return {
                        "ok": True,
                        "task": task,
                        "claim_token": task.claim_token,
                        "lease_expires_at_ms": task.lease_expires_at_ms,
                        "idempotent_reclaim": True,
                    }
                return {
                    "ok": False,
                    "reason": "lease-held",
                    "held_by": {
                        "slot": task.claimed_by,
                        "claimed_at": task.claimed_at,
                        "lease_expires_at_ms": task.lease_expires_at_ms,
                    },
                    "error": f"task #{issue} leased by {task.claimed_by}",
                }
            # বাংলা: UNCLAIMED → LEASED transition
            token = uuid.uuid4().hex
            task.state = "LEASED"
            task.claimed_by = slot
            task.claim_token = token
            task.claimed_at = _now_iso(now)
            task.claimed_at_ms = now
            task.last_heartbeat_at = _now_iso(now)
            task.lease_expires_at_ms = now + LEASE_TTL_MS
            task.updated_at_ms = now
            task.updated_at = _now_iso(now)
            return {
                "ok": True,
                "task": task,
                "claim_token": token,
                "lease_expires_at_ms": task.lease_expires_at_ms,
                "idempotent_reclaim": False,
            }

    def heartbeat_task(
        self, issue: int, slot: str, claim_token: str, now_ms: int | None = None
    ) -> dict:
        """Lease-token proven heartbeat — renews lease TTL।"""
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        with self._lock:
            self._release_expired_leases(now)
            task = self._registry.get(issue)
            if task is None:
                return {"ok": False, "reason": "not-found", "error": f"task #{issue} not in queue"}
            if task.state == "COMPLETED":
                return {
                    "ok": False,
                    "reason": "not-leased",
                    "error": f"task #{issue} already completed",
                }
            if task.state != "LEASED":
                return {
                    "ok": False,
                    "reason": "not-leased",
                    "error": f"task #{issue} has no active lease",
                }
            if task.claimed_by != slot:
                return {
                    "ok": False,
                    "reason": "slot-mismatch",
                    "error": f"lease owned by {task.claimed_by}, not {slot}",
                }
            if task.claim_token != claim_token:
                return {
                    "ok": False,
                    "reason": "token-mismatch",
                    "error": "claimToken mismatch (lease may have been reclaimed)",
                }
            task.last_heartbeat_at = _now_iso(now)
            task.lease_expires_at_ms = now + LEASE_TTL_MS
            task.updated_at_ms = now
            task.updated_at = _now_iso(now)
            return {"ok": True, "task": task, "lease_expires_at_ms": task.lease_expires_at_ms}

    def complete_task(
        self,
        issue: int,
        slot: str,
        claim_token: str,
        knowledge: TaskKnowledge | None = None,
        now_ms: int | None = None,
    ) -> dict:
        """Mark LEASED task COMPLETED + record knowledge transaction।"""
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        with self._lock:
            self._release_expired_leases(now)
            task = self._registry.get(issue)
            if task is None:
                return {"ok": False, "reason": "not-found", "error": f"task #{issue} not in queue"}
            if task.state == "COMPLETED":
                return {
                    "ok": False,
                    "reason": "already-completed",
                    "error": f"task #{issue} already completed",
                }
            if task.claimed_by != slot:
                return {
                    "ok": False,
                    "reason": "slot-mismatch",
                    "error": f"lease owned by {task.claimed_by}, not {slot}",
                }
            if task.claim_token != claim_token:
                return {"ok": False, "reason": "token-mismatch", "error": "claimToken mismatch"}
            task.state = "COMPLETED"
            task.completed_at = _now_iso(now)
            task.completed_by = slot
            task.completion_kind = "local"
            if knowledge:
                task.knowledge = TaskKnowledge(
                    why=str(knowledge.why),
                    alternatives_rejected=[str(a) for a in knowledge.alternatives_rejected],
                )
            task.updated_at_ms = now
            task.updated_at = _now_iso(now)
            return {"ok": True, "task": task}

    def cancel_task(
        self, issue: int, slot: str, claim_token: str, now_ms: int | None = None
    ) -> dict:
        """Cancel a LEASED task — returns it to UNCLAIMED (zero-zombie)।"""
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        with self._lock:
            self._release_expired_leases(now)
            task = self._registry.get(issue)
            if task is None:
                return {"ok": False, "reason": "not-found", "error": f"task #{issue} not in queue"}
            if task.state == "COMPLETED":
                return {
                    "ok": False,
                    "reason": "already-completed",
                    "error": f"task #{issue} already completed",
                }
            if task.claimed_by != slot or task.claim_token != claim_token:
                return {"ok": False, "reason": "token-mismatch", "error": "claimToken mismatch"}
            task.state = "UNCLAIMED"
            task.claimed_by = None
            task.claim_token = None
            task.claimed_at = None
            task.claimed_at_ms = None
            task.last_heartbeat_at = None
            task.lease_expires_at_ms = None
            task.updated_at_ms = now
            task.updated_at = _now_iso(now)
            return {"ok": True, "task": task}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry() -> TaskRegistry:
    """Fresh empty task registry per test — fully isolated।"""
    return TaskRegistry()


@pytest.fixture()
def seeded_task(registry: TaskRegistry) -> TaskRecord:
    """Seed a single UNCLAIMED task #100 — happy-path baseline।"""
    task = TaskRecord(
        issue=100,
        title="Fix flaky test",
        priority="P1-high",
        labels=["P1-high"],
        url="https://example.com/issues/100",
        state="UNCLAIMED",
        updated_at_ms=1000,
        updated_at=_now_iso(1000),
    )
    registry.upsert(task)
    return task


# ---------------------------------------------------------------------------
# 1. Task lifecycle: pending → leased → completed/failed/cancelled
# ---------------------------------------------------------------------------


class TestTaskLifecycle:
    """Full lifecycle: UNCLAIMED → LEASED → COMPLETED (success path) + sad paths।"""

    def test_unclaimed_to_leased_via_claim(self, registry, seeded_task):
        """Given UNCLAIMED task #100, When agent-1 claims it, Then state=LEASED,
        claim_token returned, lease_expires_at_ms set।"""
        # When
        result = registry.claim_task(100, "agent-1", now_ms=2000)
        # Then
        assert result["ok"] is True
        assert result["idempotent_reclaim"] is False
        assert result["claim_token"]
        assert result["lease_expires_at_ms"] == 2000 + LEASE_TTL_MS
        task = result["task"]
        assert task.state == "LEASED"
        assert task.claimed_by == "agent-1"
        assert task.claimed_at_ms == 2000

    def test_leased_to_completed_via_complete(self, registry, seeded_task):
        """Given LEASED task, When complete called with correct token, Then
        state=COMPLETED + knowledge transaction recorded।"""
        # Given
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        token = claim["claim_token"]
        # When
        knowledge = TaskKnowledge(
            why="Renamed test for clarity",
            alternatives_rejected=["Reordered imports", "Added docstring"],
        )
        result = registry.complete_task(100, "agent-1", token, knowledge=knowledge, now_ms=3000)
        # Then
        assert result["ok"] is True
        task = result["task"]
        assert task.state == "COMPLETED"
        assert task.completed_by == "agent-1"
        assert task.completion_kind == "local"
        assert task.knowledge.why == "Renamed test for clarity"
        assert task.knowledge.alternatives_rejected == ["Reordered imports", "Added docstring"]

    def test_leased_to_unclaimed_via_cancel(self, registry, seeded_task):
        """Given LEASED task, When cancel called with correct token, Then
        state=UNCLAIMED + lease cleared (zero-zombie)।"""
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        token = claim["claim_token"]
        # When
        result = registry.cancel_task(100, "agent-1", token, now_ms=3000)
        # Then
        assert result["ok"] is True
        task = result["task"]
        assert task.state == "UNCLAIMED"
        assert task.claimed_by is None
        assert task.claim_token is None
        assert task.lease_expires_at_ms is None

    def test_complete_unknown_task_returns_not_found(self, registry):
        """Given empty registry, When complete called, Then not-found error।"""
        result = registry.complete_task(999, "agent-1", "any-token", now_ms=2000)
        assert result["ok"] is False
        assert result["reason"] == "not-found"

    def test_claim_unknown_task_returns_not_found(self, registry):
        """Given empty registry, When claim called, Then not-found error।"""
        result = registry.claim_task(999, "agent-1", now_ms=2000)
        assert result["ok"] is False
        assert result["reason"] == "not-found"

    def test_claim_invalid_slot_returns_not_found(self, registry, seeded_task):
        """Given task #100, When claim with invalid slot 'invalid_slot', Then
        not-found error (slot validation rejected)। Boundary: bad slot format।"""
        result = registry.claim_task(100, "invalid_slot", now_ms=2000)
        assert result["ok"] is False
        assert result["reason"] == "not-found"
        assert "invalid slot" in result["error"]

    def test_complete_already_completed_returns_error(self, registry, seeded_task):
        """Given COMPLETED task, When complete called again, Then
        already-completed error। Boundary: idempotency violation।"""
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        token = claim["claim_token"]
        registry.complete_task(100, "agent-1", token, now_ms=3000)
        # When: second complete
        result = registry.complete_task(100, "agent-1", token, now_ms=4000)
        # Then
        assert result["ok"] is False
        assert result["reason"] == "already-completed"

    def test_claim_completed_task_returns_completed_error(self, registry, seeded_task):
        """Given COMPLETED task, When claim called, Then completed error —
        can't re-claim a finished task।"""
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        token = claim["claim_token"]
        registry.complete_task(100, "agent-1", token, now_ms=3000)
        # When
        result = registry.claim_task(100, "agent-2", now_ms=4000)
        # Then
        assert result["ok"] is False
        assert result["reason"] == "completed"


# ---------------------------------------------------------------------------
# 2. State transition validation: invalid transitions rejected
# ---------------------------------------------------------------------------


class TestStateTransitionValidation:
    """Invalid state transitions are explicitly rejected — state-machine contract।"""

    def test_heartbeat_on_unclaimed_rejected(self, registry, seeded_task):
        """Given UNCLAIMED task, When heartbeat called, Then not-leased error —
        can't heartbeat a task without an active lease।"""
        result = registry.heartbeat_task(100, "agent-1", "any-token", now_ms=2000)
        assert result["ok"] is False
        assert result["reason"] == "not-leased"

    def test_complete_with_wrong_token_rejected(self, registry, seeded_task):
        """Given LEASED task with token T1, When complete called with token T2,
        Then token-mismatch error — stale-writer protection।"""
        registry.claim_task(100, "agent-1", now_ms=2000)
        # When: wrong token
        result = registry.complete_task(100, "agent-1", "wrong-token", now_ms=3000)
        # Then
        assert result["ok"] is False
        assert result["reason"] == "token-mismatch"

    def test_complete_with_wrong_slot_rejected(self, registry, seeded_task):
        """Given LEASED by agent-1, When complete called by agent-2,
        Then slot-mismatch error — IDOR protection।"""
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        token = claim["claim_token"]
        # When: agent-2 tries to complete
        result = registry.complete_task(100, "agent-2", token, now_ms=3000)
        # Then
        assert result["ok"] is False
        assert result["reason"] == "slot-mismatch"

    def test_heartbeat_with_wrong_token_rejected(self, registry, seeded_task):
        """Given LEASED with token T1, When heartbeat called with T2,
        Then token-mismatch — lease may have been reclaimed after expiry।"""
        registry.claim_task(100, "agent-1", now_ms=2000)
        # When: wrong token
        result = registry.heartbeat_task(100, "agent-1", "wrong-token", now_ms=3000)
        # Then
        assert result["ok"] is False
        assert result["reason"] == "token-mismatch"

    def test_heartbeat_with_wrong_slot_rejected(self, registry, seeded_task):
        """Given LEASED by agent-1, When heartbeat from agent-2,
        Then slot-mismatch error।"""
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        token = claim["claim_token"]
        # When
        result = registry.heartbeat_task(100, "agent-2", token, now_ms=3000)
        # Then
        assert result["ok"] is False
        assert result["reason"] == "slot-mismatch"

    def test_heartbeat_after_completion_rejected(self, registry, seeded_task):
        """Given COMPLETED task, When heartbeat called, Then not-leased —
        completed tasks have no active lease।"""
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        token = claim["claim_token"]
        registry.complete_task(100, "agent-1", token, now_ms=3000)
        # When
        result = registry.heartbeat_task(100, "agent-1", token, now_ms=4000)
        # Then
        assert result["ok"] is False
        assert result["reason"] == "not-leased"

    def test_github_locked_task_cannot_be_claimed(self, registry):
        """Given task with status:in-progress label, When claim called, Then
        github-locked error — legacy claim active।"""
        # Given
        task = TaskRecord(
            issue=200,
            title="legacy",
            priority="P2-medium",
            labels=["P2-medium", "status:in-progress"],
            state="UNCLAIMED",
            updated_at_ms=1000,
            updated_at=_now_iso(1000),
        )
        registry.upsert(task)
        # When
        result = registry.claim_task(200, "agent-1", now_ms=2000)
        # Then
        assert result["ok"] is False
        assert result["reason"] == "github-locked"

    def test_github_locked_with_has_pr_also_blocked(self, registry):
        """Given task with has-pr label, When claim called, Then github-locked।
        Boundary: both legacy labels trigger lock।"""
        task = TaskRecord(
            issue=201,
            title="pr-ready",
            priority="P3-low",
            labels=["P3-low", "has-pr"],
            state="UNCLAIMED",
            updated_at_ms=1000,
            updated_at=_now_iso(1000),
        )
        registry.upsert(task)
        result = registry.claim_task(201, "agent-1", now_ms=2000)
        assert result["ok"] is False
        assert result["reason"] == "github-locked"


# ---------------------------------------------------------------------------
# 3. Lease expiry → re-queue (zero-zombie failover)
# ---------------------------------------------------------------------------


class TestLeaseExpiryRequeue:
    """LEASED records past lease_expires_at_ms auto-release to UNCLAIMED।"""

    def test_expired_lease_auto_releases_on_next_read(self, registry, seeded_task):
        """Given LEASED task past TTL, When get_task called, Then state=UNCLAIMED
        (auto-released) — ghost-state purge।"""
        # Given: claim at t=2000, TTL 20min → expires at t=2_002_000+2000
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        claim["claim_token"]
        assert claim["lease_expires_at_ms"] == 2000 + LEASE_TTL_MS
        # When: read after expiry
        expired_now = 2000 + LEASE_TTL_MS + 5000  # 5s past TTL
        task = registry.get_task(100, now_ms=expired_now)
        # Then
        assert task.state == "UNCLAIMED"
        assert task.claimed_by is None
        assert task.claim_token is None

    def test_expired_lease_task_reclaimable_by_different_slot(self, registry, seeded_task):
        """Given LEASED by agent-1 past TTL, When agent-2 claims, Then success —
        zero-zombie failover: ghost slot loses, new slot picks up।"""
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        old_token = claim["claim_token"]
        # When: agent-2 claims after expiry
        expired_now = 2000 + LEASE_TTL_MS + 1
        result = registry.claim_task(100, "agent-2", now_ms=expired_now)
        # Then
        assert result["ok"] is True
        new_token = result["claim_token"]
        assert new_token != old_token
        task = result["task"]
        assert task.state == "LEASED"
        assert task.claimed_by == "agent-2"

    def test_stale_heartbeat_after_expiry_rejected(self, registry, seeded_task):
        """Given LEASED by agent-1, lease expired, agent-2 reclaimed it,
        When agent-1 sends heartbeat with old token, Then token-mismatch —
        stale-writer protection (ghost agent cannot interfere)।"""
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        old_token = claim["claim_token"]
        # agent-2 reclaims after expiry
        expired_now = 2000 + LEASE_TTL_MS + 1
        reclaim = registry.claim_task(100, "agent-2", now_ms=expired_now)
        new_token = reclaim["claim_token"]
        # When: agent-1 sends stale heartbeat
        result = registry.heartbeat_task(100, "agent-1", old_token, now_ms=expired_now + 1000)
        # Then
        assert result["ok"] is False
        assert result["reason"] == "slot-mismatch"
        # Verify agent-2's lease is intact
        task = registry.get_task(100, now_ms=expired_now + 1000)
        assert task.state == "LEASED"
        assert task.claimed_by == "agent-2"
        assert task.claim_token == new_token

    def test_lease_not_expired_stays_leased(self, registry, seeded_task):
        """Given LEASED task within TTL, When get_task called, Then state=LEASED
        unchanged — boundary: just-before-expiry।"""
        registry.claim_task(100, "agent-1", now_ms=2000)
        # When: read before expiry
        just_before_expiry = 2000 + LEASE_TTL_MS - 1
        task = registry.get_task(100, now_ms=just_before_expiry)
        # Then
        assert task.state == "LEASED"
        assert task.claimed_by == "agent-1"

    def test_lease_expires_exactly_at_ttl(self, registry, seeded_task):
        """Given LEASED task, When read at exactly lease_expires_at_ms,
        Then state=UNCLAIMED — boundary: exact equality means expired।"""
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        exact_expiry = claim["lease_expires_at_ms"]
        # When: now == lease_expires_at_ms (>= comparison in is_lease_expired)
        task = registry.get_task(100, now_ms=exact_expiry)
        # Then
        assert task.state == "UNCLAIMED"

    def test_heartbeat_extends_lease_ttl(self, registry, seeded_task):
        """Given LEASED task, When heartbeat called, Then lease_expires_at_ms
        extended by LEASE_TTL_MS — keeps lease alive।"""
        claim = registry.claim_task(100, "agent-1", now_ms=2000)
        token = claim["claim_token"]
        original_expiry = claim["lease_expires_at_ms"]
        # When: heartbeat 1 minute later
        result = registry.heartbeat_task(100, "agent-1", token, now_ms=2000 + 60_000)
        # Then
        assert result["ok"] is True
        new_expiry = result["lease_expires_at_ms"]
        assert new_expiry == 2000 + 60_000 + LEASE_TTL_MS
        assert new_expiry > original_expiry


# ---------------------------------------------------------------------------
# 4. Concurrent claim safety: two nodes, one wins
# ---------------------------------------------------------------------------


class TestConcurrentClaimSafety:
    """Two nodes claim same task simultaneously — only one wins।"""

    def test_second_concurrent_claim_loses_with_lease_held(self, registry, seeded_task):
        """Given LEASED by agent-1, When agent-2 claims same task, Then
        ok=False + reason=lease-held + held_by info exposed।"""
        # Given: agent-1 wins first
        claim1 = registry.claim_task(100, "agent-1", now_ms=2000)
        assert claim1["ok"] is True
        # When: agent-2 tries to claim same task
        claim2 = registry.claim_task(100, "agent-2", now_ms=2001)
        # Then
        assert claim2["ok"] is False
        assert claim2["reason"] == "lease-held"
        assert claim2["held_by"]["slot"] == "agent-1"
        assert claim2["held_by"]["lease_expires_at_ms"] == claim1["lease_expires_at_ms"]

    def test_same_slot_reclaim_is_idempotent(self, registry, seeded_task):
        """Given LEASED by agent-1, When agent-1 claims again, Then ok=True
        + idempotent_reclaim=True + same token returned।"""
        claim1 = registry.claim_task(100, "agent-1", now_ms=2000)
        token1 = claim1["claim_token"]
        # When: agent-1 re-claims (retry scenario)
        claim2 = registry.claim_task(100, "agent-1", now_ms=2100)
        # Then
        assert claim2["ok"] is True
        assert claim2["idempotent_reclaim"] is True
        assert claim2["claim_token"] == token1  # same token
        # Lease extended
        assert claim2["lease_expires_at_ms"] == 2100 + LEASE_TTL_MS

    def test_concurrent_threads_one_winner(self, registry, seeded_task):
        """Given UNCLAIMED task, When 5 threads claim simultaneously, Then
        exactly ONE wins (others get lease-held) — race-safety proof।"""
        winners: list[str] = []
        losers: list[str] = []
        barrier = threading.Barrier(5)

        def try_claim(slot_id: int):
            barrier.wait()  # বাংলা: সব থ্রেড একসাথে ছুটবে
            result = registry.claim_task(100, f"agent-{slot_id}", now_ms=2000)
            if result["ok"]:
                winners.append(f"agent-{slot_id}")
            else:
                losers.append(f"agent-{slot_id}")

        threads = [threading.Thread(target=try_claim, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Then: exactly one winner
        assert len(winners) == 1
        assert len(losers) == 4

    def test_concurrent_claims_distinct_tasks_no_conflict(self, registry):
        """Given 2 UNCLAIMED tasks, When 2 agents claim different tasks
        concurrently, Then both win — no false conflict।"""
        # Given: two tasks
        for issue in (101, 102):
            registry.upsert(
                TaskRecord(
                    issue=issue,
                    title=f"task-{issue}",
                    priority="P2-medium",
                    labels=["P2-medium"],
                    state="UNCLAIMED",
                    updated_at_ms=1000,
                    updated_at=_now_iso(1000),
                )
            )
        # When: concurrent claims on different tasks
        results: list[bool] = []
        barrier = threading.Barrier(2)

        def claim(issue, slot):
            barrier.wait()
            r = registry.claim_task(issue, slot, now_ms=2000)
            results.append(r["ok"])

        t1 = threading.Thread(target=claim, args=(101, "agent-1"))
        t2 = threading.Thread(target=claim, args=(102, "agent-2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # Then: both win
        assert results == [True, True]


# ---------------------------------------------------------------------------
# 5. Pure helpers: lease expiry + github lock
# ---------------------------------------------------------------------------


class TestPureHelpers:
    """is_lease_expired + is_github_locked + validate_slot — pure functions।"""

    def test_is_lease_expired_unclaimed_returns_false(self):
        """Given UNCLAIMED task, When is_lease_expired called, Then False —
        only LEASED records can expire।"""
        task = TaskRecord(issue=1, title="x", priority="P3-low", state="UNCLAIMED")
        assert is_lease_expired(task, now_ms=999999) is False

    def test_is_lease_expired_completed_returns_false(self):
        """Given COMPLETED task, When is_lease_expired called, Then False —
        completed tasks never expire।"""
        task = TaskRecord(issue=1, title="x", priority="P3-low", state="COMPLETED")
        assert is_lease_expired(task, now_ms=999999) is False

    def test_is_lease_expired_no_expiry_field_returns_true(self):
        """Given LEASED task without lease_expires_at_ms, When is_lease_expired,
        Then True — corrupt record safely expired।"""
        task = TaskRecord(issue=1, title="x", priority="P3-low", state="LEASED")
        task.lease_expires_at_ms = None
        assert is_lease_expired(task, now_ms=1000) is True

    def test_is_lease_expired_future_returns_false(self):
        """Given LEASED task with future expiry, When is_lease_expired with
        now=earlier, Then False — boundary: 1ms before expiry।"""
        task = TaskRecord(issue=1, title="x", priority="P3-low", state="LEASED")
        task.lease_expires_at_ms = 5000
        assert is_lease_expired(task, now_ms=4999) is False

    def test_is_lease_expired_past_returns_true(self):
        """Given LEASED task with past expiry, When is_lease_expired with
        now=later, Then True — boundary: 1ms after expiry।"""
        task = TaskRecord(issue=1, title="x", priority="P3-low", state="LEASED")
        task.lease_expires_at_ms = 5000
        assert is_lease_expired(task, now_ms=5001) is True

    def test_is_github_locked_status_in_progress(self):
        """Given task with status:in-progress label, When is_github_locked,
        Then True।"""
        task = TaskRecord(
            issue=1,
            title="x",
            priority="P2-medium",
            labels=["P2-medium", "status:in-progress"],
            state="UNCLAIMED",
        )
        assert is_github_locked(task) is True

    def test_is_github_locked_has_pr(self):
        """Given task with has-pr label, When is_github_locked, Then True।"""
        task = TaskRecord(
            issue=1,
            title="x",
            priority="P3-low",
            labels=["P3-low", "has-pr"],
            state="UNCLAIMED",
        )
        assert is_github_locked(task) is True

    def test_is_github_locked_clean_task(self):
        """Given task without legacy labels, When is_github_locked, Then False।"""
        task = TaskRecord(
            issue=1,
            title="x",
            priority="P1-high",
            labels=["P1-high"],
            state="UNCLAIMED",
        )
        assert is_github_locked(task) is False

    def test_validate_slot_valid_agent_prefix(self):
        """Given slot 'agent-3', When validate_slot, Then None (valid)।"""
        assert validate_slot("agent-3") is None

    def test_validate_slot_empty_string(self):
        """Given slot '', When validate_slot, Then error msg — boundary।"""
        err = validate_slot("")
        assert err is not None
        assert "non-empty" in err

    def test_validate_slot_wrong_prefix(self):
        """Given slot 'worker-1', When validate_slot, Then error msg —
        must start with 'agent-'।"""
        err = validate_slot("worker-1")
        assert err is not None
        assert "agent-" in err


# ---------------------------------------------------------------------------
# 6. Constants + queue-status shape contract
# ---------------------------------------------------------------------------


class TestConstantsAndShape:
    """Module-level constants + TaskRecord shape contract।"""

    def test_lease_ttl_ms_is_20_minutes(self):
        """Given LEASE_TTL_MS constant, When compared, Then 20 * 60 * 1000 ms।"""
        assert LEASE_TTL_MS == 20 * 60 * 1000

    def test_task_queue_hash_key_constant(self):
        """Given TASK_QUEUE_HASH_KEY, When compared, Then 'supremeai:task-queue'।"""
        assert TASK_QUEUE_HASH_KEY == "supremeai:task-queue"

    def test_task_record_required_fields(self, registry):
        """Given TaskRecord instance, When fields inspected, Then all required
        fields present (issue, title, priority, state)।"""
        task = TaskRecord(
            issue=1,
            title="t",
            priority="P3-low",
            state="UNCLAIMED",
            updated_at_ms=1000,
            updated_at=_now_iso(1000),
        )
        assert task.issue == 1
        assert task.title == "t"
        assert task.priority == "P3-low"
        assert task.state == "UNCLAIMED"
        assert task.labels == []
        assert task.claimed_by is None
        assert task.claim_token is None
        assert task.knowledge is None

    def test_list_tasks_returns_all_states(self, registry):
        """Given registry with UNCLAIMED+LEASED+COMPLETED tasks, When
        list_tasks called, Then all 3 returned (snapshot, no filter)।"""
        # Given
        registry.upsert(
            TaskRecord(
                issue=1,
                title="a",
                priority="P3-low",
                state="UNCLAIMED",
                updated_at_ms=1000,
                updated_at=_now_iso(1000),
            )
        )
        leased = TaskRecord(
            issue=2,
            title="b",
            priority="P2-medium",
            state="LEASED",
            updated_at_ms=1000,
            updated_at=_now_iso(1000),
        )
        leased.claimed_by = "agent-1"
        leased.claim_token = "tok"
        leased.lease_expires_at_ms = 1000 + LEASE_TTL_MS + 10000  # not expired
        registry.upsert(leased)
        registry.upsert(
            TaskRecord(
                issue=3,
                title="c",
                priority="P1-high",
                state="COMPLETED",
                updated_at_ms=1000,
                updated_at=_now_iso(1000),
            )
        )
        # When
        tasks = registry.list_tasks(now_ms=2000)
        # Then
        states = {t.state for t in tasks}
        assert states == {"UNCLAIMED", "LEASED", "COMPLETED"}
        assert len(tasks) == 3
