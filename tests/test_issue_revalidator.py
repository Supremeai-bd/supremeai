"""Tests for the live-issue revalidation gate (#3215).

Pure state-machine tests (no network) + CLI exit-code contract + the
atomic_claim.sh integration guard. U7: unit layer of the 3-tier contract.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from scripts.agents.issue_revalidator import (
    BLOCKED,
    DUPLICATE,
    LIVE,
    OBSOLETE,
    REVALIDATE,
    STALE,
    RevalidationVerdict,
    main,
    revalidate,
)


def issue(
    number: int = 3215,
    body: str = "## Objective\ndo the thing",
    labels: list[str] | None = None,
    updated: str = "2026-10-01T00:00:00Z",
) -> dict:
    return {
        "number": number,
        "title": f"critical: fix #{number}",
        "body": body,
        "labels": [{"name": l} for l in (labels or [])],
        "createdAt": "2026-10-01T00:00:00Z",
        "updatedAt": updated,
    }


def base_ctx(**overrides) -> dict:
    ctx = {
        "issue": issue(),
        "merged_refs": [],
        "active_dup": None,
        "closed_dup": None,
        "check_errors": [],
    }
    ctx.update(overrides)
    return ctx


# ── LIVE ───────────────────────────────────────────────────────────────────


class TestLive:
    def test_fresh_unclaimed_issue_is_live(self):
        v = revalidate(base_ctx())
        assert v.state == LIVE
        assert v.proceed is True
        assert v.evidence["labels_checked"] is True

    def test_ledger_dashboard_is_live_by_design(self):
        v = revalidate(base_ctx(issue=issue(labels=["type:ledger"])))
        assert v.state == LIVE
        assert "#2928" in v.reasons[0]

    def test_missing_fingerprint_marker_skips_dup_checks(self):
        # No marker in body → dup lookups return None → still LIVE.
        v = revalidate(base_ctx())
        assert v.state == LIVE


# ── BLOCKED ────────────────────────────────────────────────────────────────


class TestBlocked:
    @pytest.mark.parametrize("label", [
        "status:in-progress", "status:claimed", "status:in-review",
        "blocked", "state:blocked-by-upstream", "queue:hold",
        "gate:admin-approval",
    ])
    def test_blocking_labels_refuse_claim(self, label):
        v = revalidate(base_ctx(issue=issue(labels=[label])))
        assert v.state == BLOCKED
        assert v.proceed is False
        assert label in v.reasons[0]

    def test_first_blocking_label_wins_and_fails_closed(self):
        v = revalidate(base_ctx(issue=issue(labels=["blocked", "status:in-progress"])))
        assert v.state == BLOCKED
        assert len(v.reasons) == 2  # all blocking labels reported


# ── OBSOLETE ───────────────────────────────────────────────────────────────


class TestObsolete:
    def test_merged_cross_reference_marks_obsolete(self):
        v = revalidate(base_ctx(merged_refs=[{"number": 3210, "title": "fix #3215"}]))
        assert v.state == OBSOLETE
        assert "#3210" in v.reasons[0]

    def test_complete_label_marks_obsolete(self):
        v = revalidate(base_ctx(issue=issue(labels=["status:complete"])))
        assert v.state == OBSOLETE

    def test_recently_closed_same_fingerprint_marks_obsolete(self):
        v = revalidate(base_ctx(closed_dup={"number": 3100, "closed_at": "2026-10-04T00:00:00Z"}))
        assert v.state == OBSOLETE
        assert "#3100" in v.reasons[0]

    def test_blocked_beats_obsolete_when_both_present(self):
        # Label evidence (blocked) is more decisive than a merged ref —
        # the merged ref may itself be the block's cause. BLOCKED wins.
        v = revalidate(base_ctx(
            issue=issue(labels=["status:in-progress"]),
            merged_refs=[{"number": 3210, "title": "fix #3215"}],
        ))
        assert v.state == BLOCKED


# ── DUPLICATE ──────────────────────────────────────────────────────────────


class TestDuplicate:
    def test_active_same_fingerprint_marks_duplicate(self):
        v = revalidate(base_ctx(active_dup={"number": 3199, "title": "same problem"}))
        assert v.state == DUPLICATE
        assert "#3199" in v.reasons[0]

    def test_same_issue_number_is_not_duplicate_of_itself(self):
        v = revalidate(base_ctx(active_dup={"number": 3215, "title": "itself"}))
        assert v.state == LIVE


# ── REVALIDATE (fail-closed) ───────────────────────────────────────────────


class TestRevalidate:
    def test_check_error_fails_closed(self):
        v = revalidate(base_ctx(check_errors=["merged-PR scan: gh timeout"]))
        assert v.state == REVALIDATE
        assert v.proceed is False

    def test_empty_body_is_insufficient_evidence(self):
        v = revalidate(base_ctx(issue=issue(body="   ")))
        assert v.state == REVALIDATE


# ── STALE (soft state, explicit acknowledgment) ────────────────────────────


class TestStale:
    def test_old_issue_is_stale(self):
        v = revalidate(base_ctx(issue=issue(updated="2026-07-01T00:00:00Z")))
        assert v.state == STALE
        assert v.proceed is False  # unacknowledged

    def test_acknowledged_stale_may_proceed(self):
        v = revalidate(base_ctx(issue=issue(updated="2026-07-01T00:00:00Z")))
        v.acknowledged_stale = True
        assert v.proceed is True

    def test_age_never_demotes_state(self):
        # §5: age never increases priority — STALE must not become OBSOLETE
        # or BLOCKED purely from age; it stays a re-check requirement.
        v = revalidate(base_ctx(issue=issue(updated="2025-01-01T00:00:00Z")))
        assert v.state == STALE

    def test_unparsable_updated_at_fails_closed(self):
        v = revalidate(base_ctx(issue=issue(updated="not-a-date")))
        assert v.state == REVALIDATE


# ── CLI contract ───────────────────────────────────────────────────────────


class TestCli:
    def _run(self, argv, ctx):
        with patch("scripts.agents.issue_revalidator.build_context", return_value=(ctx, [])):
            return main(argv)

    def test_live_exit_zero_with_json(self, capsys, monkeypatch):
        monkeypatch.setenv("ISSUE_REVALIDATE_STALE_DAYS", "45")
        rc = self._run(["--issue", "1", "--json"], base_ctx())
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["state"] == LIVE and payload["proceed"] is True

    def test_blocked_exit_one(self, capsys):
        rc = self._run(["--issue", "1"], base_ctx(issue=issue(labels=["blocked"])))
        assert rc == 1

    def test_stale_requires_flag(self, capsys):
        stale_ctx = base_ctx(issue=issue(updated="2026-07-01T00:00:00Z"))
        assert self._run(["--issue", "1"], stale_ctx) == 1
        assert self._run(["--issue", "1", "--acknowledge-stale"], stale_ctx) == 0

    def test_obsolete_exit_one_even_with_ack(self, capsys):
        ctx = base_ctx(merged_refs=[{"number": 9, "title": "x #1"}])
        assert self._run(["--issue", "1", "--acknowledge-stale"], ctx) == 1

    def test_stale_threshold_env_configurable(self, capsys, monkeypatch):
        monkeypatch.setenv("ISSUE_REVALIDATE_STALE_DAYS", "1")
        rc = self._run(["--issue", "1"], base_ctx(issue=issue(updated="2026-09-01T00:00:00Z")))
        assert rc == 1  # 30+ days old, threshold 1 day → STALE → unacknowledged refuse


# ── atomic_claim.sh integration guard ──────────────────────────────────────


class TestClaimGateIntegration:
    def test_claim_script_invokes_revalidation_gate(self):
        from pathlib import Path

        script = (Path(__file__).resolve().parents[1]
                  / "scripts" / "ci" / "atomic_claim.sh").read_text(encoding="utf-8")
        assert "issue_revalidator.py" in script, "claim path must run the #3215 gate"
        assert "AGENT_REVALIDATE_ACK" in script, "STALE acknowledgment must be explicit"
        assert "|| true" in script, (
            "revalidator exit 1 = verdict do-not-claim (CLI contract), not a "
            "subprocess failure — bash must not concatenate a fallback JSON "
            "onto real output (root-cause of the double-JSON bug)"
        )
        assert "fail-closed" in script, "empty output must fail closed"

    def test_bash_syntax_of_gate_block(self):
        import subprocess

        from pathlib import Path

        script_path = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "atomic_claim.sh"
        res = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
