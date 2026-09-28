"""Unit tests for Automated System Gates (Issue #2251 — constitution.gates)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # constitution pkg parent

from constitution.gates import (  # noqa: E402
    DEFAULT_LEASE_POLICY,
    DEFAULT_PREDECESSOR_POLICY,
    DEFAULT_SCOPE_POLICY,
    DEFAULT_VERIFICATION_POLICY,
    check_lease,
    check_predecessor_hold,
    extract_test_evidence,
    find_linked_issue_numbers,
    find_undeclared_files,
    load_policies,
    parse_declared_files,
    path_matches,
)


SCOPE_POLICY = dict(DEFAULT_SCOPE_POLICY)
VERIFICATION_POLICY = dict(DEFAULT_VERIFICATION_POLICY)
LEASE_POLICY = dict(DEFAULT_LEASE_POLICY)


class PathMatchingTests(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(path_matches("backend/app.py", "backend/app.py"))

    def test_wildcard_match(self):
        self.assertTrue(path_matches("docs/generated/route_inventory.json", "docs/generated/**"))
        self.assertTrue(path_matches("docs/generated/a/b/c.json", "docs/generated/**"))
        self.assertFalse(path_matches("docs/other/x.json", "docs/generated/**"))

    def test_recursive_glob(self):
        self.assertTrue(path_matches("a/b/package-lock.json", "**/package-lock.json"))

    def test_leading_dot_slash_normalised(self):
        self.assertTrue(path_matches("./docs/x.md", "docs/x.md"))


class TestEvidenceTests(unittest.TestCase):
    def test_missing_section_fails(self):
        ok, _ = extract_test_evidence("just a description", VERIFICATION_POLICY)
        self.assertFalse(ok)

    def test_valid_section_passes(self):
        body = (
            "## What\nchanged\n\n## Test Evidence\n"
            "```\n$ pytest backend/tests -q\n42 passed, 0 failed in 8.2s\n```\n"
        )
        ok, reason = extract_test_evidence(body, VERIFICATION_POLICY)
        self.assertTrue(ok, reason)

    def test_short_section_fails(self):
        ok, _ = extract_test_evidence("## Test Evidence\nok", VERIFICATION_POLICY)
        self.assertFalse(ok)

    def test_section_without_marker_fails(self):
        ok, _ = extract_test_evidence(
            "## Test Evidence\nI believe the tests would pass if run.", VERIFICATION_POLICY
        )
        self.assertFalse(ok)

    def test_bangla_section_name(self):
        body = "## টেস্ট এভিডেন্স\ncd backend && python -m pytest tests -q\n31 passed in 5s"
        ok, _ = extract_test_evidence(body, VERIFICATION_POLICY)
        self.assertTrue(ok)

    def test_empty_body_fails(self):
        ok, _ = extract_test_evidence("", VERIFICATION_POLICY)
        self.assertFalse(ok)

    def test_evidence_section_stops_at_next_heading(self):
        evidence = "pytest -q backend/tests\n" + ("31 passed, 0 failed, 2 skipped in 8.2s\n" * 3)
        body = "## Test Evidence\n" + evidence + "## Notes\nsome long notes here " * 5
        ok, reason = extract_test_evidence(body, VERIFICATION_POLICY)
        self.assertTrue(ok, reason)


class ClaimParsingTests(unittest.TestCase):
    def test_bullet_backtick_format(self):
        comment = (
            "## Atomic claim — coder-1\n\n**Touching files:**\n"
            "- `backend/api/routes/browser_routes.py` (delete — legacy router)\n"
            "- `backend/app.py` (mount rewire)\n"
        )
        declared = parse_declared_files([comment])
        self.assertIn("backend/api/routes/browser_routes.py", declared)
        self.assertIn("backend/app.py", declared)
        self.assertEqual(len(declared), 2)

    def test_inline_comma_format(self):
        comment = "Claiming. Touching files: scripts/ci/verify.py, docs/plan.md"
        declared = parse_declared_files([comment])
        self.assertEqual(declared, {"scripts/ci/verify.py", "docs/plan.md"})

    def test_non_claim_comments_ignored(self):
        declared = parse_declared_files(["random comment", "lgtm"])
        self.assertEqual(declared, set())

    def test_annotations_stripped(self):
        comment = "**Touching files:**\n- `.github/constitution/rules.yml` (new — machine-readable constitution)"
        declared = parse_declared_files([comment])
        self.assertEqual(declared, {".github/constitution/rules.yml"})


class LinkedIssueTests(unittest.TestCase):
    def test_title_suffix(self):
        self.assertEqual(
            find_linked_issue_numbers("fix(core): do thing (#2251)", ""),
            [2251],
        )

    def test_closing_keyword(self):
        self.assertEqual(
            find_linked_issue_numbers("no ref", "Closes #99 and Fixes #100"),
            [99, 100],
        )

    def test_none(self):
        self.assertEqual(find_linked_issue_numbers("plain title", "plain body"), [])


class UndeclaredFileTests(unittest.TestCase):
    def test_all_declared(self):
        changed = ["a.py", "docs/generated/route_inventory.json"]
        undeclared = find_undeclared_files(changed, {"a.py"}, DEFAULT_SCOPE_POLICY["allowlist"])
        self.assertEqual(undeclared, [])

    def test_undeclared_detected(self):
        changed = ["a.py", "b.ts", "docs/generated/x.json"]
        undeclared = find_undeclared_files(changed, {"a.py"}, DEFAULT_SCOPE_POLICY["allowlist"])
        self.assertEqual(undeclared, ["b.ts"])

    def test_directory_declaration_covers_subtree(self):
        changed = [".github/scripts/constitution/gates.py",
                   ".github/scripts/constitution/tests/test_gates.py", "outside.py"]
        undeclared = find_undeclared_files(
            changed, {".github/scripts/"}, DEFAULT_SCOPE_POLICY["allowlist"])
        self.assertEqual(undeclared, ["outside.py"])


class LeaseGateTests(unittest.TestCase):
    def test_slot_bot_matching_branch_passes(self):
        ok, reason = check_lease("supremeai-coder-1-bot[bot]", "coder-1-2251-gates", LEASE_POLICY)
        self.assertTrue(ok, reason)

    def test_cross_slot_fails(self):
        ok, reason = check_lease("supremeai-coder-1-bot", "coder-3-sneaky", LEASE_POLICY)
        self.assertFalse(ok)
        self.assertIn("cross-slot", reason)

    def test_docs_branch_allowed(self):
        ok, _ = check_lease("supremeai-coder-2-bot", "docs/2251-notes", LEASE_POLICY)
        self.assertTrue(ok)

    def test_human_passes(self):
        ok, _ = check_lease("somehuman", "feature/whatever", LEASE_POLICY)
        self.assertTrue(ok)

    def test_exempt_bots_pass(self):
        ok, _ = check_lease("dependabot[bot]", "dependabot/pip/x", LEASE_POLICY)
        self.assertTrue(ok)

    def test_bad_branch_pattern_fails_for_bot(self):
        ok, reason = check_lease("supremeai-ci-2-bot", "random-branch", LEASE_POLICY)
        self.assertFalse(ok)
        self.assertIn("slot pattern", reason)


class PolicyLoadingTests(unittest.TestCase):
    def test_real_rules_yaml_loads(self):
        rules = Path(__file__).resolve().parents[4] / ".github" / "constitution" / "rules.yml"
        policies = load_policies(rules)
        self.assertIn("declaration_marker", policies["scope_policy"])
        self.assertIn("section_names", policies["verification_policy"])
        self.assertIn("bot_author_regex", policies["lease_policy"])

    def test_missing_file_falls_back(self):
        policies = load_policies(Path("/nonexistent/rules.yml"))
        self.assertEqual(policies["scope_policy"]["undeclared_files"], "block")


class PredecessorGateTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "group_dependencies": {
                "foundation-closeout": "pipeline-governance",
            },
            "hold_label": "queue:hold",
        }

    def test_no_group_passes(self):
        ok, reason = check_predecessor_hold("", False, False, self.policy)
        self.assertTrue(ok)
        self.assertIn("not belong", reason)

    def test_group_without_predecessor_passes(self):
        ok, reason = check_predecessor_hold("pipeline-governance", False, False, self.policy)
        self.assertTrue(ok)
        self.assertIn("no predecessor dependencies", reason)

    def test_predecessor_unmerged_with_hold_label_passes(self):
        ok, reason = check_predecessor_hold("foundation-closeout", True, True, self.policy)
        self.assertTrue(ok)
        self.assertIn("correctly held", reason)

    def test_predecessor_unmerged_without_hold_label_blocks(self):
        ok, reason = check_predecessor_hold("foundation-closeout", False, True, self.policy)
        self.assertFalse(ok)
        self.assertIn("must carry 'queue:hold' label", reason)

    def test_predecessor_merged_clears_pr(self):
        ok, reason = check_predecessor_hold("foundation-closeout", False, False, self.policy)
        self.assertTrue(ok)
        self.assertIn("is merged", reason)


if __name__ == "__main__":
    unittest.main()
