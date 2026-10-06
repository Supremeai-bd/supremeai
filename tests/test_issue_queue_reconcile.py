"""Tests for the GSPQ auto-reconciliation core (#3218).

Covers the deterministic policy added to scripts/ci/issue_queue_manager.py:
automatic sequence allocation, duplicate/gap repair, frozen-issue protection,
admin-gate safety, deterministic P1→P0 promotion/demotion, and idempotency.
All tests are pure — no GitHub network access (U7: unit layer).
"""

from __future__ import annotations

import pytest

from scripts.ci.issue_queue_manager import (
    ADMIN_GATE_LABEL,
    AUTO_PROMOTION_MARKER,
    RULE_VERSION,
    effective_priorities,
    parse_metadata,
    plan_group_reconciliation,
    sequence_plan,
)
from scripts.ci import issue_queue_manager as qm


def meta(
    number: int,
    priority: str = "P2-medium",
    seq: int | None = None,
    group: str | None = "pipeline",
    *,
    claimed: bool = False,
    has_pr: bool = False,
    blocked: bool = False,
    admin_gated: bool = False,
    complete: bool = False,
    auto_promoted: bool = False,
    is_ledger: bool = False,
    labels: list[str] | None = None,
) -> dict:
    """Build a queue metadata dict directly (parse_metadata shape)."""
    lbl = list(labels or [])
    if claimed:
        lbl.append("status:in-progress")
    if has_pr:
        lbl.append("has-pr")
    if blocked:
        lbl.append("blocked")
    if admin_gated:
        lbl.append(ADMIN_GATE_LABEL)
    if complete:
        lbl.append("status:complete")
    if auto_promoted:
        lbl.append(AUTO_PROMOTION_MARKER)
    if is_ledger:
        lbl.append("type:ledger")
    lbl.append(priority)
    if seq is not None:
        lbl.append(f"seq:{seq}")
    if group:
        lbl.append(f"group:{group}")
    return {
        "number": number,
        "title": f"Issue #{number}",
        "group": group,
        "seq": seq,
        "priority": priority,
        "is_claimed": claimed,
        "has_pr": has_pr,
        "is_blocked": blocked,
        "admin_gated": admin_gated,
        "is_complete": complete,
        "auto_promoted": auto_promoted,
        "is_ledger": is_ledger,
        "created_at": "",
        "labels": lbl,
    }


def assert_contiguous_unique(plan: dict[int, int], total: int) -> None:
    values = sorted(plan.values())
    assert values == list(range(1, total + 1)), f"plan not contiguous 1..{total}: {values}"


# ── Priority reconciliation ────────────────────────────────────────────────


class TestEffectivePriorities:
    def test_no_promotion_when_real_p0_exists(self):
        metas = [meta(1, "P0-critical", 1), meta(2, "P1-high", 2)]
        eff = effective_priorities(metas)
        assert eff[2]["action"] is None
        assert eff[2]["effective"] == "P1-high"

    def test_head_p1_promoted_when_group_has_no_p0(self):
        metas = [meta(1, "P1-high", 1), meta(2, "P2-medium", 2)]
        eff = effective_priorities(metas)
        assert eff[1]["action"] == "promote"
        assert eff[1]["effective"] == "P0-critical"
        assert eff[2]["action"] is None

    def test_only_one_promotion_even_with_many_p1(self):
        metas = [meta(1, "P1-high", 1), meta(2, "P1-high", 2), meta(3, "P1-high", 3)]
        eff = effective_priorities(metas)
        promoted = [n for n, e in eff.items() if e["action"] == "promote"]
        assert promoted == [1]  # FIFO: lowest number wins (deterministic)

    def test_security_p1_wins_over_older_non_security(self):
        metas = [meta(10, "P1-high", 1), meta(20, "P1-high", 2, labels=["type:security"])]
        eff = effective_priorities(metas)
        assert eff[20]["action"] == "promote"
        assert eff[10]["action"] is None

    def test_frozen_p1_never_promoted(self):
        for kwargs in (
            {"claimed": True},
            {"has_pr": True},
            {"blocked": True},
            {"admin_gated": True},
            {"complete": True},
        ):
            metas = [meta(1, "P1-high", 1, **kwargs), meta(2, "P2-medium", 2)]
            eff = effective_priorities(metas)
            assert eff[1]["action"] is None, f"frozen {kwargs} must not be promoted"

    def test_auto_promoted_demoted_when_real_p0_arrives(self):
        metas = [
            meta(1, "P0-critical", 1),  # real P0
            meta(2, "P0-critical", 2, auto_promoted=True),  # system promotion
        ]
        eff = effective_priorities(metas)
        assert eff[2]["action"] == "demote"
        assert eff[2]["effective"] == "P1-high"
        assert eff[1]["action"] is None  # manual P0 never touched

    def test_auto_promoted_kept_when_no_real_p0(self):
        metas = [meta(2, "P0-critical", 1, auto_promoted=True), meta(3, "P1-high", 2)]
        eff = effective_priorities(metas)
        assert eff[2]["action"] is None
        assert eff[2]["effective"] == "P0-critical"
        assert eff[3]["action"] is None  # head slot already occupied by promotion


# ── Sequence planning ──────────────────────────────────────────────────────


class TestSequencePlan:
    def test_uses_effective_priority_from_promotion(self):
        # No P0 in group → P1 #1 is promoted; it must outrank the P2 movable.
        metas = [meta(1, "P1-high", None), meta(2, "P2-medium", None)]
        eff = effective_priorities(metas)
        plan = sequence_plan(metas, eff)
        assert plan[1] == 1
        assert plan[2] == 2

    def test_blocked_ranks_after_ready_within_same_priority(self):
        metas = [meta(1, "P1-high", None, blocked=True), meta(2, "P1-high", None)]
        eff = {1: {"effective": "P1-high"}, 2: {"effective": "P1-high"}}
        plan = sequence_plan(metas, eff)
        assert plan[2] == 1  # ready issue first
        assert plan[1] == 2  # blocked after

    def test_admin_gated_frozen_keeps_position_and_is_not_promoted(self):
        metas = [
            meta(1, "P1-high", 2, admin_gated=True),
            meta(2, "P2-medium", None),
            meta(3, "P2-medium", None),
        ]
        eff = effective_priorities(metas)
        plan = sequence_plan(metas, eff)
        assert plan[1] == 2          # untouched position
        assert eff[1]["action"] is None  # never promoted
        assert_contiguous_unique(plan, 3)

    def test_claimed_issue_position_is_immovable(self):
        metas = [
            meta(1, "P0-critical", 1, claimed=True),
            meta(2, "P1-high", 3),
            meta(3, "P3-low", 2),
        ]
        eff = effective_priorities(metas)
        plan = sequence_plan(metas, eff)
        assert plan[1] == 1  # claimed work keeps its slot
        # Movables fill remaining positions by rank: P1 → 2, P3 → 3.
        assert plan[2] == 2
        assert plan[3] == 3

    def test_duplicate_seq_resolved_contiguously(self):
        metas = [meta(100, "P1-high", 2), meta(200, "P2-medium", 2), meta(300, "P2-medium", None)]
        eff = {m["number"]: {"effective": m["priority"]} for m in metas}
        plan = sequence_plan(metas, eff)
        assert_contiguous_unique(plan, 3)

    def test_gap_closed_after_closure_simulation(self):
        # Issue that held seq:2 got closed → dropped from the open list.
        metas = [meta(1, "P1-high", 1), meta(3, "P2-medium", 3)]
        eff = {m["number"]: {"effective": m["priority"]} for m in metas}
        plan = sequence_plan(metas, eff)
        assert plan == {1: 1, 3: 2}

    def test_new_grouped_issue_gets_sequence_automatically(self):
        # AC-1: a new grouped issue (no seq) is allocated without --seq.
        metas = [meta(10, "P0-critical", 1), meta(20, "P2-medium", 2), meta(30, "P1-high", None)]
        eff = {m["number"]: {"effective": m["priority"]} for m in metas}
        plan = sequence_plan(metas, eff)
        assert plan[30] == 2  # ranks between the P0 and the P2
        assert plan[20] == 3  # downstream shifted +1

    def test_two_new_issues_same_rank_tie_breaks_by_number(self):
        metas = [meta(50, "P1-high", None), meta(40, "P1-high", None)]
        eff = {m["number"]: {"effective": "P1-high"} for m in metas}
        plan = sequence_plan(metas, eff)
        assert plan == {40: 1, 50: 2}  # deterministic, not dict-order dependent

    def test_concurrent_new_issue_insertion_is_total(self):
        # Two fresh issues land "simultaneously" — plan stays a bijection.
        metas = [meta(1, "P1-high", 1), meta(2, "P1-high", None), meta(3, "P1-high", None)]
        eff = {m["number"]: {"effective": "P1-high"} for m in metas}
        plan = sequence_plan(metas, eff)
        assert_contiguous_unique(plan, 3)


# ── Full reconciliation plan (idempotency + audit shape) ───────────────────


class TestPlanGroupReconciliation:
    def test_insertion_shift_is_planned_with_reasons(self):
        metas = [meta(10, "P0-critical", 1), meta(20, "P2-medium", 2), meta(30, "P1-high", None)]
        plan = plan_group_reconciliation(metas)
        by_number = {m["number"]: m for m in plan["mutations"]}
        assert plan["rule"] == RULE_VERSION
        assert by_number[30]["new_seq"] == 2
        assert by_number[30]["old_seq"] is None
        assert "auto-allocated" in by_number[30]["reason"]
        assert by_number[20]["old_seq"] == 2 and by_number[20]["new_seq"] == 3

    def test_idempotent_second_plan_is_empty(self):
        metas = [meta(10, "P0-critical", 1), meta(20, "P2-medium", 2), meta(30, "P1-high", None)]
        first = plan_group_reconciliation(metas)
        assert first["mutations"], "first plan must propose mutations"

        # Simulate apply: rewrite metas to the planned target state.
        target = sequence_plan(metas, effective_priorities(metas))
        applied = []
        for m in metas:
            m2 = dict(m)
            m2["seq"] = target[m["number"]]
            applied.append(m2)
        second = plan_group_reconciliation(applied)
        assert second["mutations"] == []
        assert second["priority_changes"] == []

    def test_priority_change_carries_audit_fields(self):
        metas = [meta(1, "P1-high", 1), meta(2, "P2-medium", 2)]
        plan = plan_group_reconciliation(metas)
        assert len(plan["priority_changes"]) == 1
        ch = plan["priority_changes"][0]
        assert ch["number"] == 1
        assert ch["old"] == "P1-high" and ch["new"] == "P0-critical"
        assert ch["action"] == "promote"
        assert ch["reason"]

    def test_promotion_changes_sequence_ranking(self):
        # Promoted P1 (no P0 in group) outranks later P2 movables.
        metas = [meta(1, "P1-high", None), meta(2, "P2-medium", None), meta(3, "P2-medium", None)]
        plan = plan_group_reconciliation(metas)
        target = {m["number"]: m["new_seq"] for m in plan["mutations"]}
        assert target[1] == 1

    def test_demotion_reverts_effective_ranking(self):
        metas = [
            meta(1, "P0-critical", 1),  # real P0 arrives
            meta(2, "P0-critical", 2, auto_promoted=True),
            meta(3, "P2-medium", 3),
        ]
        plan = plan_group_reconciliation(metas)
        demotions = [c for c in plan["priority_changes"] if c["action"] == "demote"]
        assert [c["number"] for c in demotions] == [2]


# ── parse_metadata extensions + CLI wiring ─────────────────────────────────


class TestParseMetadataExtensions:
    def test_extended_flags_parsed(self):
        issue = {
            "number": 9,
            "title": "t",
            "createdAt": "2026-10-05T00:00:00Z",
            "labels": [{"name": l} for l in (
                "group:step-1", "seq:3", "P1-high", ADMIN_GATE_LABEL,
                AUTO_PROMOTION_MARKER, "status:complete",
            )],
        }
        m = parse_metadata(issue)
        assert m["admin_gated"] is True
        assert m["auto_promoted"] is True
        assert m["is_complete"] is True
        assert m["created_at"] == "2026-10-05T00:00:00Z"
        assert m["seq"] == 3

    def test_defaults_are_unfrozen(self):
        m = parse_metadata({"number": 1, "title": "t", "labels": []})
        assert m["admin_gated"] is False
        assert m["auto_promoted"] is False
        assert m["is_complete"] is False
        assert m["is_ledger"] is False

    def test_ledger_dashboard_flag(self):
        m = parse_metadata({"number": 1, "title": "t", "labels": [{"name": "type:ledger"}]})
        assert m["is_ledger"] is True


class TestCliRegistration:
    def test_reconcile_and_allocate_subcommands_registered(self):
        import argparse

        # Rebuild the parser the same way main() does, without executing it.
        parser = argparse.ArgumentParser(description="SupremeAI Dynamic Issue Queue Manager")
        subparsers = parser.add_subparsers(dest="command", required=True)
        p_reconcile = subparsers.add_parser("reconcile")
        p_reconcile.add_argument("--group", type=str, default=None)
        p_reconcile.add_argument("--all-groups", action="store_true")
        p_reconcile.add_argument("--apply", action="store_true")
        p_reconcile.set_defaults(func=qm.cmd_reconcile)
        p_alloc = subparsers.add_parser("allocate")
        p_alloc.add_argument("--issue", type=int, required=True)
        p_alloc.set_defaults(func=qm.cmd_allocate)

        args = parser.parse_args(["reconcile", "--group", "step-1", "--apply"])
        assert args.func is qm.cmd_reconcile
        assert args.apply is True and args.all_groups is False
        args2 = parser.parse_args(["allocate", "--issue", "42"])
        assert args2.func is qm.cmd_allocate and args2.issue == 42


class TestCmdReconcileObserveOnly:
    """cmd_reconcile observe-only mode must not mutate (fail-closed)."""

    def test_observe_only_never_calls_apply(self, capsys, monkeypatch):
        issues = [
            {"number": 10, "title": "a", "createdAt": "", "labels": [
                {"name": "group:step-1"}, {"name": "P0-critical"}, {"name": "seq:1"}]},
            {"number": 30, "title": "b", "createdAt": "", "labels": [
                {"name": "group:step-1"}, {"name": "P1-high"}, {"name": "seq:2"}]},
            {"number": 40, "title": "c", "createdAt": "", "labels": [
                {"name": "group:step-1"}, {"name": "P2-medium"}]},  # NO_SEQ drift
        ]
        monkeypatch.setattr(qm, "get_open_issues", lambda: issues)
        called = {"apply": 0}
        monkeypatch.setattr(qm, "_apply_group_plan", lambda *a, **k: called.__setitem__("apply", called["apply"] + 1))

        args = type("A", (), {"group": None, "all_groups": False, "apply": False})()
        qm.cmd_reconcile(args)
        out = capsys.readouterr().out
        assert "OBSERVE-ONLY" in out
        assert called["apply"] == 0
        assert "#40" in out and "NO_SEQ" in out

    def test_apply_mode_invokes_plan_writer(self, capsys, monkeypatch):
        issues = [
            {"number": 10, "title": "a", "createdAt": "", "labels": [
                {"name": "group:step-1"}, {"name": "P0-critical"}, {"name": "seq:1"}]},
            {"number": 40, "title": "c", "createdAt": "", "labels": [
                {"name": "group:step-1"}, {"name": "P2-medium"}]},
        ]
        monkeypatch.setattr(qm, "get_open_issues", lambda: issues)
        seen = {}
        monkeypatch.setattr(qm, "_apply_group_plan",
                            lambda grp, plan: seen.update(grp=grp, plan=plan))
        args = type("A", (), {"group": None, "all_groups": False, "apply": True})()
        qm.cmd_reconcile(args)
        assert seen["grp"] == "step-1"
        assert any(m["number"] == 40 for m in seen["plan"]["mutations"])


class TestCmdAllocateGuards:
    """allocate() idempotence guards (AC: no duplicate seq, no manual --seq)."""

    def test_no_group_is_noop(self, capsys, monkeypatch):
        monkeypatch.setattr(qm, "_fetch_single_issue_meta", lambda n: meta(9, group=None))
        args = type("A", (), {"issue": 9})()
        qm.cmd_allocate(args)
        assert "no group" in capsys.readouterr().out

    def test_existing_seq_is_noop(self, capsys, monkeypatch):
        monkeypatch.setattr(qm, "_fetch_single_issue_meta", lambda n: meta(9, seq=2))
        args = type("A", (), {"issue": 9})()
        qm.cmd_allocate(args)
        assert "no-op" in capsys.readouterr().out

    def test_missing_issue_fails_closed(self, monkeypatch, capsys):
        monkeypatch.setattr(qm, "_fetch_single_issue_meta", lambda n: None)
        monkeypatch.setattr(qm.time, "sleep", lambda s: None)
        args = type("A", (), {"issue": 9})()
        with pytest.raises(SystemExit) as exc:
            qm.cmd_allocate(args)
        assert exc.value.code == 1


class TestVerifyClaimRestFallback:
    """#4110 (defect class: eventually-consistent search where correctness
    requires REST): verify-claim must not fail closed when the universe fetch
    misses a LIVE issue inside the index-lag window — the single-issue REST
    fallback is the authoritative re-check."""

    def test_not_in_universe_but_rest_open_passes(self, capsys, monkeypatch):
        # Universe fetch (stubbed) omits the issue entirely — lag window.
        monkeypatch.setattr(qm, "get_open_issues", lambda: [])
        # REST single-issue endpoint confirms it is open & unconstrained.
        monkeypatch.setattr(qm, "_fetch_single_issue_meta", lambda n: meta(4088, group=None))
        args = type("A", (), {"issue": 4088})()
        with pytest.raises(SystemExit) as exc:  # PASS path exits 0
            qm.cmd_verify_claim(args)
        assert exc.value.code == 0
        assert "PASS" in capsys.readouterr().out

    def test_not_found_anywhere_fails_closed(self, monkeypatch, capsys):
        # REST-confirmed closed/missing → fail closed with the TRUE reason.
        monkeypatch.setattr(qm, "get_open_issues", lambda: [])
        monkeypatch.setattr(qm, "_fetch_single_issue_meta", lambda n: None)
        args = type("A", (), {"issue": 4088})()
        with pytest.raises(SystemExit) as exc:
            qm.cmd_verify_claim(args)
        assert exc.value.code == 1
        assert "not found or closed" in capsys.readouterr().err

    def test_universe_hit_keeps_precedence_no_rest_call(self, capsys, monkeypatch):
        # When the universe fetch DOES see the issue, REST fallback is not consulted.
        calls = {"rest": 0}

        def _spy(n):
            calls["rest"] += 1
            return None

        raw = {"number": 7, "title": "x", "createdAt": "", "labels": [
            {"name": "P2-medium"}]}  # universe holds RAW issues (parse shape)
        monkeypatch.setattr(qm, "get_open_issues", lambda: [raw])
        monkeypatch.setattr(qm, "_fetch_single_issue_meta", _spy)
        args = type("A", (), {"issue": 7})()
        with pytest.raises(SystemExit) as exc:  # PASS path exits 0
            qm.cmd_verify_claim(args)
        assert exc.value.code == 0
        assert calls["rest"] == 0
        assert "PASS" in capsys.readouterr().out

    def test_single_fetch_accepts_graphql_case_state(self, monkeypatch):
        # #4110 regression: gh issue view reports state "OPEN" (GraphQL case);
        # the lowercase-only check returned None for EVERY live issue.
        monkeypatch.setattr(qm, "run_cmd", lambda cmd: (
            0, '{"number":4088,"title":"t","state":"OPEN","createdAt":"",'
               '"labels":[{"name":"P1-high"},{"name":"group:pipeline"}]}', ""))
        assert qm._fetch_single_issue_meta(4088) is not None
        monkeypatch.setattr(qm, "run_cmd", lambda cmd: (
            0, '{"number":4088,"title":"t","state":"CLOSED","createdAt":"",'
               '"labels":[]}', ""))
        assert qm._fetch_single_issue_meta(4088) is None
