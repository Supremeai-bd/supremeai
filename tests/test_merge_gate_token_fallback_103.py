#!/usr/bin/env python3
"""#103 contract tests — Merge Gate token-scope fallback (GH_FALLBACK_TOKEN).

# বাংলা: #4291/#4292 চুক্তির merge-gate পা — fine-grained PAT (SELF_HEAL_PAT)
# private repo-তে checks:read নেই → check-runs 403 → সব রায় fail-closed HOLD
# (fleet-deadlock)। এই টেস্টগুলো জোর করে ধরে:
#   1. token-scope-শ্রেণির ত্রুটিতে (403 "not accessible") একবার fallback retry
#   2. fallback সফল হলে রায় গণনা স্বাভাবিক (evidence-failure নেই)
#   3. fallback token অনুপস্থিত/অভিন্ন হলে বা অন্য শ্রেণির ত্রুটিতে fail-closed
#   4. প্রাইমারি সফল হলে fallback কখনো চালানো হয় না (অতিরিক্ত কল নয়)
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci.merge_gate import (  # noqa: E402
    DEFAULT_REQUIRED_CHECKS,
    Gateway,
    required_checks_verdict,
)

ENV = {"GH_TOKEN": "pat-primary", "GH_FALLBACK_TOKEN": "workflow-token"}
SCOPE_ERR = RuntimeError(
    "gh api repos/o/r/commits/abc/check-runs… failed: gh: Resource not "
    "accessible by personal access token (HTTP 403)"
)


class _Calls:
    """subprocess.run recorder — (argv, kwargs) ধরে রাখে, ফল দেয় প্রোগ্রাম অনুযায়ী।"""

    def __init__(self, outcomes):
        # outcomes: list of (returncode, stdout, stderr) — ক্রমানুসারে খরচ হয়
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append((list(cmd), kwargs))
        rc, out, err = self.outcomes.pop(0)
        return mock.Mock(returncode=rc, stdout=out, stderr=err)


class TestGatewayTokenFallback(unittest.TestCase):
    def test_403_falls_back_and_succeeds(self):
        calls = _Calls([(1, "", "gh: Resource not accessible by personal access token (HTTP 403)"),
                        (0, '{"check_runs": []}', "")])
        with mock.patch.dict(os.environ, ENV), \
                mock.patch("scripts.ci.merge_gate.subprocess.run", calls):
            out = Gateway().gh("api", "repos/o/r/commits/abc/check-runs")
        self.assertEqual(out, '{"check_runs": []}')
        self.assertEqual(len(calls.calls), 2)
        # দ্বিতীয় কলে fallback token env-ওভাররাইড
        self.assertEqual(calls.calls[1][1]["env"]["GH_TOKEN"], "workflow-token")

    def test_primary_success_no_fallback(self):
        calls = _Calls([(0, "ok", "")])
        with mock.patch.dict(os.environ, ENV), \
                mock.patch("scripts.ci.merge_gate.subprocess.run", calls):
            self.assertEqual(Gateway().gh("api", "repos/o/r/x"), "ok")
        self.assertEqual(len(calls.calls), 1)

    def test_non_scope_error_no_fallback(self):
        calls = _Calls([(1, "", "gh: HTTP 404: Not Found")])
        with mock.patch.dict(os.environ, ENV), \
                mock.patch("scripts.ci.merge_gate.subprocess.run", calls):
            with self.assertRaisesRegex(RuntimeError, "404"):
                Gateway().gh("api", "repos/o/r/x")
        self.assertEqual(len(calls.calls), 1)  # fail-honest: fallback চেষ্টাই নয়

    def test_both_fail_raises_fail_closed(self):
        calls = _Calls([(1, "", "gh: Resource not accessible by personal access token (HTTP 403)"),
                        (1, "", "gh: still broken")])
        with mock.patch.dict(os.environ, ENV), \
                mock.patch("scripts.ci.merge_gate.subprocess.run", calls):
            with self.assertRaisesRegex(RuntimeError, r"primary\+fallback"):
                Gateway().gh("api", "repos/o/r/x")
        self.assertEqual(len(calls.calls), 2)

    def test_no_fallback_token_raises(self):
        calls = _Calls([(1, "", "gh: Resource not accessible by personal access token (HTTP 403)")])
        env = {"GH_TOKEN": "pat-primary"}
        with mock.patch.dict(os.environ, env, clear=False), \
                mock.patch("scripts.ci.merge_gate.subprocess.run", calls):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                Gateway().gh("api", "repos/o/r/x")
        self.assertEqual(len(calls.calls), 1)

    def test_fallback_same_as_primary_skips(self):
        calls = _Calls([(1, "", "gh: Resource not accessible by personal access token (HTTP 403)")])
        env = {"GH_TOKEN": "same", "GH_FALLBACK_TOKEN": "same"}
        with mock.patch.dict(os.environ, env), \
                mock.patch("scripts.ci.merge_gate.subprocess.run", calls):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                Gateway().gh("api", "repos/o/r/x")
        self.assertEqual(len(calls.calls), 1)

    def test_required_checks_verdict_recovers_via_fallback(self):
        # end-to-end: evidence fetch 403 → fallback → সব required check SUCCESS
        runs = {"check_runs": [
            {"name": name, "conclusion": "SUCCESS", "id": i + 1}
            for i, name in enumerate(DEFAULT_REQUIRED_CHECKS)
        ]}
        calls = _Calls([(1, "", "gh: Resource not accessible by personal access token (HTTP 403)"),
                        (0, json.dumps(runs), "")])
        with mock.patch.dict(os.environ, ENV), \
                mock.patch("scripts.ci.merge_gate.subprocess.run", calls):
            blocked, failures = required_checks_verdict(Gateway(), "abc", DEFAULT_REQUIRED_CHECKS)
        self.assertEqual(blocked, [])
        self.assertEqual(failures, [])

    def test_required_checks_verdict_fail_closed_without_fallback(self):
        calls = _Calls([(1, "", "gh: Resource not accessible by personal access token (HTTP 403)")])
        env = {"GH_TOKEN": "pat-primary"}
        with mock.patch.dict(os.environ, env, clear=False), \
                mock.patch("scripts.ci.merge_gate.subprocess.run", calls):
            blocked, failures = required_checks_verdict(Gateway(), "abc", DEFAULT_REQUIRED_CHECKS)
        self.assertEqual(blocked, [])
        self.assertTrue(any("evidence-fetch-failed" in f for f in failures))


if __name__ == "__main__":
    unittest.main()
