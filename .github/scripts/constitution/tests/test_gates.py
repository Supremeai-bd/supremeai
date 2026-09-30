"""Unit tests for Automated System Gates (Issue #2251 — constitution.gates)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # constitution pkg parent

from constitution.gates import (  # noqa: E402
    DEFAULT_CLAIM_POLICY,
    DEFAULT_LEASE_POLICY,
    DEFAULT_SCOPE_POLICY,
    DEFAULT_VERIFICATION_POLICY,
    author_identities,
    check_lease,
    check_predecessor_hold,
    claim_matches,
    evaluate_claim,
    extract_claim_agents,
    extract_test_evidence,
    find_linked_issue_numbers,
    find_undeclared_files,
    load_policies,
    parse_declared_files,
    path_matches,
    run_claim_gate,
)

SCOPE_POLICY = dict(DEFAULT_SCOPE_POLICY)
VERIFICATION_POLICY = dict(DEFAULT_VERIFICATION_POLICY)
LEASE_POLICY = dict(DEFAULT_LEASE_POLICY)
CLAIM_POLICY = dict(DEFAULT_CLAIM_POLICY)


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

    def test_bare_root_files_declared(self):
        # (#2612) বর্ধন-বিহীন রুট-ফাইল — আগে কোনোভাবেই ডিক্লেয়ার অসম্ভব ছিল
        # ('/' বা '.' নেই → টোকেন ড্রপ) — PR #2671-এ লাইভ ধরা পড়েছিল
        comment = "Touching files: Dockerfile, Makefile, Caddyfile"
        declared = parse_declared_files([comment])
        self.assertEqual(declared, {"Dockerfile", "Makefile", "Caddyfile"})

    def test_bare_root_file_scope_gate_end_to_end(self):
        # changed "Dockerfile" এখন ডিক্লেয়ার্ড সেটের সাথে মিলবে — আগে সবসময় undeclared
        from gates import find_undeclared_files  # local import: test-module colocated
        declared = parse_declared_files(["Touching files: Dockerfile, src/a.py"])
        self.assertEqual(
            find_undeclared_files(["Dockerfile", "src/a.py"], declared, []),
            [],
        )
        self.assertEqual(
            find_undeclared_files(["Dockerfile", "rogue.txt"], declared, []),
            ["rogue.txt"],
        )


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


class AuthorIdentityTests(unittest.TestCase):
    """#2644: PR author ↔ claim agent-name normalization."""

    def test_app_prefixed_bot(self):
        self.assertEqual(
            author_identities("app/supremeai-planner"),
            {"app/supremeai-planner", "supremeai-planner"},
        )

    def test_slot_bot_all_forms(self):
        self.assertEqual(
            author_identities("supremeai-coder-1-bot[bot]"),
            {"supremeai-coder-1-bot[bot]", "supremeai-coder-1-bot", "coder-1"},
        )

    def test_plain_slot_name(self):
        self.assertEqual(author_identities("coder-1"), {"coder-1"})

    def test_human_login(self):
        self.assertEqual(author_identities("SaifulHaqueNiloy"), {"SaifulHaqueNiloy"})

    def test_empty_is_empty(self):
        self.assertEqual(author_identities(""), set())
        self.assertEqual(author_identities(None), set())

    def test_claim_matches_exact_and_slot_forms(self):
        self.assertTrue(claim_matches("app/supremeai-planner", {"supremeai-planner"}))
        self.assertTrue(claim_matches("supremeai-coder-1-bot[bot]", {"coder-1"}))
        self.assertTrue(claim_matches("supremeai-coder-1-bot", {"supremeai-coder-1-bot[bot]"}))

    def test_claim_match_is_not_substring_spoofable(self):
        # planner-2 must NOT match a planner claim (substring ≠ identity)
        self.assertFalse(claim_matches("supremeai-planner-2-bot[bot]", {"supremeai-planner"}))
        self.assertFalse(claim_matches("app/supremeai-planner", {"supremeai-planner-2"}))
        self.assertFalse(claim_matches("app/supremeai-planner", {"supremeai-coder-1-bot"}))
        self.assertFalse(claim_matches("", {"supremeai-planner"}))


class ClaimAgentExtractionTests(unittest.TestCase):
    """#2644: Atomic Claim comment agent-field parsing (atomic_claim.sh format)."""

    def test_parses_canonical_claim_comment(self):
        comments = [{
            "body": (
                "### 🔒 Atomic Claim Established (GAP-01)\n\n"
                "- **Agent:** `supremeai-coder-1-bot`\n"
                "- **Issue:** #2630\n"
                "- **Branch:** `coder-1-2630-safe-auto-merge`\n"
                "- **Touching files:** scripts/ci/x.py"
            )
        }]
        self.assertEqual(extract_claim_agents(comments), {"supremeai-coder-1-bot"})

    def test_ignores_non_claim_comments(self):
        self.assertEqual(
            extract_claim_agents([{"body": "random chatter about claims"}]),
            set(),
        )
        self.assertEqual(extract_claim_agents([]), set())

    def test_agent_name_must_come_from_parsed_field_not_body_substring(self):
        # 'supremeai-planner' merely MENTIONED in prose must not count as claimer
        comments = [{
            "body": "Atomic Claim discussion — cc @supremeai-planner for review, agent was someone-else"
        }]
        self.assertEqual(extract_claim_agents(comments), set())

    def test_string_comments_tolerated(self):
        self.assertEqual(
            extract_claim_agents(["Atomic Claim\n- **Agent:** `x-bot`"]),
            {"x-bot"},
        )


class EvaluateClaimTests(unittest.TestCase):
    """#2644: claim-before-work pure evaluation."""

    def setUp(self):
        self.policy = dict(DEFAULT_CLAIM_POLICY)

    def ev(self, author, assoc, linked):
        return evaluate_claim(author, assoc, linked, self.policy)

    def test_agent_unclaimed_blocks_even_for_owner_association(self):
        # 8-PRs-in-flight root cause: OWNER-associated app bot must NOT slip through
        ok, reason = self.ev(
            "app/supremeai-planner", "OWNER",
            [{"number": 2507, "assignees": [], "claim_agents": set(), "group_peers": set()}],
        )
        self.assertFalse(ok)
        self.assertIn("NO claim", reason)
        self.assertIn("atomic_claim.sh", reason)

    def test_agent_with_claim_passes(self):
        ok, reason = self.ev(
            "app/supremeai-planner", "NONE",
            [{"number": 2644, "assignees": [], "claim_agents": {"supremeai-planner"}, "group_peers": set()}],
        )
        self.assertTrue(ok)
        self.assertIn("claim verified", reason)

    def test_human_owner_unclaimed_is_advisory_pass(self):
        ok, _ = self.ev(
            "SaifulHaqueNiloy", "OWNER",
            [{"number": 1, "assignees": [], "claim_agents": set(), "group_peers": set()}],
        )
        self.assertTrue(ok)

    def test_human_outsider_unclaimed_blocks(self):
        ok, _ = self.ev(
            "random-contributor", "NONE",
            [{"number": 1, "assignees": [], "claim_agents": set(), "group_peers": set()}],
        )
        self.assertFalse(ok)

    def test_human_claimed_via_assignee_passes(self):
        ok, _ = self.ev(
            "SaifulHaqueNiloy", "NONE",
            [{"number": 1, "assignees": ["SaifulHaqueNiloy"], "claim_agents": set(), "group_peers": set()}],
        )
        self.assertTrue(ok)

    def test_exempt_bots_pass(self):
        for bot in ("dependabot[bot]", "app/dependabot", "renovate[bot]"):
            ok, _ = self.ev(
                bot, "NONE",
                [{"number": 1, "assignees": [], "claim_agents": set(), "group_peers": set()}],
            )
            self.assertTrue(ok, bot)

    def test_no_linked_issue_blocks(self):
        ok, reason = self.ev("somebody", "NONE", [])
        self.assertFalse(ok)
        self.assertIn("no linked issue", reason)

    def test_group_peer_claims_count(self):
        # #2378: group PR referencing closeout issue; author claimed a sibling
        ok, _ = self.ev(
            "supremeai-coder-1-bot[bot]", "NONE",
            [{"number": 999, "assignees": [], "claim_agents": set(), "group_peers": {"coder-1"}}],
        )
        self.assertTrue(ok)

    def test_other_agents_claim_does_not_count(self):
        ok, _ = self.ev(
            "app/supremeai-planner", "NONE",
            [{"number": 1, "assignees": [], "claim_agents": {"supremeai-coder-1-bot"}, "group_peers": set()}],
        )
        self.assertFalse(ok)

    def test_unclaimed_pr_policy_warn_mode(self):
        pol = dict(self.policy)
        pol["unclaimed_pr"] = "warn"
        ok, _ = evaluate_claim(
            "random-contributor", "NONE",
            [{"number": 1, "assignees": [], "claim_agents": set(), "group_peers": set()}],
            pol,
        )
        self.assertTrue(ok)


class RunClaimGateTests(unittest.TestCase):
    """#2644: API-driven run_claim_gate with a mock gh_api."""

    def setUp(self):
        self.policy = dict(DEFAULT_CLAIM_POLICY)
        # _repo() reads GH_REPO — pin it so mock endpoints resolve to repos/x/*
        self._saved_repo = os.environ.get("GH_REPO")
        os.environ["GH_REPO"] = "x"

    def tearDown(self):
        if self._saved_repo is None:
            os.environ.pop("GH_REPO", None)
        else:
            os.environ["GH_REPO"] = self._saved_repo

    @staticmethod
    def make_api(issues: dict, comments: dict):
        """issues: {num: payload}, comments: {num: [bodies]} — dict-backed API."""
        def api(endpoint):
            if endpoint.startswith("repos/x/issues/") and not endpoint.startswith("repos/x/issues?"):
                num = int(endpoint.split("/")[3].split("?")[0])
                if "/comments" in endpoint:
                    if num in comments:
                        return [{"body": b} for b in comments[num]]
                    raise RuntimeError(f"404 issue {num}")
                if num in issues:
                    return issues[num]
                raise RuntimeError(f"404 issue {num}")
            if endpoint.startswith("repos/x/issues?"):
                import urllib.parse as up
                qs = up.parse_qs(endpoint.split("?", 1)[1])
                label = (qs.get("labels") or [""])[0]
                return [i for i in issues.values()
                        if label in [l.get("name") for l in i.get("labels", [])]]
            raise RuntimeError(f"unexpected endpoint {endpoint}")
        return api

    def test_unclaimed_agent_pr_blocks(self):
        api = self.make_api(
            issues={2507: {"assignees": [], "labels": []}},
            comments={2507: []},
        )
        rc = run_claim_gate(
            2643, "app/supremeai-planner",
            "fix(quality): prune stale rows (#2507)", "Refs #2507", "OWNER",
            self.policy, api=api,
        )
        self.assertEqual(rc, 1)

    def test_claimed_agent_pr_passes(self):
        api = self.make_api(
            issues={2644: {"assignees": [], "labels": []}},
            comments={2644: [
                "### 🔒 Atomic Claim Established (GAP-01)\n- **Agent:** `supremeai-planner`"
            ]},
        )
        rc = run_claim_gate(
            0, "app/supremeai-planner",
            "feat(agents): claim gate (#2644)", "Refs #2644", "OWNER",
            self.policy, api=api,
        )
        self.assertEqual(rc, 0)

    def test_assignee_claim_passes(self):
        api = self.make_api(
            issues={100: {"assignees": [{"login": "supremeai-coder-1-bot"}], "labels": []}},
            comments={100: []},
        )
        rc = run_claim_gate(
            0, "supremeai-coder-1-bot[bot]",
            "fix(x): thing (#100)", "Closes #100", "NONE",
            self.policy, api=api,
        )
        self.assertEqual(rc, 0)

    def test_no_issue_refs_blocks(self):
        rc = run_claim_gate(
            0, "supremeai-coder-1-bot[bot]",
            "fix(x): no pointer here", "nothing to see", "NONE",
            self.policy, api=lambda e: (_ for _ in ()).throw(RuntimeError("unused")),
        )
        self.assertEqual(rc, 1)

    def test_api_total_failure_is_advisory_pass(self):
        # CI never hard-depends on API uptime (house rule)
        def dead_api(endpoint):
            raise RuntimeError("api down")
        rc = run_claim_gate(
            0, "supremeai-coder-1-bot[bot]",
            "fix(x): thing (#100)", "Closes #100", "NONE",
            self.policy, api=dead_api,
        )
        self.assertEqual(rc, 0)

    def test_group_issue_accepts_sibling_claim(self):
        api = self.make_api(
            issues={
                500: {"number": 500, "assignees": [], "labels": [{"name": "group:alpha"}]},
                501: {"number": 501, "assignees": [], "labels": [{"name": "group:alpha"}]},
            },
            comments={
                500: [],
                501: ["Atomic Claim\n- **Agent:** `coder-1`"],
            },
        )
        rc = run_claim_gate(
            0, "supremeai-coder-1-bot[bot]",
            "feat(group): closeout (#500)", "Closes #500", "NONE",
            self.policy, api=api,
        )
        self.assertEqual(rc, 0)


class ClaimGatePolicyLoadingTests(unittest.TestCase):
    def test_real_rules_yaml_carries_claim_policy(self):
        policies = load_policies()
        cp = policies["claim_policy"]
        self.assertEqual(cp["unclaimed_pr"], "block")
        self.assertEqual(cp["missing_issue_ref"], "block")
        self.assertIn("supremeai-", cp["agent_author_prefixes"])


if __name__ == "__main__":
    unittest.main()
