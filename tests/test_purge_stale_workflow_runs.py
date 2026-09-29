"""
tests/test_purge_stale_workflow_runs.py
=======================================
Unit tests for scripts/ci/purge_stale_workflow_runs.py

# বাংলা মন্তব্য:
# এই টেস্ট স্যুটটি workflow run retention ইঞ্জিনের সমস্ত ফিল্টারিং ও নিরাপত্তা নীতি
# যাচাই করে, যেন প্রোডাকশন বা ওপেন PR-এর প্রয়োজনীয় রান সুরক্ষিত থাকে এবং অপ্রয়োজনীয়
# স্টেল রানগুলো সঠিকভাবে চিহ্নিত ও ডিলিট হয়।
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

# Dynamic import to avoid polluting root package
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "purge_stale_workflow_runs.py"
spec = importlib.util.spec_from_file_location("purge_stale_workflow_runs", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules["purge_stale_workflow_runs"] = module
spec.loader.exec_module(module)

is_run_stale = module.is_run_stale
parse_iso_datetime = module.parse_iso_datetime
purge_workflow_runs = module.purge_workflow_runs
write_step_summary = module.write_step_summary


class TestParseIsoDatetime:
    def test_parse_zulu(self):
        dt = parse_iso_datetime("2026-09-29T10:00:00Z")
        assert dt.year == 2026
        assert dt.month == 9
        assert dt.day == 29
        assert dt.tzinfo == timezone.utc

    def test_parse_offset(self):
        dt = parse_iso_datetime("2026-09-29T10:00:00+00:00")
        assert dt.hour == 10
        assert dt.tzinfo == timezone.utc


class TestIsRunStale:
    @pytest.fixture
    def now_dt(self):
        return datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)

    def test_in_progress_run_never_stale(self, now_dt):
        run = {
            "id": 101,
            "status": "in_progress",
            "head_branch": "feature-x",
            "created_at": "2026-09-20T00:00:00Z",
        }
        stale, reason = is_run_stale(run, now=now_dt, min_age_days=2)
        assert not stale
        assert "not completed" in reason

    def test_main_branch_never_stale(self, now_dt):
        run = {
            "id": 102,
            "status": "completed",
            "head_branch": "main",
            "created_at": "2026-09-20T00:00:00Z",
            "event": "schedule",
            "conclusion": "success",
        }
        stale, reason = is_run_stale(run, now=now_dt, min_age_days=2)
        assert not stale
        assert "head_branch 'main' is protected" in reason

    def test_protected_workflow_never_stale(self, now_dt):
        run = {
            "id": 103,
            "status": "completed",
            "head_branch": "release-v2",
            "name": "Production Preflight",
            "path": ".github/workflows/08-production-preflight.yml",
            "created_at": "2026-09-20T00:00:00Z",
            "event": "push",
            "conclusion": "success",
        }
        stale, reason = is_run_stale(run, now=now_dt, min_age_days=2)
        assert not stale
        assert "protected" in reason

    def test_recent_run_below_threshold_never_stale(self, now_dt):
        # Only 5 hours old
        run = {
            "id": 104,
            "status": "completed",
            "head_branch": "ci-test",
            "name": "Issue Ops (Queue Ledger & Labeler)",
            "created_at": "2026-09-29T07:00:00Z",
            "event": "schedule",
            "conclusion": "success",
        }
        stale, reason = is_run_stale(run, now=now_dt, min_age_days=2)
        assert not stale
        assert "below threshold" in reason

    def test_old_schedule_success_is_stale(self, now_dt):
        # 5 days old scheduled run
        run = {
            "id": 105,
            "status": "completed",
            "head_branch": "",
            "name": "Issue Ops (Queue Ledger & Labeler)",
            "created_at": "2026-09-24T00:00:00Z",
            "event": "schedule",
            "conclusion": "success",
        }
        stale, reason = is_run_stale(run, now=now_dt, min_age_days=2)
        assert stale
        assert "scheduled routine run" in reason

    def test_cancelled_run_on_feature_branch_is_stale(self, now_dt):
        # 3 days old cancelled run
        run = {
            "id": 106,
            "status": "completed",
            "head_branch": "coder-1-2400-fix",
            "name": "PR Gate",
            "created_at": "2026-09-25T00:00:00Z",
            "event": "pull_request",
            "conclusion": "cancelled",
        }
        stale, reason = is_run_stale(run, now=now_dt, min_age_days=2)
        assert stale
        assert "cancelled/skipped run" in reason

    def test_pr_success_run_is_stale(self, now_dt):
        # 3 days old successful PR run on feature branch
        run = {
            "id": 107,
            "status": "completed",
            "head_branch": "coder-2-2401-feature",
            "name": "PR Gate",
            "created_at": "2026-09-25T00:00:00Z",
            "event": "pull_request",
            "conclusion": "success",
        }
        stale, reason = is_run_stale(run, now=now_dt, min_age_days=2)
        assert stale
        assert "completed pull_request run" in reason

    def test_active_pr_failure_kept(self, now_dt):
        # Failure on PR branch should NOT be deleted if not old enough or to keep debug logs
        run = {
            "id": 108,
            "status": "completed",
            "head_branch": "coder-3-debug-branch",
            "name": "PR Gate",
            "created_at": "2026-09-27T00:00:00Z",
            "event": "pull_request",
            "conclusion": "failure",
        }
        stale, reason = is_run_stale(run, now=now_dt, min_age_days=2)
        assert not stale
        assert "run kept" in reason


class TestPurgeWorkflowRuns:
    def test_dry_run_does_not_call_delete(self):
        sample_runs = [
            {
                "id": 201,
                "status": "completed",
                "head_branch": "feature-abc",
                "name": "CI Run",
                "created_at": "2026-09-20T00:00:00Z",
                "event": "pull_request",
                "conclusion": "success",
            },
            {
                "id": 202,
                "status": "completed",
                "head_branch": "main",
                "name": "Production Deploy",
                "created_at": "2026-09-20T00:00:00Z",
                "event": "push",
                "conclusion": "success",
            },
        ]

        with patch("purge_stale_workflow_runs.delete_single_run") as mock_delete:
            summary = purge_workflow_runs(
                repo="SaifulHaqueNiloy/supremeai",
                token="mock_token",
                min_age_days=2,
                dry_run=True,
                runs_override=sample_runs,
            )
            mock_delete.assert_not_called()
            assert summary["eligible"] == 1
            assert summary["deleted"] == 1
            assert summary["skipped"] == 1
            assert summary["dry_run"] is True

    def test_max_deletions_cap(self):
        sample_runs = [
            {
                "id": i,
                "status": "completed",
                "head_branch": f"feature-{i}",
                "name": "CI Run",
                "created_at": "2026-09-20T00:00:00Z",
                "event": "pull_request",
                "conclusion": "success",
            }
            for i in range(10)
        ]

        summary = purge_workflow_runs(
            repo="SaifulHaqueNiloy/supremeai",
            token="mock_token",
            min_age_days=2,
            max_deletions=3,
            dry_run=True,
            runs_override=sample_runs,
        )
        assert summary["eligible"] == 10
        assert summary["deleted"] == 3


class TestWriteStepSummary:
    def test_writes_formatted_markdown(self, tmp_path):
        summary_file = tmp_path / "step_summary.md"
        stats = {
            "scanned": 50,
            "eligible": 12,
            "deleted": 12,
            "skipped": 38,
            "errors": 0,
            "dry_run": False,
        }
        write_step_summary(stats, summary_file=str(summary_file))
        assert summary_file.exists()
        content = summary_file.read_text(encoding="utf-8")
        assert "Nightly Workflow Runs Retention Report" in content
        assert "| **Runs Deleted** | `12` |" in content
        assert "LIVE PURGE" in content
