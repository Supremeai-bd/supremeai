"""Unit tests for SupremeAI Auto-Sync Engine and Pre-Push Drift Protection."""

import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from scripts.git.auto_sync_main import (
    auto_sync_branch,
    get_current_branch,
    get_drift_status,
    is_working_tree_dirty,
)
from scripts.pre_push_hook import is_ref_deletion, check_regression_scanner


class TestAutoSyncMain(unittest.TestCase):
    """Test suite for branch auto-sync engine."""

    def test_get_current_branch(self):
        branch = get_current_branch()
        self.assertIsInstance(branch, str)
        self.assertTrue(len(branch) > 0)

    @patch("scripts.git.auto_sync_main.run_git")
    def test_get_drift_status_success(self, mock_run_git):
        # Mock rev-list behind=2, ahead=1
        mock_behind = MagicMock(returncode=0, stdout="2\n")
        mock_ahead = MagicMock(returncode=0, stdout="1\n")
        mock_run_git.side_effect = [mock_behind, mock_ahead]

        behind, ahead = get_drift_status("HEAD", "origin/main")
        self.assertEqual(behind, 2)
        self.assertEqual(ahead, 1)

    @patch("scripts.git.auto_sync_main.get_current_branch", return_value="agent-5")
    @patch("scripts.git.auto_sync_main.fetch_origin_main", return_value=True)
    @patch("scripts.git.auto_sync_main.get_drift_status", return_value=(0, 1))
    def test_auto_sync_already_up_to_date(self, mock_drift, mock_fetch, mock_branch):
        success, msg = auto_sync_branch(verbose=False)
        self.assertTrue(success)
        self.assertIn("up-to-date", msg)

    @patch("scripts.git.auto_sync_main.get_current_branch", return_value="agent-5")
    @patch("scripts.git.auto_sync_main.fetch_origin_main", return_value=True)
    @patch("scripts.git.auto_sync_main.get_drift_status")
    @patch("scripts.git.auto_sync_main.is_working_tree_dirty", return_value=False)
    @patch("scripts.git.auto_sync_main.run_git")
    def test_auto_sync_clean_merge(self, mock_run_git, mock_dirty, mock_drift, mock_fetch, mock_branch):
        # 1st call to drift: behind=3, ahead=0
        # 2nd call to drift: behind=0, ahead=1 (post merge)
        mock_drift.side_effect = [(3, 0), (0, 1)]
        mock_run_git.return_value = MagicMock(returncode=0, stdout="", stderr="")

        success, msg = auto_sync_branch(strategy="merge", verbose=False)
        self.assertTrue(success)
        self.assertIn("Successfully synced", msg)


class TestPrePushHookDriftProtection(unittest.TestCase):
    """Test suite for pre-push hook protections."""

    def test_is_ref_deletion_not_blocking(self):
        # Should return boolean without blocking or raising exception
        res = is_ref_deletion()
        self.assertIn(res, [True, False])

    @patch("scripts.pre_push_hook.get_changed_files", return_value=[".github/workflows/test.yml"])
    def test_check_regression_scanner_skips_when_no_backend_files(self, mock_changed):
        res = check_regression_scanner()
        self.assertTrue(res)


if __name__ == "__main__":
    unittest.main()
