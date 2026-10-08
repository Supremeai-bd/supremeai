#!/usr/bin/env python3
"""Contract tests for the Merge Gate (Sequential Landing Controller).

বাংলা সারসংক্ষেপ (Merge Gate Convergence):
  Merge Gate = Pipeline 2 — শুধু evidence consume করে, কোনো টেস্ট rerun নয়।
  এই contract tests enforce করে:
    1. Priority extraction hyphen-aware ('P1-high' → 'P1')
    2. Fail-closed: evidence-missing/fetch-fail = HOLD — কখনো merge নয় (Rule 10)
    3. Predecessor proof authoritative — "not open ⇒ merged" assumption নিষিদ্ধ
    4. Freshness #2935-প্যারিটি (merge-base == main-HEAD), exempt-actor parity
    5. Execution: --squash --delete-branch — --admin কখনো নয় (meta-test)
    6. Cross-file workflow contracts (workflow name binding, no leftover
       --admin merge path, dependabot smoke fail-closed)
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci.merge_gate import (  # noqa: E402
    DEFAULT_REQUIRED_CHECKS,
    Gateway,
    decide,
    execute_merge,
    extract_group,
    extract_priority,
    extract_seq,
    plan_queue,
    predecessor_verdict,
)


def labels(*names: str) -> list[dict[str, str]]:
    return [{"name": n} for n in names]


def pr_view_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "number": 101,
        "title": "feat: test PR",
        "state": "open",
        "isDraft": False,
        "headRefName": "coder-1-999-x",
        "headRefOid": "abc123def4567890",
        "mergeStateStatus": "CLEAN",
        "labels": [],
        "author": {"login": "supremeai-coder-1"},
        "createdAt": "2026-10-10T00:00:00Z",
    }
    base.update(overrides)
    return base


class FakeGw(Gateway):
    """পূর্ণ canned transport — কোনো network নেই।

    fail_apis: substring-match করলে সেই call exception ছোড়বে (fail-closed টেস্ট)।
    """

    def __init__(
        self,
        pr: dict[str, Any] | None = None,
        check_runs: list[dict[str, Any]] | None = None,
        protection_required: list[str] | None = None,
        open_or_all_prs: list[dict[str, Any]] | None = None,
        evaluator_verdict: str = "AUTO_MEvaluator",
        evaluator_verdict_value: str = "AUTO_MERGE",
        evaluator_missing: bool = False,
        fail_apis: tuple[str, ...] = (),
        git_fail: bool = False,
        merge_base_matches: bool = True,
    ) -> None:
        super().__init__()
        self._pr = pr if pr is not None else pr_view_payload()
        self._check_runs = check_runs if check_runs is not None else [
            {"id": 1, "name": "Branch Naming Guard", "conclusion": "SUCCESS"},
            {"id": 2, "name": "🚦 Unified PR Gate (Security, Scope & Policy Orchestrator)",
             "conclusion": "SUCCESS"},
        ]
        self._protection_required = protection_required
        self._open_or_all_prs = open_or_all_prs or []
        self._verdict_value = evaluator_verdict_value
        self._evaluator_missing = evaluator_missing
        self._fail_apis = fail_apis
        self._git_fail = git_fail
        self._merge_base_matches = merge_base_matches
        self.merge_calls: list[tuple[Any, ...]] = []

    # ── transport ──
    def gh(self, *args: str) -> str:
        joined = " ".join(args)
        for needle in self._fail_apis:
            if needle in joined:
                raise RuntimeError(f"forced failure: {needle}")
        if joined.startswith("pr view"):
            return json.dumps(self._pr)
        if joined.startswith("api repos") and "branches/main/protection" in joined:
            if self._protection_required is None:
                raise RuntimeError("protection unavailable")
            return json.dumps({"required_status_checks": {"contexts": self._protection_required}})
        if joined.startswith("api repos") and "/check-runs" in joined:
            return json.dumps({"check_runs": self._check_runs})
        if joined.startswith("pr list"):
            return json.dumps(self._open_or_all_prs)
        if joined.startswith("pr merge"):
            self.merge_calls.append(args)
            return ""
        raise AssertionError(f"unexpected gh call: {joined}")

    def git(self, *args: str) -> str:
        if self._git_fail:
            raise RuntimeError("git unavailable")
        joined = " ".join(args)
        if joined.startswith("fetch"):
            return ""
        if joined.startswith("merge-base"):
            return "aaa111bbb222" if self._merge_base_matches else "ccc333ddd444"
        if joined.startswith("rev-parse"):
            return "aaa111bbb222"
        raise AssertionError(f"unexpected git call: {joined}")

    def run(self, cmd: list[str]) -> str:
        if self._evaluator_missing:
            raise RuntimeError("evaluator missing")
        return json.dumps({"verdict": self._verdict_value})


REQUIRED = list(DEFAULT_REQUIRED_CHECKS)


# ── 1. Label parsing ─────────────────────────────────────────────────────────

class TestLabelParsing(unittest.TestCase):
    def test_priority_hyphenated_label(self):
        # rules.yml priority_regex 'P[0-3]-(critical|high|medium|low)' — এরাই বাস্তব লেবেল।
        self.assertEqual(extract_priority(labels("P1-high")), "P1")
        self.assertEqual(extract_priority(labels("P0-critical")), "P0")
        self.assertEqual(extract_priority(labels("P2-medium", "area:ci")), "P2")

    def test_priority_plain_and_default(self):
        self.assertEqual(extract_priority(labels("P0")), "P0")
        self.assertEqual(extract_priority(labels("area:ci", "type:bug")), "P3")
        self.assertEqual(extract_priority([]), "P3")

    def test_group_and_seq(self):
        self.assertEqual(extract_group(labels("group:pipeline-failures", "seq:2")), "pipeline-failures")
        self.assertEqual(extract_seq(labels("group:pipeline-failures", "seq:2")), 2)
        self.assertEqual(extract_group(labels("area:ci")), "")
        self.assertEqual(extract_seq(labels()), 0)

    def test_queue_order_priority_sequential(self):
        prs = [
            {"number": 1, "labels": labels("P1-high"), "createdAt": "2026-10-10T00:00:00Z"},
            {"number": 2, "labels": labels("P0-critical"), "createdAt": "2026-10-11T00:00:00Z"},
            {"number": 3, "labels": labels("P1-high", "group:x", "seq:1"), "createdAt": "2026-10-09T00:00:00Z"},
            {"number": 4, "labels": [], "createdAt": "2026-10-12T00:00:00Z"},
        ]
        order = [p["number"] for p in plan_queue(prs)]
        # priority-rank আগে: P0(#2) → P1-দের (#1 group-বিহীন, তারপর #3 group) → P3(#4)।
        self.assertEqual(order, [2, 1, 3, 4])


# ── 2. Happy path + fail-closed (Rule 10) ────────────────────────────────────

class TestDecide(unittest.TestCase):
    def test_happy_path_merge(self):
        d = decide(FakeGw(), 101)
        self.assertEqual(d["verdict"], "MERGE", d.get("reasons"))
        self.assertEqual(d["reasons"], [])

    def test_closed_pr_holds(self):
        d = decide(FakeGw(pr_view_payload(state="closed")), 101)
        self.assertEqual(d["verdict"], "HOLD")

    def test_draft_holds(self):
        d = decide(FakeGw(pr_view_payload(isDraft=True)), 101)
        self.assertEqual(d["verdict"], "HOLD")

    def test_queue_hold_holds(self):
        d = decide(FakeGw(pr_view_payload(labels=labels("queue:hold"))), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("queue:hold" in r for r in d["reasons"]))

    def test_red_required_check_holds(self):
        runs = [
            {"id": 1, "name": "Branch Naming Guard", "conclusion": "SUCCESS"},
            {"id": 2, "name": "🚦 Unified PR Gate (Security, Scope & Policy Orchestrator)",
             "conclusion": "FAILURE"},
        ]
        d = decide(FakeGw(check_runs=runs), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("Unified PR Gate" in r for r in d["reasons"]))

    def test_missing_required_check_run_holds_fail_closed(self):
        # check-run-ই নেই = missing evidence — কখনো pass নয় (Rule 10)।
        runs = [{"id": 1, "name": "Branch Naming Guard", "conclusion": "SUCCESS"}]
        d = decide(FakeGw(check_runs=runs), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("not green" in r and "Unified PR Gate" in r for r in d["reasons"]))

    def test_check_runs_api_failure_holds_fail_closed(self):
        d = decide(FakeGw(fail_apis=("/check-runs",)), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("evidence-fetch-failed" in r for r in d["reasons"]))

    def test_pending_check_holds(self):
        runs = [
            {"id": 1, "name": "Branch Naming Guard", "conclusion": "SUCCESS"},
            {"id": 2, "name": "🚦 Unified PR Gate (Security, Scope & Policy Orchestrator)",
             "conclusion": None},
        ]
        d = decide(FakeGw(check_runs=runs), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("PENDING" in r for r in d["reasons"]))

    def test_evaluator_hold_verdict_holds(self):
        d = decide(FakeGw(evaluator_verdict_value="HOLD_AND_FIX"), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("HOLD_AND_FIX" in r for r in d["reasons"]))

    def test_evaluator_missing_holds(self):
        d = decide(FakeGw(evaluator_missing=True), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("evidence-fetch-failed" in r for r in d["reasons"]))

    def test_behind_main_holds(self):
        d = decide(FakeGw(merge_base_matches=False), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("freshness" in r for r in d["reasons"]))

    def test_git_failure_holds_fail_closed(self):
        d = decide(FakeGw(git_fail=True), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("evidence-fetch-failed" in r for r in d["reasons"]))

    def test_exempt_actor_skips_freshness(self):
        pr = pr_view_payload(author={"login": "dependabot[bot]"})
        d = decide(FakeGw(pr=pr, merge_base_matches=False), 101)
        # freshness skip — বাকি সব evidence সবুজ হলে merge-eligible (parity)।
        self.assertEqual(d["verdict"], "MERGE", d.get("reasons"))
        self.assertFalse(d["freshness_ok"] is None and True)

    def test_merge_state_unstable_holds(self):
        # non-required লাল চেক = 'unstable' — পুরনো instant-merge এটা accept করত; আমরা নই।
        d = decide(FakeGw(pr_view_payload(mergeStateStatus="UNSTABLE")), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("UNSTABLE" in r for r in d["reasons"]))

    def test_pr_view_api_failure_holds(self):
        d = decide(FakeGw(fail_apis=("pr view",)), 101)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("evidence-fetch-failed" in r for r in d["reasons"]))


# ── 3. Predecessor: authoritative proof — কোনো assumption নয় ────────────────

class TestPredecessor(unittest.TestCase):
    def test_no_group_no_seq_passes(self):
        ok, reasons = predecessor_verdict(FakeGw(), "", 0)
        self.assertTrue(ok, reasons)

    def test_seq1_needs_no_predecessor(self):
        ok, reasons = predecessor_verdict(FakeGw(), "x", 1)
        self.assertTrue(ok, reasons)

    def _gw_with(self, prs: list[dict[str, Any]]) -> FakeGw:
        return FakeGw(open_or_all_prs=prs)

    def test_open_predecessor_blocks(self):
        prs = [{"number": 50, "state": "OPEN",
                "labels": labels("group:infra", "seq:1")}]
        ok, reasons = predecessor_verdict(self._gw_with(prs), "infra", 2)
        self.assertFalse(ok)
        self.assertTrue(any("open" in r for r in reasons))

    def test_merged_predecessor_passes(self):
        prs = [{"number": 50, "state": "MERGED",
                "labels": labels("group:infra", "seq:1")}]
        ok, reasons = predecessor_verdict(self._gw_with(prs), "infra", 2)
        self.assertTrue(ok, reasons)

    def test_closed_unmerged_predecessor_blocks(self):
        prs = [{"number": 50, "state": "CLOSED",
                "labels": labels("group:infra", "seq:1")}]
        ok, reasons = predecessor_verdict(self._gw_with(prs), "infra", 2)
        self.assertFalse(ok)
        self.assertTrue(any("closed-unmerged" in r for r in reasons))

    def test_missing_predecessor_evidence_blocks_not_assumes(self):
        # পুরনো merge_queue_manager-এর ভুল: "open নেই ⇒ merged ধরে নাও"।
        # নতুন চুক্তি: evidence-নেই = HOLD (unknown ≠ green)।
        ok, reasons = predecessor_verdict(self._gw_with([]), "infra", 2)
        self.assertFalse(ok)
        self.assertTrue(any("evidence-missing" in r for r in reasons))

    def test_predecessor_query_failure_blocks(self):
        gw = FakeGw()
        gw._fail_apis = ("pr list",)
        ok, reasons = predecessor_verdict(gw, "infra", 2)
        self.assertFalse(ok)
        self.assertTrue(any("evidence-fetch-failed" in r for r in reasons))

    def test_full_predecessor_flow_in_decide(self):
        prs = [{"number": 50, "state": "OPEN",
                "labels": labels("group:infra", "seq:1")}]
        pr = pr_view_payload(labels=labels("group:infra", "seq:2"))
        d = decide(FakeGw(pr=pr, open_or_all_prs=prs), 102)
        self.assertEqual(d["verdict"], "HOLD")
        self.assertTrue(any("seq:1" in r for r in d["reasons"]))


# ── 4. Execution — RULE 6 ────────────────────────────────────────────────────

class TestExecution(unittest.TestCase):
    def test_execute_merge_uses_squash_delete_no_admin(self):
        gw = FakeGw()
        ok, err = execute_merge(gw, 101)
        self.assertTrue(ok, err)
        self.assertEqual(len(gw.merge_calls), 1)
        args = gw.merge_calls[0]
        self.assertIn("--squash", args)
        self.assertIn("--delete-branch", args)
        self.assertNotIn("--admin", args)

    def test_gh_api_call_gets_no_repo_flag(self):
        # লাইভ-ল্যান্ডিং regression: `gh api`-তে --repo flag নেই — দিলে
        # "unknown flag: --repo" → সব evidence-fetch fail → সব রায় HOLD।
        from scripts.ci.merge_gate import Gateway as _G

        api_cmd = _G._gh_command("api", "repos/x/y/commits/abc/check-runs?per_page=100")
        pr_cmd = _G._gh_command("pr", "view", "1", "--json", "number")
        self.assertEqual(api_cmd[0], "gh")
        self.assertNotIn("--repo", api_cmd)
        self.assertIn("--repo", pr_cmd)

    def test_execute_failure_surfaced(self):
        gw = FakeGw()
        gw._fail_apis = ("pr merge",)
        ok, err = execute_merge(gw, 101)
        self.assertFalse(ok)
        self.assertIn("forced failure", err)


# ── 5. Cross-file workflow contracts (architecture enforcement) ──────────────

class TestWorkflowContracts(unittest.TestCase):
    WF = REPO_ROOT / ".github" / "workflows"

    def _read(self, name: str) -> str:
        return (self.WF / name).read_text(encoding="utf-8")

    def test_merge_gate_workflow_exists_and_single_flight(self):
        text = self._read("merge-gate.yml")
        self.assertIn("group: merge-gate", text)
        self.assertIn("cancel-in-progress: false", text)

    def test_merge_gate_binds_pr_gate_workflow_name(self):
        # workflow_run workflow-name binding অবশ্যই pr.yml-এর বাস্তব নামের সাথে মিলবে।
        pr_text = self._read("pr.yml")
        m = re.search(r'^name:\s*(.+)$', pr_text, re.MULTILINE)
        self.assertIsNotNone(m, "pr.yml-এ name নেই")
        gate_name = m.group(1).strip().strip('"')
        merge_text = self._read("merge-gate.yml")
        self.assertIn(f'workflows: ["{gate_name}"]', merge_text)

    @staticmethod
    def _code_lines(text: str) -> list[str]:
        """comment-only লাইন বাদ — মন্তব্যে doctrine-উল্লেখ থাকতে পারে, কোডে থাকবে না।"""
        return [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]

    def test_no_admin_bypass_in_any_workflow(self):
        # RULE 6: automation-এ --admin নিষিদ্ধ (enforce_admins=false ⇒ সব protection bypass)।
        for wf in self.WF.glob("*.yml"):
            for line_no, line in enumerate(self._code_lines(wf.read_text(encoding="utf-8")), 1):
                if "gh pr merge" in line:
                    self.assertNotIn(
                        "--admin", line,
                        f"{wf.name} — bot merge-এ --admin নিষিদ্ধ",
                    )

    def test_evaluator_is_evidence_producer_only(self):
        code = self._code_lines(self._read("ai-pr-evaluation.yml"))
        self.assertFalse(any("gh pr merge" in ln for ln in code))

    def test_dependabot_smoke_fail_closed(self):
        text = self._read("dependabot.yml")
        self.assertNotIn("typecheck ... 2>&1 | tail -20 || true", text)
        self.assertNotIn("tail -5 || true", text)

    def test_engine_source_never_contains_admin_flag(self):
        src = (REPO_ROOT / "scripts" / "ci" / "merge_gate.py").read_text(encoding="utf-8")
        # মন্তব্যে উল্লেখ থাকতে পারে, কিন্তু কোনো gh-call string-এ নয়।
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("বাংলা"):
                continue
            if '"gh"' in line or "'gh'" in line or "gh(" in line or '"pr", "merge"' in line:
                self.assertNotIn("--admin", line)


if __name__ == "__main__":
    unittest.main()
