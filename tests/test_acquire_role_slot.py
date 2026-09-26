"""Tests for scripts/agents/acquire_role_slot.py.

Verifies:
1. Role inference from explicit args, issue labels, and task text descriptions.
2. Occupancy evaluation against open PRs, in-progress issue claims, and mesh heartbeats.
3. Sequential slot allocation (empty slot selection or N+1 expansion).
4. CLI interaction modes (dry-run, json format).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.agents.acquire_role_slot import (
    SlotStatus,
    checkout_slot_branch,
    evaluate_slot_occupancy,
    find_next_available_slot,
    infer_role_from_context,
    main,
)


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
    def test_first_slot_empty(self, mock_branches, mock_heartbeats, mock_issues, mock_prs):
        mock_prs.return_value = set()
        mock_issues.return_value = {}
        mock_heartbeats.return_value = set()
        mock_branches.return_value = [1, 2]

        slot = find_next_available_slot(role="coder")
        assert slot.index == 1
        assert slot.branch_name == "coder-1"
        assert slot.is_occupied is False

    @patch("scripts.agents.acquire_role_slot.fetch_open_prs_head_branches")
    @patch("scripts.agents.acquire_role_slot.fetch_in_progress_issues_by_slot")
    @patch("scripts.agents.acquire_role_slot.fetch_active_mesh_heartbeats")
    @patch("scripts.agents.acquire_role_slot.fetch_existing_role_branches")
    def test_first_slot_busy_selects_second(self, mock_branches, mock_heartbeats, mock_issues, mock_prs):
        mock_prs.return_value = {"coder-1"}
        mock_issues.return_value = {}
        mock_heartbeats.return_value = set()
        mock_branches.return_value = [1, 2]

        slot = find_next_available_slot(role="coder")
        assert slot.index == 2
        assert slot.branch_name == "coder-2"
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

    @patch("scripts.agents.acquire_role_slot.fetch_open_prs_head_branches")
    @patch("scripts.agents.acquire_role_slot.fetch_in_progress_issues_by_slot")
    @patch("scripts.agents.acquire_role_slot.fetch_active_mesh_heartbeats")
    @patch("scripts.agents.acquire_role_slot.fetch_existing_role_branches")
    def test_no_existing_branches_defaults_to_slot_1(self, mock_branches, mock_heartbeats, mock_issues, mock_prs):
        mock_prs.return_value = set()
        mock_issues.return_value = {}
        mock_heartbeats.return_value = set()
        mock_branches.return_value = []

        slot = find_next_available_slot(role="planner")
        assert slot.index == 1
        assert slot.branch_name == "planner-1"
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

        with patch("sys.argv", ["acquire_role_slot.py", "--role", "planner", "--dry-run", "--format", "json"]):
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
