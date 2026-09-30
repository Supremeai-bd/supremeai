"""Tests for scripts/agents/acquire_role_slot.py.

Verifies:
1. Role inference from explicit args, issue labels, and task text descriptions.
2. Occupancy evaluation against open PRs, in-progress issue claims, and mesh heartbeats.
3. Sequential slot allocation (empty slot selection or N+1 expansion).
4. CLI interaction modes (dry-run, json format).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.agents.acquire_role_slot import (
    SlotStatus,
    checkout_slot_branch,
    evaluate_slot_occupancy,
    find_next_available_slot,
    find_next_unclaimed_issue,
    infer_role_from_context,
    main,
    GroupCooldownManager,
    group_has_active_branch,
    sync_have_branch_labels_for_group,
    GROUP_COOLDOWN_SECONDS,
)
from scripts.agents.acquire_role_slot import ROOT_DIR


class TestInferRoleFromContext:
    def test_explicit_roles(self):
        assert infer_role_from_context(explicit_role="planner") == "planner"
        assert infer_role_from_context(explicit_role="coder") == "coder"
        assert infer_role_from_context(explicit_role="pr-helper") == "pr-helper"
        assert infer_role_from_context(explicit_role="ci") == "ci"
        assert infer_role_from_context(explicit_role="platform") == "platform"

    def test_explicit_role_variants(self):
        assert infer_role_from_context(explicit_role="planning") == "planner"
        assert infer_role_from_context(explicit_role="solver") == "coder"
        assert infer_role_from_context(explicit_role="ci/cd") == "ci"
        assert infer_role_from_context(explicit_role="platform-sweeper") == "platform"
        assert infer_role_from_context(explicit_role="pr") == "pr-helper"

    def test_infer_from_labels(self):
        assert infer_role_from_context(labels=["role:planner"]) == "planner"
        assert infer_role_from_context(labels=["handoff:ci"]) == "ci"
        assert infer_role_from_context(labels=["infrastructure", "platform"]) == "platform"
        assert infer_role_from_context(labels=["pr-helper", "merge-gate"]) == "pr-helper"
        assert infer_role_from_context(labels=["bug", "feature"]) == "coder"

    def test_infer_from_text(self):
        assert infer_role_from_context(title="Architecture gap-analysis and backlog planning") == "planner"
        assert infer_role_from_context(title="Fix broken github-actions workflow pipeline") == "ci"
        assert infer_role_from_context(title="Supabase health sweep and redis connection check") == "platform"
        assert infer_role_from_context(title="Consolidate open PRs into merge train rollup") == "pr-helper"
        assert infer_role_from_context(title="Implement zero-cost streaming agent loop") == "coder"

    def test_fallback_to_coder(self):
        assert infer_role_from_context(title="Random unknown thing without keywords") == "coder"
        assert infer_role_from_context() == "coder"


class TestEvaluateSlotOccupancy:
    def test_empty_slot(self):
        status = evaluate_slot_occupancy(
            role="coder",
            index=1,
            open_pr_branches=set(),
            busy_issue_slots={},
            active_heartbeats=set(),
        )
        assert status.is_occupied is False
        assert status.branch_name == "coder-1"
        assert status.occupancy_reason == ""

    def test_occupied_by_open_pr(self):
        status = evaluate_slot_occupancy(
            role="coder",
            index=1,
            open_pr_branches={"coder-1"},
            busy_issue_slots={},
            active_heartbeats=set(),
        )
        assert status.is_occupied is True
        assert "open PR" in status.occupancy_reason

    def test_occupied_by_in_progress_issue(self):
        status = evaluate_slot_occupancy(
            role="planner",
            index=2,
            open_pr_branches=set(),
            busy_issue_slots={"planner-2": 1690},
            active_heartbeats=set(),
        )
        assert status.is_occupied is True
        assert "#1690" in status.occupancy_reason

    def test_occupied_by_mesh_heartbeat(self):
        status = evaluate_slot_occupancy(
            role="platform",
            index=1,
            open_pr_branches=set(),
            busy_issue_slots={},
            active_heartbeats={"platform-1"},
        )
        assert status.is_occupied is True
        assert "heartbeat" in status.occupancy_reason


class TestFindNextAvailableSlot:
    @patch("scripts.agents.acquire_role_slot.fetch_open_prs_head_branches")
    @patch("scripts.agents.acquire_role_slot.fetch_in_progress_issues_by_slot")
    @patch("scripts.agents.acquire_role_slot.fetch_active_mesh_heartbeats")
    @patch("scripts.agents.acquire_role_slot.fetch_existing_role_branches")
    def test_no_existing_branches_defaults_to_slot_1(self, mock_branches, mock_heartbeats, mock_issues, mock_prs):
        mock_prs.return_value = set()
        mock_issues.return_value = {}
        mock_heartbeats.return_value = set()
        mock_branches.return_value = []

        slot = find_next_available_slot(role="coder")
        assert slot.index == 1
        assert slot.branch_name == "coder-1"
        assert slot.is_occupied is False

    @patch("scripts.agents.acquire_role_slot.fetch_open_prs_head_branches")
    @patch("scripts.agents.acquire_role_slot.fetch_in_progress_issues_by_slot")
    @patch("scripts.agents.acquire_role_slot.fetch_active_mesh_heartbeats")
    @patch("scripts.agents.acquire_role_slot.fetch_existing_role_branches")
    def test_branches_1_and_2_busy_selects_slot_3(self, mock_branches, mock_heartbeats, mock_issues, mock_prs):
        mock_prs.return_value = set()
        mock_issues.return_value = {}
        mock_heartbeats.return_value = set()
        mock_branches.return_value = [1, 2]

        slot = find_next_available_slot(role="coder")
        assert slot.index == 3
        assert slot.branch_name == "coder-3"
        assert slot.is_occupied is False

    @patch("scripts.agents.acquire_role_slot.fetch_open_prs_head_branches")
    @patch("scripts.agents.acquire_role_slot.fetch_in_progress_issues_by_slot")
    @patch("scripts.agents.acquire_role_slot.fetch_active_mesh_heartbeats")
    @patch("scripts.agents.acquire_role_slot.fetch_existing_role_branches")
    def test_gap_allocation_selects_missing_slot_2(self, mock_branches, mock_heartbeats, mock_issues, mock_prs):
        # Gap: slot 1 and 3 are present, slot 2 was merged/deleted
        mock_prs.return_value = set()
        mock_issues.return_value = {}
        mock_heartbeats.return_value = set()
        mock_branches.return_value = [1, 3]

        slot = find_next_available_slot(role="coder")
        assert slot.index == 2
        assert slot.branch_name == "coder-2"
        assert slot.is_occupied is False

    @patch("scripts.agents.acquire_role_slot.fetch_open_prs_head_branches")
    @patch("scripts.agents.acquire_role_slot.fetch_in_progress_issues_by_slot")
    @patch("scripts.agents.acquire_role_slot.fetch_active_mesh_heartbeats")
    @patch("scripts.agents.acquire_role_slot.fetch_existing_role_branches")
    def test_branch_name_with_issue_and_slug(self, mock_branches, mock_heartbeats, mock_issues, mock_prs):
        mock_prs.return_value = set()
        mock_issues.return_value = {}
        mock_heartbeats.return_value = set()
        mock_branches.return_value = [1]

        slot = find_next_available_slot(
            role="coder",
            issue=2275,
            title="chore(cleanup): [Step-2.2] retire in-memory swarm orchestrator",
        )
        assert slot.index == 2
        assert slot.branch_name == "coder-2-2275-retire-in-memory-swarm"
        assert slot.is_occupied is False

    @patch("scripts.agents.acquire_role_slot.fetch_open_prs_head_branches")
    @patch("scripts.agents.acquire_role_slot.fetch_in_progress_issues_by_slot")
    @patch("scripts.agents.acquire_role_slot.fetch_active_mesh_heartbeats")
    @patch("scripts.agents.acquire_role_slot.fetch_existing_role_branches")
    def test_all_existing_slots_busy_creates_n_plus_one(self, mock_branches, mock_heartbeats, mock_issues, mock_prs):
        mock_prs.return_value = {"coder-1", "coder-2"}
        mock_issues.return_value = {"coder-3": 1700}
        mock_heartbeats.return_value = set()
        mock_branches.return_value = [1, 2, 3]

        slot = find_next_available_slot(role="coder")
        assert slot.index == 4
        assert slot.branch_name == "coder-4"
        assert slot.is_occupied is False


class TestCheckoutSlotBranch:
    @patch("subprocess.run")
    def test_checkout_slot_branch_success(self, mock_subproc):
        mock_subproc.return_value = MagicMock(returncode=0)
        assert checkout_slot_branch("coder-1") is True
        assert mock_subproc.call_count == 2

    @patch("subprocess.run", side_effect=Exception("Git fetch failed"))
    def test_checkout_slot_branch_failure(self, mock_subproc):
        assert checkout_slot_branch("coder-1") is False


class TestMainCli:
    @patch("scripts.agents.acquire_role_slot.find_next_available_slot")
    def test_main_dry_run_json(self, mock_find, capsys):
        mock_find.return_value = SlotStatus(
            role="planner",
            index=3,
            branch_name="planner-3",
            is_occupied=False,
            occupancy_reason="",
        )

        with patch("sys.argv", ["acquire_role_slot.py", "--role", "planner", "--issue", "999", "--dry-run", "--format", "json"]):
            code = main()

        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["role"] == "planner"
        assert data["slot_index"] == 3
        assert data["branch_name"] == "planner-3"
        assert data["checkout_performed"] is False

    @patch("scripts.agents.acquire_role_slot.find_next_available_slot")
    def test_main_dry_run_text(self, mock_find, capsys):
        mock_find.return_value = SlotStatus(
            role="ci",
            index=1,
            branch_name="ci-1",
            is_occupied=False,
            occupancy_reason="",
        )

        with patch("sys.argv", ["acquire_role_slot.py", "--task", "Fix CI actions", "--dry-run"]):
            code = main()

        assert code == 0
        captured = capsys.readouterr()
        assert "Assigned Role:   ci" in captured.out
        assert "Acquired Slot:   ci-1" in captured.out
        assert "Dry Run" in captured.out


class TestFindNextUnclaimedIssue:
    @patch("subprocess.run")
    def test_find_next_unclaimed_priority_order(self, mock_subproc):
        mock_issues = [
            {"number": 101, "title": "P3 issue", "labels": [{"name": "P3-low"}, {"name": "handoff:coder"}], "createdAt": "2026-09-01T00:00:00Z"},
            {"number": 102, "title": "In progress issue", "labels": [{"name": "status:in-progress"}, {"name": "P0-critical"}], "createdAt": "2026-09-02T00:00:00Z"},
            {"number": 103, "title": "Step 2 Seq 2", "labels": [{"name": "group:step-2"}, {"name": "seq:2"}, {"name": "handoff:coder"}], "createdAt": "2026-09-03T00:00:00Z"},
            {"number": 104, "title": "P0 Critical blocker", "labels": [{"name": "P0-critical"}, {"name": "handoff:coder"}], "createdAt": "2026-09-04T00:00:00Z"},
        ]
        mock_subproc.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_issues))

        top = find_next_unclaimed_issue(role="coder")
        assert top is not None
        assert top["number"] == 104
        assert top["title"] == "P0 Critical blocker"

    @patch("subprocess.run")
    def test_find_next_unclaimed_seq_order(self, mock_subproc):
        mock_issues = [
            {"number": 201, "title": "Step 2 Seq 3", "labels": [{"name": "group:step-2"}, {"name": "seq:3"}, {"name": "handoff:coder"}], "createdAt": "2026-09-01T00:00:00Z"},
            {"number": 202, "title": "Step 2 Seq 2", "labels": [{"name": "group:step-2"}, {"name": "seq:2"}, {"name": "handoff:coder"}], "createdAt": "2026-09-02T00:00:00Z"},
        ]
        mock_subproc.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_issues))

        top = find_next_unclaimed_issue(role="coder")
        assert top is not None
        assert top["number"] == 202
        assert top["title"] == "Step 2 Seq 2"

    @patch("scripts.agents.acquire_role_slot.load_group_dependencies")
    @patch("subprocess.run")
    def test_find_next_unclaimed_predecessor_group_hold(self, mock_subproc, mock_deps):
        mock_deps.return_value = {"foundation-closeout": "pipeline-governance"}
        mock_issues = [
            {"number": 301, "title": "Foundation seq 1", "labels": [{"name": "group:foundation-closeout"}, {"name": "seq:1"}, {"name": "handoff:coder"}], "createdAt": "2026-09-01T00:00:00Z"},
            {"number": 302, "title": "Pipeline seq 4", "labels": [{"name": "group:pipeline-governance"}, {"name": "seq:4"}, {"name": "handoff:coder"}], "createdAt": "2026-09-02T00:00:00Z"},
        ]
        mock_subproc.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_issues))

        top = find_next_unclaimed_issue(role="coder")
        assert top is not None
        # Pipeline governance is predecessor to foundation-closeout, so pipeline governance MUST be picked first!
        assert top["number"] == 302
        assert top["title"] == "Pipeline seq 4"


class TestGroupCooldownManager:
    @patch("scripts.agents.acquire_role_slot.time.time")
    def test_record_and_block_when_other_agents_exist(self, mock_time):
        mgr = GroupCooldownManager.__new__(GroupCooldownManager)
        mgr.state_file = Path("/tmp/nonexistent-cooldown.json")
        mgr.state = {}
        now = 1700000000.0
        mock_time.return_value = now
        mgr.state["group-a"] = {
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "issue_number": 100,
            "agent_name": "agent-1",
        }
        mock_time.return_value = now + 1
        blocked, remaining = mgr.is_blocked("group-a", "agent-1", 3)
        assert blocked is True
        assert 0 <= remaining <= GROUP_COOLDOWN_SECONDS

    @patch("scripts.agents.acquire_role_slot.time.time")
    def test_bypass_when_single_agent(self, mock_time):
        mgr = GroupCooldownManager.__new__(GroupCooldownManager)
        mgr.state_file = Path("/tmp/nonexistent-cooldown.json")
        mgr.state = {}
        now = 1700000000.0
        mock_time.return_value = now
        mgr.state["group-a"] = {
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "issue_number": 100,
            "agent_name": "agent-1",
        }
        blocked, _ = mgr.is_blocked("group-a", "agent-1", 1)
        assert blocked is False

    @patch("scripts.agents.acquire_role_slot.time.time")
    def test_bypass_for_different_agent(self, mock_time):
        mgr = GroupCooldownManager.__new__(GroupCooldownManager)
        mgr.state_file = Path("/tmp/nonexistent-cooldown.json")
        mgr.state = {}
        now = 1700000000.0
        mock_time.return_value = now
        mgr.state["group-a"] = {
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "issue_number": 100,
            "agent_name": "agent-1",
        }
        blocked, _ = mgr.is_blocked("group-a", "agent-2", 2)
        assert blocked is False

    def test_expiry_clears_cooldown(self):
        mgr = GroupCooldownManager.__new__(GroupCooldownManager)
        mgr.state_file = Path("/tmp/nonexistent-cooldown.json")
        mgr.state = {}
        past_ts = time.time() - (GROUP_COOLDOWN_SECONDS + 10)
        mgr.state["group-a"] = {
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(past_ts)),
            "issue_number": 100,
            "agent_name": "agent-1",
        }
        blocked, _ = mgr.is_blocked("group-a", "agent-1", 2)
        assert blocked is False
        assert "group-a" not in mgr.state


class TestHaveBranchTracking:
    @patch("subprocess.run")
    def test_group_has_active_branch_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc1234 refs/heads/group/pipeline-governance\n")
        assert group_has_active_branch(ROOT_DIR, "pipeline-governance") is True

    @patch("subprocess.run")
    def test_group_has_active_branch_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert group_has_active_branch(ROOT_DIR, "pipeline-governance") is False

    @patch("scripts.agents.acquire_role_slot.group_has_active_branch")
    @patch("subprocess.run")
    def test_sync_have_branch_labels_adds_when_branch_exists(self, mock_run, mock_has_branch):
        mock_has_branch.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([{"number": 10}, {"number": 11}]))
        sync_have_branch_labels_for_group(ROOT_DIR, "step-1")
        add_calls = [c for c in mock_run.call_args_list if "--add-label" in str(c)]
        assert len(add_calls) >= 2

    @patch("scripts.agents.acquire_role_slot.group_has_active_branch")
    @patch("subprocess.run")
    def test_sync_have_branch_labels_removes_when_branch_gone(self, mock_run, mock_has_branch):
        mock_has_branch.return_value = False
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([{"number": 10}]))
        sync_have_branch_labels_for_group(ROOT_DIR, "step-1")
        remove_calls = [c for c in mock_run.call_args_list if "--remove-label" in str(c)]
        assert len(remove_calls) >= 1


# ═══════════════════════════════════════════════════════════════════════
# #2745 — নির্বাচন-স্তরের admin-approval ফিল্টার
# ═══════════════════════════════════════════════════════════════════════

class TestAdminApprovalSelectionFilter:
    """`gate:admin-approval` লেবেলযুক্ত ইস্যু অনুমোদন ছাড়া claimable হতে পারবে না।"""

    def _issues(self):
        return [
            {
                "number": 1,
                "title": "routine bugfix",
                "body": "",
                "labels": [{"name": "P2-medium"}, {"name": "handoff:coder"}],
                "createdAt": "2026-09-30T10:00:00Z",
            },
            {
                "number": 2,
                "title": "drop production database",
                "body": "",
                "labels": [
                    {"name": "P0-critical"},
                    {"name": "handoff:coder"},
                    {"name": "gate:admin-approval"},
                ],
                "createdAt": "2026-09-30T09:00:00Z",
            },
            {
                "number": 3,
                "title": "rotate master secrets",
                "body": "",
                "labels": [
                    {"name": "P1-high"},
                    {"name": "handoff:coder"},
                    {"name": "gate:admin-approval"},
                    {"name": "approved-by:admin"},
                ],
                "createdAt": "2026-09-30T08:00:00Z",
            },
        ]

    def test_gated_unapproved_issue_is_skipped(self, monkeypatch, tmp_path):
        from scripts.agents import acquire_role_slot as ars

        def fake_subprocess_run(cmd, **kwargs):
            import json as _json
            import types

            if "issue" in cmd and "list" in cmd:
                return types.SimpleNamespace(
                    returncode=0, stdout=_json.dumps(self._issues())
                )
            if cmd[:2] == ["git", "ls-remote"]:
                return types.SimpleNamespace(returncode=0, stdout="")
            raise AssertionError(f"unexpected cmd: {cmd}")

        monkeypatch.setattr(ars.subprocess, "run", fake_subprocess_run)
        result = ars.find_next_unclaimed_issue(role="coder", repo_dir=tmp_path)
        # গেটেড-অনুমোদনহীন #2 (P0-critical!) স্কিপ হয়েছে — এমনকি P0-ও গেট ভাঙতে
        # পারে না; অনুমোদিত P1 #3-ই প্রাধান্য-ক্রমে বাছাই (P1 > P2)
        assert result is not None
        assert result.get("number") == 3
        assert result.get("number") != 2

    def test_approved_gated_issue_is_claimable(self, monkeypatch, tmp_path):
        from scripts.agents import acquire_role_slot as ars

        approved_only = [self._issues()[2]]  # approved-by:admin সহ

        def fake_subprocess_run(cmd, **kwargs):
            import json as _json
            import types

            if "issue" in cmd and "list" in cmd:
                return types.SimpleNamespace(
                    returncode=0, stdout=_json.dumps(approved_only)
                )
            if cmd[:2] == ["git", "ls-remote"]:
                return types.SimpleNamespace(returncode=0, stdout="")
            raise AssertionError(f"unexpected cmd: {cmd}")

        monkeypatch.setattr(ars.subprocess, "run", fake_subprocess_run)
        result = ars.find_next_unclaimed_issue(role="coder", repo_dir=tmp_path)
        assert result is not None
        assert result.get("number") == 3
