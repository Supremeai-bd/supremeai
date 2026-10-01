"""Template Conformance Gate tests (#2912) — fixed template mandate, সব agent-এর জন্য।

Fake-issue/PR injection — কোনো নেটওয়ার্ক কল নেই (test_branch_creation_guard-প্যাটার্ন)।
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # constitution pkg parent

import template_gate as tg  # noqa: E402

REPO = "SaifulHaqueNiloy/supremeai"
REPO_ROOT = Path(__file__).resolve().parents[4]  # …/supremeai-repo
RULES = REPO_ROOT / ".github" / "constitution" / "rules.yml"  # policy SSOT
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "issue-template-guard.yml"
PR_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr.yml"

AFTER = "2026-10-01T20:30:00Z"  # enforce_from (20:00Z)-এর পরের সময়
BEFORE = "2026-10-01T19:30:00Z"  # enforce_from-এর আগের সময় (grandfathered)


def policy(**overrides):
    p = dict(tg.DEFAULT_TEMPLATE_POLICY)
    p.update(overrides)
    return p


def agent_issue(**overrides) -> dict:
    """সম্পূর্ণ template-compliant agent-issue (baseline)।"""
    issue = {
        "number": 3000,
        "title": "fix(ci): sample compliant issue",
        "body": (
            "### Mission & Problem Statement\nকী ও কেন।\n\n"
            "### Priority Tier\nP1-high (governance)\n\n"
            "### Touching Files (Scope Gate Boundary)\n- path/a.py\n\n"
            "### 3-Tier Verification Contract\n1. Reflection\n2. Boot\n3. Pytest\n"
        ),
        "user": {"login": "supremeai-planner[bot]"},
        "labels": [{"name": "P1-high"}],
        "created_at": AFTER,
        "state": "open",
    }
    issue.update(overrides)
    return issue


def agent_pr(**overrides) -> dict:
    pr = {
        "number": 4000,
        "title": "fix(ci): sample compliant PR (#3000)",
        "body": (
            "## Summary\nকী বদলালো।\n\n"
            "## Linked Issue / Claim\nRefs #3000\n\n"
            "## Rollback Path\n- [ ] git revert-নিরাপদ\n"
        ),
        "user": {"login": "supremeai-coder-1-bot[bot]"},
        "created_at": AFTER,
    }
    pr.update(overrides)
    return pr


# ---------------------------------------------------------------------------
# Identity — default-deny (#2912 V1)
# ---------------------------------------------------------------------------
class IdentityDefaultDenyTests(unittest.TestCase):
    def test_known_fleet_identities_are_agents(self):
        p = policy()
        for a in (
            "supremeai-planner",
            "supremeai-planner[bot]",
            "app/supremeai-planner",
            "supremeai-coder-1-bot[bot]",
            "supremeai-3rd-party-platform",
            "app/supremeai-coder-1-bot",
        ):
            self.assertEqual(tg.actor_category(a, p), "agent", a)

    def test_unknown_identity_is_agent_not_human(self):
        # ROOT-CAUSE regression: অজানা নতুন বট আর "human" বলে ফাঁকি দিতে পারবে না
        p = policy()
        for a in (
            "niloy-helper-bot",
            "some-new-agent[bot]",
            "auto-coder-2",
            "release-bot",
            "mystery-ci",
            "",
        ):
            self.assertEqual(tg.actor_category(a, p), "agent", a)

    def test_human_allowlist_and_trusted_bots(self):
        p = policy()
        self.assertEqual(tg.actor_category("SaifulHaqueNiloy", p), "human")
        self.assertEqual(tg.actor_category("app/dependabot", p), "trusted_bot")
        self.assertEqual(tg.actor_category("dependabot[bot]", p), "trusted_bot")
        self.assertEqual(tg.actor_category("github-actions[bot]", p), "trusted_bot")

    def test_is_agent_actor_wrapper(self):
        p = policy()
        self.assertTrue(tg.is_agent_actor("supremeai-planner[bot]", p))
        self.assertFalse(tg.is_agent_actor("SaifulHaqueNiloy", p))
        self.assertTrue(tg.is_agent_actor("unknown-newcomer", p))  # default-deny

    def test_login_normalization(self):
        self.assertEqual(
            tg.normalize_login("app/supremeai-planner"), "supremeai-planner"
        )
        self.assertEqual(
            tg.normalize_login("supremeai-planner[bot]"), "supremeai-planner"
        )
        self.assertEqual(tg.normalize_login(""), "")


# ---------------------------------------------------------------------------
# Issue validation — চুক্তি যাচাই
# ---------------------------------------------------------------------------
class IssueValidationTests(unittest.TestCase):
    def test_compliant_agent_issue_passes(self):
        status, missing, _ = tg.validate_issue(agent_issue(), policy())
        self.assertEqual(status, "compliant")
        self.assertEqual(missing, [])

    def test_freeform_agent_issue_violates(self):
        # red-team V3: `gh issue create --body` freeform — সব চুক্তি অদৃশ্য
        status, missing, _ = tg.validate_issue(
            agent_issue(
                title="Smart loop improvement",
                body="Just do it better.",
                labels=[{"name": "area:ci"}],
            ),
            policy(),
        )
        self.assertEqual(status, "violating")
        joined = " | ".join(missing)
        self.assertIn("title-convention", joined)
        self.assertIn("Mission", joined)
        self.assertIn("Touching Files", joined)
        self.assertIn("Verification", joined)
        self.assertIn("priority tier", joined)

    def test_title_convention_variants(self):
        p = policy()
        for title in (
            "fix(ci): x",
            "feat(backend): y",
            "chore(repo): z",
            "docs(master): w",
            "refactor(frontend): v",
            "perf(db): u",
            "test(api): t",
            "audit(sec): s",
            "ops(infra): r",
            "task(tool): q",
        ):
            self.assertEqual(
                tg.validate_issue(agent_issue(title=title), p)[0], "compliant", title
            )
        for title in (
            "no convention here",
            "Fix(ci): uppercase lane",
            "fix(ci) missing colon",
            "fix: no scope",
        ):
            self.assertEqual(
                tg.validate_issue(agent_issue(title=title), p)[0], "violating", title
            )

    def test_each_missing_section_reported(self):
        p = policy()
        body = "### Mission & Problem Statement\nok\n"  # শুধু Mission আছে
        status, missing, _ = tg.validate_issue(
            agent_issue(body=body, labels=[{"name": "area:ci"}]), p
        )
        self.assertEqual(status, "violating")
        self.assertIn("section 'Touching Files'", missing)
        self.assertIn("section 'Verification'", missing)
        self.assertTrue(any("priority tier" in m for m in missing))

    def test_priority_via_label_only_counts(self):
        # group_sequence template: body-তে Priority সেকশন নেই, লেবেল আছে
        body = (
            "### Mission & Problem Statement\nx\n### Touching Files (Atomic Blast Radius)\ny\n"
            "### 3-Tier Verification Contract\nz\n"
        )
        status, _, _ = tg.validate_issue(agent_issue(body=body), policy())
        self.assertEqual(status, "compliant")

    def test_human_author_skipped(self):
        status, _, reason = tg.validate_issue(
            agent_issue(
                user={"login": "SaifulHaqueNiloy"},
                title="যেকোনো freeform শিরোনাম",
                body="ফ্রিফর্ম",
            ),
            policy(),
        )
        self.assertEqual(status, "skip")
        self.assertIn("human", reason)

    def test_trusted_bot_author_skipped(self):
        status, _, _ = tg.validate_issue(
            agent_issue(user={"login": "dependabot[bot]"}), policy()
        )
        self.assertEqual(status, "skip")

    def test_exempt_labels_skip(self):
        for lb in ("type:ledger", "type:platform-alert", "template:exempt"):
            issue = agent_issue(labels=[{"name": lb}], title="no convention", body="")
            status, _, reason = tg.validate_issue(issue, policy())
            self.assertEqual(status, "skip", lb)
            self.assertIn(lb, reason)

    def test_marker_quoted_mid_prose_is_not_exempt(self):
        # SELF-RED-TEAM regression (#2912): মার্কার-টেক্সট উদ্ধৃত-করা ডকুমেন্টেশন-
        # ইস্যু false-exempt হবে না — সাধারণ ইস্যুর মতোই যাচাই হবে
        issue = agent_issue(
            title="fix(docs): ledger ব্যাখ্যা",
            body="ব্যাখ্যা: ledger body শুরু হয় `<!-- SUPREMEAI_PRIORITY_QUEUE_LEDGER` দিয়ে।",
        )
        status, _, _ = tg.validate_issue(issue, policy())
        self.assertEqual(status, "violating")  # সেকশন-চুক্তি নেই → স্বাভাবিক যাচাই

    def test_ledger_body_marker_skips_even_without_label(self):
        issue = agent_issue(
            body="<!-- SUPREMEAI_PRIORITY_QUEUE_LEDGER v1 -->\n# queue", title="x"
        )
        status, _, reason = tg.validate_issue(issue, policy())
        self.assertEqual(status, "skip")
        self.assertIn("marker", reason)

    def test_grandfathered_before_enforce_from(self):
        status, _, reason = tg.validate_issue(
            agent_issue(created_at=BEFORE, title="no convention", body="freeform"),
            policy(),
        )
        self.assertEqual(status, "skip")
        self.assertIn("grandfathered", reason)

    def test_enforced_on_or_after_enforce_from(self):
        status, _, _ = tg.validate_issue(
            agent_issue(
                created_at="2026-10-01T20:00:00Z", title="no convention", body=""
            ),
            policy(),
        )
        self.assertEqual(status, "violating")

    def test_disabled_policy_skips(self):
        status, _, _ = tg.validate_issue(
            agent_issue(title="x", body=""), policy(enabled=False)
        )
        self.assertEqual(status, "skip")

    def test_group_sequence_shaped_issue_passes(self):
        body = (
            "### Group Name\nstep-3\n### Sequence Number (seq:N)\n2\n"
            "### Mission & Problem Statement\nমিশন\n"
            "### Touching Files (Atomic Blast Radius)\nbackend/x.py\n"
            "### 3-Tier Verification Contract\n1..2..3\n"
        )
        issue = agent_issue(
            title="refactor(core): [Step-3.2] sample",
            body=body,
            labels=[{"name": "P2-medium"}],
        )
        status, _, _ = tg.validate_issue(issue, policy())
        self.assertEqual(status, "compliant")


# ---------------------------------------------------------------------------
# PR validation — চুক্তি + chain
# ---------------------------------------------------------------------------
class PrValidationTests(unittest.TestCase):
    def test_compliant_pr_passes(self):
        status, missing, _ = tg.validate_pr(agent_pr(), [agent_issue()], policy())
        self.assertEqual(status, "compliant")

    def test_missing_pr_sections_reported(self):
        status, missing, _ = tg.validate_pr(
            agent_pr(body="এক লাইনের body"), [], policy()
        )
        self.assertEqual(status, "violating")
        joined = " | ".join(missing)
        self.assertIn("Summary", joined)
        self.assertIn("Linked Issue", joined)
        self.assertIn("Rollback", joined)

    def test_bangla_rollback_heading_accepted(self):
        body = (
            "## Summary\nx\n## Related Issue\nRefs #3000\n## রোলব্যাক পথ\nrevert-safe\n"
        )
        status, _, _ = tg.validate_pr(agent_pr(body=body), [], policy())
        self.assertEqual(status, "compliant")

    def test_related_issue_heading_alias_accepted(self):
        body = "## Summary\nx\n## Related Issue\nCloses #3000\n## Rollback Path\nok\n"
        status, _, _ = tg.validate_pr(agent_pr(body=body), [], policy())
        self.assertEqual(status, "compliant")

    def test_grandfathered_pr_skipped(self):
        status, _, reason = tg.validate_pr(
            agent_pr(created_at=BEFORE, body="one-liner"), [], policy()
        )
        self.assertEqual(status, "skip")
        self.assertIn("grandfathered", reason)

    def test_human_pr_skipped(self):
        status, _, _ = tg.validate_pr(
            agent_pr(user={"login": "SaifulHaqueNiloy"}, body="x"), [], policy()
        )
        self.assertEqual(status, "skip")

    def test_chain_violating_linked_issue_blocks_pr(self):
        # চেইন-ডকট্রিন: linked issue template-অসম্পূর্ণ হলে PR-ও violating
        bad_issue = agent_issue(title="no convention", body="freeform")
        status, missing, _ = tg.validate_pr(agent_pr(), [bad_issue], policy())
        self.assertEqual(status, "violating")
        joined = " | ".join(missing)
        self.assertIn("#3000", joined)
        self.assertIn("template-অসম্পূর্ণ", joined)

    def test_chain_exempt_linked_issue_does_not_block(self):
        ledger_issue = agent_issue(
            labels=[{"name": "type:ledger"}], title="x", body="y"
        )
        status, _, _ = tg.validate_pr(agent_pr(), [ledger_issue], policy())
        self.assertEqual(status, "compliant")

    def test_chain_human_linked_issue_does_not_block(self):
        human_issue = agent_issue(
            user={"login": "SaifulHaqueNiloy"}, title="free", body="form"
        )
        status, _, _ = tg.validate_pr(agent_pr(), [human_issue], policy())
        self.assertEqual(status, "compliant")


# ---------------------------------------------------------------------------
# Self-heal — label/comment প্রয়োগ
# ---------------------------------------------------------------------------
class FakeApi:
    def __init__(self):
        self.calls = []

    def __call__(self, endpoint, method="GET", payload=None):
        self.calls.append((method, endpoint, payload))
        return {}


class ApplyVerdictTests(unittest.TestCase):
    def test_violating_labels_and_comments_once(self):
        api = FakeApi()
        issue = agent_issue(title="no convention", body="freeform")  # লেবেল নেই
        verdict = tg.validate_issue(issue, policy())
        actions = tg.apply_issue_verdict(issue, verdict, policy(), api, REPO)
        joined = " | ".join(actions)
        self.assertIn("label 'template:violating' added", joined)
        self.assertIn("corrective comment posted", joined)
        methods = [(m, e.split("/")[-1]) for m, e, _ in api.calls]
        self.assertIn(("POST", "labels"), methods)
        self.assertIn(("POST", "comments"), methods)

    def test_repeat_violation_no_comment_spam(self):
        # লেবেল আগেই আছে → শুধু লেবেল-রি-অ্যাড নয়, কমেন্ট-স্প্যামও নয়
        api = FakeApi()
        issue = agent_issue(
            title="no convention",
            body="freeform",
            labels=[{"name": "template:violating"}, {"name": "P1-high"}],
        )
        verdict = tg.validate_issue(issue, policy())
        actions = tg.apply_issue_verdict(issue, verdict, policy(), api, REPO)
        self.assertEqual(actions, [])
        self.assertEqual(api.calls, [])

    def test_compliant_removes_stale_label(self):
        api = FakeApi()
        issue = agent_issue(labels=[{"name": "template:violating"}])
        verdict = tg.validate_issue(issue, policy())
        actions = tg.apply_issue_verdict(issue, verdict, policy(), api, REPO)
        joined = " | ".join(actions)
        self.assertIn("label 'template:violating' removed", joined)
        self.assertIn("resolution comment posted", joined)
        methods = [m for m, _, _ in api.calls]
        self.assertIn("DELETE", methods)

    def test_compliant_without_label_is_noop(self):
        api = FakeApi()
        issue = agent_issue()
        verdict = tg.validate_issue(issue, policy())
        actions = tg.apply_issue_verdict(issue, verdict, policy(), api, REPO)
        self.assertEqual(actions, [])
        self.assertEqual(api.calls, [])

    def test_skip_is_noop(self):
        api = FakeApi()
        issue = agent_issue(user={"login": "SaifulHaqueNiloy"})
        verdict = tg.validate_issue(issue, policy())
        actions = tg.apply_issue_verdict(issue, verdict, policy(), api, REPO)
        self.assertEqual(actions, [])


# ---------------------------------------------------------------------------
# Policy SSOT + workflow wiring
# ---------------------------------------------------------------------------
class PolicySsotTests(unittest.TestCase):
    def test_real_rules_yaml_carries_template_policy(self):
        import yaml

        data = yaml.safe_load(RULES.read_text(encoding="utf-8"))
        tp = data.get("template_policy")
        self.assertIsInstance(tp, dict)
        self.assertTrue(tp.get("enabled"))
        self.assertEqual(tp["issue"]["violating_label"], "template:violating")
        self.assertIn("Mission", tp["issue"]["required_sections"])
        self.assertIn("Touching Files", tp["issue"]["required_sections"])
        # identity default-deny SSOT
        ident = data.get("identity_policy")
        self.assertIsInstance(ident, dict)
        self.assertIn("SaifulHaqueNiloy", ident.get("human_allowlist", []))
        # branch policy সংযোগ
        bcp = data.get("branch_creation_policy")
        self.assertIn("template:violating", bcp.get("claim_source_blocked_labels", []))
        # #2912 V2: backport/release আর exempt নয়; group/docs স্পষ্টভাবে PR-gated
        self.assertNotIn("backport/*", bcp.get("exempt_branch_patterns", []))
        self.assertNotIn("release/*", bcp.get("exempt_branch_patterns", []))
        self.assertIn("group/*", bcp.get("pr_gated_branch_patterns", []))
        self.assertIn("docs/*", bcp.get("pr_gated_branch_patterns", []))

    def test_load_template_policy_merges_rules(self):
        pol = tg.load_template_policy(RULES)
        self.assertTrue(pol["enabled"])
        self.assertEqual(pol["issue"]["violating_label"], "template:violating")
        self.assertIn("SaifulHaqueNiloy", pol["human_allowlist"])

    def test_load_defaults_on_missing_file(self):
        pol = tg.load_template_policy(Path("/nonexistent/rules.yml"))
        self.assertTrue(pol["enabled"])
        self.assertEqual(pol["issue"]["violating_label"], "template:violating")


class WorkflowWiringTests(unittest.TestCase):
    def setUp(self):
        import yaml

        self.wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        self.pw = yaml.safe_load(PR_WORKFLOW.read_text(encoding="utf-8"))

    def _triggers(self, wf) -> dict:
        return wf.get("on") or wf.get(True) or {}

    def test_issue_workflow_triggers(self):
        trg = self._triggers(self.wf)
        self.assertEqual(
            trg.get("issues", {}).get("types"), ["opened", "edited", "reopened"]
        )

    def test_issue_workflow_permissions(self):
        perms = self.wf.get("permissions") or {}
        self.assertEqual(perms.get("issues"), "write")
        self.assertEqual(perms.get("contents"), "read")

    def test_issue_workflow_invokes_gate(self):
        run = self.wf["jobs"]["validate"]["steps"][-1]["run"]
        self.assertIn("template_gate.py --issue", run)

    def test_pr_wiring_has_blocking_template_gate(self):
        # pr.yml → system-gates → Constitutional Gates Execution স্টেপে blocking কল
        steps = self.pw["jobs"]["system-gates"]["steps"]
        gate_step = next(
            s for s in steps if "Constitutional Gates Execution" in s.get("name", "")
        )
        self.assertIn("template_gate.py --pr", gate_step["run"])
        # || true (advisory) নয় — blocking হতে হবে
        for line in gate_step["run"].splitlines():
            if "template_gate.py --pr" in line:
                self.assertNotIn("|| true", line)
                break


if __name__ == "__main__":
    unittest.main()
