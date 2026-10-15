"""Regression and contract tests for Schedule Watchdog workflow and runner.

Covers:
1. schedule-watchdog.yml trigger and execution condition contract:
   - Must trigger on completed workflow_run of watched workflows.
   - Job condition must NOT restrict workflow_run to conclusion == 'success'
     (so that failed watched workflows like Bridge Intake still trigger the watchdog).
2. scripts/ci/schedule_watchdog.py cron parsing and next-due calculations.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import unittest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "schedule-watchdog.yml"


class TestScheduleWatchdogContract(unittest.TestCase):
    def test_workflow_file_exists(self):
        self.assertTrue(WORKFLOW_FILE.is_file(), f"Missing workflow file: {WORKFLOW_FILE}")

    def test_job_condition_allows_failed_workflow_runs(self):
        with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        jobs = data.get("jobs", {})
        self.assertIn("watchdog", jobs, "Missing 'watchdog' job in workflow")
        watchdog_job = jobs["watchdog"]

        condition = watchdog_job.get("if", "")
        self.assertIsInstance(condition, str)

        # Must NOT require conclusion == 'success' (the bug from failed Bridge Intake run #38494896681)
        self.assertNotIn(
            "conclusion == 'success'",
            condition,
            "watchdog job condition must not require conclusion == 'success'; failed runs must also self-heal",
        )

        # Must explicitly allow workflow_run and workflow_dispatch
        self.assertIn("workflow_dispatch", condition)
        self.assertIn("workflow_run", condition)

    def test_watched_workflows_list(self):
        with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        on_block = data.get("on", {}) or data.get(True, {})
        self.assertIn("workflow_run", on_block)
        wf_run = on_block["workflow_run"]
        watched = wf_run.get("workflows", [])

        self.assertIn("Main CI/CD", watched)
        self.assertIn("Bridge Intake (public work orders → private gates)", watched)
        self.assertEqual(wf_run.get("types"), ["completed"])

    def test_cron_math_calculation(self):
        from scripts.ci.schedule_watchdog import cron_next

        # 5-field cron: '23 * * * *' (hourly at :23)
        base = dt.datetime(2026, 10, 14, 1, 0, 0, tzinfo=dt.timezone.utc)
        nxt = cron_next("23 * * * *", base)
        self.assertEqual(nxt, dt.datetime(2026, 10, 14, 1, 23, 0, tzinfo=dt.timezone.utc))

        base2 = dt.datetime(2026, 10, 14, 1, 25, 0, tzinfo=dt.timezone.utc)
        nxt2 = cron_next("23 * * * *", base2)
        self.assertEqual(nxt2, dt.datetime(2026, 10, 14, 2, 23, 0, tzinfo=dt.timezone.utc))


if __name__ == "__main__":
    unittest.main()
