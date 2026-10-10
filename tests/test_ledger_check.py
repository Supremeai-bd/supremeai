#!/usr/bin/env python3
"""Contract tests for the Task Outcome Ledger validator (#4271 Phase 0).

বাংলা সারসংক্ষেপ:
  Ledger হলো স্কোরকার্ডের 6.2/6.7/7.2 সারির প্রতিকার — প্রমাণ-ভিত্তিক outcome
  রেকর্ড। এই টেস্টগুলো validator-এর fail-closed চুক্তি ধরে রাখে:
    1. বৈধ রেকর্ড pass করে (happy path)
    2. required field / enum / SHA / URL ভাঙলে exit 1
    3. verifier-independence: verifier.identity == agent হলে block (স্ব-যাচাই নিষিদ্ধ)
    4. append-only: historical line delete/modify হলে block
    5. first_pass null শুধুমাত্র backfilled + note থাকলে
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci.ledger_check import (  # noqa: E402
    Violations,
    _validate_record,
    check_append_only,
)


def make_record(**overrides) -> dict:
    """A fully valid record — tests override single fields to break it."""
    rec = {
        "task_id": "T-0042",
        "date": "2026-10-09",
        "issue_url": "https://github.com/SaifulHaqueNiloy/supremeai/issues/4271",
        "agent": "supremeai-coder-1-bot",
        "pr_url": "https://github.com/SaifulHaqueNiloy/supremeai/pull/4290",
        "merge_sha": "a" * 40,
        "test_evidence": "pytest tests/test_ledger_check.py 9/9 green",
        "deployment": None,
        "runtime_verification": None,
        "verifier": {
            "identity": "ci:nightly-run-1",
            "verdict": "independent re-run green",
            "at": "2026-10-09",
        },
        "outcome": "SUCCESS",
        "first_pass": True,
        "cost": None,
        "backfilled": False,
        "notes": "",
    }
    rec.update(overrides)
    return rec


def validate(rec: dict) -> list[str]:
    v = Violations()
    _validate_record(rec, 1, set(), v)
    return v.items


class TestHappyPath(unittest.TestCase):
    def test_valid_record_passes(self):
        self.assertEqual(validate(make_record()), [])

    def test_valid_record_without_verifier_passes(self):
        self.assertEqual(validate(make_record(verifier=None)), [])

    def test_retry_outcome_valid(self):
        self.assertEqual(validate(make_record(outcome="SUCCESS_WITH_RETRIES")), [])


class TestRequiredFieldsAndFormats(unittest.TestCase):
    def test_missing_required_field_fails(self):
        rec = make_record()
        del rec["merge_sha"]
        self.assertTrue(any("merge_sha" in m for m in validate(rec)))

    def test_empty_test_evidence_fails(self):
        self.assertTrue(any("test_evidence" in m for m in validate(make_record(test_evidence="  "))))

    def test_bad_task_id_format_fails(self):
        self.assertTrue(any("task_id" in m for m in validate(make_record(task_id="T-42"))))

    def test_short_sha_fails(self):
        self.assertTrue(any("merge_sha" in m for m in validate(make_record(merge_sha="abcd1234"))))

    def test_non_hex_sha_fails(self):
        self.assertTrue(any("merge_sha" in m for m in validate(make_record(merge_sha="z" * 40))))

    def test_bad_issue_url_fails(self):
        self.assertTrue(
            any("issue_url" in m for m in validate(make_record(issue_url="https://github.com/other/repo/issues/1")))
        )

    def test_bad_pr_url_fails(self):
        self.assertTrue(
            any("pr_url" in m for m in validate(make_record(pr_url="https://github.com/SaifulHaqueNiloy/supremeai/issues/9")))
        )

    def test_bad_date_fails(self):
        self.assertTrue(any("date" in m for m in validate(make_record(date="2026-13-45"))))

    def test_duplicate_task_id_fails(self):
        v = Violations()
        seen = {"T-0042"}
        _validate_record(make_record(), 2, seen, v)
        self.assertTrue(any("duplicate task_id" in m for m in v.items))


class TestOutcomeAndFirstPass(unittest.TestCase):
    def test_bad_outcome_enum_fails(self):
        self.assertTrue(any("outcome" in m for m in validate(make_record(outcome="MAYBE"))))

    def test_first_pass_missing_fails(self):
        rec = make_record()
        del rec["first_pass"]
        self.assertTrue(any("first_pass" in m for m in validate(rec)))

    def test_first_pass_null_requires_backfilled(self):
        items = validate(make_record(first_pass=None, backfilled=False))
        self.assertTrue(any("backfilled" in m for m in items))

    def test_first_pass_null_requires_note(self):
        items = validate(make_record(first_pass=None, backfilled=True, notes=""))
        self.assertTrue(any("note" in m.lower() for m in items))

    def test_first_pass_null_ok_when_backfilled_with_note(self):
        items = validate(make_record(first_pass=None, backfilled=True, notes="owner-loop merge; unknown"))
        self.assertEqual(items, [])


class TestVerifierIndependence(unittest.TestCase):
    def test_self_verification_blocked(self):
        """The core law: implementing agent can never sign its own verdict."""
        rec = make_record()
        rec["verifier"] = {"identity": rec["agent"], "verdict": "looks good", "at": "2026-10-09"}
        items = validate(rec)
        self.assertTrue(any("verifier-independence" in m for m in items))

    def test_verifier_without_identity_blocked(self):
        rec = make_record(verifier={"verdict": "x", "at": "2026-10-09"})
        self.assertTrue(any("verifier.identity" in m for m in validate(rec)))

    def test_verifier_without_verdict_blocked(self):
        rec = make_record(verifier={"identity": "ci:x", "at": "2026-10-09"})
        self.assertTrue(any("verifier.verdict" in m for m in validate(rec)))

    def test_independent_verifier_passes(self):
        self.assertEqual(validate(make_record()), [])


class TestDeploymentShape(unittest.TestCase):
    def test_deployment_missing_keys_fail(self):
        items = validate(make_record(deployment={"station": "render-backend"}))
        self.assertTrue(any("deployment.sha" in m for m in items))
        self.assertTrue(any("deployment.at" in m for m in items))

    def test_deployment_short_sha_ok(self):
        rec = make_record(deployment={"station": "vercel-frontend", "sha": "abc1234", "at": "2026-10-09"})
        self.assertEqual(validate(rec), [])


class TestAppendOnly(unittest.TestCase):
    def test_pure_append_passes(self):
        old = ['{"task_id": "T-0001"}', '{"task_id": "T-0002"}']
        new = old + ['{"task_id": "T-0003"}']
        v = Violations()
        check_append_only(old, new, v)
        self.assertTrue(v.ok)

    def test_deletion_blocked(self):
        old = ['{"task_id": "T-0001"}', '{"task_id": "T-0002"}']
        new = ['{"task_id": "T-0002"}']
        v = Violations()
        check_append_only(old, new, v)
        self.assertFalse(v.ok)
        self.assertTrue(any("removed/modified" in m for m in v.items))

    def test_modification_blocked(self):
        """Editing a historical line = rewriting evidence = fabrication."""
        old = ['{"task_id": "T-0001", "outcome": "SUCCESS"}']
        new = ['{"task_id": "T-0001", "outcome": "FAILED"}']
        v = Violations()
        check_append_only(old, new, v)
        self.assertFalse(v.ok)

    def test_whitespace_normalization_tolerated(self):
        old = ['{"task_id": "T-0001"}  ']
        new = ['{"task_id": "T-0001"}']
        v = Violations()
        check_append_only(old, new, v)
        self.assertTrue(v.ok)


if __name__ == "__main__":
    unittest.main()
