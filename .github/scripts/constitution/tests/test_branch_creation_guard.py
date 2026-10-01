"""Branch Creation Guard tests (#2907) — no-branch-without-claim, branch-টাইম enforcement.

Fake-api injection প্যাটার্ন (test_gates.py-র মতোই) — কোনো নেটওয়ার্ক কল নেই।
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)  # constitution pkg parent (test_gates-প্যাটার্ন)

import branch_creation_guard as guard  # noqa: E402

REPO = "SaifulHaqueNiloy/supremeai"
CLAIM_COMMENT_PLANNER = {
    "body": "### 🔒 Atomic Claim Established\n\n- **Agent:** `supremeai-planner`\n- **Issue:** #2891"
}
CLAIM_COMMENT_CODER = {
    "body": "🔐 **Atomic Claim** — #2907\n\n**Agent:** `supremeai-coder-1-bot`"
}
REPO_ROOT = Path(__file__).resolve().parents[4]  # …/supremeai-repo
REGISTRY = REPO_ROOT / "docs" / "master_docs" / "AGENT_SLOT_REGISTRY.yaml"
RULES = REPO_ROOT / ".github" / "constitution" / "rules.yml"  # policy SSOT
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "branch-creation-guard.yml"


class FakeApi:
    """GET/POST/DELETE রেকর্ড করা in-memory API।"""

    def __init__(self, issues=None, comments=None, open_prs=None, fail_endpoints=None):
        self.issues = issues or {}  # {issue_num: dict | Exception}
        self.comments = comments or {}  # {issue_num: [comment-dicts]}
        self.open_prs = open_prs or {}  # {branch: [pr-dicts]}
        self.fail_endpoints = fail_endpoints or set()
        self.calls: list = []

    def __call__(self, endpoint, method="GET", payload=None):
        self.calls.append((method, endpoint, payload))
        for frag in self.fail_endpoints:
            if frag in endpoint:
                raise RuntimeError(f"api down: {endpoint}")
        if (
            method == "GET"
            and endpoint.startswith(f"repos/{REPO}/issues/")
            and endpoint.endswith("/comments?per_page=100")
        ):
            num = int(endpoint.split("/issues/")[1].split("/")[0])
            return self.comments.get(num, [])
        if method == "GET" and endpoint.startswith(f"repos/{REPO}/pulls?head="):
            branch = (
                endpoint.split("head=")[1]
                .split("&")[0]
                .removeprefix(f"{REPO.split('/')[0]}:")
            )
            return self.open_prs.get(branch, [])
        if method == "GET" and endpoint.startswith(f"repos/{REPO}/issues/"):
            num = int(endpoint.rsplit("/", 1)[1])
            hit = self.issues.get(num)
            if isinstance(hit, Exception):
                raise hit
            return hit if hit is not None else {"message": "Not Found"}
        return {}


def policy(**overrides):
    p = dict(guard.DEFAULT_BRANCH_CREATION_POLICY)
    p["agent_author_prefixes"] = ["supremeai-", "app/supremeai-"]
    p.update(overrides)
    return p


OPEN_ISSUE = {"number": 2891, "state": "open", "assignees": []}


class ParseTests(unittest.TestCase):
    def test_lane_branch_extracts_issue_not_slot(self):
        # coder-1-2891-slug → 2891 (slot "1" বাদ)
        self.assertEqual(guard.parse_issue_numbers("coder-1-2891-slug", 2), [2891])

    def test_multi_issue_branch_all_numbers(self):
        self.assertEqual(
            guard.parse_issue_numbers("fix/2829-2833-test-assertion-fixes", 2),
            [2829, 2833],
        )

    def test_pr_suffix_digit_skipped(self):
        # plan-2841-pr2-doc → "2" এক-ডিজিট, বাদ
        self.assertEqual(guard.parse_issue_numbers("plan-2841-pr2-doc", 2), [2841])

    def test_bare_slot_branch_has_no_issue(self):
        self.assertEqual(guard.parse_issue_numbers("agent-8", 2), [])

    def test_empty_and_none(self):
        self.assertEqual(guard.parse_issue_numbers("", 2), [])
        self.assertEqual(guard.parse_issue_numbers(None, 2), [])


class ActorTests(unittest.TestCase):
    def test_supremeai_bots_are_agents(self):
        self.assertTrue(guard.is_agent_actor("supremeai-planner[bot]", policy()))
        self.assertTrue(guard.is_agent_actor("app/supremeai-coder-1-bot", policy()))
        self.assertTrue(
            guard.is_agent_actor("supremeai-3rd-party-platform[bot]", policy())
        )

    def test_humans_and_external_bots_are_not(self):
        self.assertFalse(guard.is_agent_actor("SaifulHaqueNiloy", policy()))
        self.assertFalse(guard.is_agent_actor("dependabot[bot]", policy()))
        self.assertFalse(guard.is_agent_actor("github-actions[bot]", policy()))

    def test_unknown_identity_is_agent_default_deny(self):
        # #2912 V1 ROOT-CAUSE regression: অজানা/নতুন বট আর "human" বলে
        # ফাঁকি দিতে পারবে না — allowlist-of-prefixes নয়, default-deny।
        for a in (
            "niloy-helper-bot",
            "some-new-agent[bot]",
            "auto-coder-2",
            "release-bot",
            "mystery-ci",
        ):
            self.assertTrue(guard.is_agent_actor(a, policy()), a)


class ExemptTests(unittest.TestCase):
    def test_exempt_patterns(self):
        p = policy()
        for b in (
            "main",
            "develop",
            "dependabot/pip/backend/x-1.2",
            "gh-readonly-queue/main-abc",
            "renovate/x-1",
        ):
            self.assertTrue(guard.is_exempt_branch(b, p["exempt_branch_patterns"]), b)

    def test_backport_release_no_longer_exempt(self):
        # #2912 V2: backport/* ও release/* এখন সাধারণ branch — issue+claim চায়
        p = policy()
        for b in ("backport/2891-x", "release/2.1", "release/anything"):
            self.assertFalse(guard.is_exempt_branch(b, p["exempt_branch_patterns"]), b)
            self.assertFalse(
                guard.is_exempt_branch(b, p.get("pr_gated_branch_patterns")), b
            )

    def test_group_docs_are_pr_gated(self):
        # #2912: group/* + docs/* branch-জন্মে ছাড় পায়, কিন্তু শব্দার্থ আলাদা —
        # PR-টাইম Lease Gate-এর এখতিয়ার (exempt full-bypass নয়)।
        p = policy()
        for b in ("group/foundation-closeout", "docs/some-notes"):
            self.assertFalse(guard.is_exempt_branch(b, p["exempt_branch_patterns"]), b)
            self.assertTrue(guard.is_exempt_branch(b, p["pr_gated_branch_patterns"]), b)

    def test_issue_branches_not_exempt(self):
        p = policy()
        for b in (
            "coder-1-2891-slug",
            "fix/2891-x",
            "plan-2841-pr2-y",
            "agent-3-2608-fix",
        ):
            self.assertFalse(guard.is_exempt_branch(b, p["exempt_branch_patterns"]), b)
            self.assertFalse(
                guard.is_exempt_branch(b, p.get("pr_gated_branch_patterns")), b
            )

    def test_slot_registry_branches(self):
        reg = guard.slot_registry_branches(REGISTRY)
        self.assertIn("agent-1-planner", reg)  # legacy slot-branch sanctioned
        self.assertIn("agent-2-pr-helper", reg)

    def test_missing_registry_is_empty_fail_open(self):
        self.assertEqual(
            guard.slot_registry_branches("/nonexistent/registry.yaml"), set()
        )


class CheckBranchTests(unittest.TestCase):
    def test_claimed_lane_branch_allows(self):
        api = FakeApi(
            issues={2907: {"number": 2907, "state": "open", "assignees": []}},
            comments={2907: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, num = guard.check_branch(
            "coder-1-2907-branch-guard",
            "supremeai-coder-1-bot[bot]",
            policy(),
            api=api,
            repo=REPO,
        )
        self.assertEqual(verdict, "ALLOW")
        self.assertIn("Atomic-Claim verified", reason)
        self.assertEqual(num, 2907)

    def test_claim_by_other_agent_violates(self):
        api = FakeApi(
            issues={2891: OPEN_ISSUE}, comments={2891: [CLAIM_COMMENT_PLANNER]}
        )
        verdict, reason, num = guard.check_branch(
            "coder-1-2891-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("no claim by", reason)

    def test_no_issue_number_violates(self):
        api = FakeApi()
        verdict, reason, _ = guard.check_branch(
            "coder-1-some-random-work",
            "supremeai-planner[bot]",
            policy(),
            api=api,
            repo=REPO,
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("no issue number", reason)

    def test_missing_issue_violates(self):
        # ৪০৪-dict (gh-CLI fallback path) ও HTTPError(404) — দুই রূপেই not-found violation
        api = FakeApi(issues={99999: {"message": "Not Found"}})
        verdict, reason, _ = guard.check_branch(
            "fix/99999-ghost", "supremeai-planner[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("not found", reason)

        import urllib.error

        api2 = FakeApi(
            issues={99999: urllib.error.HTTPError("url", 404, "Not Found", None, None)}
        )
        verdict2, reason2, _ = guard.check_branch(
            "fix/99999-ghost", "supremeai-planner[bot]", policy(), api=api2, repo=REPO
        )
        self.assertEqual(verdict2, "VIOLATION")
        self.assertIn("404", reason2)

    def test_api_5xx_fail_open_skip(self):
        import urllib.error

        api = FakeApi(
            issues={2907: urllib.error.HTTPError("url", 503, "unavailable", None, None)}
        )
        verdict, _, _ = guard.check_branch(
            "coder-1-2907-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "SKIP")

    def test_closed_issue_violates(self):
        api = FakeApi(
            issues={2891: {"number": 2891, "state": "closed", "assignees": []}},
            comments={2891: [CLAIM_COMMENT_PLANNER]},
        )
        verdict, reason, _ = guard.check_branch(
            "fix/2891-x", "supremeai-planner[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("closed", reason)

    def test_human_actor_advisory_allow(self):
        api = FakeApi()
        verdict, _, _ = guard.check_branch(
            "whatever-branch", "SaifulHaqueNiloy", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "ALLOW")

    def test_exempt_and_registry_allow_without_api(self):
        api = FakeApi()
        v1, r1, _ = guard.check_branch(
            "group/audit-triage-fixes",
            "supremeai-planner[bot]",
            policy(),
            api=api,
            repo=REPO,
        )
        v2, _, _ = guard.check_branch(
            "agent-1-planner", "supremeai-planner[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual((v1, v2), ("ALLOW", "ALLOW"))
        self.assertIn("PR-gated", r1)  # group/* এখন শব্দার্থ-স্পষ্ট কারণসহ ছাড় পায়
        self.assertEqual(api.calls, [])  # কোনো API কল লাগেই না

    def test_multi_issue_branch_any_claim_suffices(self):
        # fix/2829-2833-x — 2829-এ নেই, 2833-এ আছে → ALLOW
        api = FakeApi(
            issues={
                2829: {"number": 2829, "state": "open", "assignees": []},
                2833: {"number": 2833, "state": "open", "assignees": []},
            },
            comments={2829: [], 2833: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, num = guard.check_branch(
            "fix/2829-2833-test-assertion-fixes",
            "supremeai-coder-1-bot[bot]",
            policy(),
            api=api,
            repo=REPO,
        )
        self.assertEqual(verdict, "ALLOW")
        self.assertEqual(num, 2833)

    def test_assignee_claim_counts(self):
        api = FakeApi(
            issues={
                2907: {
                    "number": 2907,
                    "state": "open",
                    "assignees": [{"login": "supremeai-coder-1-bot"}],
                }
            },
            comments={2907: []},
        )
        verdict, reason, _ = guard.check_branch(
            "coder-1-2907-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "ALLOW")
        self.assertIn("assignee-claim", reason)

    def test_api_down_fail_open_skip(self):
        api = FakeApi(fail_endpoints=["/issues/2907"])
        verdict, _, _ = guard.check_branch(
            "coder-1-2907-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "SKIP")

    def test_disabled_policy_noop(self):
        api = FakeApi()
        verdict, _, _ = guard.check_branch(
            "anything",
            "supremeai-planner[bot]",
            policy(enabled=False),
            api=api,
            repo=REPO,
        )
        self.assertEqual(verdict, "SKIP")
        self.assertEqual(api.calls, [])


class ClaimSourceHygieneTests(unittest.TestCase):
    """#2912 V5 — ledger/telemetry/template:violating issue-র claim = license নয়।"""

    # সম্পূর্ণ (template-compliant) issue-payload — user/body/labels/created_at সহ
    COMPLIANT_BODY = (
        "### Mission & Problem Statement\nমিশন\n\n"
        "### Priority Tier\nP1-high (gov)\n\n"
        "### Touching Files (Scope Gate Boundary)\n- a.py\n\n"
        "### 3-Tier Verification Contract\n1..2..3\n"
    )

    def _full_issue(self, **overrides) -> dict:
        issue = {
            "number": 2907,
            "state": "open",
            "assignees": [],
            "user": {"login": "supremeai-planner[bot]"},
            "body": self.COMPLIANT_BODY,
            "labels": [{"name": "P1-high"}],
            "created_at": "2026-10-01T20:30:00Z",
        }
        issue.update(overrides)
        return issue

    def test_ledger_label_claim_rejected(self):
        api = FakeApi(
            issues={
                2415: self._full_issue(
                    labels=[{"name": "type:ledger"}, {"name": "P0-critical"}]
                )
            },
            comments={2415: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, _ = guard.check_branch(
            "fix/2415-anything",
            "supremeai-coder-1-bot[bot]",
            policy(),
            api=api,
            repo=REPO,
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("not a claimable work-issue", reason)

    def test_platform_alert_claim_rejected(self):
        api = FakeApi(
            issues={2483: self._full_issue(labels=[{"name": "type:platform-alert"}])},
            comments={2483: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, _ = guard.check_branch(
            "fix/2483-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("not a claimable work-issue", reason)

    def test_template_violating_label_claim_rejected(self):
        api = FakeApi(
            issues={3001: self._full_issue(labels=[{"name": "template:violating"}])},
            comments={3001: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, _ = guard.check_branch(
            "fix/3001-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("template:violating", reason)

    def test_marker_quoted_mid_prose_is_not_ledger(self):
        # SELF-RED-TEAM regression (#2912): এই ফিক্সের নিজের issue-ই marker-টেক্সট
        # উদ্ধৃত করেছিল (V5-বর্ণনায়) — substring-match তাকে false-ledger ভেবে
        # branch মুছেছিল। startswith-সিম্যান্টিক্সে উদ্ধৃতি-ইস্যু আর ব্লক হয় না।
        body = (
            "### Mission & Problem Statement\nV5 ফাঁক: ledger-marker "
            "`<!-- SUPREMEAI_PRIORITY_QUEUE_LEDGER` দিয়ে claim করা যায়।\n\n"
            "### Priority Tier\nP1-high\n\n"
            "### Touching Files (Scope Gate Boundary)\n- a.py\n\n"
            "### 3-Tier Verification Contract\n1..2..3\n"
        )
        api = FakeApi(
            issues={2912: self._full_issue(body=body, title="fix(governance): x")},
            comments={2912: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, _ = guard.check_branch(
            "coder-1-2912-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "ALLOW")
        self.assertIn("Atomic-Claim verified", reason)

    def test_ledger_body_marker_claim_rejected(self):
        # লেবেল নেই, কিন্তু ledger-marker body-তে আছে — marker-ও যথেষ্ট
        api = FakeApi(
            issues={
                2415: self._full_issue(
                    body="<!-- SUPREMEAI_PRIORITY_QUEUE_LEDGER v1 -->\n# queue"
                )
            },
            comments={2415: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, _ = guard.check_branch(
            "fix/2415-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("body-marker", reason)


class TemplateChainTests(unittest.TestCase):
    """#2912 V3-chain — claim-উৎস issue-র inline template-যাচাই (label-নির্ভর নয়)।"""

    COMPLIANT_BODY = (
        "### Mission & Problem Statement\nমিশন\n\n"
        "### Priority Tier\nP1-high (gov)\n\n"
        "### Touching Files (Scope Gate Boundary)\n- a.py\n\n"
        "### 3-Tier Verification Contract\n1..2..3\n"
    )

    def _issue(self, **overrides) -> dict:
        issue = {
            "number": 3002,
            "state": "open",
            "assignees": [],
            "user": {"login": "supremeai-planner[bot]"},
            "body": self.COMPLIANT_BODY,
            "labels": [{"name": "P1-high"}],
            "created_at": "2026-10-01T20:30:00Z",
        }
        issue.update(overrides)
        return issue

    def test_claim_on_template_violating_issue_blocks_branch(self):
        # claim comment আছে, কিন্তু issue body freeform → chain ব্লক
        api = FakeApi(
            issues={3002: self._issue(title="no convention", body="freeform body")},
            comments={3002: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, _ = guard.check_branch(
            "fix/3002-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("template-অসম্পূর্ণ", reason)

    def test_label_removed_still_blocks_inline_check(self):
        # template:violating লেবেল agent মুছে দিলেও inline যাচাই ধরে রাখবে —
        # এটাই label-bypass-নিরোধের প্রমাণ
        api = FakeApi(
            issues={
                3002: self._issue(
                    title="no convention", body="freeform", labels=[{"name": "P1-high"}]
                )
            },
            comments={3002: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, _ = guard.check_branch(
            "fix/3002-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("template-অসম্পূর্ণ", reason)

    def test_compliant_issue_claim_allows(self):
        api = FakeApi(
            issues={3002: self._issue(title="fix(ci): compliant issue")},
            comments={3002: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, _ = guard.check_branch(
            "fix/3002-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "ALLOW")
        self.assertIn("Atomic-Claim verified", reason)

    def test_human_authored_issue_skips_template_subcheck(self):
        # মানুষের issue-তে agent-template বাধ্য নয় — সেখানে claim বৈধ
        api = FakeApi(
            issues={
                2885: self._issue(
                    user={"login": "SaifulHaqueNiloy"},
                    title="freeform",
                    body="founder issue",
                )
            },
            comments={2885: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, _ = guard.check_branch(
            "fix/2885-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "ALLOW")

    def test_grandfathered_issue_skips_template_subcheck(self):
        # enforce_from-এর আগের issue — chain-subcheck ও grandfathered
        api = FakeApi(
            issues={
                2900: self._issue(
                    title="no convention",
                    body="freeform",
                    created_at="2026-10-01T19:00:00Z",
                )
            },
            comments={2900: [CLAIM_COMMENT_CODER]},
        )
        verdict, _, _ = guard.check_branch(
            "fix/2900-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "ALLOW")

    def test_minimal_payload_skips_subcheck_chain_intact(self):
        # পুরনো/অসম্পূর্ণ payload (user/body নেই) — sub-check বাদ, প্রধান চেইন অক্ষুণ্ণ
        api = FakeApi(
            issues={2907: {"number": 2907, "state": "open", "assignees": []}},
            comments={2907: [CLAIM_COMMENT_CODER]},
        )
        verdict, reason, _ = guard.check_branch(
            "coder-1-2907-x", "supremeai-coder-1-bot[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "ALLOW")
        self.assertIn("Atomic-Claim verified", reason)


class BackportReleaseTests(unittest.TestCase):
    """#2912 V2 — backport/* ও release/* এখন issue+claim চায়।"""

    def test_release_branch_without_issue_number_violates(self):
        api = FakeApi()
        verdict, reason, _ = guard.check_branch(
            "release/anything", "supremeai-planner[bot]", policy(), api=api, repo=REPO
        )
        self.assertEqual(verdict, "VIOLATION")
        self.assertIn("no issue number", reason)

    def test_backport_branch_with_claim_allows(self):
        api = FakeApi(
            issues={2891: {"number": 2891, "state": "open", "assignees": []}},
            comments={2891: [CLAIM_COMMENT_PLANNER]},
        )
        verdict, _, _ = guard.check_branch(
            "backport/2891-hotfix",
            "supremeai-planner[bot]",
            policy(),
            api=api,
            repo=REPO,
        )
        self.assertEqual(verdict, "ALLOW")


class EnforceTests(unittest.TestCase):
    def test_violation_deletes_branch_and_comments(self):
        api = FakeApi(issues={2891: OPEN_ISSUE})
        actions = guard.enforce(
            "fix/2891-x",
            "supremeai-planner[bot]",
            "VIOLATION",
            "no claim by 'supremeai-planner[bot]' on 2891",
            2891,
            policy(),
            api=api,
            repo=REPO,
        )
        joined = " | ".join(actions)
        self.assertIn("commented on #2891", joined)
        self.assertIn("branch 'fix/2891-x' deleted", joined)
        methods = {c[0] for c in api.calls}
        self.assertIn("POST", methods)
        self.assertIn("DELETE", methods)

    def test_open_pr_skips_delete(self):
        api = FakeApi(open_prs={"fix/2891-x": [{"number": 123}]})
        actions = guard.enforce(
            "fix/2891-x",
            "supremeai-planner[bot]",
            "VIOLATION",
            "no claim on 2891",
            2891,
            policy(),
            api=api,
            repo=REPO,
        )
        joined = " | ".join(actions)
        self.assertIn("delete skipped — open PR", joined)
        self.assertNotIn("deleted", joined.replace("delete skipped", ""))

    def test_allow_takes_no_action(self):
        api = FakeApi()
        actions = guard.enforce(
            "coder-1-2907-x",
            "supremeai-coder-1-bot[bot]",
            "ALLOW",
            "claim verified",
            2907,
            policy(),
            api=api,
            repo=REPO,
        )
        self.assertEqual(actions, [])
        self.assertEqual(api.calls, [])

    def test_delete_disabled_by_policy(self):
        api = FakeApi()
        actions = guard.enforce(
            "fix/2891-x",
            "supremeai-planner[bot]",
            "VIOLATION",
            "no claim on 2891",
            2891,
            policy(delete_violating_branch=False),
            api=api,
            repo=REPO,
        )
        self.assertEqual(actions, ["commented on #2891"])


class PolicySsotTests(unittest.TestCase):
    def test_real_rules_yaml_carries_branch_creation_policy(self):
        # test_gates-এর claim_policy-carrier প্যাটার্ন (#2907-এর SSOT-সংযোগ যাচাই)
        import yaml

        data = yaml.safe_load(RULES.read_text(encoding="utf-8"))
        bcp = data.get("branch_creation_policy")
        self.assertIsInstance(bcp, dict)
        self.assertTrue(bcp.get("enabled"))
        # #2912 V2: group/* এখন pr_gated_branch_patterns-এ (PR-টাইম Lease Gate-এর এখতিয়ার)
        self.assertIn("group/*", bcp.get("pr_gated_branch_patterns", []))
        self.assertNotIn("backport/*", bcp.get("exempt_branch_patterns", []))
        self.assertEqual(bcp.get("issue_number_min_digits"), 2)
        self.assertTrue(bcp.get("require_claim"))
        gate = (data.get("gates") or {}).get("branch_creation_gate")
        self.assertEqual(gate.get("workflow"), "branch-creation-guard.yml")
        self.assertTrue(gate.get("wired"))

    def test_load_branch_policy_merges_rules_over_default(self):
        pol = guard.load_branch_policy(RULES)
        self.assertTrue(pol["enabled"])
        self.assertIn("supremeai-", "".join(pol["agent_author_prefixes"]))
        # claim_policy থেকে ওঠা SSOT-সংজ্ঞা
        self.assertIn("app/supremeai-", pol["agent_author_prefixes"])

    def test_load_branch_policy_defaults_on_missing_file(self):
        pol = guard.load_branch_policy(Path("/nonexistent/rules.yml"))
        self.assertTrue(pol["enabled"])
        self.assertEqual(pol["issue_number_min_digits"], 2)


class WorkflowWiringTests(unittest.TestCase):
    """Workflow-ফাইল চুক্তি — on:create + ref_type-ফিল্টার + guard-ইনভোকেশন।"""

    def setUp(self):
        import yaml

        self.wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    def _triggers(self) -> dict:
        # YAML 1.1-এ `on:` → True-key; দুই রূপেই ধরা
        return self.wf.get("on") or self.wf.get(True) or {}

    def test_triggers_on_create_only(self):
        self.assertIn("create", self._triggers())
        self.assertNotIn("pull_request", self._triggers())

    def test_branch_only_job_filter(self):
        job = self.wf["jobs"]["guard"]
        self.assertIn("github.event.ref_type == 'branch'", job["if"])

    def test_guard_script_invoked_with_env(self):
        step = self.wf["jobs"]["guard"]["steps"][-1]
        self.assertIn("branch_creation_guard.py", step["run"])
        env = step["env"]
        for key in ("GITHUB_TOKEN", "GUARD_ACTOR", "GUARD_BRANCH", "GUARD_REF_TYPE"):
            self.assertIn(key, env)

    def test_permissions_declared(self):
        perms = self.wf["jobs"]["guard"].get("permissions") or self.wf.get(
            "permissions"
        )
        self.assertEqual(perms.get("contents"), "write")
        self.assertEqual(perms.get("issues"), "write")


if __name__ == "__main__":
    unittest.main()
