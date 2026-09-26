"""Root acceptance tests for issue #1572 — Part 3: External Agents Contracts.

Covers:
* ``TaskContract`` — task_id, issue_number, goal, constraints, allowed_providers.
* ``PlannerArtifact`` — structured planning schema (steps, risks, targets).
* ``ArchitectureArtifact`` — architecture review + edge-case verification verdict.
* ``CodeArtifact`` — changeset metadata (branch, commit_sha, changed_files, diff)
  and task-scope violation detection.
* Serialisation round-trips (model_dump → model_validate) for durable transport.
"""

from __future__ import annotations

import pytest
from external_agents.contracts.architecture_artifact import (
    ArchitectureArtifact,
    EdgeCaseFinding,
)
from external_agents.contracts.code_artifact import ChangedFile, CodeArtifact
from external_agents.contracts.planner_artifact import PlannerArtifact, PlanStep
from external_agents.contracts.task_contract import (
    AgentProvider,
    TaskContract,
    new_task_id,
)
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# TaskContract
# ---------------------------------------------------------------------------
def test_task_contract_core_fields():
    contract = TaskContract(
        issue_number=1572,
        goal="Implement the external agents state machine",
        constraints={
            "allowed_paths": ["backend/external_agents/**"],
            "max_budget_usd": 5,
        },
        allowed_providers=[AgentProvider.ZCODE, AgentProvider.CHATGPT],
    )
    assert contract.task_id.startswith("task-")
    assert contract.issue_number == 1572
    assert contract.goal
    assert contract.constraints["allowed_paths"] == ["backend/external_agents/**"]
    assert AgentProvider.ZCODE in contract.allowed_providers
    assert AgentProvider.GEMINI not in contract.allowed_providers


def test_task_contract_defaults_allow_all_providers():
    contract = TaskContract(goal="explore")
    assert set(contract.allowed_providers) == set(AgentProvider)


def test_task_contract_goal_required():
    with pytest.raises(ValidationError):
        TaskContract(goal="")


def test_task_contract_with_constraints_merges():
    contract = TaskContract(goal="g", constraints={"a": 1})
    merged = contract.with_constraints(b=2)
    assert merged.constraints == {"a": 1, "b": 2}
    assert contract.constraints == {"a": 1}  # original untouched


def test_new_task_id_unique():
    assert new_task_id() != new_task_id()


# ---------------------------------------------------------------------------
# PlannerArtifact
# ---------------------------------------------------------------------------
def test_planner_artifact_structured_roundtrip():
    artifact = PlannerArtifact(
        task_id=new_task_id(),
        summary="Two-step plan: contracts then state manager",
        steps=[
            PlanStep(
                index=1,
                title="Define contracts",
                target_files=["backend/external_agents/contracts/task_contract.py"],
                acceptance=["TaskContract validates"],
            ),
            PlanStep(
                index=2,
                title="State manager",
                target_files=["backend/external_agents/control/state_manager.py"],
                acceptance=["Transitions durable"],
            ),
        ],
        risks=["schema drift"],
        provider="chatgpt",
    )
    data = artifact.model_dump(mode="json")
    revived = PlannerArtifact.model_validate(data)
    assert revived == artifact
    assert revived.step_targets() == [
        "backend/external_agents/contracts/task_contract.py",
        "backend/external_agents/control/state_manager.py",
    ]


def test_planner_step_index_must_be_positive():
    with pytest.raises(ValidationError):
        PlanStep(index=0, title="bad")


# ---------------------------------------------------------------------------
# ArchitectureArtifact
# ---------------------------------------------------------------------------
def test_architecture_artifact_edge_case_verification():
    artifact = ArchitectureArtifact(
        task_id="task-x",
        verdict="approved_with_changes",
        rationale="Solid plan, two gaps",
        edge_cases=[
            EdgeCaseFinding(
                scenario="process restart mid-run", handled=True, severity="high"
            ),
            EdgeCaseFinding(
                scenario="provider timeout",
                handled=False,
                severity="high",
                notes="no retry",
            ),
            EdgeCaseFinding(scenario="cosmetic typo", handled=False, severity="low"),
        ],
        required_changes=["Add provider timeout retry"],
        provider="gemini",
    )
    blocking = artifact.blocking_edge_cases
    assert len(blocking) == 1 and blocking[0].scenario == "provider timeout"
    assert artifact.is_actionable is False  # required_changes outstanding

    # clearing required_changes alone is not enough — the blocking edge case
    # must also be resolved before a coder may proceed
    half_cleared = artifact.model_copy(update={"required_changes": []})
    assert half_cleared.is_actionable is False

    cleared = artifact.model_copy(
        update={
            "required_changes": [],
            "verdict": "approved",
            "edge_cases": [
                EdgeCaseFinding(
                    scenario="process restart mid-run", handled=True, severity="high"
                ),
                EdgeCaseFinding(
                    scenario="provider timeout",
                    handled=True,
                    severity="high",
                    notes="retry added",
                ),
                EdgeCaseFinding(
                    scenario="cosmetic typo", handled=False, severity="low"
                ),
            ],
        }
    )
    assert cleared.is_actionable is True  # low-severity unhandled case doesn't block


def test_architecture_rejected_is_never_actionable():
    artifact = ArchitectureArtifact(task_id="t", verdict="rejected")
    assert artifact.is_actionable is False


# ---------------------------------------------------------------------------
# CodeArtifact
# ---------------------------------------------------------------------------
def test_code_artifact_changeset_metadata():
    artifact = CodeArtifact(
        task_id="task-x",
        branch="agent-2",
        commit_sha="abcdef123456",
        base_branch="main",
        changed_files=[
            ChangedFile(
                path="backend/app.py", change_type="modified", additions=10, deletions=2
            ),
            ChangedFile(path="backend/new.py", change_type="added", additions=42),
        ],
        diff="--- a/backend/app.py\n+++ b/backend/app.py\n...",
        provider="zcode",
    )
    data = artifact.model_dump(mode="json")
    revived = CodeArtifact.model_validate(data)
    assert revived == artifact
    assert revived.touched_paths() == ["backend/app.py", "backend/new.py"]


def test_code_artifact_scope_violation_detection():
    artifact = CodeArtifact(
        task_id="task-x",
        branch="b",
        commit_sha="abc",
        changed_files=[
            ChangedFile(
                path="backend/external_agents/control/state_manager.py",
                change_type="modified",
            ),
            ChangedFile(path="backend/api/routes/admin.py", change_type="modified"),
        ],
    )
    violations = artifact.violates_scope(["backend/external_agents"])
    assert violations == ["backend/api/routes/admin.py"]
    # empty scope = no enforcement
    assert artifact.violates_scope([]) == []


def test_code_artifact_requires_branch_and_sha():
    with pytest.raises(ValidationError):
        CodeArtifact(task_id="t", branch="", commit_sha="abc")
    with pytest.raises(ValidationError):
        CodeArtifact(task_id="t", branch="b", commit_sha="")
