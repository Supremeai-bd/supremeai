#!/usr/bin/env python3
"""Contract tests for Persistent Branch Workflow (#4200).

বাংলা সারসংক্ষেপ:
------------------
#4200-র acceptance criteria-র জন্য contract tests:
  1. Branch state labels exist and are valid
  2. mark_branch_state transitions are correct
  3. MutationLease acquire/release works
  4. cleanup safety preserves active/paused/orphaned branches
  5. Branch discovery finds existing branches
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci.mark_branch_state import (
    VALID_STATES,
    STATE_LABELS,
    ALL_BRANCH_LABELS,
    mark_branch_state,
    discover_branch,
)
from scripts.ci.mutation_lease import MutationLease
from scripts.ci.cleanup_stale_branches import (
    PRESERVE_LABELS,
    extract_issue_number,
    is_branch_safe_to_delete,
)


class TestBranchStateLabels(unittest.TestCase):
    """Test #4200 §1: branch state labels exist and are valid."""

    def test_all_four_states_defined(self):
        """All 4 states from #4200 §2 are defined."""
        self.assertEqual(len(VALID_STATES), 4)
        self.assertIn("active", VALID_STATES)
        self.assertIn("paused", VALID_STATES)
        self.assertIn("orphaned", VALID_STATES)
        self.assertIn("ready", VALID_STATES)

    def test_state_labels_mapping(self):
        """Each state maps to correct label name."""
        self.assertEqual(STATE_LABELS["active"], "branch:active")
        self.assertEqual(STATE_LABELS["paused"], "branch:paused")
        self.assertEqual(STATE_LABELS["orphaned"], "branch:orphaned")
        self.assertEqual(STATE_LABELS["ready"], "branch:ready")

    def test_all_labels_in_set(self):
        """All branch labels are in ALL_BRANCH_LABELS set."""
        self.assertEqual(len(ALL_BRANCH_LABELS), 4)
        self.assertIn("branch:active", ALL_BRANCH_LABELS)
        self.assertIn("branch:paused", ALL_BRANCH_LABELS)
        self.assertIn("branch:orphaned", ALL_BRANCH_LABELS)
        self.assertIn("branch:ready", ALL_BRANCH_LABELS)


class TestBranchStateTransitions(unittest.TestCase):
    """Test #4200 §2: state transitions via mark_branch_state."""

    @patch("scripts.ci.mark_branch_state.get_gh_token", return_value="fake-token")
    @patch("scripts.ci.mark_branch_state.api_call")
    def test_mark_active_removes_old_labels(self, mock_api, mock_token):
        """Marking active removes old branch:* labels and adds branch:active."""
        # Mock: issue has branch:paused label
        mock_api.side_effect = [
            {"labels": [{"name": "branch:paused"}, {"name": "P1-high"}]},  # GET issue
            {},  # DELETE branch:paused
            {},  # POST add branch:active
            {},  # POST comment
        ]

        result = mark_branch_state(4200, "active", "agent/4200-test")
        self.assertTrue(result)

        # Verify DELETE was called for branch:paused
        calls = mock_api.call_args_list
        delete_calls = [c for c in calls if c.args[0] == "DELETE"]
        self.assertTrue(len(delete_calls) >= 1)

    @patch("scripts.ci.mark_branch_state.get_gh_token", return_value="fake-token")
    @patch("scripts.ci.mark_branch_state.api_call")
    def test_mark_ready_posts_comment(self, mock_api, mock_token):
        """Marking ready posts a comment with 'ready for PR' message."""
        mock_api.side_effect = [
            {"labels": []},  # GET issue (no branch labels)
            {},  # POST add branch:ready
            {},  # POST comment
        ]

        result = mark_branch_state(4200, "ready", "agent/4200-test")
        self.assertTrue(result)

    def test_invalid_state_rejected(self):
        """Invalid state returns False."""
        result = mark_branch_state(4200, "invalid", "agent/4200-test", token="fake")
        self.assertFalse(result)


class TestMutationLease(unittest.TestCase):
    """Test #4200 §6: mutation lease."""

    def test_acquire_succeeds_when_free(self):
        """Acquire succeeds when no existing lease."""
        with patch.object(MutationLease, "_load_leases", return_value={}):
            with patch.object(MutationLease, "_save_leases") as mock_save:
                lease = MutationLease("agent/4200-test", "coder-1")
                self.assertTrue(lease.acquire())
                self.assertTrue(lease.acquired)
                mock_save.assert_called_once()

    def test_acquire_fails_when_held_by_other(self):
        """Acquire fails when another agent holds a fresh lease."""
        import time
        with patch.object(MutationLease, "_load_leases", return_value={
            "agent/4200-test": {
                "agent_id": "other-agent",
                "acquired_at": time.time(),
                "state": "MUTATING",
            }
        }):
            lease = MutationLease("agent/4200-test", "coder-1")
            self.assertFalse(lease.acquire())

    def test_acquire_steals_stale_lease(self):
        """Acquire succeeds when existing lease is stale (> timeout)."""
        with patch.object(MutationLease, "_load_leases", return_value={
            "agent/4200-test": {
                "agent_id": "other-agent",
                "acquired_at": 0,  # epoch — very stale
                "state": "MUTATING",
            }
        }):
            with patch.object(MutationLease, "_save_leases"):
                lease = MutationLease("agent/4200-test", "coder-1", timeout=1)
                self.assertTrue(lease.acquire())

    def test_release_clears_lease(self):
        """Release clears the lease."""
        with patch.object(MutationLease, "_load_leases", return_value={}):
            with patch.object(MutationLease, "_save_leases"):
                lease = MutationLease("agent/4200-test", "coder-1")
                lease.acquire()
                lease.release()
                self.assertFalse(lease.acquired)

    def test_context_manager(self):
        """Context manager acquires and releases."""
        with patch.object(MutationLease, "_load_leases", return_value={}):
            with patch.object(MutationLease, "_save_leases"):
                with MutationLease("agent/4200-test", "coder-1") as lease:
                    self.assertTrue(lease.acquired)
                self.assertFalse(lease.acquired)


class TestCleanupSafety(unittest.TestCase):
    """Test #4200 §9: cleanup preserves active/paused/orphaned branches."""

    def test_preserve_labels_set(self):
        """PRESERVE_LABELS contains the right labels."""
        self.assertIn("branch:active", PRESERVE_LABELS)
        self.assertIn("branch:paused", PRESERVE_LABELS)
        self.assertIn("branch:orphaned", PRESERVE_LABELS)
        self.assertNotIn("branch:ready", PRESERVE_LABELS)

    def test_extract_issue_number_agent_pattern(self):
        """Extract issue from agent/<issue>-<slug> pattern."""
        self.assertEqual(extract_issue_number("agent/4200-persistent-branch"), 4200)
        self.assertEqual(extract_issue_number("agent/123-fix"), 123)

    def test_extract_issue_number_slot_pattern(self):
        """Extract issue from coder-1-4200-slug pattern."""
        self.assertEqual(extract_issue_number("coder-1-4200-slug"), 4200)

    def test_extract_issue_number_no_match(self):
        """Returns None when no issue number found."""
        self.assertIsNone(extract_issue_number("main"))
        self.assertIsNone(extract_issue_number("develop"))

    @patch("scripts.ci.cleanup_stale_branches.get_issue_labels")
    @patch("scripts.ci.cleanup_stale_branches.get_pr_merge_state")
    def test_safe_to_delete_needs_labels_and_merge_proof(self, mock_pr, mock_labels):
        """#4204 corrected contract: no preserve labels is NOT enough —
        deletion additionally requires merged/completed proof."""
        mock_labels.return_value = {"P1-high", "status:in-progress"}
        # proof unavailable (PR API fails) → fail-closed, preserve
        mock_pr.return_value = None
        self.assertFalse(is_branch_safe_to_delete("agent/4200-test", "fake-token"))
        # merged PR proof present → safe
        mock_pr.return_value = "merged"
        self.assertTrue(is_branch_safe_to_delete("agent/4200-test", "fake-token"))

    @patch("scripts.ci.cleanup_stale_branches.get_issue_labels")
    @patch("scripts.ci.cleanup_stale_branches.get_pr_merge_state")
    def test_not_safe_to_delete_when_active(self, mock_pr, mock_labels):
        """Branch is NOT safe to delete when issue has branch:active."""
        mock_labels.return_value = {"P1-high", "branch:active"}
        mock_pr.return_value = "merged"
        self.assertFalse(is_branch_safe_to_delete("agent/4200-test", "fake-token"))

    @patch("scripts.ci.cleanup_stale_branches.get_issue_labels")
    @patch("scripts.ci.cleanup_stale_branches.get_pr_merge_state")
    def test_not_safe_to_delete_when_paused(self, mock_pr, mock_labels):
        """Branch is NOT safe to delete when issue has branch:paused."""
        mock_labels.return_value = {"branch:paused"}
        mock_pr.return_value = "merged"
        self.assertFalse(is_branch_safe_to_delete("coder-1-4200-test", "fake-token"))

    @patch("scripts.ci.cleanup_stale_branches.get_issue_labels")
    @patch("scripts.ci.cleanup_stale_branches.get_pr_merge_state")
    def test_not_safe_to_delete_when_orphaned(self, mock_pr, mock_labels):
        """Branch is NOT safe to delete when issue has branch:orphaned."""
        mock_labels.return_value = {"branch:orphaned"}
        mock_pr.return_value = "merged"
        self.assertFalse(is_branch_safe_to_delete("agent/4200-test", "fake-token"))


class TestBranchDiscovery(unittest.TestCase):
    """Test #4200 §3: branch discovery for session-independent continuation."""

    @patch("subprocess.run")
    def test_discover_finds_existing_branch(self, mock_run):
        """discover_branch returns branch name when it exists."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123\trefs/heads/agent/4200-persistent-branch\n",
        )

        result = discover_branch(4200, "fake-token")
        self.assertEqual(result, "agent/4200-persistent-branch")

    @patch("subprocess.run")
    def test_discover_returns_none_when_no_branch(self, mock_run):
        """discover_branch returns None when no branch exists."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = discover_branch(4200, "fake-token")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
