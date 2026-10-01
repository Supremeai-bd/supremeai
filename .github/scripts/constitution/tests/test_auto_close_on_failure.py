"""Contract tests for auto_close_on_failure (#2892).

বাংলা: Claim Gate ব্যর্থ হলে ghost-PR স্বয়ংক্রিয়ভাবে বন্ধ হওয়ার চুক্তি-পরীক্ষা।
৪টি নকশা-সীমাবদ্ধতা (issue #2892-এর ডিজাইন-নোট):
  ১. শুধু claim-gate ব্যর্থতায় close — transient/অন্য gate ব্যর্থতা কখনো নয়
  ২. শুধু agent-author close — মানুষ পান advisory (close নয়)
  ৩. newest-run race-guard — head-SHA mismatch হলে abort
  ৪. Bangla কমেন্ট — সঠিক পথ (atomic_claim.sh) নির্দেশ করে
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # constitution pkg parent

from constitution.auto_close_on_failure import (
    Outcomes,
    run_auto_close,
)

REPO = "SaifulHaqueNiloy/supremeai"
SHA_GOOD = "a" * 40
SHA_EXPECTED = "b" * 40


def make_policy(**overrides):
    """Claim policy defaults (gates.py DEFAULT_CLAIM_POLICY চুক্তি)।"""
    policy = {
        "agent_author_prefixes": ["supremeai-", "app/supremeai-"],
        "advisory_authors": ["OWNER", "MEMBER", "COLLABORATOR"],
        "exempt_authors": [
            "dependabot[bot]", "app/dependabot",
            "github-actions[bot]", "renovate[bot]",
        ],
        "unclaimed_pr": "block",
        "missing_issue_ref": "block",
        "claim_comment_marker": "Atomic Claim",
        "agent_field_regex": r"\*\*Agent:\*\*\s*`([^`]+)`",
    }
    policy.update(overrides)
    return policy


class FakeApi:
    """gates.gh_api চুক্তির injectable দ্বিগুণ — endpoint→payload ম্যাপ।"""

    def __init__(self, routes=None, fail_on=None):
        self.routes = routes or {}
        self.calls = []
        self.fail_on = fail_on or ()

    def __call__(self, endpoint):
        self.calls.append(endpoint)
        if endpoint in self.fail_on:
            raise RuntimeError(f"API down: {endpoint}")
        if endpoint not in self.routes:
            raise AssertionError(f"unexpected endpoint: {endpoint}")
        return self.routes[endpoint]


class Recorder:
    """close/comment/label side-effect কল ধরে রাখে।"""

    def __init__(self):
        self.closed = []
        self.comments = []
        self.labels_removed = []

    def close_pr(self, pr_number, comment_body):
        self.closed.append((pr_number, comment_body))

    def comment_only(self, pr_number, comment_body):
        self.comments.append((pr_number, comment_body))

    def remove_has_pr(self, issue_number):
        self.labels_removed.append(issue_number)


def make_pr(author="supremeai-coder-1-bot[bot]", state="open",
            head_sha=SHA_GOOD, association="NONE",
            title="fix: something (#2892)", body="Refs #2892"):
    return {
        "number": 9999,
        "state": state,
        "title": title,
        "body": body,
        "user": {"login": author},
        "author_association": association,
        "head": {"sha": head_sha, "ref": "coder-1-2892-test"},
    }


def base_routes(pr):
    # run_claim_gate লিংকড-ইস্যু evidence আনে — খালি assignees + কোনো claim নেই
    return {
        f"repos/{REPO}/issues/2892": {"number": 2892, "assignees": [], "labels": []},
        f"repos/{REPO}/issues/2892/comments?per_page=100": [],
    }


class AgentNoClaimCloses(unittest.TestCase):
    """সীমাবদ্ধতা ১+২+৪: agent-লেখক + claim নেই → close + Bangla কমেন্ট।"""

    def setUp(self):
        os.environ["GH_REPO"] = REPO
        self.pr = make_pr()
        self.api = FakeApi({f"repos/{REPO}/pulls/9999": self.pr, **base_routes(self.pr)})
        self.rec = Recorder()
        self.outcome = run_auto_close(
            9999, SHA_GOOD, policy=make_policy(), api=self.api, effects=self.rec,
        )

    def test_outcome_closed(self):
        self.assertEqual(self.outcome, Outcomes.CLOSED_AGENT)

    def test_pr_closed_once(self):
        self.assertEqual(len(self.rec.closed), 1)
        self.assertEqual(self.rec.closed[0][0], 9999)

    def test_comment_is_bangla_and_names_fix_path(self):
        body = self.rec.closed[0][1]
        self.assertIn("Claim Gate", body)
        self.assertIn("atomic_claim.sh", body)
        self.assertIn("বন্ধ", body)

    def test_has_pr_removed_from_linked_issue(self):
        self.assertEqual(self.rec.labels_removed, [2892])


class HumanAuthorAdvisoryOnly(unittest.TestCase):
    """সীমাবদ্ধতা ২: মানুষ-লেখক → advisory কমেন্ট, close নয়।"""

    def test_member_human_not_closed(self):
        os.environ["GH_REPO"] = REPO
        pr = make_pr(author="human-maintainer", association="MEMBER")
        api = FakeApi({f"repos/{REPO}/pulls/9999": pr, **base_routes(pr)})
        rec = Recorder()
        outcome = run_auto_close(9999, SHA_GOOD, policy=make_policy(), api=api, effects=rec)
        self.assertEqual(outcome, Outcomes.ADVISORY_HUMAN)
        self.assertEqual(rec.closed, [])
        self.assertEqual(len(rec.comments), 1)

    def test_firsttime_contributor_human_not_closed(self):
        # association NONE-ও মানুষ — শুধু supremeai-* উপসর্গই agent
        os.environ["GH_REPO"] = REPO
        pr = make_pr(author="newcomer", association="NONE")
        api = FakeApi({f"repos/{REPO}/pulls/9999": pr, **base_routes(pr)})
        rec = Recorder()
        outcome = run_auto_close(9999, SHA_GOOD, policy=make_policy(), api=api, effects=rec)
        self.assertEqual(outcome, Outcomes.ADVISORY_HUMAN)
        self.assertEqual(rec.closed, [])


class ExemptAuthorNeverTouched(unittest.TestCase):
    """exempt_authors (dependabot ইত্যাদি) → কোনো ক্রিয়া নেই।"""

    def test_dependabot_skipped(self):
        os.environ["GH_REPO"] = REPO
        pr = make_pr(author="dependabot[bot]")
        api = FakeApi({f"repos/{REPO}/pulls/9999": pr})
        rec = Recorder()
        outcome = run_auto_close(9999, SHA_GOOD, policy=make_policy(), api=api, effects=rec)
        self.assertEqual(outcome, Outcomes.SKIP_EXEMPT)
        self.assertEqual(rec.closed, [])
        self.assertEqual(rec.comments, [])


class RaceGuardHeadSha(unittest.TestCase):
    """সীমাবদ্ধতা ৩: head-SHA mismatch → abort, কোনো ক্রিয়া নেই।"""

    def test_sha_mismatch_aborts(self):
        os.environ["GH_REPO"] = REPO
        pr = make_pr(head_sha=SHA_GOOD)  # রান শুরুর SHA থেকে আলাদা
        api = FakeApi({f"repos/{REPO}/pulls/9999": pr})
        rec = Recorder()
        outcome = run_auto_close(
            9999, SHA_EXPECTED, policy=make_policy(), api=api, effects=rec,
        )
        self.assertEqual(outcome, Outcomes.RACE_GUARD_ABORT)
        self.assertEqual(rec.closed, [])
        self.assertEqual(rec.comments, [])


class AlreadyClosedNoop(unittest.TestCase):
    def test_closed_pr_noop(self):
        os.environ["GH_REPO"] = REPO
        pr = make_pr(state="closed")
        api = FakeApi({f"repos/{REPO}/pulls/9999": pr})
        rec = Recorder()
        outcome = run_auto_close(9999, SHA_GOOD, policy=make_policy(), api=api, effects=rec)
        self.assertEqual(outcome, Outcomes.ALREADY_CLOSED)
        self.assertEqual(rec.closed, [])


class ValidClaimNoClose(unittest.TestCase):
    """সীমাবদ্ধতা ১: claim এখন বৈধ হলে (re-run-এ ঠিক হয়েছে/ভুল ব্যর্থতা) close নয়।"""

    def test_valid_claim_noop(self):
        os.environ["GH_REPO"] = REPO
        pr = make_pr()
        routes = {
            f"repos/{REPO}/pulls/9999": pr,
            f"repos/{REPO}/issues/2892": {"number": 2892, "assignees": [], "labels": []},
            f"repos/{REPO}/issues/2892/comments?per_page=100": [
                {"body": "Atomic Claim\n\n**Agent:** `supremeai-coder-1-bot`"}
            ],
        }
        api = FakeApi(routes)
        rec = Recorder()
        outcome = run_auto_close(9999, SHA_GOOD, policy=make_policy(), api=api, effects=rec)
        self.assertEqual(outcome, Outcomes.NO_CLAIM_FAILURE)
        self.assertEqual(rec.closed, [])


class NoLinkedIssueAgentCloses(unittest.TestCase):
    """লিংকড-ইস্যু ছাড়া agent-PR = claim অনুপস্থিতই → close (has-pr removal স্কিপ)।"""

    def test_no_linked_issue_closes(self):
        os.environ["GH_REPO"] = REPO
        pr = make_pr(title="fix: orphan work", body="no refs here")
        api = FakeApi({f"repos/{REPO}/pulls/9999": pr})
        rec = Recorder()
        outcome = run_auto_close(9999, SHA_GOOD, policy=make_policy(), api=api, effects=rec)
        self.assertEqual(outcome, Outcomes.CLOSED_AGENT)
        self.assertEqual(len(rec.closed), 1)
        self.assertEqual(rec.labels_removed, [])


class ApiFailureFailsOpen(unittest.TestCase):
    """ঘরের নিয়ম: CI API uptime-এর ওপর hard-depend করে না — fail-open।"""

    def test_pr_fetch_failure_aborts_clean(self):
        os.environ["GH_REPO"] = REPO
        api = FakeApi(fail_on=(f"repos/{REPO}/pulls/9999",))
        rec = Recorder()
        outcome = run_auto_close(9999, SHA_GOOD, policy=make_policy(), api=api, effects=rec)
        self.assertEqual(outcome, Outcomes.ABORTED_API)
        self.assertEqual(rec.closed, [])


if __name__ == "__main__":
    unittest.main()
