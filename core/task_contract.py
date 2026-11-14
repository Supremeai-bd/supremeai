# backend/core/task_contract.py
"""Universal Task Contract (P0 Canonical Intelligence Abstraction).

Provides a single unified contract for all agents, planners, executors,
evaluators, and evolution engines across SupremeAI.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VerificationPolicy(StrEnum):
    STRICT = "strict"  # Must pass tests, AST scan & deterministic benchmark
    STANDARD = "standard"  # Must pass schema validation & confidence check
    PERMISSIVE = "permissive"  # Fast path for read-only / low-risk queries


class CapabilityState(StrEnum):
    DECLARED = "declared"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"


@dataclass
class TaskBudget:
    """Structured compute, token, and monetary budget constraints."""

    max_cost_usd: float = 0.50
    max_tokens: int = 16000
    max_tool_calls: int = 10
    max_execution_seconds: float = 60.0
    max_parallel_agents: int = 4

    tokens_used: int = 0
    cost_incurred: float = 0.0
    tool_calls_count: int = 0


class InvalidTaskStateTransition(Exception):
    """Raised when an illegal transition is attempted on a Task Contract."""

    pass


class TaskStateMachine:
    """Enforces strict, unidirectional state transitions for tasks."""

    ALLOWED_TRANSITIONS: dict[TaskStatus, list[TaskStatus]] = {
        TaskStatus.PENDING: [TaskStatus.PLANNING, TaskStatus.EXECUTING, TaskStatus.FAILED],
        TaskStatus.PLANNING: [TaskStatus.EXECUTING, TaskStatus.FAILED],
        TaskStatus.EXECUTING: [TaskStatus.VERIFYING, TaskStatus.FAILED],
        TaskStatus.VERIFYING: [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.EXECUTING],
        TaskStatus.COMPLETED: [],  # Terminal
        TaskStatus.FAILED: [TaskStatus.ROLLED_BACK],
        TaskStatus.ROLLED_BACK: [],  # Terminal
    }

    @classmethod
    def validate_transition(cls, current: TaskStatus, target: TaskStatus) -> bool:
        allowed = cls.ALLOWED_TRANSITIONS.get(current, [])
        if target not in allowed:
            raise InvalidTaskStateTransition(
                f"Illegal state transition from {current.value} to {target.value}. Allowed: {[s.value for s in allowed]}"
            )
        return True


@dataclass
class TaskContract:
    """Universal Task Object connecting Planner -> Reasoner -> Executor -> Evaluator -> Memory."""

    goal: str
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    constraints: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    budget: TaskBudget = field(default_factory=TaskBudget)
    deadline: datetime | None = None
    required_capabilities: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    verification_policy: VerificationPolicy = VerificationPolicy.STANDARD
    allowed_tools: list[str] = field(default_factory=list)
    memory_scope: str = "session"  # "global" | "session" | "ephemeral"
    status: TaskStatus = TaskStatus.PENDING
    plan_steps: list[dict[str, Any]] = field(default_factory=list)
    execution_history: list[dict[str, Any]] = field(default_factory=list)
    result: Any | None = None
    confidence: float = 0.0
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def transition_to(self, new_status: TaskStatus, note: str | None = None) -> None:
        """Advance task state with strict state machine validation."""
        TaskStateMachine.validate_transition(self.status, new_status)
        self.status = new_status
        self.execution_history.append(
            {
                "stage": new_status.value,
                "timestamp": datetime.now().isoformat(),
                "note": note or "",
            }
        )

    def mark_in_progress(self, stage: TaskStatus) -> None:
        self.transition_to(stage)

    def complete(self, result: Any, confidence: float = 0.95) -> None:
        if self.status != TaskStatus.VERIFYING:
            self.transition_to(TaskStatus.VERIFYING)
        self.transition_to(TaskStatus.COMPLETED)
        self.result = result
        self.confidence = confidence
        self.completed_at = datetime.now()

    def fail(self, error_message: str) -> None:
        self.transition_to(TaskStatus.FAILED, note=error_message)
        self.error = error_message
        self.completed_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "constraints": self.constraints,
            "risk_level": self.risk_level.value,
            "budget": {
                "max_cost_usd": self.budget.max_cost_usd,
                "max_tokens": self.budget.max_tokens,
                "tokens_used": self.budget.tokens_used,
            },
            "required_capabilities": self.required_capabilities,
            "success_criteria": self.success_criteria,
            "verification_policy": self.verification_policy.value,
            "allowed_tools": self.allowed_tools,
            "memory_scope": self.memory_scope,
            "status": self.status.value,
            "plan_steps_count": len(self.plan_steps),
            "confidence": self.confidence,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metrics": self.metrics,
        }


# ── Task Queue Envelope & Primitives (Migrated from task_queue/task_contract.py) ──
_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")


class TaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class TaskEnvelope:
    task_id: str
    tenant_id: str
    idempotency_key: str
    task_type: str
    payload: dict[str, Any]
    state: TaskState = TaskState.QUEUED
    attempt: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("task_id", self.task_id),
            ("tenant_id", self.tenant_id),
            ("idempotency_key", self.idempotency_key),
        ):
            if not _ID_RE.fullmatch(value):
                raise ValueError(f"invalid {name}")
        if not self.task_type or len(self.task_type) > 80:
            raise ValueError("invalid task_type")
        if self.attempt < 0 or self.attempt > 5:
            raise ValueError("attempt must be between 0 and 5")

    @property
    def dedup_key(self) -> str:
        raw = f"{self.tenant_id}:{self.idempotency_key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "state": self.state.value, "dedup_key": self.dedup_key}


def canonical_payload(payload: dict[str, Any]) -> str:
    """Stable representation for cache and idempotency fingerprints."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

