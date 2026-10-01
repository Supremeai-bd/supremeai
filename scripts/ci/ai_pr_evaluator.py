#!/usr/bin/env python3
"""AI PR Evaluator (#2935, seq:1) — 2-criteria decision engine.

# বাংলা মন্তব্য: #2930-এর Instant Auto-Merge ডকট্রিন + ci-fixer-এর
# 2-ক্রাইটেরিয়া সিম্পল-ক্লিন ডিসিশন ম্যাট্রিক্সের ইঞ্জিন-বাস্তবায়ন:
#
#   ক্রাইটেরিয়া ১ (Value)      = PR কি বাস্তব সমস্যা সমাধান করে?
#   ক্রাইটেরিয়া ২ (Safety)     = রিগ্রেশন-মুক্ত? (গেট-সবুজ + conflict-শূন্য +
#                                 নতুন main-এর সাথে synced + claim-chain বৈধ)
#
#   Value ✅ + Safety ✅ → AUTO_MERGE    (Instant Auto-Merge candidate)
#   Value ✅ + Safety ❌ → HOLD_AND_FIX  (state:hold — কারণসহ fix-issue, ci-fixer সারাবে)
#   Value ❌ (যেকোনো)   → CLOSE         (কারণসহ — অকেজো/প্রক্রিয়া-বহির্ভূত)
#
# অ্যাডমিন-নির্দেশ (2026-10-01): "hold kore daowa gulo karon soho issue te
# add korte hobe… so that ci fixer pr er issue gulo solve korte pare" —
# HOLD_AND_FIX রায়ের প্রতিটি কারণ per-PR fix-issue-তে লেখা হয়
# (group:pipeline-failures গ্রুপে — এক গ্রুপ, আলাদা ইস্যু, যাতে এক agent-কে
# সব ঠিক করতে না হয়)। pipeline_failure_register.py-র সাথে শেয়ার্ড মার্কার-
# চুক্তি: `<!-- pfr-fix:pr:{N} -->` — দুই স্ক্রিপ্ট একই ইস্যু খুঁজে/জন্ম দেয়,
# ডুপ্লিকেট হয় না।
#
# ডায়নামিজম (অ্যাডমিন-নির্দেশ: "any new pipeline added we dont need to
# update again"): কোনো workflow-নাম হার্ডকোড নেই — statusCheckRollup-এর
# সব চেক, compare-API-র freshness, claim-chain — সবই জেনেরিক সংকেত।
# নতুন pipeline যোগ হলে স্বয়ংক্রিয়ভাবে "checks green" হিসাবে গণ্য হবে।
#
# LLM-enrichment: ইন্টারফেস প্লাগেবল (evaluate_enrichment) — ডিফল্ট
# deterministic-evidence স্কোরিং (CI-তে সর্বদা চলে, বাইরের নির্ভরতা শূন্য)।
# ভবিষ্যতে SupremeAI LLM/Guardian বা CodeRabbit-সামারি এখানে জুড়ে দেওয়া
# যাবে — verdict-চুক্তি অপরিবর্তিত থাকবে।
#
# Usage:
#   python scripts/ci/ai_pr_evaluator.py --pr 2926                # এক PR
#   python scripts/ci/ai_pr_evaluator.py --pr 2926 --apply        # verdict-কমেন্ট + hold-issue
#   python scripts/ci/ai_pr_evaluator.py --scan --apply           # সব open PR
#   python scripts/ci/ai_pr_evaluator.py --pr 2926 --strict-exit  # টেস্ট: exit=verdict
#
# Exit codes (default: bookkeeping-সফলতা = 0, রায় যাই হোক):
#   --strict-exit হলে: 0=AUTO_MERGE · 3=HOLD_AND_FIX · 4=CLOSE
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")
RULES_PATH = Path(__file__).resolve().parents[2] / ".github" / "constitution" / "rules.yml"

# ── Policy SSOT (rules.yml ai_pr_evaluation_policy) + DEFAULT fallback ────────
DEFAULT_POLICY: dict[str, Any] = {
    "enabled": True,
    # শেয়ার্ড চুক্তি pipeline_failure_policy-র সাথে (একই per-PR ইস্যু-মার্কার)
    "hold_marker_prefix": "<!-- pfr-fix:",
    "verdict_marker_prefix": "<!-- ai-eval:",
    "group_label": "group:pipeline-failures",
    "hold_labels": ["P2-medium", "area:ci", "type:bug", "ci-failure", "group:pipeline-failures"],
    # কোন PR মূল্যায়ন থেকে বাদ — trusted bots-এর নিজস্ব লেন
    "exempt_authors": ["dependabot[bot]", "app/dependabot", "renovate[bot]"],
    "comment_on_auto_merge": True,
    "max_reasons": 12,
}

VERDICTS = ("AUTO_MERGE", "HOLD_AND_FIX", "CLOSE")
EXIT_CODES = {"AUTO_MERGE": 0, "HOLD_AND_FIX": 3, "CLOSE": 4}

OK_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}
CLAIM_LABELS = {"status:claimed", "status:in-progress"}
VIOLATING_LABEL = "template:violating"

TITLE_RE = re.compile(r"^(feat|fix|chore|docs|refactor|test|perf|audit|ops|task)\([^)]+\): .+")
REFS_RE = re.compile(r"(?:\bRefs\s*#(\d+)|\(#(\d+)\)\s*$)", re.IGNORECASE)


def load_policy(rules_path: Path = RULES_PATH) -> dict[str, Any]:
    """rules.yml → ai_pr_evaluation_policy (DEFAULT-merge)।"""
    pol = dict(DEFAULT_POLICY)
    try:
        import yaml  # noqa: PLC0415 — lazy: CI-রানারে সবসময় থাকে

        data = yaml.safe_load(Path(rules_path).read_text(encoding="utf-8")) or {}
        override = data.get("ai_pr_evaluation_policy") or {}
        for key, val in override.items():
            if key in pol:
                pol[key] = val
    except Exception:  # noqa: BLE001 — policy-লোড ব্যর্থতা মূল্যায়ন থামাবে না
        pass
    return pol


def now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ── ইনজেক্টেবল GitHub-স্তর (tests: FakeApi/FakeGh) ────────────────────────────

def real_api(endpoint: str, method: str = "GET", payload: dict | None = None) -> Any:
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    req = urllib.request.Request(  # noqa: S310
        f"https://api.github.com/{endpoint.lstrip('/')}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        raw = resp.read().decode()
    return json.loads(raw) if raw.strip() else None


def real_gh(*args: str) -> str:
    res = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=60, check=False
    )
    if res.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}… failed: {res.stderr[:200]}")
    return res.stdout


Api = Callable[..., Any]
Gh = Callable[..., str]


# ── সংকেত-সংগ্রহ (সবই ডায়নামিক — কোনো workflow-নাম হার্ডকোড নেই) ─────────────

def fetch_pr(gh: Gh, pr_number: int) -> dict:
    out = gh("pr", "view", str(pr_number), "--repo", REPO, "--json",
             "number,title,body,author,headRefName,baseRefName,isDraft,mergeable,"
             "statusCheckRollup,additions,deletions,changedFiles")
    return json.loads(out or "{}")


def fetch_freshness(api: Api, head_ref: str, base_ref: str = "main") -> dict:
    """compare-API → behind_by/status — নতুন main-এর সাথে sync কি না (#2935)।"""
    try:
        cmp = api(f"repos/{REPO}/compare/{base_ref}...{head_ref}") or {}
        return {
            "behind_by": int(cmp.get("behind_by") or 0),
            "status": cmp.get("status", "unknown"),
        }
    except Exception:  # noqa: BLE001 — compare-ব্যর্থতায় অজানা ধরা হবে fresh (সৎ-অনুমান নয়)
        return {"behind_by": 0, "status": "unknown", "error": True}


def parse_linked_issue(body: str, title: str) -> int | None:
    """body-র `Refs #N` (টেমপ্লেট-চুক্তি) বা title-এর শেষ `(#N)` — claim-chain শিকল।"""
    for match in REFS_RE.finditer(body or ""):
        if match.group(1):
            return int(match.group(1))
    title_match = re.search(r"\(#(\d+)\)\s*$", title or "")
    return int(title_match.group(1)) if title_match else None


def fetch_issue(api: Api, number: int) -> dict | None:
    try:
        return api(f"repos/{REPO}/issues/{number}")
    except Exception:  # noqa: BLE001 — ইস্যু মুছে গেলে None
        return None


def checks_verdict(pr: dict) -> tuple[bool, list[str]]:
    """statusCheckRollup → (সবুজ?, ব্যর্থ-চেকের নাম) — ডায়নামিক, যেকোনো নতুন গেটসহ।"""
    checks = pr.get("statusCheckRollup") or []
    if not checks:
        return False, ["কোনো CI-check রান হয়নি (গেট-প্রমাণ শূন্য)"]
    if any(not c.get("conclusion") for c in checks):
        return False, ["চেক এখনো চলছে (in-progress)"]
    failed = [c.get("name", "?") for c in checks if c.get("conclusion") not in OK_CONCLUSIONS]
    return (not failed), failed


# ── 2-ক্রাইটেরিয়া মূল্যায়ন ───────────────────────────────────────────────────

def evaluate_pr(pr: dict, api: Api = real_api, pol: dict | None = None) -> dict[str, Any]:
    """একটি PR-এর 2-ক্রাইটেরিয়া রায় — সব কারণ স্পষ্টভাবে তালিকাভুক্ত।"""
    pol = pol or load_policy()
    number = int(pr.get("number") or 0)
    title = pr.get("title") or ""
    body = pr.get("body") or ""
    author = ((pr.get("author") or {}).get("login")) or ""

    value_reasons: list[str] = []
    safety_reasons: list[str] = []

    # ── ক্রাইটেরিয়া ১: Value — বাস্তব সমস্যা সমাধান?
    linked = parse_linked_issue(body, title)
    issue = fetch_issue(api, linked) if linked else None
    if not linked:
        value_reasons.append("কোনো linked issue নেই — `Refs #N` (PR-টেমপ্লেট) বাধ্যতামূলক; কাজ-ইস্যু ছাড়া ভ্যালু প্রমাণ-অযোগ্য")
    elif not issue or issue.get("state") != "open":
        value_reasons.append(f"linked issue #{linked} খোলা নেই — বাস্তব সমস্যার জীবন্ত সংজ্ঞা নেই")

    if not re.search(r"^##\s*Summary\b", body, re.MULTILINE) or "Refs #" not in body:
        value_reasons.append("PR-টেমপ্লেট v2 অসম্পূর্ণ (## Summary + Refs #N লাগবে) — ইচ্ছার ঘোষণা যাচাই-যোগ্য নয়")

    additions = int(pr.get("additions") or 0)
    deletions = int(pr.get("deletions") or 0)
    changed = int(pr.get("changedFiles") or 0)
    if changed == 0 or (additions == 0 and deletions > 0):
        value_reasons.append(f"অর্থবহ diff নেই (files={changed}, +{additions}/-{deletions}) — revert-only/খালি PR")

    if not TITLE_RE.match(title):
        value_reasons.append(f"টাইটেল কনভেনশনাল-ফরম্যাটে নয়: `type(scope): description` — পাওয়া গেছে: {title[:60]!r}")

    value_ok = not value_reasons

    # ── ক্রাইটেরিয়া ২: Safety — রিগ্রেশন-মুক্ত + প্রক্রিয়া-বৈধ?
    green, failed_checks = checks_verdict(pr)
    if not green:
        safety_reasons.append("CI গেট লাল: " + ", ".join(failed_checks[:6]) + ("…" if len(failed_checks) > 6 else ""))

    if pr.get("mergeable") is False:
        safety_reasons.append("main-এর সাথে merge-conflict — rebase/merge দরকার")

    fresh = fetch_freshness(api, pr.get("headRefName") or "", pr.get("baseRefName") or "main")
    if fresh.get("behind_by", 0) > 0:
        safety_reasons.append(
            f"PR-head সর্বশেষ main-এর {fresh['behind_by']} commit পেছনে — old-code-push ঝুঁকি "
            "(#2935 Freshness Gate-এ root-ব্লক); `git fetch origin && git merge origin/main` করুন"
        )

    if issue:
        labels = {lab.get("name", "") for lab in (issue.get("labels") or [])}
        if VIOLATING_LABEL in labels:
            safety_reasons.append(f"linked issue #{linked} `template:violating` — Mission/Priority/Touching Files/Verification সেকশন ঠিক না করলে claim-চেইন খোলা হবে না")
        elif not (labels & CLAIM_LABELS) and not (issue.get("assignees") or []):
            safety_reasons.append(f"linked issue #{linked} এখনো unclaimed — atomic claim ছাড়া কাজ অস্বীকৃত (No Claim, No Code)")

    safety_ok = not safety_reasons

    # ── রায় (founder-ম্যাট্রিক্স)
    if value_ok and safety_ok:
        verdict = "AUTO_MERGE"
    elif value_ok and not safety_ok:
        verdict = "HOLD_AND_FIX"
    else:
        verdict = "CLOSE"

    return {
        "pr": number,
        "title": title,
        "author": author,
        "verdict": verdict,
        "criterion_1_value": value_ok,
        "criterion_2_safe": safety_ok,
        "value_reasons": value_reasons[: pol["max_reasons"]],
        "safety_reasons": safety_reasons[: pol["max_reasons"]],
        "checks_green": green,
        "fresh": fresh.get("behind_by", 0) == 0,
        "mergeable": pr.get("mergeable") is not False,
        "linked_issue": linked,
        "evaluated_at": now_utc(),
    }


def evaluate_enrichment(result: dict, pr: dict) -> dict:  # noqa: ARG001 — pluggable interface
    """LLM-enrichment হুক (ভবিষ্যৎ: SupremeAI LLM/Guardian, CodeRabbit-সামারি)।

    # বাংলা মন্তব্য: seq:1-এ deterministic-evidence যথেষ্ট — ডিফারেনশিয়াল
    # কনভার্জেন্সের চেয়ে সৎ-সংকেতই ভালো। ইন্টারফেস অপরিবর্তিত: result নিয়ে
    # এসে confidence/সামারি যোগ করে ফেরত দিতে হবে; verdict ওভাররাইড নিষিদ্ধ।
    """
    result["confidence"] = "deterministic-evidence"
    return result


# ── --apply: verdict-কমেন্ট + hold-issue (কারণসহ) ────────────────────────────

def verdict_marker(result: dict, pol: dict) -> str:
    """রায়+কারণ-ফিঙ্গারপ্রিন্ট — রায় বদলালে নতুন কমেন্ট, নাহলে dedup।"""
    digest = hashlib.md5(  # noqa: S324 — dedup-key, নিরাপত্তা নয়
        json.dumps([result["verdict"], result["value_reasons"], result["safety_reasons"]]).encode()
    ).hexdigest()[:12]
    return f"{pol['verdict_marker_prefix']}{result['pr']}:{result['verdict']}:{digest}-->"


def already_commented(api: Api, pr_number: int, marker: str) -> bool:
    comments = api(f"repos/{REPO}/issues/{pr_number}/comments?per_page=100") or []
    return any(marker in (c.get("body") or "") for c in comments)


VERDICT_BADGES = {
    "AUTO_MERGE": "🚀 **AUTO_MERGE** — Instant Auto-Merge candidate",
    "HOLD_AND_FIX": "⏳ **HOLD_AND_FIX** — কাজের ভ্যালু আছে, সুরক্ষা-সারি লাগবে",
    "CLOSE": "🛑 **CLOSE** — ভ্যালু-প্রমাণ অপর্যাপ্ত",
}


def render_verdict_comment(result: dict, pol: dict) -> str:
    lines = [
        verdict_marker(result, pol),
        f"## 🤖 AI PR Evaluator (#2935) — {VERDICT_BADGES[result['verdict']]}",
        "",
        f"**2-ক্রাইটেরিয়া ম্যাট্রিক্স** · মূল্যায়ন: {result['evaluated_at']} · "
        f"কনফিডেন্স: `{result.get('confidence', 'deterministic-evidence')}`",
        "",
        f"| ক্রাইটেরিয়া | ফল |",
        f"|---|---|",
        f"| ১ — Value (বাস্তব সমস্যা সমাধান) | {'✅' if result['criterion_1_value'] else '❌'} |",
        f"| ২ — Safety (রিগ্রেশন-মুক্ত + প্রক্রিয়া-বৈধ) | {'✅' if result['criterion_2_safe'] else '❌'} |",
    ]
    if result["value_reasons"]:
        lines.append("\n**Value-কারণ (Criterion 1):**")
        lines += [f"- ❌ {r}" for r in result["value_reasons"]]
    if result["safety_reasons"]:
        lines.append("\n**Safety-কারণ (Criterion 2):**")
        lines += [f"- ⚠️ {r}" for r in result["safety_reasons"]]
    if result["verdict"] == "AUTO_MERGE":
        lines.append(
            "\n🚀 সব সংকেত সবুজ — Instant Auto-Merge candidate। "
            "এক্সিকিউশন-লুপ (seq:2) চালু হলে স্বয়ংক্রিয়ভাবে main-এ যাবে।"
        )
    elif result["verdict"] == "HOLD_AND_FIX":
        lines.append(
            "\n⏳ এই PR **Hold**-এ — প্রতিটি কারণ সহ একটি fix-issue "
            f"(`{pol['group_label']}` গ্রুপে) তৈরি/হালনাগাদ করা হয়েছে — ci-fixer এজেন্টরা "
            "সেখান থেকে claim করে সারাতে পারবে। সব কারণ সবুজ হলেই রায় বদলে AUTO_MERGE হবে।"
        )
    else:
        lines.append(
            "\n🛑 প্রস্তাবিত রায় CLOSE — কারণগুলো সারানোর পথ খোলা: linked issue + Refs + "
            "টেমপ্লেট + অর্থবহ diff যোগ করলে পুনরায় মূল্যায়নে রায় বদলাবে।"
        )
    lines.append("\n_#2935 seq:1 (ইঞ্জিন) — এক্সিকিউশন-লুপ seq:2-এ; মন্তব্য dedup: রায়/কারণ বদলালেই নতুন কমেন্ট।_")
    return "\n".join(lines)


def pr_issue_marker(pr_number: int, pol: dict) -> str:
    """pipeline_failure_register.py-র সাথে শেয়ার্ড চুক্তি — একই per-PR ইস্যু।"""
    return f"{pol['hold_marker_prefix']}pr:{pr_number}-->"


def find_pr_fix_issue(api: Api, pr_number: int, pol: dict) -> int | None:
    marker = pr_issue_marker(pr_number, pol)
    issues = api(f"repos/{REPO}/issues?state=open&labels=ci-failure&per_page=100") or []
    for issue in issues:
        if marker in (issue.get("body") or ""):
            return int(issue["number"])
    return None


def render_hold_issue_body(result: dict, pol: dict) -> str:
    """টেমপ্লেট-সম্মত hold-issue (Mission/Touching Files/Verification + P-টোকেন)।"""
    pr_number = result["pr"]
    linked = result.get("linked_issue")
    reasons = result["safety_reasons"] or result["value_reasons"] or ["(মূল্যায়ন-কারণ দেখুন)"]
    return (
        f"{pr_issue_marker(pr_number, pol)}\n"
        f"## Mission\n\n"
        f"**PR #{pr_number}** — HOLD_AND_FIX রায় (AI PR Evaluator #2935): কাজের ভ্যালু আছে, "
        f"কিন্তু নিচের কারণগুলো সারা না হওয়া পর্যন্ত merge-অযোগ্য। প্রতিটি কারণ আলাদাভাবে "
        f"সমাধানযোগ্য — একটিমাত্র এজেন্টের পুরো PR-মালিকার দরকার নেই।\n\n"
        f"### Hold-কারণ (আলাদা আলাদা সমাধানযোগ্য)\n"
        + "\n".join(f"- [ ] ⚠️ {r}" for r in reasons)
        + "\n\n"
        f"### PR-প্রসঙ্গ\n"
        f"| Field | Value |\n|---|---|\n"
        f"| PR | [#{pr_number}](https://github.com/{REPO}/pull/{pr_number}) |\n"
        f"| Linked issue | {f'#{linked}' if linked else '— (Refs #N যোগ করতে হবে)'} |\n"
        f"| Verdict | `{result['verdict']}` @ {result['evaluated_at']} |\n\n"
        f"## Touching Files\n\n"
        f"```text\n"
        f"Touching files: PR #{pr_number}-এর ফাইল-সেট (gh pr view {pr_number} --json files) — "
        f"কারণ-নির্দিষ্ট ফাইল claim-কমেন্টে ঘোষণা করতে হবে\n"
        f"```\n\n"
        f"## Verification\n\n"
        f"1. প্রতিটি hold-কারণ সারা হলে চেকবক্স টিক দিন + প্রমাণ-লিংক\n"
        f"2. `python scripts/ci/ai_pr_evaluator.py --pr {pr_number}` → AUTO_MERGE রায় নিশ্চিত\n"
        f"3. PR-গেট সবুজ + Freshness Gate PASS (নতুন main-এর সাথে synced)\n\n"
        f"**Priority:** P2-medium\n"
    )


def ensure_hold_issue(api: Api, result: dict, pol: dict) -> int:
    """HOLD_AND_FIX → per-PR fix-issue (শেয়ার্ড মার্কার-চুক্তি, dedup-সৃষ্টি)।"""
    existing = find_pr_fix_issue(api, result["pr"], pol)
    if existing:
        return existing
    issue = api(
        f"repos/{REPO}/issues", method="POST",
        payload={
            "title": f"fix(ci): [hold:{result['pr']}] PR #{result['pr']} HOLD_AND_FIX — কারণসহ self-heal তালিকা",
            "body": render_hold_issue_body(result, pol),
            "labels": pol["hold_labels"],
        },
    )
    return int(issue["number"])


def apply_verdict(api: Api, result: dict, pol: dict) -> dict[str, Any]:
    """রায় প্রয়োগ: PR-কমেন্ট (dedup) + HOLD → hold-issue জন্ম/হালনাগাদ।"""
    actions: dict[str, Any] = {"commented": False, "hold_issue": None}
    marker = verdict_marker(result, pol)
    wants_comment = (
        result["verdict"] != "AUTO_MERGE"
        or pol.get("comment_on_auto_merge", True)
    )
    if wants_comment and not already_commented(api, result["pr"], marker):
        api(f"repos/{REPO}/issues/{result['pr']}/comments", method="POST",
            payload={"body": render_verdict_comment(result, pol)})
        actions["commented"] = True
    if result["verdict"] == "HOLD_AND_FIX":
        actions["hold_issue"] = ensure_hold_issue(api, result, pol)
    return actions


# ── স্ক্যান (সব open PR — ডায়নামিক) ──────────────────────────────────────────

def list_open_prs(api: Api) -> list[dict]:
    return api(f"repos/{REPO}/pulls?state=open&per_page=50") or []


def scan(api: Api = real_api, gh: Gh = real_gh, pol: dict | None = None,
         apply: bool = False) -> dict[str, Any]:
    """সব open PR মূল্যায়ন → verdict-map (+ --apply হলে কমেন্ট/hold-issue)।"""
    pol = pol or load_policy()
    if not pol.get("enabled", True):
        return {"skipped": "policy disabled"}
    results = []
    skipped = []
    for pr in list_open_prs(api):
        number = int(pr.get("number") or 0)
        author = ((pr.get("user") or {}).get("login")) or ""
        if pr.get("draft"):
            skipped.append({"pr": number, "why": "draft"})
            continue
        if author in set(pol["exempt_authors"]):
            skipped.append({"pr": number, "why": f"exempt author {author}"})
            continue
        try:
            detail = fetch_pr(gh, number)
            result = evaluate_enrichment(evaluate_pr(detail, api=api, pol=pol), detail)
            if apply:
                result["actions"] = apply_verdict(api, result, pol)
            results.append(result)
        except Exception as exc:  # noqa: BLE001 — এক PR-ব্যর্থতা পুরো স্ক্যান থামাবে না
            skipped.append({"pr": number, "why": f"error: {str(exc)[:120]}"})
    return {
        "evaluated": len(results),
        "verdicts": {r["pr"]: r["verdict"] for r in results},
        # বাংলা মন্তব্য: on_hold = রায়-ভিত্তিক (apply-নির্বিশেষে); hold_issues =
        # apply-করা স্ক্যানে জন্ম/পুনঃব্যবহৃত ইস্যু-নম্বর।
        "on_hold": [r["pr"] for r in results if r["verdict"] == "HOLD_AND_FIX"],
        "hold_issues": {r["pr"]: r["actions"]["hold_issue"] for r in results
                        if r.get("actions", {}).get("hold_issue")},
        "skipped": skipped,
        "results": results,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="AI PR Evaluator (#2935) — 2-criteria Merge/Hold/Close")
    parser.add_argument("--pr", type=int, default=None, help="একটি PR মূল্যায়ন")
    parser.add_argument("--scan", action="store_true", help="সব open PR মূল্যায়ন")
    parser.add_argument("--apply", action="store_true", help="verdict-কমেন্ট + hold-issue (নেটওয়ার্ক-লেখা)")
    parser.add_argument("--strict-exit", action="store_true",
                        help="exit-code = verdict (0=AUTO_MERGE, 3=HOLD_AND_FIX, 4=CLOSE) — টেস্ট/CI-চুক্তি")
    args = parser.parse_args()

    pol = load_policy()
    if not pol.get("enabled", True):
        print(json.dumps({"skipped": "policy disabled"}, ensure_ascii=False))
        return 0

    if args.pr:
        detail = fetch_pr(real_gh, args.pr)
        result = evaluate_enrichment(evaluate_pr(detail, pol=pol), detail)
        if args.apply:
            result["actions"] = apply_verdict(real_api, result, pol)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n🤖 PR #{result['pr']} → {VERDICT_BADGES[result['verdict']]}", file=sys.stderr)
        return EXIT_CODES[result["verdict"]] if args.strict_exit else 0

    if args.scan:
        summary = scan(apply=args.apply, pol=pol)
        compact = {k: summary[k] for k in ("evaluated", "verdicts", "on_hold", "hold_issues", "skipped")}
        print(json.dumps(compact, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
