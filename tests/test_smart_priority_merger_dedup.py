"""Tests for scripts/ci/smart_priority_merger.py — conflict-issue dedup race (#2603).

বাংলা মন্তব্য: #2599 + #2600-এর root-cause — `gh issue list --search`
eventually-consistent search index-এ চলে; নতুন issue-এর পরের ~১০–৬০s-এ
dedup চেক ওই issue দেখতে পায় না → হুবহু ডুপ্লিকেট। ফিক্স: REST /issues
লিস্ট (read-your-writes consistent) + Python-side match (body-marker
`conflict-of: PR #<n>` + legacy title-প্রিফিক্স) + fail-closed।

সব টেস্ট অফলাইন — run_gh_json / subprocess.run ইনজেক্টেড fake।
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_MERGER = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "smart_priority_merger.py"
_spec = importlib.util.spec_from_file_location("smart_priority_merger_dedup", _MERGER)
spm = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("smart_priority_merger_dedup", spm)
_spec.loader.exec_module(spm)


def _issue(num: int, title: str, body: str = "") -> dict:
    return {"number": num, "title": title, "body": body, "state": "open"}


def _pr_entry(num: int) -> dict:
    # REST /issues-এ PR-ও আসে — pull_request কী-ই আলাদা করে দেয়
    return {"number": num, "title": f"some PR #{num}", "body": "", "pull_request": {"url": "x"}}


class TestMatchOpenConflictIssue(unittest.TestCase):
    def test_legacy_title_prefix_matched(self) -> None:
        # #2599/#2600-প্যাটার্ন: marker-পূর্ববর্তী ইস্যু — টাইটেল প্রিফিক্স ধরতে হবে
        issues = [_issue(2599, "fix(conflict): PR #2595 has merge conflict with current main branch")]
        self.assertEqual(spm.match_open_conflict_issue(issues, 2595), 2599)

    def test_body_marker_matched(self) -> None:
        # নতুন ফরম্যাট — টাইটেল বদলালেও marker ধরবে
        issues = [_issue(2700, "টাইটেল যা-ই হোক", body="### Alert\n\n---\nconflict-of: PR #2595")]
        self.assertEqual(spm.match_open_conflict_issue(issues, 2595), 2700)

    def test_pr_entries_ignored(self) -> None:
        # PR #2595-এর টাইটেল-বডি যদি ম্যাচ করত তবু বাদ — pull_request কী-ই যথেষ্ট
        self.assertIsNone(spm.match_open_conflict_issue(
            [_pr_entry(2595)], 2595))

    def test_wrong_pr_number_not_matched(self) -> None:
        # PR #2595-এর কনফ্লিক্ট ইস্যু PR #2594-এর dedup-এ ধরা পড়বে না
        issues = [_issue(2599, "fix(conflict): PR #2595 has merge conflict", body="")]
        self.assertIsNone(spm.match_open_conflict_issue(issues, 2594))

    def test_empty_and_none(self) -> None:
        self.assertIsNone(spm.match_open_conflict_issue(None, 2595))
        self.assertIsNone(spm.match_open_conflict_issue([], 2595))


class TestIsConflictIssueAlreadyOpen(unittest.TestCase):
    def test_rest_success_found(self) -> None:
        with patch.object(spm, "list_open_issues_via_rest",
                           return_value=[_issue(2599, "fix(conflict): PR #2595 has merge conflict")]):
            self.assertTrue(spm.is_conflict_issue_already_open(2595))

    def test_rest_success_not_found(self) -> None:
        with patch.object(spm, "list_open_issues_via_rest", return_value=[_issue(1, "অসংশ্লিষ্ট")]):
            self.assertFalse(spm.is_conflict_issue_already_open(2595))

    def test_rest_failure_fail_closed(self) -> None:
        # REST ব্যর্থ → অজানা অবস্থা → ডুপ্লিকেট রিস্ক এড়াতে 'আছে' ধরা (skip create)
        with patch.object(spm, "list_open_issues_via_rest", return_value=None):
            self.assertTrue(spm.is_conflict_issue_already_open(2595))


class TestHandleConflictPr(unittest.TestCase):
    def _run(self, dedup_result: bool) -> list:
        calls: list = []

        class FakeProc:
            def __init__(self, rc=0, out="https://github.com/x/y/issues/2700"):
                self.returncode = rc
                self.stdout = out
                self.stderr = ""

        def fake_subprocess_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:3] == ["gh", "pr", "edit"]:
                return FakeProc()
            if cmd[:3] == ["gh", "issue", "create"]:
                return FakeProc()
            raise AssertionError(f"unexpected cmd {cmd}")

        with patch.object(spm, "is_conflict_issue_already_open", return_value=dedup_result), \
             patch.object(spm.subprocess, "run", side_effect=fake_subprocess_run):
            spm.handle_conflict_pr(2595, "feature/x", "টাইটেল", "agent-3")
        return calls

    def test_dedup_hit_skips_create(self) -> None:
        calls = self._run(dedup_result=True)
        # শুধু queue:hold লেবেল — issue create ডাকা হয়নি
        create_calls = [c for c in calls if c[:3] == ["gh", "issue", "create"]]
        self.assertEqual(create_calls, [])

    def test_create_body_contains_marker(self) -> None:
        calls = self._run(dedup_result=False)
        create_calls = [c for c in calls if c[:3] == ["gh", "issue", "create"]]
        self.assertEqual(len(create_calls), 1)
        cmd = create_calls[0]
        body = cmd[cmd.index("--body") + 1]
        self.assertIn("conflict-of: PR #2595", body)
        title = cmd[cmd.index("--title") + 1]
        self.assertTrue(title.startswith("fix(conflict): PR #2595 "))


class TestRaceWindowRootCause(unittest.TestCase):
    def test_old_search_path_removed(self) -> None:
        # পুরনো `--search` কল-পথ আর থাকবে না (search-index = race-এর উৎস)।
        # ডকস্ট্রিং-এ backtick-`--search` থাকতে পারে — আসল যাচাই: অ্যারে-
        # লিটারেল `"--search",` আর নেই
        import inspect
        src = inspect.getsource(spm.is_conflict_issue_already_open)
        self.assertNotIn('"--search",', src)
        src_listing = inspect.getsource(spm.list_open_issues_via_rest)
        self.assertIn("gh", src_listing)
        self.assertIn("per_page=100", src_listing)


if __name__ == "__main__":
    unittest.main()
