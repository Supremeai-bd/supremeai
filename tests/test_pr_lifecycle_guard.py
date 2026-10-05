#!/usr/bin/env python3
"""PR Lifecycle Guard-এর টেস্ট (#3516) — fake-API injected, নেটওয়ার্ক-মুক্ত।

বাংলা মন্তব্য: তিন শ্রেণির বট-আত্মঘাতী আচরণের প্রতিটির জন্য অন্তত একটি
red→green টেস্ট — গার্ড যেন ঠিক সিদ্ধান্তই নেয় এবং dry-run-এ কোনো লেখা-কল না করে।
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

guard = importlib.import_module("scripts.agents.pr_lifecycle_guard")


def _pr(number, head_ref, state="open", merged_at=None, title="", body="", labels=(), base_sha="b" * 40, head_sha="h" * 40):
    return {
        "number": number,
        "state": state,
        "merged_at": merged_at,
        "title": title,
        "body": body,
        "labels": [{"name": l} for l in labels],
        "head": {"ref": head_ref, "sha": head_sha},
        "base": {"sha": base_sha},
    }


def _eval_comment(verdict, user="SaifulHaqueNiloy"):
    return {"user": {"login": user}, "body": f"<!-- ai-eval:1:{verdict}:abc-->\nরায়: {verdict}"}


class FakeApi:
    """রুট-প্যাটার্ন ভিত্তিক স্ক্রিপ্টেবল fake — কোন HTTP নয়।"""

    def __init__(self):
        self.routes: dict[str, object] = {}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, endpoint, method="GET", payload=None):
        self.calls.append((method, endpoint))
        for pattern, value in self.routes.items():
            if pattern in endpoint:
                if callable(value):
                    return value(endpoint, method, payload)
                return value
        return []


class TestLatestVerdict(unittest.TestCase):
    """সর্বশেষ ai-eval verdict নির্ণয় — পুরনো→নতুন ক্রমে শেষটি জয়ী।"""

    def test_last_comment_wins(self):
        comments = [_eval_comment("HOLD_AND_FIX"), _eval_comment("AUTO_MERGE")]
        self.assertEqual(guard.latest_verdict(comments), "AUTO_MERGE")

    def test_no_marker_is_none(self):
        self.assertIsNone(guard.latest_verdict([{"body": "সাধারণ কমেন্ট"}]))

    def test_hold_and_fix_detected(self):
        self.assertEqual(guard.latest_verdict([_eval_comment("HOLD_AND_FIX")]), "HOLD_AND_FIX")


class TestBotLane(unittest.TestCase):
    """মানুষের লেনে হস্তক্ষেপ-বিরোধী দৈর্ঘ্য।"""

    def test_agent_prefix_is_bot_lane(self):
        self.assertTrue(guard.is_bot_lane("coder-1-3157-pii-log-gate"))
        self.assertTrue(guard.is_bot_lane("fix/pr-lifecycle-guard"))

    def test_human_branch_not_bot_lane(self):
        self.assertFalse(guard.is_bot_lane("feature/nasir-ui-tweak"))


class TestDedupMarker(unittest.TestCase):
    """গার্ড-মার্কার ডিডাপ — একই সতর্কতা বারবার নয়।"""

    def test_marker_present(self):
        comments = [{"body": f"{guard.GUARD_MARKER_PREFIX}conflict:9-->\nকনফ্লিক্ট"}]
        self.assertTrue(guard.guard_marker_present(comments, "conflict"))

    def test_marker_absent(self):
        self.assertFalse(guard.guard_marker_present([{"body": "hello"}], "conflict"))


class TestMergedTwin(unittest.TestCase):
    """wrongful-closure শর্ত: merged যমজ থাকলে ক্লোজ সঠিক — reopen নয়।"""

    def test_twin_merged_same_issue(self):
        all_prs = [
            _pr(3230, "coder-1-3227-a", state="closed", title="fix: #3227 x"),
            _pr(3241, "coder-1-3227-b", state="closed", merged_at="2026-10-05T16:31:00Z", title="fix: #3227 y"),
        ]
        self.assertTrue(guard.merged_twin_exists(3230, [3227], all_prs))

    def test_no_merged_twin(self):
        all_prs = [_pr(3230, "coder-1-3227-a", state="closed", title="fix: #3227 x")]
        self.assertFalse(guard.merged_twin_exists(3230, [3227], all_prs))

    def test_self_excluded(self):
        all_prs = [_pr(3230, "coder-1-3227-a", state="closed", merged_at="2026-10-05T16:31:00Z", title="fix: #3227")]
        self.assertFalse(guard.merged_twin_exists(3230, [3227], all_prs))


class TestHealFreshness(unittest.TestCase):
    """freshness self-heal — behind হলে update-branch; conflict-এ পতাকা।"""

    def test_behind_pr_gets_update_branch_on_apply(self):
        fake = FakeApi()
        fake.routes["/pulls?state=open"] = [_pr(3513, "coder-1-3156-workload-admission")]
        fake.routes["/compare/"] = {"behind_by": 1}
        fake.routes["/update-branch"] = {"message": "Updating pull request branch."}
        report = guard.GuardReport()
        guard.heal_freshness(fake, apply=True, report=report)
        kinds = [a.kind for a in report.actions]
        self.assertIn("update_branch", kinds)
        self.assertTrue(any(a.applied for a in report.actions if a.kind == "update_branch"))
        self.assertTrue(any("update-branch" in ep and method == "PUT" for method, ep in fake.calls))

    def test_dry_run_makes_no_write_call(self):
        fake = FakeApi()
        fake.routes["/pulls?state=open"] = [_pr(3513, "coder-1-3156-workload-admission")]
        fake.routes["/compare/"] = {"behind_by": 2}
        report = guard.GuardReport()
        guard.heal_freshness(fake, apply=False, report=report)
        self.assertFalse(any(m == "PUT" for m, _ in fake.calls), "dry-run-এ PUT নিষিদ্ধ")

    def test_fresh_pr_skipped(self):
        fake = FakeApi()
        fake.routes["/pulls?state=open"] = [_pr(3511, "coder-1-3478-vault-ai-bridge")]
        fake.routes["/compare/"] = {"behind_by": 0}
        report = guard.GuardReport()
        guard.heal_freshness(fake, apply=True, report=report)
        self.assertEqual(report.actions, [])

    def test_conflict_flagged_once(self):
        fake = FakeApi()
        fake.routes["/pulls?state=open"] = [_pr(3301, "fix/3295-loop-agent-rules-source")]
        fake.routes["/compare/"] = {"behind_by": 7}
        fake.routes["/update-branch"] = {"__http_error": 422, "__body__": "merge conflict"}
        fake.routes["/comments"] = []
        report = guard.GuardReport()
        guard.heal_freshness(fake, apply=True, report=report)
        self.assertIn("conflict_flag", [a.kind for a in report.actions])
        # দ্বিতীয় রান — মার্কার-ডিডাপ
        fake2 = FakeApi()
        fake2.routes["/pulls?state=open"] = [_pr(3301, "fix/3295-loop-agent-rules-source")]
        fake2.routes["/compare/"] = {"behind_by": 7}
        fake2.routes["/update-branch"] = {"__http_error": 422, "__body__": "merge conflict"}
        fake2.routes["/comments"] = [{"body": f"{guard.GUARD_MARKER_PREFIX}conflict:3301-->"}]
        report2 = guard.GuardReport()
        guard.heal_freshness(fake2, apply=True, report=report2)
        self.assertTrue(any("dedup" in a.detail for a in report2.actions))

    def test_human_lane_untouched(self):
        fake = FakeApi()
        fake.routes["/pulls?state=open"] = [_pr(999, "nasir-human-branch")]
        fake.routes["/compare/"] = {"behind_by": 5}
        report = guard.GuardReport()
        guard.heal_freshness(fake, apply=True, report=report)
        self.assertEqual(report.actions, [])
        self.assertFalse(any("update-branch" in ep for _, ep in fake.calls))


class TestGuardLifecycle(unittest.TestCase):
    """wrongful-closure পুনর্বাসন + ডুপ্লিকেট-সতর্কতা + hold-protection।"""

    def _api_with_wrongful_closed(self):
        fake = FakeApi()
        fake.routes["/pulls?state=all"] = [
            # খোলা যমজ-সন্দেহ: একই issue-তে দুটি খোলা PR (title-primary রেফারেন্স)
            _pr(100, "coder-1-3900-a", title="fix: #3900 one"),
            _pr(101, "coder-1-3900-b", title="fix: #3900 two"),
            # wrongful-closure: HOLD verdict + merged যমজ নেই + issue খোলা
            _pr(3231, "coder-1-3161-a", state="closed", title="fix(deps): #3161 one"),
        ]
        fake.routes["/issues/3231/comments"] = [_eval_comment("HOLD_AND_FIX")]
        fake.routes["/issues/3161"] = {"state": "open", "number": 3161}
        fake.routes["/issues/100/comments"] = []
        return fake

    def test_wrongful_closed_reopened_on_apply(self):
        fake = self._api_with_wrongful_closed()
        report = guard.GuardReport()
        guard.guard_lifecycle(fake, apply=True, report=report)
        self.assertIn("reopen_wrongful", [a.kind for a in report.actions])
        self.assertTrue(any(m == "PATCH" and "pulls/3231" in ep for m, ep in fake.calls))

    def test_superseded_closed_not_reopened(self):
        fake = FakeApi()
        fake.routes["/pulls?state=all"] = [
            _pr(3209, "coder-1-3208-a", state="closed", title="fix: #3208 one"),
            _pr(3212, "coder-1-3208-b", state="closed", merged_at="2026-10-05T13:03:00Z", title="fix: #3208 two"),
        ]
        fake.routes["/issues/3209/comments"] = [_eval_comment("HOLD_AND_FIX")]
        report = guard.GuardReport()
        guard.guard_lifecycle(fake, apply=True, report=report)
        self.assertNotIn("reopen_wrongful", [a.kind for a in report.actions])

    def test_closed_with_no_hold_verdict_untouched(self):
        fake = FakeApi()
        fake.routes["/pulls?state=all"] = [_pr(3000, "coder-1-3000-a", state="closed", title="fix: #3000")]
        fake.routes["/issues/3000/comments"] = [_eval_comment("CLOSE")]
        report = guard.GuardReport()
        guard.guard_lifecycle(fake, apply=True, report=report)
        self.assertNotIn("reopen_wrongful", [a.kind for a in report.actions])

    def test_closed_issue_means_no_reopen_3116_lesson(self):
        """#3116-শিক্ষা: issue বন্ধ = কাজ অন্য পথে মিশেছে/বাতিল — reopen শব্দ-দূষণ।"""
        fake = FakeApi()
        fake.routes["/pulls?state=all"] = [
            _pr(3116, "fix/constitution-validator-sync", state="closed", title="fix(ci): #3114 sync"),
        ]
        fake.routes["/issues/3116/comments"] = [_eval_comment("HOLD_AND_FIX")]
        fake.routes["/issues/3114"] = {"state": "closed", "number": 3114}
        report = guard.GuardReport()
        guard.guard_lifecycle(fake, apply=True, report=report)
        self.assertNotIn("reopen_wrongful", [a.kind for a in report.actions])

    def test_body_only_ref_is_not_twin_title_primary_wins(self):
        """body-র discovery-parent রেফারেন্স যমজ নয় (#3301 vs #3354 parent #3088)।"""
        fake = FakeApi()
        fake.routes["/pulls?state=all"] = [
            _pr(3301, "fix/a", title="fix(agents): #3295 loop rules", body="parent #3088"),
            _pr(3354, "fix/b", title="fix(agents): #3330 breaker", body="parent #3088 ref"),
        ]
        report = guard.GuardReport()
        guard.guard_lifecycle(fake, apply=False, report=report)
        self.assertNotIn("duplicate_warning", [a.kind for a in report.actions])

    def test_duplicate_pair_warned_once(self):
        fake = self._api_with_wrongful_closed()
        report = guard.GuardReport()
        guard.guard_lifecycle(fake, apply=True, report=report)
        dup = [a for a in report.actions if a.kind == "duplicate_warning"]
        self.assertTrue(dup, "যমজ-খোলা PR-এ সতর্কতা জারি হওয়া চাই")
        # দ্বিতীয় রান — dedup
        fake.routes["/issues/100/comments"] = [{"body": f"{guard.GUARD_MARKER_PREFIX}duplicate:100-->\nযমজ"}]
        report2 = guard.GuardReport()
        guard.guard_lifecycle(fake, apply=True, report=report2)
        self.assertTrue(any("dedup" in a.detail for a in report2.actions if a.kind == "duplicate_warning"))

    def test_hold_protection_label_on_open_hold_pr(self):
        fake = FakeApi()
        fake.routes["/pulls?state=all"] = [
            _pr(3415, "coder-1-3157-pii-log-gate", title="fix: #3157 x", labels=[]),
        ]
        fake.routes["/issues/3415/comments"] = [_eval_comment("HOLD_AND_FIX")]
        fake.routes["/issues/3157"] = {"state": "open", "number": 3157}
        report = guard.GuardReport()
        guard.guard_lifecycle(fake, apply=True, report=report)
        self.assertIn("hold_protect", [a.kind for a in report.actions])
        self.assertTrue(any(m == "POST" and "labels" in ep for m, ep in fake.calls))

    def test_hold_protection_skipped_when_issue_closed(self):
        fake = FakeApi()
        fake.routes["/pulls?state=all"] = [
            _pr(3415, "coder-1-3157-pii-log-gate", title="fix: #3157 x", labels=[]),
        ]
        fake.routes["/issues/3415/comments"] = [_eval_comment("HOLD_AND_FIX")]
        fake.routes["/issues/3157"] = {"state": "closed", "number": 3157}
        report = guard.GuardReport()
        guard.guard_lifecycle(fake, apply=True, report=report)
        self.assertNotIn("hold_protect", [a.kind for a in report.actions])

    def test_already_protected_label_skipped(self):
        fake = FakeApi()
        fake.routes["/pulls?state=all"] = [
            _pr(3415, "coder-1-3157-pii-log-gate", title="fix: #3157 x", labels=[guard.HOLD_PROTECTED_LABEL]),
        ]
        fake.routes["/issues/3415/comments"] = [_eval_comment("HOLD_AND_FIX")]
        report = guard.GuardReport()
        guard.guard_lifecycle(fake, apply=True, report=report)
        self.assertNotIn("hold_protect", [a.kind for a in report.actions])


class TestMainDryRunDefault(unittest.TestCase):
    """CLI ডিফল্ট dry-run — প্রমাণিত লেখা-কল-শূন্যতা (প্রোডাকশন-নিরাপত্তা)।"""

    def test_default_is_dry_run(self):
        with patch.object(guard, "real_api", FakeApi()):
            with patch.object(guard, "heal_freshness") as mh, patch.object(guard, "guard_lifecycle") as mg:
                rc = guard.main([])
        self.assertEqual(rc, 0)
        mh.assert_called_once()
        self.assertFalse(mh.call_args.args[1], "apply=False হতে হবে (dry-run ডিফল্ট)")
        mg.assert_called_once()

    def test_apply_flag_passes_true(self):
        with patch.object(guard, "real_api", FakeApi()):
            with patch.object(guard, "heal_freshness") as mh, patch.object(guard, "guard_lifecycle") as mg:
                guard.main(["--apply"])
        self.assertTrue(mh.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
