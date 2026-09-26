"""Contract tests for the Merge-Train Rollup workflow (Issue #1711).

These guard the OPS invariants that make the concurrency-gated merge queue safe:
exactly one integration CI execution at a time, a reviewable batch PR, and
Tier-3 human approval before any automatic landing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML required for workflow contract tests")

WORKFLOW = Path(".github/workflows/merge-train-rollup.yml")


def _load() -> dict:
    assert WORKFLOW.exists(), f"missing workflow: {WORKFLOW}"
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_single_flight_concurrency_group_is_strict():
    doc = _load()
    concurrency = doc["concurrency"]
    assert concurrency["group"] == "supremeai-integration-gate"
    # A cancelled integration run would let a second batch CI start concurrently.
    assert concurrency["cancel-in-progress"] is False


def test_expected_jobs_and_scheduling_triggers():
    doc = _load()
    jobs = doc["jobs"]
    assert set(jobs) == {"plan", "rollup", "gate", "land", "request-approval"}
    assert set(jobs["land"]["needs"]) == {"plan", "rollup", "gate"}
    assert set(jobs["gate"]["needs"]) == {"plan", "rollup"}

    on_block = doc[True] if True in doc else doc["on"]
    assert set(on_block) == {"pull_request", "push", "schedule", "workflow_dispatch"}


def test_auto_land_is_opt_in_and_requires_green_gate():
    doc = _load()
    land_if = doc["jobs"]["land"]["if"]
    assert "needs.gate.outputs.result == 'pass'" in land_if
    assert "MERGE_TRAIN_AUTO_LAND" in land_if
    assert "github.event.inputs.auto_land == 'true'" in land_if

    approval_if = doc["jobs"]["request-approval"]["if"]
    assert "needs.gate.outputs.result == 'pass'" in approval_if


def test_queue_state_machine_labels_are_wired():
    text = WORKFLOW.read_text(encoding="utf-8")
    # Queue lane, in-flight lane and the frozen lane must all be managed.
    assert "queue:pending-rollup" in text
    assert "queue:in-batch" in text
    assert "queue:hold" in text
    assert "queue:failed" in text


def test_mutations_use_self_heal_pat_fallback():
    text = WORKFLOW.read_text(encoding="utf-8")
    # Anti-recursion (Issue #1634): PAT fallback is mandatory for push/PR create.
    assert "git push" in text
    assert "gh pr create" in text
    assert "secrets.SELF_HEAL_PAT || github.token" in text
