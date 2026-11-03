# tests/test_core_task_contract.py
"""Tests for the core P0 Universal Task Contract and state machine."""

import pytest

from core.task_contract import (
    CapabilityState,
    InvalidTaskStateTransition,
    RiskLevel,
    TaskBudget,
    TaskContract,
    TaskStateMachine,
    TaskStatus,
    VerificationPolicy,
)


def test_enum_values():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.ROLLED_BACK.value == "rolled_back"
    assert RiskLevel.CRITICAL.value == "critical"
    assert VerificationPolicy.STRICT.value == "strict"
    assert CapabilityState.PRODUCTION.value == "production"


def test_task_budget_defaults():
    b = TaskBudget()
    assert b.max_cost_usd == 0.50
    assert b.max_tokens == 16000
    assert b.tokens_used == 0
    assert b.cost_incurred == 0.0


def test_state_machine_valid_transition():
    assert TaskStateMachine.validate_transition(TaskStatus.PENDING, TaskStatus.PLANNING) is True
    assert TaskStateMachine.validate_transition(TaskStatus.EXECUTING, TaskStatus.VERIFYING) is True
    assert TaskStateMachine.validate_transition(TaskStatus.FAILED, TaskStatus.ROLLED_BACK) is True


def test_state_machine_terminal_states_have_no_transitions():
    assert TaskStateMachine.ALLOWED_TRANSITIONS[TaskStatus.COMPLETED] == []
    assert TaskStateMachine.ALLOWED_TRANSITIONS[TaskStatus.ROLLED_BACK] == []


def test_state_machine_invalid_transition_raises():
    with pytest.raises(InvalidTaskStateTransition):
        TaskStateMachine.validate_transition(TaskStatus.COMPLETED, TaskStatus.PENDING)

    with pytest.raises(InvalidTaskStateTransition):
        TaskStateMachine.validate_transition(TaskStatus.PENDING, TaskStatus.COMPLETED)


def test_contract_defaults_and_task_id():
    c = TaskContract(goal="do something")
    assert c.goal == "do something"
    assert c.status == TaskStatus.PENDING
    assert c.task_id.startswith("task_")
    assert c.risk_level == RiskLevel.MEDIUM
    assert c.verification_policy == VerificationPolicy.STANDARD


def test_contract_transition_to_records_history():
    c = TaskContract(goal="g")
    c.transition_to(TaskStatus.PLANNING, note="start planning")
    assert c.status == TaskStatus.PLANNING
    assert len(c.execution_history) == 1
    assert c.execution_history[0]["stage"] == "planning"
    assert c.execution_history[0]["note"] == "start planning"


def test_contract_complete_flow():
    c = TaskContract(goal="g")
    c.transition_to(TaskStatus.EXECUTING)
    c.transition_to(TaskStatus.VERIFYING)
    c.complete(result={"ok": True}, confidence=0.9)
    assert c.status == TaskStatus.COMPLETED
    assert c.result == {"ok": True}
    assert c.confidence == 0.9
    assert c.completed_at is not None


def test_contract_complete_from_non_verifying_inserts_verifying():
    c = TaskContract(goal="g")
    c.transition_to(TaskStatus.EXECUTING)
    c.complete(result="done")
    stages = [h["stage"] for h in c.execution_history]
    assert "verifying" in stages
    assert "completed" in stages


def test_contract_fail_flow():
    c = TaskContract(goal="g")
    c.transition_to(TaskStatus.EXECUTING)
    c.fail("boom")
    assert c.status == TaskStatus.FAILED
    assert c.error == "boom"
    assert c.completed_at is not None


def test_contract_illegal_transition_raises():
    c = TaskContract(goal="g")
    c.transition_to(TaskStatus.EXECUTING)
    c.transition_to(TaskStatus.VERIFYING)
    c.transition_to(TaskStatus.COMPLETED)
    with pytest.raises(InvalidTaskStateTransition):
        c.transition_to(TaskStatus.PENDING)


def test_contract_to_dict_shape():
    c = TaskContract(goal="g", risk_level=RiskLevel.HIGH)
    d = c.to_dict()
    assert d["goal"] == "g"
    assert d["status"] == "pending"
    assert d["risk_level"] == "high"
    assert d["budget"]["max_tokens"] == 16000
    assert d["created_at"]
    assert "completed_at" in d
