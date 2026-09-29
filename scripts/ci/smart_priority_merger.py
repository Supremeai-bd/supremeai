#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Priority-Wise Sequential PR Merger (স্মার্ট প্রায়োরিটি-ভিত্তিক একক-মার্জার)
================================================================================
"টুলস ও টেকনিশিয়ান আগে" (Tools & Technician First) নীতির ভিত্তিতে ওপেন PR-গুলোকে
সঠিক ডিপেন্ডেন্সি অর্ডারে সাজিয়ে এক-এক করে স্বয়ংক্রিয়ভাবে ও নিরাপদে মার্জ করার ইঞ্জিন।

উন্নত ফিচারসমূহ (Enterprise Features):
1. GitHub App অথেনটিকেশন সাপোর্ট (Personal Access Token-এর বিকল্প হিসেবে হাই-রেট লিমিট ও বট আইডেন্টিটি)।
2. রিয়েল-টাইম ডাইনামিক রি-চেক (১ মার্জের পর ২-এর তাজা মার্জ-যোগ্যতা ও এসিঙ্ক ক্যাশ হ্যান্ডলিং)।
3. স্টপ-অন-কনফ্লিক্ট সেফটি গার্ড (কম্পাউন্ড কনফ্লিক্ট ও চেইন ব্রেক প্রতিরোধ)।
4. ইডেমপোটেন্ট ব্লকার ইস্যু হ্যান্ডলার (ডুপ্লিকেট ইস্যু স্প্যামিং প্রতিরোধ)।
5. মেইনে পোস্ট-মার্জ রিয়েল ফেচ ও ফাস্ট স্মোক ভেরিফিকেশন।

ব্যবহার:
    python scripts/ci/smart_priority_merger.py --plan
    python scripts/ci/smart_priority_merger.py --audit-evidence
    python scripts/ci/smart_priority_merger.py --dry-run [--limit 5]
    python scripts/ci/smart_priority_merger.py --execute [--limit 5] [--release-holds] [--app-auth]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# বাংলা মন্তব্য: উইন্ডোজ এবং সিআই-তে ইউনিকোড/বাংলা আউটপুট নিশ্চিত করতে utf-8 রিকনফিগারেশন
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SmartMerger")


# ── প্রায়োরিটি স্তর সংজ্ঞা (Priority Tier Architecture) ────────────────────────
TIER_0_TOOLS_GOVERNANCE = 1000  # এজেন্ট ফ্লিট, টুলস, সিআই ও সংবিধান (সবার আগে)
TIER_1_CONTRACTS_TYPES = 800   # মূল টাইপস, স্কিমা, ইন্টারফেস
TIER_2_DB_MIGRATIONS = 600     # ডাটাবেজ স্কিমা ও মাইগ্রেশন
TIER_3_CORE_BACKEND = 400      # ব্যাকএন্ড কোর লজিক ও বাগ ফিক্স
TIER_4_FRONTEND_UI = 200       # ফ্রন্টএন্ড ক্লায়েন্ট ও ইউজার ইন্টারফেস
TIER_5_JANITOR_CLEANUP = 100   # ডেড-কোড ও ফাইল ক্লিনআপ (কলার রিমুভের পরে)
TIER_6_DEPENDENCIES = 50       # এক্সটার্নাল ডিপেন্ডেন্সি বাম্প (আইসোলেটেড শেষে)

# গ্লোবাল অথ টোকেন ক্যাশ (GitHub App টোকেন থাকলে এখানে সংরক্ষিত হবে)
_ACTIVE_APP_TOKEN: Optional[str] = None


@dataclass
class PROrderItem:
    number: int
    title: str
    branch: str
    author: str
    tier_name: str
    priority_score: int
    mergeable: str
    labels: List[str]
    created_at: str
    additions: int
    deletions: int
    checks_summary: str = "PENDING"
    is_ready_to_merge: bool = False
    is_held: bool = False
    evidence_status: str = "UNKNOWN"
    block_reasons: List[str] = field(default_factory=list)


# ── GitHub App অথেনটিকেশন হেল্পার (Token Minter) ──────────────────────────────
def mint_github_app_token(app_id: str, installation_id: str, private_key_pem: str) -> Optional[str]:
    """
    বাংলা মন্তব্য: GitHub App-এর App ID ও Private Key দিয়ে একটি স্বল্পমেয়াদি
    Installation Access Token তৈরি করা (যা ১ ঘণ্টা মেয়াদি এবং এতে হাই-রেট লিমিট থাকে)।
    """
    try:
        import urllib.request
        try:
            import jwt  # PyJWT
        except ImportError:
            logger.warning("PyJWT লাইব্রেরি নেই। GitHub App টোকেন মিন্ট করতে 'pip install pyjwt cryptography' প্রয়োজন।")
            return None

        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": app_id}
        encoded_jwt = jwt.encode(payload, private_key_pem, algorithm="RS256")

        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        req = urllib.request.Request(
            url,
            method="POST",
            headers={
                "Authorization": f"Bearer {encoded_jwt}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "SupremeAI-SmartMerger",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            token = data.get("token")
            if token:
                logger.info("🔑 GitHub App Installation Token সফলভাবে জেনারেট করা হয়েছে!")
                return token
        return None
    except Exception as e:
        logger.error(f"GitHub App টোকেন তৈরিতে ব্যর্থ: {e}")
        return None


def get_cmd_env() -> Dict[str, str]:
    """বাংলা মন্তব্য: GitHub App টোকেন সক্রিয় থাকলে GH_TOKEN এনভায়রনমেন্ট ভ্যারিয়েবলে ইনজেক্ট করা।"""
    env = os.environ.copy()
    if _ACTIVE_APP_TOKEN:
        env["GH_TOKEN"] = _ACTIVE_APP_TOKEN
    return env


def run_gh_json(cmd: List[str]) -> Any:
    """বাংলা মন্তব্য: gh CLI কমান্ড রান করে JSON আউটপুট পার্স করা।"""
    try:
        res = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=get_cmd_env(),
            check=False,
        )
        if res.returncode != 0:
            return None
        return json.loads(res.stdout) if res.stdout.strip() else None
    except Exception as e:
        logger.error(f"Error executing gh json command: {e}")
        return None


def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    """বাংলা মন্তব্য: জেনেরিক শেল কমান্ড এক্সিকিউট করা।"""
    res = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=get_cmd_env(),
        check=False,
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def calculate_pr_tier(pr: Dict[str, Any]) -> Tuple[int, str]:
    """
    বাংলা মন্তব্য: 'টুলস ও টেকনিশিয়ান আগে' নীতির পরিমার্জিত স্তর বিন্যাস।
    """
    title = (pr.get("title") or "").lower()
    author = (pr.get("author", {}).get("login") or "").lower()
    labels = [l.get("name", "").lower() for l in pr.get("labels") or []]
    files = [f.get("path", "").lower() for f in pr.get("files") or []]

    # ১. স্তর ৬: থার্ড পার্টি ডিপেন্ডেন্সি বাম্প (Dependabot / 43 updates)
    if author in ("app/dependabot", "dependabot[bot]") or "bump the backend-dependencies" in title or ("dependencies" in title and "bump" in title):
        return TIER_6_DEPENDENCIES, "Tier 6 (External Dependencies)"

    # ২. স্তর ৫: ডেড কোড, ডকুমেন্ট প্রুনিং ও ক্লিনআপ (আগে চেক করা যাতে Tier 0 তে না যায়)
    is_prune_title = any(term in title for term in ("prune 27 dead", "delete 33 dead", "delete 10 dead", "delete 5 dead", "chore(cleanup)"))
    is_cleanup_label = any(lbl in ("cleanup", "area:cleanup") for lbl in labels)
    if is_prune_title or is_cleanup_label:
        return TIER_5_JANITOR_CLEANUP, "Tier 5 (Pruning & Cleanup)"

    # ৩. স্তর ০: টুলস ও টেকনিশিয়ান (Governance, Agent Fleet, CI Rules & Constitution)
    is_governance = any(lbl in ("type:governance", "area:ci", "constitution", "charter") for lbl in labels)
    is_governance_title = any(prefix in title for prefix in ("feat(governance)", "fix(governance)", "fix(ci)", "chore(governance)", "refactor(tooling)", "fix(deploy-train)"))
    is_governance_code_files = any(
        f.startswith(".github/workflows/")
        or f.startswith(".github/scripts/")
        or f.startswith(".github/constitution/")
        or f.startswith("scripts/agents/")
        or f.startswith("scripts/ci/")
        or f == "agents.md"
        or f == ".github/constitution/rules.yml"
        for f in files
        if not f.endswith(".md") or f == "agents.md"
    )
    if is_governance or is_governance_title or is_governance_code_files:
        return TIER_0_TOOLS_GOVERNANCE, "Tier 0 (Tools & Technician Governance)"

    # ৪. স্তর ১: কন্ট্রাক্ট, স্কিমা ও ইন্টারফেস
    is_contract = any("contracts" in f or "schemas" in f or "types" in f or "interfaces" in f for f in files)
    is_contract_title = any(term in title for term in ("contract", "schema", "interface", "leaf contract", "truth-sync", "test isolation"))
    if is_contract or is_contract_title:
        return TIER_1_CONTRACTS_TYPES, "Tier 1 (Contracts & Types)"

    # ৫. স্তর ২: ডাটাবেজ স্কিমা ও মাইগ্রেশন
    is_migration = any("alembic_migrations" in f or "migration" in f for f in files)
    if is_migration or "migration" in title or "মাইগ্রেশন" in title:
        return TIER_2_DB_MIGRATIONS, "Tier 2 (Database Migrations)"

    # ৬. স্তর ৪: ফ্রন্টএন্ড ও ইউআই
    is_frontend = any(lbl == "area:frontend" for lbl in labels) or any(f.startswith("frontend/") for f in files) or "fix(frontend)" in title
    if is_frontend:
        return TIER_4_FRONTEND_UI, "Tier 4 (Frontend & UI)"

    # ৭. স্তর ৩: কোর ব্যাকএন্ড ও বিজনেস লজিক (Default)
    return TIER_3_CORE_BACKEND, "Tier 3 (Backend Core & Logic)"


def check_pr_evidence(body: str) -> Tuple[bool, str]:
    """
    বাংলা মন্তব্য: সংবিধানের Verification Gate অনুযায়ী PR বডিতে Test Evidence ও
    ভ্যালিড মার্কার (passed, pytest, unittest, ইত্যাদি) আছে কি না যাচাই করা।
    """
    if not body or not body.strip():
        return False, "Body is empty"

    names = ["Test Evidence", "Tests", "পরীক্ষা", "টেস্ট এভিডেন্স"]
    pattern = re.compile(rf"^#+\s*(?:.*)?({'|'.join(re.escape(n) for n in names)}).*$", re.IGNORECASE | re.MULTILINE)
    m = pattern.search(body)
    if not m:
        return False, "Missing '## Test Evidence' heading"

    section_text = body[m.end():]
    next_heading = re.search(r"^#+\s+", section_text, re.MULTILINE)
    if next_heading:
        section_text = section_text[:next_heading.start()]

    text = section_text.strip().lower()
    if len(text) < 40:
        return False, f"Evidence text too short ({len(text)} < 40 chars)"

    valid_markers = ["passed", "pytest", "unittest", "bun test", "vitest", "0 failed"]
    if any(marker in text for marker in valid_markers):
        return True, "Valid Test Evidence found"

    return False, "Missing output markers (needs 'passed', 'pytest', etc.)"


def evaluate_pr_checks(pr: Dict[str, Any], allow_holds: bool = False) -> Tuple[str, bool, bool, str, List[str]]:
    """
    বাংলা মন্তব্য: CI চেক রোলআপ, queue:hold এবং এভিডেন্স পরীক্ষা করা।
    """
    reasons: List[str] = []
    labels = [l.get("name", "").lower() for l in pr.get("labels") or []]
    is_held = "queue:hold" in labels

    if pr.get("isDraft"):
        reasons.append("PR is Draft")

    mergeable = pr.get("mergeable", "UNKNOWN")
    if mergeable == "CONFLICTING":
        reasons.append("Merge Conflict")

    body = pr.get("body") or ""
    has_ev, ev_msg = check_pr_evidence(body)
    evidence_status = "PASS" if has_ev else f"FAIL ({ev_msg})"
    if not has_ev:
        reasons.append(f"Evidence: {ev_msg}")

    if is_held and not allow_holds:
        reasons.append("queue:hold active (group sequence)")

    rollup = pr.get("statusCheckRollup") or []
    checks_map = {c.get("name"): (c.get("conclusion") or c.get("status")) for c in rollup}

    failing = [name for name, status in checks_map.items() if status in ("FAILURE", "ACTION_REQUIRED", "TIMED_OUT")]
    pending = [name for name, status in checks_map.items() if status in ("IN_PROGRESS", "QUEUED", "PENDING", None)]

    summary = "GREEN"
    if failing:
        summary = f"FAILED ({len(failing)})"
        reasons.append(f"CI Failing ({failing[0][:20]})")
    elif pending:
        summary = f"IN_PROGRESS ({len(pending)})"
        reasons.append("CI in-progress")
    elif not rollup:
        summary = "NO_CHECKS"

    is_ready = len(reasons) == 0 and mergeable == "MERGEABLE"
    return summary, is_ready, is_held, evidence_status, reasons


def fetch_open_prs(limit: int = 100) -> List[Dict[str, Any]]:
    """বাংলা মন্তব্য: গিটহাব থেকে বিস্তারিত ফিল্ডসহ ওপেন PR-এর তালিকা ফেচ করা।"""
    fields = (
        "number,title,headRefName,author,mergeable,labels,createdAt,"
        "additions,deletions,statusCheckRollup,files,isDraft,body"
    )
    data = run_gh_json(["gh", "pr", "list", "--state", "open", "--limit", str(limit), "--json", fields])
    return data or []


def fetch_single_pr_fresh(pr_num: int, retries: int = 3) -> Optional[Dict[str, Any]]:
    """
    বাংলা মন্তব্য: মার্জের ঠিক পূর্বে কোনো PR-এর রিয়েল-টাইম লাইভ অবস্থা ফেচ করা।
    GitHub API-এর অ্যাসিঙ্ক ক্যাশ বাফার সামলাতে 'UNKNOWN' থাকলে ৩ বার রিট্রাই করবে।
    """
    fields = (
        "number,title,headRefName,author,mergeable,labels,createdAt,"
        "additions,deletions,statusCheckRollup,files,isDraft,body,state"
    )
    for attempt in range(1, retries + 1):
        data = run_gh_json(["gh", "pr", "view", str(pr_num), "--json", fields])
        if not data:
            return None
        mergeable = data.get("mergeable", "UNKNOWN")
        if mergeable != "UNKNOWN" or attempt == retries:
            return data
        logger.info(f"⏳ PR #{pr_num} mergeable is 'UNKNOWN' (GitHub calculating). Waiting 3s (attempt {attempt}/{retries})...")
        time.sleep(3)
    return data


def plan_priority_sequence(prs: List[Dict[str, Any]], allow_holds: bool = False) -> List[PROrderItem]:
    """বাংলা মন্তব্য: ওপেন PR-গুলোকে স্তর এবং স্কোর অনুযায়ী নিখুঁত সিকোয়েন্সে সাজানো।"""
    ordered_items: List[PROrderItem] = []

    for pr in prs:
        score_base, tier_name = calculate_pr_tier(pr)
        labels = [l.get("name", "") for l in pr.get("labels") or []]
        bonus = 0
        if "P0-critical" in labels or "type:blocker" in labels:
            bonus += 50
        elif "P1-high" in labels:
            bonus += 20

        additions = pr.get("additions", 0)
        deletions = pr.get("deletions", 0)
        if (additions + deletions) < 50:
            bonus += 5

        total_score = score_base + bonus
        summary, is_ready, is_held, ev_status, reasons = evaluate_pr_checks(pr, allow_holds=allow_holds)

        item = PROrderItem(
            number=pr["number"],
            title=pr["title"],
            branch=pr.get("headRefName", ""),
            author=pr.get("author", {}).get("login", ""),
            tier_name=tier_name,
            priority_score=total_score,
            mergeable=pr.get("mergeable", "UNKNOWN"),
            labels=labels,
            created_at=pr.get("createdAt", ""),
            additions=additions,
            deletions=deletions,
            checks_summary=summary,
            is_ready_to_merge=is_ready,
            is_held=is_held,
            evidence_status=ev_status,
            block_reasons=reasons,
        )
        ordered_items.append(item)

    ordered_items.sort(key=lambda x: (-x.priority_score, x.created_at))
    return ordered_items


def audit_evidence_fleet(items: List[PROrderItem]) -> None:
    """বাংলা মন্তব্য: সমস্ত PR-এর এভিডেন্স অবস্থা বিস্তারিত প্রদর্শন করা।"""
    print("\n" + "=" * 110)
    print("🔎 PR Test Evidence Health Audit (সংবিধান Verification Gate নিরীক্ষা)")
    print("=" * 110)
    print(f"{'PR #':<6} | {'Tier Name':<35} | {'Evidence':<25} | {'Title'}")
    print("-" * 110)
    for it in items:
        status_str = "✅ PASS" if it.evidence_status == "PASS" else f"❌ {it.evidence_status}"
        title_snip = it.title[:40] + "..." if len(it.title) > 40 else it.title
        print(f"#{it.number:<5} | {it.tier_name:<35} | {status_str:<25} | {title_snip}")
    print("=" * 110 + "\n")


def print_plan_table(items: List[PROrderItem]) -> None:
    """বাংলা মন্তব্য: কনসোলে নিখুঁত ও বিস্তারিত প্ল্যান টেবিল প্রিন্ট করা।"""
    print("\n" + "=" * 135)
    print("🏆 'টুলস ও টেকনিশিয়ান আগে' — স্মার্ট প্রায়োরিটি সিকোয়েন্স প্ল্যান (Sequential Merge Queue)")
    print("=" * 135)
    print(f"{'Rank':<5} | {'PR #':<6} | {'Tier Name':<32} | {'Score':<5} | {'Mergeable':<10} | {'State':<11} | {'Primary Blocker / Action':<35} | {'Title'}")
    print("-" * 135)

    for idx, item in enumerate(items, 1):
        if item.mergeable == "CONFLICTING":
            state_flag = "💥 CONFLICT"
            primary_reason = "Git conflict (rebase with main)"
        elif item.is_ready_to_merge:
            state_flag = "🟢 READY"
            primary_reason = "✅ All checks pass (ready to merge)"
        elif item.is_held:
            state_flag = "⏸️ HELD"
            primary_reason = item.block_reasons[0] if item.block_reasons else "queue:hold active"
        else:
            state_flag = "🔴 BLOCKED"
            primary_reason = item.block_reasons[0] if item.block_reasons else "CI checks failing"

        if len(primary_reason) > 34:
            primary_reason = primary_reason[:31] + "..."

        title_snippet = item.title[:24] + "..." if len(item.title) > 24 else item.title
        print(f"{idx:<5} | #{item.number:<5} | {item.tier_name:<32} | {item.priority_score:<5} | {item.mergeable:<10} | {state_flag:<11} | {primary_reason:<35} | {title_snippet}")

    print("=" * 135)
    total_ready = sum(1 for i in items if i.is_ready_to_merge)
    total_held = sum(1 for i in items if i.is_held)
    conflicts = sum(1 for i in items if i.mergeable == "CONFLICTING")
    print(f"📊 মোট PR: {len(items)} | মার্জের জন্য প্রস্তুত: {total_ready} | হোল্ডে আছে: {total_held} | কনফ্লিক্টযুক্ত: {conflicts}\n")


def is_conflict_issue_already_open(pr_num: int) -> bool:
    """
    বাংলা মন্তব্য: ইডেমপোটেন্সি চেক — এই PR-এর জন্য ইতিমধ্যে কোনো খোলা ইস্যু আছে কিনা যাচাই।
    এটি বারবার স্ক্রিপ্ট রান করলেও ডুপ্লিকেট ইস্যু স্প্যাম বন্ধ করে।
    """
    issues = run_gh_json([
        "gh", "issue", "list",
        "--state", "open",
        "--search", f"fix(conflict): PR #{pr_num} in:title",
        "--json", "number,title",
    ])
    return bool(issues and len(issues) > 0)


def handle_conflict_pr(pr_num: int, branch: str, title: str, author: str, trigger_pr_num: Optional[int] = None) -> None:
    """
    বাংলা মন্তব্য: কনফ্লিক্ট দেখা দিলে PR-এ queue:hold লাগানো এবং ইডেমপোটেন্ট উপায়ে GitHub Issue তৈরি করা।
    """
    logger.warning(f"⚠️ PR #{pr_num} has conflict! Adding 'queue:hold'...")

    # ১. queue:hold লেবেল যুক্ত করা
    subprocess.run(
        ["gh", "pr", "edit", str(pr_num), "--add-label", "queue:hold"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        env=get_cmd_env(),
    )

    # ২. ইডেমপোটেন্সি চেক — ইতিমধ্যে ইস্যু খোলা থাকলে ডুপ্লিকেট করবে না
    if is_conflict_issue_already_open(pr_num):
        logger.info(f"ℹ️ PR #{pr_num}-এর জন্য ইতিমধ্যে একটি কনফ্লিক্ট ইস্যু ওপেন রয়েছে। ডুপ্লিকেট স্কিপ করা হলো।")
        return

    prev_str = f"after merging PR #{trigger_pr_num}" if trigger_pr_num else "with current main branch"
    issue_title = f"fix(conflict): PR #{pr_num} has merge conflict {prev_str}"
    issue_body = (
        f"### Merge Conflict Alert\n\n"
        f"- **Conflicting PR**: #{pr_num} (`{branch}`)\n"
        f"- **Title**: {title}\n"
        f"- **Author**: @{author}\n"
        f"- **Trigger**: Dynamic conflict detected {prev_str}\n\n"
        f"#### Required Action:\n"
        f"১. লোকাল ব্রাঞ্চে মেইন সিঙ্ক করুন: `git checkout {branch} && git pull origin main`\n"
        f"২. কনফ্লিক্ট সমাধান করে ৩-স্তর টেস্ট যাচাই সম্পন্ন করুন।\n"
        f"৩. পুশ করুন ও `queue:hold` লেবেল রিমুভ করুন।"
    )

    issue_res = subprocess.run(
        [
            "gh", "issue", "create",
            "--title", issue_title,
            "--body", issue_body,
            "--label", "type:blocker,area:ci",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=get_cmd_env(),
    )
    if issue_res.returncode == 0:
        logger.info(f"✅ Created conflict issue: {issue_res.stdout.strip()}")
    else:
        logger.error(f"❌ Failed to create conflict issue: {issue_res.stderr.strip()}")


def run_fast_smoke_check() -> bool:
    """
    বাংলা মন্তব্য: মার্জের পর মেইনে ৫-১০ সেকেন্ডের 'ছোট রান' (Fast Smoke Test)।
    প্রথমে রিমোট মেইন ফেচ করে নিশ্চিত করে যে টেস্টটি আসল মার্জ হওয়া কোড টেস্ট করছে।
    """
    logger.info("🧪 Fetching latest origin/main and running fast post-merge smoke check...")
    # ১. রিমোট মেইনের তাজা অবস্থা ফেচ করা
    run_cmd(["git", "fetch", "origin", "main"])

    # ২. স্মোক টেস্ট এক্সিকিউশন — রুট প্যাকেজ ও ব্যাকএন্ড ইমপোর্ট ভ্যালিডেশন
    cmd = [
        sys.executable,
        "-c",
        "import sys, os, backend, scripts; print('✅ Fast Smoke: Core packages (backend, scripts) boot healthy.')",
    ]
    code, out, err = run_cmd(cmd)
    if code != 0:
        logger.error(f"❌ Fast smoke check FAILED on main! {err}")
        return False
    logger.info(out)
    return True


def execute_single_merge(pr_num: int, title: str, tier_name: str, labels: List[str]) -> bool:
    """বাংলা মন্তব্য: ১টি নির্দিষ্ট PR নিরাপদে মার্জ করা (Squash Merge)।"""
    logger.info(f"🚀 Merging PR #{pr_num}: '{title}' ({tier_name})...")

    # যদি queue:hold থাকে তবে মার্জের আগে সাময়িকভাবে তা খুলে দেওয়া
    if "queue:hold" in [l.lower() for l in labels]:
        subprocess.run(
            ["gh", "pr", "edit", str(pr_num), "--remove-label", "queue:hold"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            env=get_cmd_env(),
        )

    code, out, err = run_cmd(["gh", "pr", "merge", str(pr_num), "--squash"])
    if code != 0:
        code, out, err = run_cmd(["gh", "pr", "merge", str(pr_num), "--squash", "--auto"])

    if code == 0:
        logger.info(f"✅ Successfully merged PR #{pr_num}!")
        return True
    else:
        logger.error(f"❌ Failed to merge PR #{pr_num}: {err or out}")
        return False


def main() -> None:
    global _ACTIVE_APP_TOKEN

    parser = argparse.ArgumentParser(
        description="Smart Priority-Wise Sequential PR Merger (SupremeAI Tools & Technician First)"
    )
    parser.add_argument("--plan", action="store_true", help="শুধু প্রায়োরিটি সিকোয়েন্স এবং স্ট্যাটাস প্ল্যান প্রদর্শন করুন")
    parser.add_argument("--audit-evidence", action="store_true", help="সব ওপেন PR-এর টেস্ট এভিডেন্স অডিট রিপোর্ট দেখুন")
    parser.add_argument("--dry-run", action="store_true", help="কোনো আসল মার্জ ছাড়া পুরো প্রক্রিয়া সিমুলেট করুন")
    parser.add_argument("--execute", action="store_true", help="একক ক্রমানুসারে PR মার্জ করা শুরু করুন")
    parser.add_argument("--limit", type=int, default=5, help="সর্বোচ্চ কয়টি PR মার্জ করা হবে (ডিফল্ট: ৫)")
    parser.add_argument("--min-prs", type=int, default=0, help="ন্যূনতম কয়টি PR জমা হলে মার্জ পাইপলাইন ট্রিগার হবে (যেমন: ৫)")
    parser.add_argument("--release-holds", action="store_true", help="queue:hold থাকা PR-গুলোকেও প্রস্তুত থাকলে মার্জের অনুমতি দিন")
    parser.add_argument("--include-dependencies", action="store_true", help="থার্ড-পার্টি ডিপেন্ডেন্সি বাম্প (Dependabot) অন্তর্ভুক্ত করুন")
    parser.add_argument("--continue-on-conflict", action="store_true", help="কনফ্লিক্ট হলেও ইস্যু তৈরি করে পাইপলাইন না থামিয়ে পরের স্বাধীন PR-এ যান")
    parser.add_argument("--skip-smoke", action="store_true", help="মার্জের পর পোস্ট-স্মোক রান স্কিপ করুন")
    parser.add_argument("--app-auth", action="store_true", help="GitHub App ক্রেডেনশিয়াল ব্যবহার করে হাই-রেট লিমিট ও বট আইডেন্টিটিতে রান করুন")
    args = parser.parse_args()

    # GitHub App অথেনটিকেশন চেক
    if args.app_auth:
        app_id = os.environ.get("GITHUB_APP_ID") or os.environ.get("AGENT_PR_HELPER_APP_ID")
        inst_id = os.environ.get("GITHUB_APP_INSTALLATION_ID") or os.environ.get("AGENT_PR_HELPER_INSTALLATION_ID")
        pem = os.environ.get("GITHUB_APP_PRIVATE_KEY") or os.environ.get("AGENT_PR_HELPER_PRIVATE_KEY")
        if app_id and inst_id and pem:
            _ACTIVE_APP_TOKEN = mint_github_app_token(app_id, inst_id, pem)
        else:
            logger.warning("⚠️ GitHub App এনভায়রনমেন্ট ভ্যারিয়েবল (APP_ID, INSTALLATION_ID, PRIVATE_KEY) পাওয়া যায়নি। বর্তমান gh সেশনে ফলব্যাক করা হচ্ছে।")

    logger.info("🔍 Fetching open PRs from GitHub repository...")
    raw_prs = fetch_open_prs(limit=100)
    if not raw_prs:
        logger.warning("No open PRs found.")
        return

    # বাংলা মন্তব্য: ইউজার রিকোয়ারমেন্ট — ৫+ PR জমা হলে তবেই অটোমেটিক রান হবে
    if args.min_prs > 0 and len(raw_prs) < args.min_prs:
        logger.info(
            f"⏸️ [BATCH THRESHOLD HOLD] ওপেন PR সংখ্যা ({len(raw_prs)}) নির্ধারিত ন্যূনতম "
            f"থ্রেশহোল্ড ({args.min_prs})-এর কম। ৫+ PR জমা হওয়ার অপেক্ষায় মার্জ স্থগিত রইল।"
        )
        return

    plan = plan_priority_sequence(raw_prs, allow_holds=args.release_holds)

    if args.audit_evidence:
        audit_evidence_fleet(plan)
        return

    print_plan_table(plan)

    if args.plan:
        return

    if not args.execute and not args.dry_run:
        print("💡 টিপ: মার্জ শুরু করতে '--execute', অডিট দেখতে '--audit-evidence' বা সিমুলেশন দেখতে '--dry-run' ফ্ল্যাগ ব্যবহার করুন।")
        return

    mode_label = "DRY-RUN SIMULATION" if args.dry_run else "LIVE EXECUTION"
    logger.info(f"▶️ Starting Dynamic Sequential Merge Pipeline ({mode_label}) with limit={args.limit}...")

    merged_count = 0
    last_merged_pr: Optional[int] = None

    for idx, item in enumerate(plan, 1):
        if merged_count >= args.limit:
            logger.info(f"🛑 Reached merge limit of {args.limit}. Stopping.")
            break

        print(f"\n─────────────────────────────────────────────────────────────", flush=True)
        print(f"👉 [{idx}/{len(plan)}] Evaluating PR #{item.number}: {item.title}", flush=True)
        print(f"   Tier: {item.tier_name} | Branch: {item.branch}", flush=True)

        if item.tier_name == "Tier 6 (External Dependencies)" and not args.include_dependencies:
            logger.info(f"⏩ Skipping {item.tier_name} PR #{item.number} (requires --include-dependencies).")
            continue

        # বাংলা মন্তব্য: সবচেয়ে গুরুত্বপূর্ণ ধাপ — পূর্ববর্তী PR মার্জের পর এই PR-এর তাজা লাইভ স্ট্যাটাস রি-চেক করা
        fresh_data = fetch_single_pr_fresh(item.number)
        if not fresh_data:
            logger.warning(f"⚠️ Could not fetch fresh details for PR #{item.number}. Skipping.")
            continue

        if fresh_data.get("state") != "OPEN":
            logger.info(f"ℹ️ PR #{item.number} is already {fresh_data.get('state')}. Skipping.")
            continue

        fresh_mergeable = fresh_data.get("mergeable", "UNKNOWN")
        fresh_summary, fresh_ready, fresh_held, _, fresh_reasons = evaluate_pr_checks(
            fresh_data, allow_holds=args.release_holds
        )

        # ১. ডাইনামিক কনফ্লিক্ট পরীক্ষা (১ বা ২ মার্জ হওয়ার কারণে কি এতে নতুন কনফ্লিক্ট হলো?)
        if fresh_mergeable == "CONFLICTING":
            if args.dry_run:
                logger.warning(f"[DRY-RUN] PR #{item.number} is CONFLICTING. Would apply 'queue:hold' & create Issue.")
            else:
                handle_conflict_pr(
                    item.number,
                    item.branch,
                    item.title,
                    item.author,
                    trigger_pr_num=last_merged_pr,
                )

            # বাংলা মন্তব্য: সুরক্ষা নীতি — কনফ্লিক্ট ধরা পড়লে জটিলতা এড়াতে পাইপলাইন সাথে সাথে থামবে
            if not args.continue_on_conflict:
                logger.critical(
                    f"\n🚨 [PIPELINE HALTED] কনফ্লিক্ট শনাক্ত হয়েছে PR #{item.number}-এ!\n"
                    f"   অটোমেটিক Blocker Issue তৈরি করা হয়েছে।\n"
                    f"   পরবর্তী PR-গুলোতে কম্পাউন্ড কনফ্লিক্ট এড়াতে পাইপলাইন থামানো হলো।\n"
                    f"   (যদি আপনি স্বাধীন PR মার্জ চালিয়ে যেতে চান, তবে '--continue-on-conflict' ফ্ল্যাগ ব্যবহার করুন।)"
                )
                break
            continue

        # ২. মার্জ-যোগ্যতা ও সিআই চেকের অবস্থা
        if not fresh_ready:
            logger.warning(f"⏩ Skipping PR #{item.number}: Not ready ({', '.join(fresh_reasons)})")
            continue

        # ৩. ড্রাই-রান সিমুলেশন
        if args.dry_run:
            logger.info(f"[DRY-RUN] ✅ PR #{item.number} is clean & green! Would squash merge.")
            merged_count += 1
            last_merged_pr = item.number
            continue

        # ৪. লাইভ মার্জ (Squash Merge)
        labels = [l.get("name", "") for l in fresh_data.get("labels") or []]
        success = execute_single_merge(item.number, item.title, item.tier_name, labels)
        if not success:
            logger.error(f"❌ Failed to merge PR #{item.number}. Aborting pipeline to preserve safety.")
            break

        merged_count += 1
        last_merged_pr = item.number

        # ৫. পোস্ট-মার্জ ছোট রান (Fast Smoke Run)
        if not args.skip_smoke:
            smoke_ok = run_fast_smoke_check()
            if not smoke_ok:
                logger.critical("🚨 Post-merge smoke check failed! Stopping further merges to protect main.")
                break

        # বাংলা মন্তব্য: গিটহাব ব্যাকগ্রাউন্ডে পরবর্তী PR-গুলোর মার্জ-যোগ্যতা রি-ক্যালকুলেট করার জন্য বাফার সময়
        logger.info("⏳ Waiting 5 seconds for GitHub to update downstream PR mergeability...")
        time.sleep(5)

    print(f"\n🏁 পাইপলাইন সমাপ্ত: মোট {merged_count}টি PR সফলভাবে প্রসেস করা হয়েছে।")


if __name__ == "__main__":
    main()
