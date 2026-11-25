# বাংলা মন্তব্য: acquire_role_slot.py-এর তিনটি প্রধান ধাপ (issue-discovery, slot-lease, branch-creation)-এর ইউনিট টেস্ট।
# CLI behavior অপরিবর্তিত রাখা হয়েছে — কেবল লজিক আলাদা ফাংশনে ভাগ করা হয়েছে।
import json
import sys
from pathlib import Path

import pytest

_TARGET_MODULE = Path(__file__).resolve().parents[3] / "scripts" / "agents" / "acquire_role_slot.py"
# বাংলা মন্তব্য: ফাইল সরে গেলে opaque ImportError-এর বদলে স্পষ্ট assertion বার্তা পাওয়া যাবে।
assert _TARGET_MODULE.is_file(), f"Expected acquire_role_slot.py not found: {_TARGET_MODULE}"
sys.path.insert(0, str(_TARGET_MODULE.parent))

import acquire_role_slot as ars  # noqa: E402  # type: ignore[import-not-found]


class _FakeRunResult:
    # বাংলা মন্তব্য: subprocess.run-এর ফেক রেজাল্ট স্টাব — আগে তিনটি টেস্টে একই ক্লাস ডুপ্লিকেট ছিল।
    def __init__(self, stdout_json: str | None, returncode: int = 0, stderr: str = ""):
        self.stdout = stdout_json
        self.returncode = returncode
        self.stderr = stderr


def make_result(stdout_json: str | None, returncode: int = 0):
    return _FakeRunResult(stdout_json, returncode)


class TestFindNextUnclaimedIssue:
    # বাংলা মন্তব্য: issue-discovery ফাংশনের প্রায়োরিটি সর্টিং যাচাই।
    def test_priority_order_and_filtering(self, monkeypatch):
        issues = [
            {"number": 1, "title": "old P2", "body": "", "labels": [{"name": "P2-medium"}], "createdAt": "2026-01-01"},
            {"number": 2, "title": "critical", "body": "", "labels": [{"name": "P0-critical"}], "createdAt": "2026-01-02"},
            {"number": 3, "title": "claimed", "body": "", "labels": [{"name": "status:in-progress"}], "createdAt": "2026-01-03"},
            {"number": 4, "title": "high", "body": "", "labels": [{"name": "P1-high"}], "createdAt": "2026-01-04"},
            {"number": 5, "title": "has pr", "body": "", "labels": [{"name": "has-pr"}], "createdAt": "2026-01-05"},
        ]

        fake_run = lambda *a, **kw: make_result(json.dumps(issues))  # noqa: E731

        monkeypatch.setattr(ars.subprocess, "run", fake_run)
        result = ars.find_next_unclaimed_issue()
        assert result is not None
        assert result["number"] == 2  # P0-critical সবার আগে

    def test_all_filtered_returns_none(self, monkeypatch):
        issues = [{"number": 9, "title": "x", "body": "", "labels": [{"name": "status:in-progress"}], "createdAt": ""}]

        monkeypatch.setattr(ars.subprocess, "run", lambda *a, **kw: make_result(json.dumps(issues)))
        assert ars.find_next_unclaimed_issue() is None

    def test_gh_failure_returns_none(self, monkeypatch):
        def boom(*a, **kw):
            raise OSError("gh not found")

        monkeypatch.setattr(ars.subprocess, "run", boom)
        assert ars.find_next_unclaimed_issue() is None

    def test_role_handoff_mismatch_skipped(self, monkeypatch):
        issues = [
            {"number": 10, "title": "for coder", "body": "", "labels": [{"name": "handoff:coder"}], "createdAt": ""},
            {"number": 11, "title": "for planner", "body": "", "labels": [{"name": "handoff:planner"}], "createdAt": ""},
        ]

        monkeypatch.setattr(ars.subprocess, "run", lambda *a, **kw: make_result(json.dumps(issues)))
        result = ars.find_next_unclaimed_issue(role="planner")
        assert result is not None
        assert result["number"] == 11

    def test_same_priority_tie_breaks_on_older_created_at(self, monkeypatch):
        # বাংলা মন্তব্য: একই প্রায়োরিটির দুটি P0 ইস্যু — পুরোনো createdAt-টি আগে আসবে।
        issues = [
            {"number": 20, "title": "newer", "body": "", "labels": [{"name": "P0-critical"}], "createdAt": "2026-02-01"},
            {"number": 21, "title": "older", "body": "", "labels": [{"name": "P0-critical"}], "createdAt": "2026-01-15"},
        ]

        monkeypatch.setattr(ars.subprocess, "run", lambda *a, **kw: make_result(json.dumps(issues)))
        result = ars.find_next_unclaimed_issue()
        assert result is not None
        assert result["number"] == 21


class TestLeaseSlot:
    # বাংলা মন্তব্য: slot-lease ফাংশনের গ্যাপ-অ্যালোকেশন ও branch naming যাচাই।
    def _stub_lease_sources(self, monkeypatch, prs=None, busy=None, beats=None, branches=None):
        monkeypatch.setattr(ars, "fetch_open_prs_head_branches", lambda repo_dir: set(prs or []))
        monkeypatch.setattr(ars, "fetch_in_progress_issues_by_slot", lambda repo_dir: dict(busy or {}))
        monkeypatch.setattr(ars, "fetch_active_mesh_heartbeats", lambda base_url=None: set(beats or []))
        monkeypatch.setattr(ars, "fetch_existing_role_branches", lambda role, repo_dir: list(branches or []))
        monkeypatch.setattr(ars.subprocess, "run", lambda *a, **kw: None)

    def test_first_free_gap(self, monkeypatch):
        self._stub_lease_sources(monkeypatch)
        slot = ars.find_next_available_slot(role="coder")
        assert slot.index == 1
        assert slot.branch_name == "coder-1"

    def test_gap_fills_deleted_slot(self, monkeypatch):
        # slots 1,2,4 ব্যস্ত — 3 ফাঁকা, তাই 3 নেবে
        self._stub_lease_sources(
            monkeypatch,
            prs=["coder-1-fix", "coder-2-x"],
            busy={"coder-4": 10},
            branches=[1, 2, 4],
        )
        slot = ars.find_next_available_slot(role="coder")
        assert slot.index == 3

    def test_busy_slot_occupied(self, monkeypatch):
        self._stub_lease_sources(monkeypatch, prs=["coder-1"], busy={"coder-2": 5})
        status = ars.evaluate_slot_occupancy(
            role="coder", index=1,
            open_pr_branches={"coder-1"}, busy_issue_slots={}, active_heartbeats=set(),
        )
        assert status.is_occupied

    def test_branch_name_with_issue_and_title(self, monkeypatch):
        self._stub_lease_sources(monkeypatch)
        slot = ars.find_next_available_slot(role="coder", issue=2275, title="Fix: login [bug] crash")
        assert slot.branch_name.startswith("coder-1-2275-")
        assert "login-crash" in slot.branch_name

    def test_occupied_via_active_heartbeat(self, monkeypatch):
        # বাংলা মন্তব্য: heartbeat-ভিত্তিক occupancy পথ — অন্য উৎস খালি থাকলেও ব্যস্ত ধরা হবে।
        status = ars.evaluate_slot_occupancy(
            role="coder", index=3,
            open_pr_branches=set(), busy_issue_slots={}, active_heartbeats={"coder-3"},
        )
        assert status.is_occupied


class TestCreateBranch:
    # বাংলা মন্তব্য: branch-creation ফাংশনের success/failure পথ যাচাই।
    def test_checkout_success(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            return make_result(None)

        monkeypatch.setattr(ars.subprocess, "run", fake_run)
        assert ars.checkout_slot_branch("coder-1-100-fix") is True
        assert ["git", "checkout", "-B", "coder-1-100-fix", "origin/main"] in calls

    def test_checkout_failure_returns_false(self, monkeypatch):
        def fake_run(cmd, **kw):
            # বাংলা মন্তব্য: substring নয় — স্পষ্ট কমান্ড নাম দিয়ে fetch শনাক্ত করা হচ্ছে।
            if len(cmd) > 1 and cmd[1] == "fetch":
                return make_result(None)
            raise ars.subprocess.SubprocessError("checkout failed")

        monkeypatch.setattr(ars.subprocess, "run", fake_run)
        assert ars.checkout_slot_branch("bad-branch") is False
