# backend/tests/runtime/test_planner.py
"""Tests for Canonical Planner decomposition."""

import pytest

from core.task_contract import RiskLevel, TaskContract, VerificationPolicy
from runtime.planner import StepStatus, get_planner


@pytest.mark.asyncio
async def test_planner_creates_multi_step_plan():
    planner = get_planner()

    task = TaskContract(
        goal="Develop a rate-limited cache decorator in Python",
        risk_level=RiskLevel.HIGH,
        required_capabilities=["python", "caching"],
        verification_policy=VerificationPolicy.STRICT,
        success_criteria=["def rate_limited_cache"],
    )

    plan = await planner.create_plan(task)

    assert plan.task_id == task.task_id
    assert len(plan.steps) == 3
    assert plan.steps[0].status == StepStatus.PENDING
    assert len(task.plan_steps) == 3
    assert "rate_limited_cache" in task.success_criteria[0]
