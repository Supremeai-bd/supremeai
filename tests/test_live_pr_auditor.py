"""Tests for live_pr_auditor (Guardian gate)."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.live_pr_auditor import _violations_for_pr, audit_prs, load_input


REPO_ROOT = Path(__file__).resolve().parents[1]


def _good_pr() -> dict:
    return {
        "repo": "Supremeai-bd/supremeai-open",
        "number": 10,
        "draft": False,
        "body": "Closes #5\n## Reflection Evidence\n3-Tier Verify passed",
        "commits_behind": 0,
        "checks": [{"name": "ci", "conclusion": "success"}],
        "head": "feat/foo",
        "files": ["scripts/ci/x.py"],
    }


def test_good_pr_has_no_violations() -> None:
    assert _violations_for_pr(_good_pr()) == []


def test_draft_pr_flagged() -> None:
    pr = _good_pr()
    pr["draft"] = True
    assert any("draft" in v for v in _violations_for_pr(pr))


def test_missing_issue_ref_flagged() -> None:
    pr = _good_pr()
    pr["body"] = "## Reflection Evidence\n3-Tier Verify"
    assert any("issue reference" in v for v in _violations_for_pr(pr))


def test_missing_reflection_flagged() -> None:
    pr = _good_pr()
    pr["body"] = "Closes #5\n3-Tier Verify"
    assert any("Reflection Evidence" in v for v in _violations_for_pr(pr))


def test_missing_verify_flagged() -> None:
    pr = _good_pr()
    pr["body"] = "Closes #5\n## Reflection Evidence"
    assert any("3-Tier Verify" in v or "Test Evidence" in v for v in _violations_for_pr(pr))


def test_stale_base_flagged() -> None:
    pr = _good_pr()
    pr["commits_behind"] = 4
    assert any("stale base" in v for v in _violations_for_pr(pr))


def test_ci_failure_flagged() -> None:
    pr = _good_pr()
    pr["checks"] = [{"name": "tests", "conclusion": "failure"}]
    assert any("tests" in v and "failure" in v for v in _violations_for_pr(pr))


def test_cross_domain_collision_flagged() -> None:
    pr = _good_pr()
    pr["head"] = "feat/studio-login"
    pr["files"] = ["core/engine/auth.py"]
    assert any("cross-domain" in v for v in _violations_for_pr(pr))


def test_audit_summary() -> None:
    res = audit_prs([_good_pr()])
    assert res["audited"] == 1
    assert res["ok"] is True
    res2 = audit_prs([_good_pr(), {**_good_pr(), "draft": True}])
    assert res2["audited"] == 2
    assert res2["ok"] is False


def test_load_input_list_and_wrapper(tmp_path: Path) -> None:
    p = tmp_path / "prs.json"
    p.write_text(json.dumps([_good_pr()]), encoding="utf-8")
    assert len(load_input(str(p))) == 1
    p2 = tmp_path / "w.json"
    p2.write_text(json.dumps({"prs": [_good_pr()]}), encoding="utf-8")
    assert len(load_input(str(p2))) == 1