"""Tests for scripts/ci/ai_pr_evaluator.py (#2935 seq:1).

# বাংলা মন্তব্য: 2-ক্রাইটেরিয়া ডিসিশন-ম্যাট্রিক্সের চুক্তি-পরীক্ষা —
# দুটোই ✅ → AUTO_MERGE · ভ্যালু ✅ + সেফটি ❌ → HOLD_AND_FIX (কারণসহ
# per-PR fix-issue) · ভ্যালু ❌ → CLOSE। শেয়ার্ড মার্কার-চুক্তি
# (pipeline_failure_register.py-র সাথে) + কমেন্ট-dedup + exit-code।
"""

from __future__ import annotations

import json


import scripts.ci.ai_pr_evaluator as ape
from scripts.ci.ai_pr_evaluator import (
    DEFAULT_POLICY,
    EXIT_CODES,
    apply_verdict,
    evaluate_pr,
    parse_linked_issue,
    scan,
    verdict_marker,
)

REPO = ape.REPO


# ── Fakes ────────────────────────────────────────────────────────────────────

class FakeApi:
    """in-memory GitHub REST — compare/issues/comments এন্ডপয়েন্ট।"""

    def __init__(self, *, compares=None, issues=None, comments=None,
                 open_prs=None, existing_fix_issues=None):
        self.compares = compares or {}       # head_ref → {behind_by, status}
        self.issues = issues or {}           # issue-number → issue-dict
        self.comments = comments or {}       # number → [{body}]
        self.open_prs = open_prs or []
        self.existing_fix_issues = existing_fix_issues or []
        self.created_issues: list[dict] = []
        self.posted_comments: list[tuple[int, str]] = []
        self.calls: list = []

    def __call__(self, endpoint, method="GET", payload=None):
        self.calls.append((method, endpoint, payload))
        if method == "GET":
            if "/compare/" in endpoint:
                head = endpoint.split("...")[1]
                return self.compares.get(head, {"behind_by": 0, "status": "ahead"})
            if "pulls?state=open" in endpoint:
                return self.open_prs
            if "issues?state=open&labels=ci-failure" in endpoint:
                return self.existing_fix_issues
            if "comments" in endpoint:
                num = int(endpoint.split("/issues/")[1].split("/comments")[0])
                return [{"body": c} for c in self.comments.get(num, [])]
            if "/issues/" in endpoint:
                num = int(endpoint.rsplit("/", 1)[1])
                return self.issues.get(num)
            raise AssertionError(f"unexpected GET {endpoint}")
        if method == "POST":
            if endpoint.endswith("/comments"):
                num = int(endpoint.split("/issues/")[1].split("/comments")[0])
                self.posted_comments.append((num, payload["body"]))
                return {}
            if endpoint.endswith("/issues"):
                self.created_issues.append(payload)
                num = 970 + len(self.created_issues)
                return {"number": num, **payload}
        raise AssertionError(f"unexpected {method} {endpoint}")


class FakeGh:
    """gh CLI ফেক — pr-view JSON ফেরত।"""

    def __init__(self, prs=None):
        self.prs = prs or {}   # number → pr-detail-dict

    def __call__(self, *args):
        if args[0] == "pr" and "view" in args:
            num = int(args[args.index("view") + 1])
            return json.dumps(self.prs[num])
        raise AssertionError(f"unexpected gh {args}")


GREEN_CHECKS = [
    {"name": "Branch Naming Guard", "conclusion": "SUCCESS"},
    {"name": "🛡️ Constitutional System Gates", "conclusion": "SUCCESS"},
    {"name": "🧪 Test & Build Verification", "conclusion": "SUCCESS"},
]
RED_CHECKS = [
    {"name": "Branch Naming Guard", "conclusion": "SUCCESS"},
    {"name": "🛡️ Constitutional System Gates", "conclusion": "FAILURE"},
    {"name": "🚦 Unified PR Gate", "conclusion": "FAILURE"},
]

TEMPLATE_BODY = (
    "## Summary\nপরিবর্তনের সারমর্ম।\n\n"
    "## Linked Issue / Claim\nRefs #500\n\n"
    "## Touching Files (Scope Boundary)\n- `scripts/a.py`\n\n"
    "## Test Evidence\n1. pytest পাস\n\n"
    "## Rollback Path\n- [ ] `git revert`-নিরাপদ\n"
)
CLAIMED_ISSUE = {
    "number": 500, "state": "open",
    "labels": [{"name": "status:claimed"}, {"name": "P0-critical"}],
    "assignees": [],
}
VIOLATING_ISSUE = {
    "number": 500, "state": "open",
    "labels": [{"name": "template:violating"}],
    "assignees": [],
}


def _pr_detail(num=2926, title="feat(ci): smart thing (#500)", body=TEMPLATE_BODY,
               checks=GREEN_CHECKS, mergeable=True, additions=120, deletions=5,
               changed=3, head="fix/2925-x", author="app/supremeai-planner"):
    return {
        "number": num, "title": title, "body": body, "author": {"login": author},
        "headRefName": head, "baseRefName": "main", "isDraft": False,
        "mergeable": mergeable, "statusCheckRollup": checks,
        "additions": additions, "deletions": deletions, "changedFiles": changed,
    }


# ── ম্যাট্রিক্স-চুক্তি (#2935-এর Verification-তালিকা) ───────────────────────────

class TestVerdictMatrix:
    def test_both_yes_is_auto_merge(self):
        api = FakeApi(issues={500: CLAIMED_ISSUE}, compares={"fix/2925-x": {"behind_by": 0, "status": "ahead"}})
        result = evaluate_pr(_pr_detail(), api=api)
        assert result["verdict"] == "AUTO_MERGE"
        assert result["criterion_1_value"] is True
        assert result["criterion_2_safe"] is True

    def test_value_yes_safety_no_is_hold_and_fix(self):
        # গেট লাল + behind main + issue unclaimed → HOLD (কারণগুলো স্পষ্ট)
        api = FakeApi(
            issues={500: {**CLAIMED_ISSUE, "labels": [{"name": "P0-critical"}], "assignees": []}},
            compares={"fix/2925-x": {"behind_by": 4, "status": "behind"}},
        )
        result = evaluate_pr(_pr_detail(checks=RED_CHECKS, mergeable=False), api=api)
        assert result["verdict"] == "HOLD_AND_FIX"
        assert result["criterion_1_value"] is True
        assert result["criterion_2_safe"] is False
        reasons = " ".join(result["safety_reasons"])
        assert "CI গেট লাল" in reasons
        assert "merge-conflict" in reasons
        assert "4 commit পেছনে" in reasons
        assert "unclaimed" in reasons

    def test_value_no_is_close_even_if_green(self):
        # লিংকড ইস্যু নেই + টাইটেল অ-কনভেনশনাল + revert-only → ভ্যালু-প্রমাণ শূন্য
        api = FakeApi()
        result = evaluate_pr(
            _pr_detail(title="update stuff", body="no template", checks=GREEN_CHECKS,
                       additions=0, deletions=50, changed=2),
            api=api,
        )
        assert result["verdict"] == "CLOSE"
        assert result["criterion_1_value"] is False
        assert any("linked issue নেই" in r for r in result["value_reasons"])

    def test_violating_linked_issue_is_safety_reason(self):
        api = FakeApi(issues={500: VIOLATING_ISSUE})
        result = evaluate_pr(_pr_detail(), api=api)
        assert result["criterion_2_safe"] is False
        assert any("template:violating" in r for r in result["safety_reasons"])

    def test_checks_in_progress_is_not_safe(self):
        api = FakeApi(issues={500: CLAIMED_ISSUE})
        in_progress = GREEN_CHECKS + [{"name": "New Gate", "conclusion": None}]
        result = evaluate_pr(_pr_detail(checks=in_progress), api=api)
        assert result["checks_green"] is False

    def test_exit_codes_strict(self):
        assert EXIT_CODES == {"AUTO_MERGE": 0, "HOLD_AND_FIX": 3, "CLOSE": 4}


# ── সংকেত-পার্সিং ────────────────────────────────────────────────────────────

class TestParsing:
    def test_parse_linked_issue_refs_and_title(self):
        assert parse_linked_issue("Refs #123", "t") == 123
        assert parse_linked_issue("nope", "feat(x): y (#77)") == 77
        assert parse_linked_issue("nope", "plain title") is None

    def test_freshness_behind_reason_includes_count(self):
        api = FakeApi(compares={"b1": {"behind_by": 7, "status": "behind"}})
        result = evaluate_pr(_pr_detail(head="b1"), api=api)
        assert result["fresh"] is False
        assert any("7 commit পেছনে" in r for r in result["safety_reasons"])


# ── --apply: কমেন্ট-dedup + hold-issue (শেয়ার্ড মার্কার) ─────────────────────

class TestApply:
    def test_hold_creates_reason_issue_with_shared_marker(self):
        api = FakeApi(
            issues={500: CLAIMED_ISSUE},
            compares={"fix/2925-x": {"behind_by": 2, "status": "behind"}},
        )
        result = evaluate_pr(_pr_detail(checks=RED_CHECKS), api=api)
        actions = apply_verdict(api, result, DEFAULT_POLICY)
        assert actions["hold_issue"] is not None
        assert api.created_issues, "hold-issue জন্মাতে হবে"
        issue = api.created_issues[0]
        # শেয়ার্ড মার্কার-চুক্তি (register-ও এটিই খোঁজে)
        assert "<!-- pfr-fix:pr:2926-->" in issue["body"]
        # কারণগুলো ইস্যু-বডিতে (অ্যাডমিন-নির্দেশ: "hold kore daowa gulo karon soho")
        assert "Hold-কারণ" in issue["body"]
        assert "CI গেট লাল" in issue["body"]
        # টেমপ্লেট-সম্মত
        for section in ("Mission", "Touching Files", "Verification"):
            assert section in issue["body"]
        assert "P2-medium" in issue["body"]
        # গ্রুপ-লেবেল
        assert "group:pipeline-failures" in issue["labels"]
        # PR-তে রায়-কমেন্ট
        assert api.posted_comments and any(num == 2926 for num, _ in api.posted_comments)

    def test_hold_reuses_existing_register_created_issue(self):
        # register আগে ইস্যু বানিয়ে থাকলে evaluator ডুপ্লিকেট বানায় না
        api = FakeApi(
            issues={500: CLAIMED_ISSUE},
            compares={"fix/2925-x": {"behind_by": 2, "status": "behind"}},
            existing_fix_issues=[{"number": 4001, "body": "<!-- pfr-fix:pr:2926-->\n## Mission"}],
        )
        result = evaluate_pr(_pr_detail(checks=RED_CHECKS), api=api)
        actions = apply_verdict(api, result, DEFAULT_POLICY)
        assert actions["hold_issue"] == 4001
        assert api.created_issues == []

    def test_verdict_comment_dedup_on_same_state(self):
        api = FakeApi(issues={500: CLAIMED_ISSUE})
        result = evaluate_pr(_pr_detail(), api=api)
        marker = verdict_marker(result, DEFAULT_POLICY)
        apply_verdict(api, result, DEFAULT_POLICY)
        assert len(api.posted_comments) == 1
        # একই রায়+কারণ → নতুন কমেন্ট নয়
        api.comments[2926] = [b for n, b in api.posted_comments if n == 2926]
        apply_verdict(api, result, DEFAULT_POLICY)
        assert len(api.posted_comments) == 1
        assert marker in api.posted_comments[0][1]

    def test_close_verdict_comments_but_no_issue(self):
        api = FakeApi()
        result = evaluate_pr(_pr_detail(title="bad", body="x", checks=RED_CHECKS), api=api)
        actions = apply_verdict(api, result, DEFAULT_POLICY)
        assert result["verdict"] == "CLOSE"
        assert actions["hold_issue"] is None
        assert api.created_issues == []
        assert api.posted_comments


# ── স্ক্যান (সব open PR — ডায়নামিক) ─────────────────────────────────────────

class TestScan:
    def test_scan_mixed_queue(self):
        api = FakeApi(
            issues={500: CLAIMED_ISSUE, 501: CLAIMED_ISSUE},
            compares={"green-fresh": {"behind_by": 0, "status": "ahead"},
                      "red-stale": {"behind_by": 3, "status": "behind"}},
            open_prs=[
                {"number": 10, "user": {"login": "agent-a"}, "draft": False},
                {"number": 11, "user": {"login": "agent-b"}, "draft": False},
                {"number": 12, "user": {"login": "agent-c"}, "draft": True},
                {"number": 13, "user": {"login": "dependabot[bot]"}, "draft": False},
            ],
        )
        gh = FakeGh(prs={
            10: _pr_detail(num=10, head="green-fresh"),
            11: _pr_detail(num=11, head="red-stale", checks=RED_CHECKS),
        })
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["evaluated"] == 2
        assert summary["verdicts"] == {10: "AUTO_MERGE", 11: "HOLD_AND_FIX"}
        assert 11 in summary["on_hold"]  # রায়-ভিত্তিক (apply-নির্বিশেষে)
        skipped = {s["pr"]: s["why"] for s in summary["skipped"]}
        assert "draft" in skipped[12]
        assert "exempt" in skipped[13]

    def test_scan_apply_posts_verdicts(self):
        api = FakeApi(
            issues={500: CLAIMED_ISSUE},
            compares={"green-fresh": {"behind_by": 0, "status": "ahead"}},
            open_prs=[{"number": 10, "user": {"login": "agent-a"}, "draft": False}],
        )
        gh = FakeGh(prs={10: _pr_detail(num=10, head="green-fresh")})
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY, apply=True)
        assert summary["verdicts"] == {10: "AUTO_MERGE"}
        assert any(num == 10 for num, _ in api.posted_comments)

    def test_one_pr_error_does_not_stop_scan(self):
        api = FakeApi(
            issues={500: CLAIMED_ISSUE},
            compares={"green-fresh": {"behind_by": 0, "status": "ahead"}},
            open_prs=[
                {"number": 10, "user": {"login": "agent-a"}, "draft": False},
                {"number": 11, "user": {"login": "agent-b"}, "draft": False},
            ],
        )
        class ExplodingGh(FakeGh):
            def __call__(self, *args):
                if "view" in args and args[args.index("view") + 1] == "11":
                    raise RuntimeError("boom")
                return super().__call__(*args)
        gh = ExplodingGh(prs={10: _pr_detail(num=10, head="green-fresh")})
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["evaluated"] == 1
        assert any(s["pr"] == 11 and "boom" in s["why"] for s in summary["skipped"])


# ── SSOT ──────────────────────────────────────────────────────────────────────

class TestPolicy:
    def test_load_policy_merges_rules_yml(self):
        pol = ape.load_policy()
        # rules.yml ai_pr_evaluation_policy — SSOT থেকেই
        assert pol["group_label"] == "group:pipeline-failures"
        # শেয়ার্ড মার্কার-উভয়় স্ক্রিপ্টে একই (চুক্তি-ডকtrine)
        from scripts.ci.pipeline_failure_register import DEFAULT_POLICY as PFR_POL
        assert pol["hold_marker_prefix"] == PFR_POL["fix_marker_prefix"]

    def test_policy_disabled_skips_scan(self):
        summary = scan(api=FakeApi(), gh=FakeGh(), pol={**DEFAULT_POLICY, "enabled": False})
        assert summary == {"skipped": "policy disabled"}


# ── #3015: CLI --json চুক্তি (instant-merge জবের অনুমিত কল) ────────────────────

class TestCliJsonContract:
    """instant-merge (ai-pr-evaluation.yml) `--pr N --json` কল করে — ফ্ল্যাগ
    না থাকলে argparse exit-2 → verdict চির-খালি → চির-নিষ্ক্রিয় merge (#3015)।"""

    def test_json_flag_accepted_by_argparse(self):
        # argparse-নির্মাণ-স্তরের চুক্তি — ফ্ল্যাগটি বিদ্যমান ও গ্রহণযোগ্য
        import scripts.ci.ai_pr_evaluator as _ape
        # আসল main()-এর parser-এ ফ্ল্যাগ আছে কি না — সোর্স-সত্য যাচাই
        import inspect
        source = inspect.getsource(_ape.main)
        assert '"--json"' in source, "CLI-তে --json ফ্ল্যাগ নেই — instant-merge আবার ভাঙবে"

    def test_cli_json_flag_end_to_end_hermetic(self, monkeypatch, capsys):
        # প্রকৃত main() পথ — argparse থেকে stdout-JSON পর্যন্ত; নেটওয়ার্ক-স্তর
        # (fetch_pr/fetch_issue/fetch_freshness) ইনজেকশন — hermetic থাকে।
        import sys as _sys
        import scripts.ci.ai_pr_evaluator as _ape
        monkeypatch.setattr(_ape, "fetch_pr", lambda gh, n: {
            "number": n, "title": "fix(x): demo", "body": "## Summary\nx\nRefs #3015",
            "additions": 5, "deletions": 0, "changedFiles": 1,
            "author": {"login": "demo"}, "headRefName": "demo-b", "baseRefName": "main",
            "mergeable": True, "statusCheckRollup": [], "url": "u",
        })
        monkeypatch.setattr(_ape, "fetch_issue", lambda api, n: None)
        monkeypatch.setattr(_ape, "fetch_freshness", lambda api, head, base="main": {"behind_by": 0})
        monkeypatch.setattr(_sys, "argv", ["ai_pr_evaluator.py", "--pr", "42", "--json"])
        rc = _ape.main()
        assert rc == 0
        import json as _json
        payload = _json.loads(capsys.readouterr().out)
        # instant-merge-এর parser ঠিক এই কীটিই পড়ে (`d.get('verdict')`)
        assert "verdict" in payload
