# backend/tests/verification/test_verifier.py
"""Tests for Deterministic Verifier Engine."""

import pytest

from core.task_contract import TaskContract, VerificationPolicy
from verification.verifier import get_verifier


@pytest.mark.asyncio
async def test_verifier_valid_python_ast():
    verifier = get_verifier()

    task = TaskContract(
        goal="Write greeting function",
        required_capabilities=["python"],
        verification_policy=VerificationPolicy.STRICT,
        success_criteria=["def greet"],
    )

    valid_code = "def greet(name: str) -> str:\n    return f'Hello {name}'\n"
    report = await verifier.verify(task, valid_code)

    assert report.verified is True
    assert "Python AST Syntax Validation" in report.criteria_passed
    assert report.score == 1.0
    assert len(report.failures) == 0


@pytest.mark.asyncio
async def test_verifier_empty_output_rejection():
    verifier = get_verifier()

    task = TaskContract(
        goal="Produce data",
        verification_policy=VerificationPolicy.STANDARD,
    )

    report = await verifier.verify(task, "")
    assert report.verified is False
    assert any("empty" in f.lower() for f in report.criteria_failed)
    assert report.score == 0.0
