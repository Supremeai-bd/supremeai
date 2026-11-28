import json
import pytest

from scripts.ci.promote_decision_record import promote_candidate, stage_candidate


VALID_BODY = (
    "Some commit message\n\n"
    "<!-- ai-decision-record v1 -->\n"
    + json.dumps({
        "schema": "ai-decision-record/1",
        "agent": "codex",
        "task_type": "bugfix",
        "task_ref": "PR-945",
        "decision": "Auto-update PR branch on pr_base_changed",
        "reason": "Avoid false CI failure when main advances mid-run",
        "alternatives_rejected": ["Manual rebase"],
        "evidence": ["unified-pipeline.yml"],
        "verification": ["pytest tests/test_tiny_brain_guard.py"],
        "limitations": ["Requires GH_TOKEN"],
        "status": "tested",
        "reasoning_pattern": {
            "task_family": "debugging",
            "steps": ["clarify_goal"],
            "checks": ["user_constraints"],
            "stop_conditions": ["missing_consent"],
        },
    })
    + "\n<!-- /ai-decision-record -->\n"
)


def test_stage_candidate_always_sets_pending_verification():
    posted = []
    staged = stage_candidate(
        repo="Supremeai-bd/supremeai",
        source_kind="pr",
        source_number=945,
        body=VALID_BODY,
        commit_sha="abc1234",
        post_fn=lambda url, key, table, row: posted.append((table, row)) or True,
        supabase_url="https://example.supabase.co",
        supabase_key="service-key",
    )
    assert len(staged) == 1
    assert staged[0]["status"] == "pending_verification"
    assert posted[0][0] == "ai_decision_candidates"


def test_stage_candidate_rejects_missing_record():
    with pytest.raises(ValueError):
        stage_candidate("Supremeai-bd/supremeai", "commit", 0, "no record here")


def test_promote_candidate_fails_closed_without_approval():
    with pytest.raises(PermissionError):
        promote_candidate(
            candidate_id=1,
            candidate_row={"decision": "d", "status": "pending_verification", "record_json": {}},
            reviewer="admin",
            approved=False,
        )


def test_promote_candidate_succeeds_with_approval_and_reviewer():
    posted = []
    mem = promote_candidate(
        candidate_id=42,
        candidate_row={
            "decision": "Auto-update PR branch",
            "status": "pending_verification",
            "record_json": {"reasoning_pattern": {"task_family": "ci_gate_fix"}},
        },
        reviewer="SaifulHaqueNiloy",
        approved=True,
        post_fn=lambda url, key, table, row: posted.append((table, row)) or True,
        supabase_url="https://example.supabase.co",
        supabase_key="service-key",
    )
    assert mem["candidate_id"] == 42
    assert mem["task_family"] == "ci_gate_fix"
    assert posted[0][0] == "ai_verified_memories"
