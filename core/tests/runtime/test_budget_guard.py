# backend/tests/runtime/test_budget_guard.py
"""Tests for Runtime BudgetGuard enforcement."""

import pytest

from core.task_contract import TaskBudget, TaskContract
from runtime.budget_guard import BudgetExceededError, BudgetGuard


def test_budget_guard_pre_execution_passes():
    task = TaskContract(
        goal="Quick calculation",
        budget=TaskBudget(max_tokens=1000, max_cost_usd=0.10),
    )
    BudgetGuard.check_pre_execution(task)
    assert task.budget.tokens_used == 0


def test_budget_guard_exhausted_tokens_rejection():
    task = TaskContract(
        goal="Exhausted token test",
        budget=TaskBudget(max_tokens=500, tokens_used=500),
    )
    with pytest.raises(BudgetExceededError, match="Token budget exhausted"):
        BudgetGuard.check_pre_execution(task)


def test_budget_guard_record_and_enforce_limit_breach():
    task = TaskContract(
        goal="Accumulate breach",
        budget=TaskBudget(max_tokens=1000, max_cost_usd=0.05),
    )
    # Exceed cost
    with pytest.raises(BudgetExceededError, match="Cost limit exceeded"):
        BudgetGuard.record_and_enforce(task, cost_usd=0.10)
