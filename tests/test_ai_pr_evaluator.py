"""Tests for scripts/ci/ai_pr_evaluator.py (#2935 seq:1).

# বাংলা মন্তব্য: 2-ক্রাইটেরিয়া ডিসিশন-ম্যাট্রিক্সের চুক্তি-পরীক্ষা —
# দুটোই ✅ → AUTO_MERGE · ভ্যালু ✅ + সেফটি ❌ → HOLD_AND_FIX (কারণসহ
# per-PR fix-issue) · ভ্যালু ❌ → CLOSE। শেয়ার্ড মার্কার-চুক্তি
# (pipeline_failure_register.py-র সাথে) + কমেন্ট-dedup + exit-code।
"""

from __future__ import annotations

import json

import pytest


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
               changed=3, head="fix/2925-x", author="app/supremeai-planner",
               files=None):
    # বাংলা মন্তব্য (#3191): files=None হলে PR-detail-এ `files` কী থাকে না —
    # সেক্ষেত্রে evaluator `pr.get("files") or []` দিয়ে খালি ধরে (metadata-only
    # fallback, backward-compat)। files দিলে smart diff-aware scoring চালু।
    detail = {
        "number": num, "title": title, "body": body, "author": {"login": author},
        "headRefName": head, "baseRefName": "main", "isDraft": False,
        "mergeable": mergeable, "statusCheckRollup": checks,
        "additions": additions, "deletions": deletions, "changedFiles": changed,
    }
    if files is not None:
        detail["files"] = files
    return detail


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
        # #3207 কনট্র্যাক্ট-আপডেট: In-Progress ≠ Broken — চেক চলছে মানেই মিথ্যা
        # "গেট লাল" নয় (PENDING রায়); প্রকৃত FAILURE-ই regression।
        api = FakeApi(issues={500: CLAIMED_ISSUE})
        in_progress = GREEN_CHECKS + [{"name": "New Gate", "conclusion": None}]
        result = evaluate_pr(_pr_detail(checks=in_progress), api=api)
        assert result["checks_pending"] is True
        assert result["verdict"] == "PENDING"  # premature-merge আটকায়, মিথ্যা hold নয়
        assert not any("CI গেট লাল" in r for r in result["safety_reasons"])
        # প্রকৃত ব্যর্থতা আগের মতোই unsafe:
        result2 = evaluate_pr(_pr_detail(checks=RED_CHECKS), api=api)
        assert result2["checks_green"] is False
        assert result2["verdict"] == "HOLD_AND_FIX"

    def test_exit_codes_strict(self):
        # #3207: PENDING (exit 5) — In-Progress রায়-স্থগিত, নতুন চুক্তি
        assert EXIT_CODES == {"AUTO_MERGE": 0, "HOLD_AND_FIX": 3, "CLOSE": 4, "PENDING": 5}


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


# ── #3191: smart diff-aware value scoring + security close-protection ────────
#
# বাংলা মন্তব্য (#3191): এই test-class-গুলো smart evaluator-র চুক্তি পরীক্ষা করে —
# PR #3176-এর mis-close root-cause: শুধু metadata (title-format) দিয়ে CLOSE হয়েছিল,
# diff-এ আসল security fix (tenant_id scope + --accept-data-loss removal) থাকা সত্ত্বেও।
# এখন diff-content দেখে বিচার — security-signal থাকলে কখনো CLOSE নয় (close-protection)।

from scripts.ci.ai_pr_evaluator import (
    parse_linked_issues,
    _diff_value_signals,
    _extract_touching_files,
    _extract_evidence_text,
    SECURITY_DIFF_PATTERNS,
)


class TestMultiIssueParsing:
    """#3191 — `Refs #N #M #K` বহু-ইস্যু চুক্তি (আগে শুধু প্রথম #N ধরত)।"""

    def test_multiple_refs_after_refs_keyword(self):
        # PR #3176-এর রূপ: "Refs #3159 #3163" → দুটোই ধরা দরকার
        nums = parse_linked_issues("## Summary\nx\nRefs #3159 #3163", "")
        assert nums == [3159, 3163]

    def test_single_ref_still_works(self):
        # backward-compat — একক Refs #N
        assert parse_linked_issues("Refs #500", "") == [500]

    def test_title_paren_ref_captured(self):
        # title-এর শেষে (#N) — claim-chain শিকল
        assert parse_linked_issues("nope", "feat(x): y (#77)") == [77]

    def test_no_refs_returns_empty(self):
        assert parse_linked_issues("nope", "plain title") == []

    def test_parse_linked_issue_singular_wraps_plural(self):
        # backward-compat — singular returns first of plural list
        from scripts.ci.ai_pr_evaluator import parse_linked_issue
        assert parse_linked_issue("Refs #3159 #3163", "") == 3159


class TestDiffValueSignals:
    """#3191 — _diff_value_signals চার-সংকেত স্কোরিং।"""

    ISSUE_3163 = {
        "number": 3163, "state": "open",
        "body": ("## Mission\ntenant scope\n\n"
                 "## Touching Files\n- `backend/workers/synaptic_dream.py`\n\n"
                 "## Evidence\n"
                 "`SynapticDreamWorker.execute_dream_cycle(tenant_id=...)` logs "
                 "the tenant but `ai_memory.delete()` filters only `importance_score`"),
        "labels": [{"name": "status:claimed"}], "assignees": [],
    }

    def test_file_alignment_changed_file_in_touching_files(self):
        files = [{"path": "backend/workers/synaptic_dream.py", "additions": 5,
                  "patch": "+x"}]
        sig = _diff_value_signals(files, [self.ISSUE_3163])
        assert sig["file_alignment"] is True
        assert sig["aligned_issue"] == 3163

    def test_file_alignment_no_overlap(self):
        files = [{"path": "unrelated/file.py", "additions": 5, "patch": "+x"}]
        sig = _diff_value_signals(files, [self.ISSUE_3163])
        assert sig["file_alignment"] is False
        assert sig["aligned_issue"] is None

    def test_keyword_anchors_evidence_token_in_patch(self):
        # Evidence-এ "importance_score" identifier — patch-এ থাকলে anchor
        files = [{"path": "x.py", "additions": 3,
                  "patch": "-        .lt(\"importance_score\", 0.2)"}]
        sig = _diff_value_signals(files, [self.ISSUE_3163])
        assert sig["keyword_anchors"] is True

    def test_security_signal_accept_data_loss_removal(self):
        # #3160/#3176 root-fix: --accept-data-loss সরানো
        files = [{"path": "deploy.yml", "additions": 1, "deletions": 1,
                  "patch": "-          prisma db push --accept-data-loss\n+          prisma db push"}]
        sig = _diff_value_signals(files, [])
        assert sig["security_signal"] is True
        assert any("accept-data-loss" in m for m in sig["security_matches"])

    def test_security_signal_tenant_scope_addition(self):
        # #3163 root-fix: tenant_id filter যোগ
        files = [{"path": "worker.py", "additions": 2,
                  "patch": "+    if tenant_id:\n+        q = q.eq(\"tenant_id\", tenant_id)"}]
        sig = _diff_value_signals(files, [])
        assert sig["security_signal"] is True
        assert any("tenant-scope" in m for m in sig["security_matches"])

    def test_no_security_signal_for_benign_diff(self):
        # সাধারণ feature diff — security-signal নয়
        files = [{"path": "feature.py", "additions": 10,
                  "patch": "+def new_feature():\n+    return 42"}]
        sig = _diff_value_signals(files, [])
        assert sig["security_signal"] is False
        assert sig["security_matches"] == []

    def test_substantive_real_additions(self):
        files = [{"path": "a.py", "additions": 15, "patch": "+code"}]
        sig = _diff_value_signals(files, [])
        assert sig["substantive"] is True

    def test_empty_files_returns_all_false(self):
        sig = _diff_value_signals([], [])
        assert sig["file_alignment"] is False
        assert sig["keyword_anchors"] is False
        assert sig["security_signal"] is False
        assert sig["substantive"] is False

    def test_extract_touching_files_backtick_paths(self):
        body = "## Touching Files\n- `a/b.py`\n- `c/d.ts`\n"
        paths = _extract_touching_files(body)
        assert "a/b.py" in paths
        assert "c/d.ts" in paths
        # backtick দূষণ নয় (#3191 regex-fix)
        assert all(not p.startswith("`") for p in paths)

    def test_extract_evidence_text_section(self):
        body = "## Mission\nx\n## Evidence\nthis is evidence\n## Verification\nv"
        assert "this is evidence" in _extract_evidence_text(body)


class TestSecurityCloseProtection:
    """#3191 — security-signal থাকা PR কখনো CLOSE নয় (#3176 regression)।"""

    # PR #3176-এর নির্ভুল পুনরুৎপাদন — টাইটেলে scope-parentheses নেই, CI in-progress,
    # কিন্তু diff-এ আসল security fix (tenant_id + --accept-data-loss removal)।
    PR_3176_FILES = [
        {"path": "apps/mission-control/package.json", "additions": 1, "deletions": 1,
         "patch": '-    "db:push": "prisma db push --accept-data-loss",\n+    "db:push": "prisma db push",'},
        {"path": "backend/workers/synaptic_dream.py", "additions": 6, "deletions": 3,
         "patch": ("+                if tenant_id:\n"
                    '+                    delete_query = delete_query.eq("tenant_id", tenant_id)')},
    ]

    def test_security_fix_with_bad_title_is_hold_not_close(self):
        # #3176 regression: টাইটেলে (scope) নেই → আগে CLOSE হতো, এখন HOLD
        api = FakeApi(issues={3163: {
            "number": 3163, "state": "open",
            "body": "## Touching Files\n- `backend/workers/synaptic_dream.py`\n",
            "labels": [{"name": "status:claimed"}], "assignees": [],
        }}, compares={"fix/3176": {"behind_by": 0, "status": "ahead"}})
        pr = _pr_detail(
            num=3176,
            title="fix: #3163 tenant scope in deletion",  # কোনো (scope) নেই
            body="## Summary\ntenant scope\nRefs #3163",
            additions=7, deletions=4, changed=2, head="fix/3176",
            files=self.PR_3176_FILES,
        )
        result = evaluate_pr(pr, api=api)
        assert result["verdict"] != "CLOSE", "security-fix PR কখনো CLOSE নয় (#3191)"
        assert result["verdict"] == "HOLD_AND_FIX"
        assert result["close_protection"] is True
        assert result["value_signals"]["security_signal"] is True

    def test_security_fix_with_closed_linked_issue_is_hold(self):
        # linked issue বন্ধ হলেও diff-এ security-signal থাকলে CLOSE নয়
        api = FakeApi(issues={3163: {
            "number": 3163, "state": "closed",  # বন্ধ — আগে false CLOSE
            "body": "## Touching Files\n- `backend/workers/synaptic_dream.py`\n",
            "labels": [], "assignees": [],
        }}, compares={"fix/x": {"behind_by": 0, "status": "ahead"}})
        pr = _pr_detail(
            num=42, title="fix: #3163 tenant scope",
            body="## Summary\nx\nRefs #3163",
            head="fix/x", files=self.PR_3176_FILES,
        )
        result = evaluate_pr(pr, api=api)
        assert result["verdict"] == "HOLD_AND_FIX"
        assert result["close_protection"] is True

    def test_security_signal_surfaces_in_safety_reasons(self):
        api = FakeApi(issues={3163: {
            "number": 3163, "state": "open",
            "body": "## Touching Files\n- `backend/workers/synaptic_dream.py`\n",
            "labels": [{"name": "status:claimed"}], "assignees": [],
        }}, compares={"fix/x": {"behind_by": 0, "status": "ahead"}})
        pr = _pr_detail(
            num=42, title="fix: #3163 x",  # non-conv title → metadata gap
            body="## Summary\nx\nRefs #3163", head="fix/x",
            files=self.PR_3176_FILES,
        )
        result = evaluate_pr(pr, api=api)
        reasons = " ".join(result["safety_reasons"])
        assert "security-signal" in reasons or "close-protection" in reasons


class TestGenuinelyEmptyStillCloses:
    """#3191 backward-compat — সত্যিকারের খালি PR এখনো CLOSE (no security, no alignment)।"""

    def test_no_linked_issue_no_security_no_diff_still_close(self):
        # no Refs + no template + revert-only diff + no files → CLOSE থাকে
        api = FakeApi()
        result = evaluate_pr(
            _pr_detail(title="update stuff", body="no template", checks=GREEN_CHECKS,
                       additions=0, deletions=50, changed=2),
            api=api,
        )
        assert result["verdict"] == "CLOSE"
        assert result["close_protection"] is False
        assert any("linked issue নেই" in r for r in result["value_reasons"])

    def test_benign_diff_no_linked_issue_still_close(self):
        # files আছে কিন্তু কোনো security/alignment নেই + linked issue নেই → CLOSE
        api = FakeApi()
        pr = _pr_detail(
            title="random change", body="just experimenting",
            additions=20, deletions=5, changed=2,
            files=[{"path": "feature.py", "additions": 20,
                    "patch": "+def new_feature():\n+    return 42"}],
        )
        result = evaluate_pr(pr, api=api)
        assert result["verdict"] == "CLOSE"
        assert result["close_protection"] is False


class TestVerdictCommentRendersSignals:
    """#3191 — verdict-কমেন্টে diff-signal প্রমাণ দেখায় (transparency)।"""

    def test_close_protection_note_in_comment(self):
        from scripts.ci.ai_pr_evaluator import render_verdict_comment
        api = FakeApi(issues={3163: {
            "number": 3163, "state": "open",
            "body": "## Touching Files\n- `backend/workers/synaptic_dream.py`\n",
            "labels": [{"name": "status:claimed"}], "assignees": [],
        }}, compares={"fix/x": {"behind_by": 0, "status": "ahead"}})
        pr = _pr_detail(
            num=42, title="fix: #3163 tenant scope",
            body="## Summary\nx\nRefs #3163", head="fix/x",
            files=[{"path": "w.py", "additions": 2,
                    "patch": '+    q = q.eq("tenant_id", tenant_id)'}],
        )
        result = evaluate_pr(pr, api=api)
        comment = render_verdict_comment(result, DEFAULT_POLICY)
        assert "Diff-সংকেত" in comment
        assert "security" in comment.lower()
        assert "close-protection" in comment.lower()



# ── #3207: In-Progress ≠ Broken + diff-risk বিশ্লেষণ + LLM-enrichment ────────


@pytest.fixture(autouse=True)
def _no_llm_keys(monkeypatch):
    """#3207 hermeticity: টেস্ট-স্যুটে LLM কী নেই — নেটওয়ার্ক-শূন্য deterministic ডিফল্ট।"""
    for var in ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)


PENDING_CHECKS = [
    {"name": "Branch Naming Guard", "conclusion": "SUCCESS"},
    {"name": "🧪 Full Backend Suite", "conclusion": None},  # এখনো চলছে
]

ENRICH_FILES = [
    {"path": "app/module.py", "additions": 10, "deletions": 2, "patch": "+x = 1"},
    {"path": "tests/test_module.py", "additions": 20, "deletions": 0,
     "patch": "def test_ok():\n    assert True"},
]


class TestCiPendingTriage:
    """#3207 AC: In-Progress ≠ Broken — মিথ্যা hold-issue নয়, premature merge-ও নয়।"""

    def _green_pr(self, **kw):
        api = FakeApi(issues={500: CLAIMED_ISSUE},
                      compares={"fix/2925-x": {"behind_by": 0, "status": "ahead"}})
        return api, _pr_detail(**kw)

    def test_checks_verdict_ignores_pending(self):
        green, failed = ape.checks_verdict({"statusCheckRollup": PENDING_CHECKS})
        assert green is True
        assert failed == []

    def test_checks_pending_true_and_false(self):
        assert ape.checks_pending({"statusCheckRollup": PENDING_CHECKS}) is True
        assert ape.checks_pending({"statusCheckRollup": GREEN_CHECKS}) is False

    def test_pending_green_value_pr_is_pending_not_hold(self):
        api, pr = self._green_pr(checks=PENDING_CHECKS)
        result = evaluate_pr(pr, api=api)
        assert result["verdict"] == "PENDING"
        assert result["checks_pending"] is True
        assert not any("CI গেট লাল" in r for r in result["safety_reasons"])

    def test_pending_with_real_failure_is_hold(self):
        api, pr = self._green_pr(checks=RED_CHECKS)
        result = evaluate_pr(pr, api=api)
        assert result["verdict"] == "HOLD_AND_FIX"
        assert any("CI গেট লাল" in r for r in result["safety_reasons"])

    def test_apply_verdict_pending_is_silent_noop(self):
        api = FakeApi()
        result = {"pr": 42, "verdict": "PENDING", "value_reasons": [],
                  "safety_reasons": []}
        actions = apply_verdict(api, result, dict(DEFAULT_POLICY))
        assert actions["commented"] is False
        assert actions["hold_issue"] is None
        assert api.posted_comments == []
        assert api.created_issues == []

    def test_exit_codes_document_pending(self):
        assert EXIT_CODES["PENDING"] == 5


class TestBotAuthorExemption:
    """#3207 AC: Dependabot/Renovate synthetic `Refs #N`-মুক্ত (#2948 মূল-সমাধান)।"""

    def _bot_pr(self):
        api = FakeApi(compares={"dependabot/pip/x": {"behind_by": 0, "status": "ahead"}})
        pr = _pr_detail(
            num=77, title="chore(deps): bump pyyaml 6.0.1 to 6.0.2",
            body="Bump pyyaml from 6.0.1 to 6.0.2",  # টেমপ্লেট নেই, Refs নেই
            head="dependabot/pip/x", author="dependabot[bot]",
            additions=4, deletions=4, changed=1,
            files=[{"path": "pyproject.toml", "additions": 4, "deletions": 4,
                    "patch": '+version = "6.0.2"'}],
        )
        return api, pr

    def test_bot_pr_without_refs_is_auto_merge_when_green(self):
        api, pr = self._bot_pr()
        result = evaluate_pr(pr, api=api)
        assert result["exempt_author"] is True
        assert result["verdict"] == "AUTO_MERGE"
        assert not any("linked issue" in r for r in result["value_reasons"])

    def test_bot_pr_with_red_ci_is_hold_not_close(self):
        api, pr = self._bot_pr()
        pr["statusCheckRollup"] = RED_CHECKS
        result = evaluate_pr(pr, api=api)
        assert result["verdict"] == "HOLD_AND_FIX"

    def test_non_bot_without_refs_still_gap(self):
        api = FakeApi(compares={"fix/2925-x": {"behind_by": 0, "status": "ahead"}})
        pr = _pr_detail(body="no template here")
        result = evaluate_pr(pr, api=api)
        assert result["exempt_author"] is False
        assert any("linked issue" in r for r in result["value_reasons"])


class TestEnrichment:
    """#3207 AC: diff-risk বিশ্লেষণ + multi-key LLM failover + সৎ confidence।"""

    def test_no_keys_is_deterministic_evidence(self):
        result = {"pr": 1, "title": "t", "verdict": "HOLD_AND_FIX"}
        out = ape.evaluate_enrichment(result, {"files": ENRICH_FILES})
        assert out["confidence"] == "deterministic-evidence"
        assert out["summary"]
        assert out["verdict"] == "HOLD_AND_FIX"  # রায়-ওভাররাইড নিষিদ্ধ
        assert out["diff_analysis"]["test_coverage_signal"] is True

    def test_diff_risk_reports_names_not_values(self):
        files = [{"path": "auth/config.py", "additions": 1, "deletions": 0,
                  "patch": 'key = "AKIAIOSFODNN7EXAMPLE"'}]
        analysis = ape._diff_risk_analysis(files)
        assert analysis["risky_paths"] == ["auth/config.py"]
        assert analysis["secret_pattern_hits"] == ["aws-access-key:auth/config.py"]
        assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(analysis)  # মান কখনো নয়

    def test_llm_enriched_first_provider_wins(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gqk_test")
        calls = []

        def fake_call(provider, prompt):
            calls.append(provider["name"])
            if provider["name"] == "groq":
                return ('```json\n{"regression_risk": "low", "summary": "adds tenant scope", '
                        '"concerns": ["minor"]}\n```')
            return "garbage{{{"

        monkeypatch.setattr(ape, "_llm_call", fake_call)
        result = {"pr": 2, "title": "fix: tenant scope", "verdict": "AUTO_MERGE",
                  "value_signals": {}}
        out = ape.evaluate_enrichment(result, {"files": ENRICH_FILES})
        assert out["confidence"] == "llm-enriched"
        assert out["llm_review"]["provider"] == "groq"
        assert out["llm_review"]["regression_risk"] == "low"
        assert out["verdict"] == "AUTO_MERGE"  # রায় অপরিবর্তিত
        assert calls == ["groq"]  # প্রথম সফল provider-এই থামে

    def test_provider_failover_to_second(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gqk_test")
        monkeypatch.setenv("GEMINI_API_KEY", "gem_test")

        def fake_call(provider, prompt):
            if provider["name"] == "groq":
                return None  # ব্যর্থ
            return '{"regression_risk": "medium", "summary": "s", "concerns": []}'

        monkeypatch.setattr(ape, "_llm_call", fake_call)
        out = ape.evaluate_enrichment(
            {"pr": 4, "title": "t", "verdict": "HOLD_AND_FIX"}, {"files": []})
        assert out["llm_review"]["provider"] == "gemini"

    def test_all_providers_fail_is_llm_unavailable(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gqk_test")
        monkeypatch.setenv("GEMINI_API_KEY", "gem_test")
        monkeypatch.setattr(ape, "_llm_call", lambda p, prompt: None)
        out = ape.evaluate_enrichment(
            {"pr": 3, "title": "t", "verdict": "CLOSE", "value_signals": {}}, {"files": []})
        assert out["confidence"] == "llm-unavailable"
        assert out["summary"]  # deterministic fallback সৎ-থাকে
        assert out["verdict"] == "CLOSE"


class TestRenderPendingAndSummary:
    """#3207: PENDING badge + enrichment-সেকশন কমেন্টে সৎ-প্রমাণ হিসেবে।"""

    def test_pending_badge_and_note(self):
        pol = dict(DEFAULT_POLICY)
        result = {"pr": 9, "verdict": "PENDING", "value_reasons": [], "safety_reasons": [],
                  "criterion_1_value": True, "criterion_2_safe": True, "evaluated_at": "x"}
        text = ape.render_verdict_comment(result, pol)
        assert "PENDING" in text
        assert "in-progress ≠ broken" in text

    def test_summary_and_risk_lines(self):
        pol = dict(DEFAULT_POLICY)
        result = {"pr": 10, "verdict": "HOLD_AND_FIX", "value_reasons": [],
                  "safety_reasons": ["CI গেট লাল: X"],
                  "criterion_1_value": True, "criterion_2_safe": False,
                  "evaluated_at": "x", "confidence": "llm-enriched",
                  "summary": "adds tenant scope with tests",
                  "llm_review": {"provider": "groq", "model": "llama",
                                 "regression_risk": "low",
                                 "concerns": ["watch migration"]},
                  "diff_analysis": {"risky_paths": ["auth/config.py"],
                                    "secret_pattern_hits": [],
                                    "test_coverage_signal": True}}
        text = ape.render_verdict_comment(result, pol)
        assert "adds tenant scope with tests" in text
        assert "regression-risk" in text
        assert "`low`" in text
        assert "groq/llama" in text
        assert "watch migration" in text
        assert "auth/config.py" in text


# ── #4222: template_gate-সংগত contract (SSOT drift-প্রতিরোধ) ────────────────────
class TestTemplateGateSummaryAlignment:
    """#4222: evaluator-এর Summary-শনাক্ত ক্যানোনিক্যাল গেটের সাথে একমত কিনা।

    বাংলা: .github/scripts/constitution/template_gate.py COMPLIANT দেওয়া body
    evaluator-এর কঠোর `^##\\s*Summary\\b` রেগেক্সে ভুয়া metadata-gap খেলে
    ভুয়া Safety ❌ → ghost pipeline-issue (#4219-শ্রেণি)। এই contract-test
    representative body-গুলোতে দুই বাস্তবায়নকে বাঁধে — ভবিষ্যৎ drift এখন
    টেস্ট-ফেইল, প্রোডাকশন-অঘটনা নয় (P6 poka-yoke)।
    """

    @staticmethod
    def _gate_has_summary(body: str) -> bool:
        import sys as _sys
        from pathlib import Path as _Path
        const_dir = _Path(__file__).resolve().parents[1] / ".github" / "scripts" / "constitution"
        if str(const_dir) not in _sys.path:
            _sys.path.insert(0, str(const_dir))
        import template_gate
        return template_gate._has_section(body, "Summary")

    @pytest.mark.parametrize("body", [
        "## Summary\nসারমর্ম\n",
        "## Mission & Summary (মিশন ও সারসংক্ষেপ)\n...\n",
        "### Summary\n...\n",
        "# Summary\n...\n",
        "## Summary (সারসংক্ষেপ)\n...\n",
        "## linked summary of work\n...\n",  # case-insensitive substring
        "### Mission & Summary — রোলআপ\n...\n",
        "prerequisite: ## Summary কথায় নয়, হেডিংয়ে\n\n## Summary\nok\n",
    ])
    def test_positive_bodies_agree_with_gate(self, body):
        assert ape._has_summary_section(body) is True
        assert self._gate_has_summary(body) is True

    @pytest.mark.parametrize("body", [
        "",
        "প্লেইন টেক্সট — কোনো হেডিং নেই\n",
        "## Mission\n## Verification\n",
        "## summery (বানান-ভুল)\n",
        "Summary হেডিংয়ে নয়, সাধারণ লাইনে\n",
    ])
    def test_negative_bodies_agree_with_gate(self, body):
        assert ape._has_summary_section(body) is False
        assert self._gate_has_summary(body) is False

    def test_mission_summary_heading_no_false_metadata_gap(self):
        # বাংলা: ক্যানোনিক্যাল টেমপ্লেট-বৈচিত্র্য আর ভুয়া gap/Safety ❌ খাবে না —
        # গেট COMPLIANT হলে evaluator-ও একই রায় দেবে (#4222-মূল-অঘটনা)।
        body = (
            "## Mission & Summary (মিশন ও সারসংক্ষেপ)\nফিক্সের সারমর্ম।\n\n"
            "## Linked Issue / Claim\nRefs #500\n\n"
            "## Touching Files (Scope Boundary)\n- `scripts/a.py`\n\n"
            "## Rollback Path\n- [ ] `git revert`-নিরাপদ\n"
        )
        api = FakeApi(issues={500: CLAIMED_ISSUE},
                      compares={"fix/2925-x": {"behind_by": 0, "status": "ahead"}})
        result = evaluate_pr(_pr_detail(body=body), api=api)
        assert result["verdict"] == "AUTO_MERGE"
        assert result["criterion_2_safe"] is True
        assert not any("টেমপ্লেট v2" in r for r in
                       result["safety_reasons"] + result["value_reasons"])

    def test_missing_summary_still_flagged(self):
        # বাংলা: আলগা হলেও গেট সৎ — Summary সত্যিই না থাকলে gap ধরা পড়বেই।
        body = (
            "## Mission\nসারমর্ম নেই।\n\n"
            "## Linked Issue / Claim\nRefs #500\n\n"
            "## Rollback Path\n- [ ] ok\n"
        )
        api = FakeApi(issues={500: CLAIMED_ISSUE},
                      compares={"fix/2925-x": {"behind_by": 0, "status": "ahead"}})
        result = evaluate_pr(_pr_detail(body=body), api=api)
        reasons = " ".join(result["safety_reasons"] + result["value_reasons"])
        assert "টেমপ্লেট v2" in reasons


class TestSectionExtractionGateAlignment:
    """#4222 U9-sweep: একই কঠোর-হেডিং drift-শ্রেণির sibling-ফাংশন দুটির চুক্তি।

    বাংলা: `_extract_touching_files`/`_extract_evidence_text` আগে কঠোর
    `^##\\s*<Keyword>\\b` ব্যবহার করত — গেট COMPLIANT issue-র
    `### Touching Files`/`### Evidence` ধরতে পারত না (value-signal হারাত)।
    """

    def test_touching_files_any_heading_level(self):
        body = ("## Mission\nমিশন\n\n### Touching Files\n- `backend/worker.py`\n\n"
                "## Verification\npytest পাস\n")
        assert _extract_touching_files(body) == {"backend/worker.py"}

    def test_touching_files_bare_bullet_paths(self):
        body = "## Touching Files (Scope Boundary)\n- scripts/ci/eval.py\n- `tests/x.py`\n"
        assert _extract_touching_files(body) == {"scripts/ci/eval.py", "tests/x.py"}

    def test_evidence_any_heading_level(self):
        body = "### Evidence\nrun #391 green\n\n## Verification\nok\n"
        assert "run #391 green" in _extract_evidence_text(body)

    def test_section_stops_at_any_level_heading(self):
        body = "## Touching Files\n- `a.py`\n\n### Note\n- `b.py`\n"
        assert _extract_touching_files(body) == {"a.py"}

    def test_missing_section_empty(self):
        assert _extract_touching_files("## Mission\nx\n") == set()
        assert _extract_evidence_text("") == ""


# ── #4250: টাইটেল-গ্যাপ একক-সংগ্রহ + #3207-চুক্তিতে exempt-অব্যাহতি ─────────────
class TestTitleGapContract:
    """#4250: টাইটেল-কনভেনশন গ্যাপ এখন শুধু exempt-guard-এর ভেতরে একবার।

    বাংলা: আগে guard-বাইরেও একটি append-site ছিল — non-exempt লেখকের
    খারাপ টাইটেলে একই এন্ট্রি দুইবার যেত, আর exempt/bot লেখকের
    (Dependabot-টাইটেল conventional হয়ই না) ভুয়া metadata-gap → ভুয়া HOLD।
    """

    def test_nonexempt_bad_title_gap_appended_once(self):
        # বাংলা: খারাপ টাইটেল → গ্যাপ ঠিকই থাকবে, কিন্তু ঠিক ১ বার
        api = FakeApi(issues={500: CLAIMED_ISSUE},
                      compares={"fix/2925-x": {"behind_by": 0, "status": "ahead"}})
        result = evaluate_pr(_pr_detail(title="Bump foo from 1 to 2"), api=api)
        all_reasons = result["value_reasons"] + result["safety_reasons"]
        count = sum(1 for r in all_reasons if "টাইটেল কনভেনশনাল" in r)
        assert count == 1

    def test_exempt_author_no_title_gap(self):
        # বাংলা: Dependabot-টাইটেল conventional হয় না — #3207-চুক্তিতে
        # exempt-লেখক টেমপ্লেট-গ্যাপ থেকে অব্যাহত; ভুয়া HOLD আর নয়
        api = FakeApi(issues={500: CLAIMED_ISSUE},
                      compares={"fix/2925-x": {"behind_by": 0, "status": "ahead"}})
        result = evaluate_pr(_pr_detail(title="Bump foo from 1 to 2",
                                        author="dependabot[bot]"), api=api)
        all_reasons = result["value_reasons"] + result["safety_reasons"]
        assert not any("টাইটেল কনভেনশনাল" in r for r in all_reasons)

    def test_good_title_no_gap(self):
        # বাংলা: সংশোধন non-exempt ভালো-টাইটেল প্রত্যাশাও ভাঙে না
        api = FakeApi(issues={500: CLAIMED_ISSUE},
                      compares={"fix/2925-x": {"behind_by": 0, "status": "ahead"}})
        result = evaluate_pr(_pr_detail(), api=api)
        all_reasons = result["value_reasons"] + result["safety_reasons"]
        assert not any("টাইটেল কনভেনশনাল" in r for r in all_reasons)
