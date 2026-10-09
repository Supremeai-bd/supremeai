#!/usr/bin/env python3
"""Contract tests: evaluator REST fallback (#4291 — repo went PRIVATE).

বাংলা সারসংক্ষেপ:
  রিপো প্রাইভেট হওয়ার পর SELF_HEAL_PAT (fine-grained)-এ checks:read নেই —
  GraphQL statusCheckRollup 403 → evaluator ক্র্যাশ → merge gate সব PR HOLD।
  fetch_pr-এর degradation চুক্তি এই টেস্টগুলো ধরে রাখে:
    1. স্বাভাবিক পথে fallback চলে না (GraphQL parity — কোনো behavior change নেই)
    2. PAT-ব্যর্থতায় reduced-fetch + REST check-runs fallback (fail-honest)
    3. conclusion mapping: completed → UPPER, in-progress → None (#3207 চুক্তি)
    4. SHA/token অনুপস্থিত হলে raise (fail-closed — কখনো মিথ্যা সবুজ নয়)
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci import ai_pr_evaluator as ev  # noqa: E402
from scripts.ci.ai_pr_evaluator import fetch_pr, checks_verdict, checks_pending  # noqa: E402


class FakeGhPermissionDeath:
    """gh যেন প্রথম কলে (statusCheckRollup সহ) মরে, দ্বিতীয় কলে (বাদে) বাঁচে।"""

    def __init__(self, pr_without_rollup: dict):
        self._body = pr_without_rollup
        self.calls: list[tuple] = []

    def __call__(self, *args: str) -> str:
        self.calls.append(args)
        fields = args[-1] if args else ""
        if "statusCheckRollup" in fields:
            raise RuntimeError(
                "gh pr view… failed: GraphQL: Resource not accessible by "
                "personal access token (repository.pullRequest.statusCheckRollup)"
            )
        return json.dumps(self._body)


def fake_rest(check_runs: list[dict]):
    def _rest(repo: str, sha: str, token: str) -> list[dict]:
        assert sha == "abc1234" and token == "tok-fallback", (sha, token)
        return [
            {
                "name": c["name"],
                "status": c["status"],
                "conclusion": (c["conclusion"].upper() if c.get("conclusion") else None)
                if c["status"] == "completed"
                else None,
            }
            for c in check_runs
        ]
    return _rest


class TestHappyPathUnchanged(unittest.TestCase):
    def test_no_fallback_on_healthy_graphql(self):
        body = {"number": 1, "statusCheckRollup": [{"name": "X", "conclusion": "SUCCESS"}]}
        calls = []

        def healthy_gh(*args: str) -> str:
            calls.append(args)
            return json.dumps(body)

        pr = fetch_pr(healthy_gh, 1, api=lambda *a, **k: None)
        self.assertEqual(pr["statusCheckRollup"][0]["conclusion"], "SUCCESS")
        self.assertEqual(len(calls), 1)  # এক কল — fallback চলেইনি (GraphQL parity)


class TestFallbackPath(unittest.TestCase):
    def test_permission_death_triggers_rest_fallback(self):
        pr_body = {"number": 4291, "headRefOid": "abc1234", "title": "t"}
        gh = FakeGhPermissionDeath(pr_body)
        seen = {}

        def rest(repo, sha, token):
            seen["sha"], seen["token"] = sha, token
            return ["raw-check-a", "raw-check-b"]

        original = ev._check_runs_rest
        ev._check_runs_rest = rest  # type: ignore[assignment]
        try:
            pr = fetch_pr(gh, 4291, api=lambda *a, **k: {}, fallback_token="tok-fallback")
        finally:
            ev._check_runs_rest = original  # type: ignore[assignment]
        self.assertEqual(seen, {"sha": "abc1234", "token": "tok-fallback"})
        self.assertEqual(pr["statusCheckRollup"], ["raw-check-a", "raw-check-b"])

    def test_real_check_runs_rest_mapping(self):
        """The REAL _check_runs_rest: completed → UPPER conclusion, else None."""
        payload = json.dumps({"check_runs": [
            {"name": "🚦 Unified PR Gate", "status": "completed", "conclusion": "success"},
            {"name": "🧪 Tests", "status": "in_progress", "conclusion": None},
            {"name": "🤖 Eval", "status": "completed", "conclusion": "neutral"},
        ]}).encode()

        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return payload

        def fake_urlopen(req, timeout=None):
            assert "check-runs" in req.full_url and sha_frag in req.full_url
            return FakeResp()

        sha_frag = "abc1234"
        original = ev.urllib.request.urlopen
        ev.urllib.request.urlopen = fake_urlopen  # type: ignore[assignment]
        try:
            rollup = ev._check_runs_rest("o/r", "abc1234", "tok")
        finally:
            ev.urllib.request.urlopen = original  # type: ignore[assignment]
        self.assertEqual(rollup[0]["conclusion"], "SUCCESS")   # UPPER (OK_CONCLUSIONS parity)
        self.assertIsNone(rollup[1]["conclusion"])             # in-progress → None (#3207)
        self.assertEqual(rollup[2]["conclusion"], "NEUTRAL")

    def test_mapped_rollup_feeds_verdict_functions(self):
        rollup = [
            {"name": "A", "status": "completed", "conclusion": "SUCCESS"},
            {"name": "B", "status": "completed", "conclusion": "FAILURE"},
        ]
        green, failed = checks_verdict({"statusCheckRollup": rollup})
        self.assertFalse(green)
        self.assertEqual(failed, ["B"])
        self.assertFalse(checks_pending({"statusCheckRollup": rollup}))
        rollup2 = [{"name": "C", "status": "in_progress", "conclusion": None}]
        self.assertTrue(checks_pending({"statusCheckRollup": rollup2}))
        green, failed = checks_verdict({"statusCheckRollup": rollup2})
        # #3207 চুক্তি: checks_verdict = "কোনো ব্যর্থতা নেই" (in-progress ভাঙা নয়);
        # pending-অবস্থা আলাদাভাবে checks_pending() দিয়ে মোকাবিলা হয় (PENDING verdict)।
        self.assertTrue(green)
        self.assertEqual(failed, [])
        self.assertTrue(checks_pending({"statusCheckRollup": rollup2}))


class TestFailClosed(unittest.TestCase):
    def test_fallback_network_failure_raises(self):
        """REST leg also fails → raise — evaluator never fabricates a verdict."""
        gh = FakeGhPermissionDeath({"number": 1, "headRefOid": "abc1234"})
        original = ev._check_runs_rest

        def boom(repo, sha, token):
            raise RuntimeError("HTTP Error 403: forbidden")

        ev._check_runs_rest = boom  # type: ignore[assignment]
        try:
            with self.assertRaises(RuntimeError):
                fetch_pr(gh, 1, api=lambda *a, **k: {}, fallback_token="tok")
        finally:
            ev._check_runs_rest = original  # type: ignore[assignment]

    def test_missing_sha_raises(self):
        gh = FakeGhPermissionDeath({"number": 1})  # headRefOid নেই
        original = ev._check_runs_rest
        ev._check_runs_rest = lambda *a: []  # type: ignore[assignment]
        try:
            with self.assertRaises(RuntimeError):
                fetch_pr(gh, 1, api=lambda *a, **k: {}, fallback_token="tok")
        finally:
            ev._check_runs_rest = original  # type: ignore[assignment]

    def test_missing_token_raises(self):
        gh = FakeGhPermissionDeath({"number": 1, "headRefOid": "abc1234"})
        env_backup = {k: None for k in ("GH_FALLBACK_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")}
        saved = {}
        import os
        for k in env_backup:
            saved[k] = os.environ.pop(k, None)
        original = ev._check_runs_rest
        ev._check_runs_rest = lambda *a: []  # type: ignore[assignment]
        try:
            with self.assertRaises(RuntimeError):
                fetch_pr(gh, 1, api=lambda *a, **k: {})
        finally:
            ev._check_runs_rest = original  # type: ignore[assignment]
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
