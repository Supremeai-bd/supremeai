# backend/tests/runtime/test_task_runtime.py
"""Tests for Canonical Task Runtime and Execution Lifecycle."""

import pytest

from core.task_contract import RiskLevel, TaskBudget, TaskContract, TaskStatus, VerificationPolicy
from runtime.task_context import TaskContext
from runtime.task_runtime import get_task_runtime


@pytest.mark.asyncio
async def test_task_runtime_execution_success():
    runtime = get_task_runtime()

    task = TaskContract(
        goal="Summarize authentication guidelines",
        risk_level=RiskLevel.LOW,
        budget=TaskBudget(max_execution_seconds=10.0),
        verification_policy=VerificationPolicy.STANDARD,
        success_criteria=["Processed solution"],
    )

    ctx = TaskContext(tenant_id="test_tenant")
    result = await runtime.execute_task(task, ctx)

    assert result.success is True
    assert result.task_id == task.task_id
    assert task.status == TaskStatus.COMPLETED
    assert result.confidence >= 0.70
    assert len(runtime.experience_ledger) >= 1


@pytest.mark.asyncio
async def test_task_runtime_rejects_missing_tenant_context():
    runtime = get_task_runtime()
    task = TaskContract(
        goal="Run without tenant context",
        risk_level=RiskLevel.LOW,
        budget=TaskBudget(max_execution_seconds=5.0),
        verification_policy=VerificationPolicy.STANDARD,
    )

    result = await runtime.execute_task(task)

    assert result.success is False
    assert task.status == TaskStatus.FAILED
    assert result.error == "Task execution requires an authenticated tenant_id"


@pytest.mark.asyncio
async def test_task_runtime_strict_verification_failure():
    runtime = get_task_runtime()

    task = TaskContract(
        goal="Produce broken code",
        risk_level=RiskLevel.HIGH,
        budget=TaskBudget(max_execution_seconds=5.0),
        verification_policy=VerificationPolicy.STRICT,
        required_capabilities=["python"],
        success_criteria=["CRITICAL_TOKEN_THAT_DOES_NOT_EXIST"],
    )

    result = await runtime.execute_task(task, TaskContext(tenant_id="test-tenant"))

    assert result.success is False
    assert task.status == TaskStatus.FAILED
    assert "Verification failed" in (task.error or "")
