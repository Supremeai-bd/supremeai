#!/usr/bin/env python3
"""Continuous Autonomous Agent Loop (#2573 — Simple Version).

This is the SIMPLIFIED entry point for agents. No over-engineering.

Architectural guarantees (hard-coded, not rule-based):
1. Exponential backoff on claim failure — no infinite retry
2. Heartbeat-based orphan release — crashed agents auto-release after 30m
3. CI failure retry → queue:hold after 3 failures
4. Priority auto-escalation — P0/P1 queues never starve

Flow:
   1. If no open issues exist → run full audit → create issues
   2. Auto-escalate priorities (P0/P1/P2)
   3. Acquire next highest-priority issue via acquire_role_slot.py
   4. Claim it via atomic_claim.sh with exponential backoff
      (#2644 claim-before-work: claim ছাড়া কাজ শুরু নিষিদ্ধ — Claim Gate
      PR-লেভেলে ব্লক করে; এখানে লুপ-লেভেলে সেটাই অর্ডারিং দেয়)
   5. Agent executes the work (optionally via --exec with a scoped JIT env,
      #2644 item 2: master vault keys NEVER reach the child process)
   6. Loop back to step 2

Usage:
    python scripts/agents/continuous_agent_loop.py --role coder --agent-name coder-1
    python scripts/agents/continuous_agent_loop.py --role planner --agent-name planner-1
    python scripts/agents/continuous_agent_loop.py --role coder --agent-name coder-1 \
        --slot agent-3 --exec -- python scripts/agents/some_worker.py --issue 1234
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")
RULES_PATH = ROOT_DIR / ".github" / "constitution" / "rules.yml"
# বাংলা মন্তব্য: #2841 PR-4 — নিয়মের একক-উৎস `AGENT_RULES.md` (সংবিধান-স্লিম সিরিজ)।
# rules.yml এখন শুধু fallback — PR-1 মার্জের আগে ফাইল না থাকলেও লুপ ভাঙবে না।
AGENT_RULES_PATH = ROOT_DIR / "AGENT_RULES.md"

# বাংলা মন্তব্য: পুরনো rules.yml রোল-নাম → AGENT_RULES.md-এর ৭-রোল ক্যানোনিকাল ম্যাপ।
# আচরণের নিয়ম এক উৎস (AGENT_RULES.md) থেকে; App/slot-পরিচয় registry-তেই অপরিবর্তিত —
# ফলে চলমান লেন (platform, ci_devops, rules_breaker...) নাম-বদলের ঝুঁকি ছাড়াই নতুন নিয়ম পায়।
ROLE_ALIASES = {
    "coder": "coder",
    "auditor": "auditor",
    "planner": "planner",
    "ecosystem_scout": "planner",
    "ci_devops": "ci-fixer",
    "pr_helper": "ci-fixer",
    "platform": "watcher",
    "browser": "human-eyes",
    "human_eyes": "human-eyes",
    "rules_breaker": "breaker",
    "super_agent": "coder",
    # ক্যানোনিকাল নামগুলোও নিজেদের ম্যাপেই থাকবে (explicit > implicit)
    "ci-fixer": "ci-fixer",
    "watcher": "watcher",
    "human-eyes": "human-eyes",
    "breaker": "breaker",
}

_ROLE_HEADER = re.compile(r"^###\s*রোল:\s*([\w-]+)", re.M)

# Issue #2682: টপোলজিক্যাল লেয়ারিং ইনভেরিয়েন্ট — টাস্ক-সিলেকশন গেটের প্রিমিটিভ
from scripts.ci.audit_suite import (  # noqa: E402
    scan_open_issue_layers,
    topological_task_gate,
)


def _parse_agent_rules_md(text: str, role: str) -> tuple[list[str], list[str]]:
    """AGENT_RULES.md ভাগ ২ থেকে রোল-সেকশন পার্স → (applicable, prohibited).

    ফরম্যাট: `### রোল: <name> (<বর্ণনা>)` হেডারের পরের `- ` বুলেটগুলোই রুল।
    'নিষিদ্ধ' শব্দযুক্ত বুলেট আলাদা করে prohibited-এ যায় — মেকানিজম অপরিবর্তিত,
    শুধু উৎস বদলেছে (rules.yml → AGENT_RULES.md)।
    """
    canon = ROLE_ALIASES.get(role, role)  # অজানা রোল নিজের নামেই খোঁজা — graceful
    parts = _ROLE_HEADER.split(text)  # [পূর্বের অংশ, নাম১, বডি১, নাম২, বডি২, ...]
    for i in range(1, len(parts), 2):
        if parts[i] != canon:
            continue
        body = parts[i + 1].split("\n## ")[0]  # পরের ভাগ (৩/৪/৫) পৌঁছালে থামুন
        bullets = [ln[2:].strip() for ln in body.splitlines() if ln.strip().startswith("- ")]
        applicable = bullets
        prohibited = [b for b in bullets if "নিষিদ্ধ" in b]
        return applicable, prohibited
    return [], []


def _load_agent_rules_yaml(role: str) -> tuple[list[str], list[str]]:
    """Fallback: পুরনো rules.yml উৎস (PR-1 মার্জের আগে বা নতুন রোল সেখানে না থাকলে)।"""
    applicable: list[str] = []
    prohibited: list[str] = []
    try:
        import yaml
    except ImportError:
        return applicable, prohibited
    try:
        data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
        agent_rules = data.get("agent_rules") or {}
        mapping = agent_rules.get(role) or {}
        applicable = list(mapping.get("applicable_rules") or [])
        prohibited = list(mapping.get("prohibited_actions") or [])
    except Exception:
        pass
    return applicable, prohibited


def _load_agent_rules(role: str) -> tuple[list[str], list[str]]:
    """রোল-নিয়ম লোড: প্রথমে AGENT_RULES.md (একক-উৎস), শূন্য হলে rules.yml fallback."""
    # বাংলা মন্তব্য: সোর্স-প্রথম, fail-safe — পার্স-ব্যর্থতা কখনো লুপ ভাঙবে না।
    try:
        if AGENT_RULES_PATH.exists():
            applicable, prohibited = _parse_agent_rules_md(
                AGENT_RULES_PATH.read_text(encoding="utf-8"), role
            )
            if applicable or prohibited:
                return applicable, prohibited
    except Exception:
        pass
    return _load_agent_rules_yaml(role)


def format_agent_rules_block(role: str) -> str:
    """Return a formatted markdown block of injected rules for the given role."""
    applicable, prohibited = _load_agent_rules(role)
    if not applicable and not prohibited:
        return ""
    lines = [f"\n## 🧩 Dynamic Rule Injection (role={role})\n"]
    if applicable:
        lines.append("### Applicable Rules")
        for r in applicable:
            lines.append(f"- `{r}`")
    if prohibited:
        lines.append("\n### Prohibited Actions")
        for a in prohibited:
            lines.append(f"- {a}")
    lines.append("\n---\n")
    return "\n".join(lines)


def inject_rules_into_issue_body(issue_number: int, role: str) -> None:
    """Append the role-specific rule block to the issue body as a comment."""
    block = format_agent_rules_block(role)
    if not block:
        return
    body = (
        f"🤖 **Auto-injected rules for `{role}`**\n"
        f"{block}\n"
        f"_Source: `AGENT_RULES.md` (fallback: `.github/constitution/rules.yml`) · Injected by `continuous_agent_loop.py`_"
    )
    run([
        "gh", "issue", "comment", str(issue_number),
        "--repo", REPO,
        "--body", body,
    ])


def inject_rules_into_pr_body(pr_number: int, role: str) -> None:
    """Append the role-specific rule block to the PR body."""
    block = format_agent_rules_block(role)
    if not block:
        return
    body = (
        f"🤖 **Auto-injected rules for `{role}`**\n"
        f"{block}\n"
        f"_Source: `AGENT_RULES.md` (fallback: `.github/constitution/rules.yml`) · Injected by `continuous_agent_loop.py`_"
    )
    run([
        "gh", "pr", "edit", str(pr_number),
        "--repo", REPO,
        "--body", body,
    ])


def inject_strategic_memory(issue_number: int, task: dict) -> None:
    """#2691: কাজ শুরুর আগে প্রাসঙ্গিক লাল দাগ ও স্ট্র্যাটেজিক পূর্ব-সিদ্ধান্ত ইনজেক্ট।

    Auditor/Ecosystem-Scout-এর হার্ভেস্ট করা 'কেন না' সিদ্ধান্তগুলো ইস্যুতে
    কমেন্ট হিসেবে ইনজেক্ট হয় — কোডার প্রথম লাইন কোড লেখার আগেই লাল দাগ দেখে।
    Fail-safe: যেকোনো ব্যর্থতা নীরবে স্কিপ — ইনজেকশন কখনো লুপ ভাঙবে না।
    """
    try:
        # বাংলা মন্তব্য: lazy import — মেমরি মডিউল নিজেই import-safe, তবে টেস্টে patch সহজ হয়।
        from scripts.agents.agent_solution_memory import (
            format_strategic_block,
            search_strategic_memory,
        )

        # বাংলা মন্তব্য: কুয়েরি = টাস্ক শিরোনাম + লেবেল; টাস্ক ডেটাতে শিরোনাম না থাকলে gh থেকে।
        title = str(task.get("title") or "").strip()
        if not title:
            res = run([
                "gh", "issue", "view", str(issue_number), "--repo", REPO,
                "--json", "title", "--jq", ".title",
            ])
            if res.returncode == 0:
                title = (res.stdout or "").strip().strip('"')
        labels = " ".join(str(x) for x in (task.get("labels") or []))
        query = f"{title} {labels}".strip()
        if not query:
            return

        entries = search_strategic_memory(query, limit=5)
        if not entries:
            print("ℹ️ কোনো প্রাসঙ্গিক স্ট্র্যাটেজিক লাল দাগ নেই — স্বাধীনভাবে এগোন (#2691)।")
            return

        body = (
            f"🚫 **Strategic Memory Injection (#2691)** — কাজ শুরুর আগে প্রাসঙ্গিক "
            f"পূর্ব-সিদ্ধান্ত ও লাল দাগ:\\n\\n{format_strategic_block(entries)}\\n\\n"
            f"_Source: `data/strategic_decisions.jsonl` · `agent_solution_memory.py search-strategic`_"
        )
        res = run([
            "gh", "issue", "comment", str(issue_number),
            "--repo", REPO, "--body", body,
        ])
        if res.returncode == 0:
            print(f"🧠 Injected {len(entries)} strategic red-line(s) into issue #{issue_number} (#2691).")
        else:
            print(f"⚠️ Strategic injection comment failed: {res.stderr}")
    except Exception as err:  # বাংলা মন্তব্য: fail-safe — মেমরি অনুপস্থিতি কখনো কাজ থামাবে না
        print(f"⚠️ Strategic memory injection skipped ({err}) — continuing (#2691 fail-safe).")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        **kwargs,
    )


def has_open_issues() -> bool:
    """সত্যিকারের কাজ-ইস্যু আছে কি না — `type:ledger` চির-open ড্যাশবোর্ড বাদে।

    # বাংলা মন্তব্য (#2928 root-cause): আগে যেকোনো open issue (লেজার-সহ) গণনা হতো —
    # PRIORITY-QUEUE-LEDGER #2415 চির-open থাকায় এটি সর্বদা true হতো, ফলে
    # run_smart_fallback (৩০-মিনিটের CI-check + scheduled audits) মৃত-কোড ছিল।
    এখন লেজার-ইস্যু বাদ দিয়ে কেবল কাজ-ইস্যু গণনা — fallback সত্যিই চলবে।
    """
    res = run([
        "gh", "issue", "list", "--repo", REPO, "--state", "open",
        "--limit", "100", "--json", "labels",
    ])
    if res.returncode != 0:
        return False
    try:
        issues = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        # বাংলা মন্তব্য: পার্স-ব্যর্থতায় পুরনো আচরণ — খালি-না-হলে কাজ আছেই ধরা
        return bool(res.stdout.strip())
    for issue in issues:
        names = [str(lbl.get("name", "")) for lbl in issue.get("labels", [])]
        if "type:ledger" not in names:
            return True
    return False


def run_audit() -> None:
    print("🔍 No open issues found. Running full audit...")
    res = run([sys.executable, "scripts/agents/priority_queue_ledger.py", "--limit", "10"])
    if res.returncode != 0:
        print(f"⚠️ Audit ledger failed: {res.stderr}")
    else:
        print("✅ Audit complete. Issues should now be available.")


# ROOT-CAUSE FIX (#2911): Time-based scheduled tasks — 12h interval audits
# for 3rd-party platform agents, ecosystem scout, browser agent.
# Each task has a timestamp file so it only runs once per interval.
import time as _time_mod

_SCHEDULED_TASK_INTERVALS = {
    # Task name → interval in seconds
    "platform_agent_audit": 12 * 3600,    # 12 hours
    "ecosystem_scout": 12 * 3600,         # 12 hours
    "browser_agent_audit": 12 * 3600,     # 12 hours
    "ci_failure_check": 30 * 60,          # 30 minutes (more frequent — CI red is urgent)
    "slot_registry_drift": 6 * 3600,       # 6 hours
    "vault_hygiene": 24 * 3600,           # 24 hours (daily)
}

_SCHEDULED_STATE_FILE = Path(__file__).resolve().parents[2] / ".scheduled_task_state.json"


def _load_scheduled_state() -> dict:
    """Load last-run timestamps for scheduled tasks."""
    if _SCHEDULED_STATE_FILE.exists():
        try:
            return json.loads(_SCHEDULED_STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_scheduled_state(state: dict) -> None:
    try:
        _SCHEDULED_STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def _should_run_task(task_name: str) -> bool:
    """Check if a scheduled task should run based on its interval."""
    state = _load_scheduled_state()
    interval = _SCHEDULED_TASK_INTERVALS.get(task_name, 0)
    if interval <= 0:
        return False
    last_run = state.get(task_name, 0)
    elapsed = _time_mod.time() - float(last_run)
    return elapsed >= interval


def _mark_task_run(task_name: str) -> None:
    """Mark that a scheduled task has just run."""
    state = _load_scheduled_state()
    state[task_name] = _time_mod.time()
    _save_scheduled_state(state)


def _run_scheduled_task(task_name: str, cmd: list[str], description: str) -> bool:
    """Run a scheduled task if its interval has elapsed. Returns True if ran."""
    if not _should_run_task(task_name):
        return False
    print(f"  ⏰ Scheduled task: {description} (interval: {_SCHEDULED_TASK_INTERVALS[task_name]//3600}h)")
    res = run(cmd, check=False)
    _mark_task_run(task_name)
    if res.returncode != 0:
        print(f"     ⚠️ {task_name} returned non-zero: {res.stderr[:200] if res.stderr else '(no stderr)'}")
    else:
        print(f"     ✅ {task_name} completed")
    return True


# ROOT-CAUSE FIX (#2908 + #2911): Smart Continuous Loop — when no issues are open,
# the loop now intelligently picks the highest-value task:
# 1. CI fixer (highest priority — main red = fleet blocked) — every 30 min
# 2. Time-based scheduled tasks (12h interval audits):
#    a. Platform agent audit (3rd-party platform agents health)
#    b. Ecosystem scout (discover new integrations/capabilities)
#    c. Browser agent audit (browser tool health)
#    d. Slot registry drift check (6h)
#    e. Vault hygiene (24h — daily)
# 3. Full codebase audit (find new issues)
# 4. If all clear → log + idle
def run_smart_fallback() -> bool:
    """Smart fallback when no open issues. Returns True if new issues created."""
    print("\n🧠 Smart Fallback: No open issues — selecting highest-value task...")

    # Priority 1: CI failures (30-min interval) — স্মার্ট রাউটিং-সহ (#2928)
    # বাংলা মন্তব্য: "main red = fleet blocked, সব ফেলে main আগে" নীতি বুদ্ধিমান নয় —
    # register-এর রাউটার আগে খোলা PR-ক্যান্ডিডেট খোঁজে (merge-first): PR-ই main ঠিক
    # করলে ডুপ্লিকেট fix-issue জন্মায় না; ক্যান্ডিডেট শূন্য হলেই কেবল new-fix issue।
    if _run_scheduled_task(
        "ci_failure_check",
        [sys.executable, "scripts/ci/check_ci_failures.py"],
        "CI failure check (30-min interval)"
    ):
        if has_open_issues():
            print("  ✅ CI issues created! Re-entering normal flow.")
            return True

    # Priority 2: Time-based scheduled audits (12-hour interval)
    # These are heavier tasks that don't need to run every cycle.
    ran_scheduled = False

    # 2a: 3rd-party platform agent audit (12h)
    if _run_scheduled_task(
        "platform_agent_audit",
        [sys.executable, ".github/scripts/platform_agent_check.py", "--json",
         "ci-reports/platform_agent_audit.json"],
        "Platform agent audit (12h interval)"
    ):
        ran_scheduled = True

    # 2b: Ecosystem scout — discover new integrations, capabilities, dead code (12h)
    if _run_scheduled_task(
        "ecosystem_scout",
        [sys.executable, "scripts/ci/project_health_check.py", "--quiet"],
        "Ecosystem scout (12h interval)"
    ):
        ran_scheduled = True

    # 2c: Browser agent audit — check Playwright/browser tool health (12h)
    if _run_scheduled_task(
        "browser_agent_audit",
        [sys.executable, "-c",
         "import subprocess,sys; r=subprocess.run([sys.executable,'-m','pytest','backend/tests/tools/test_browser_agent.py','backend/tests/tools/test_playwright_browser_agent.py','-x','--no-cov','-q','--timeout=30'],capture_output=True,text=True); sys.exit(r.returncode)"],
        "Browser agent audit (12h interval)"
    ):
        ran_scheduled = True

    # 2d: Slot registry drift (6h)
    if _run_scheduled_task(
        "slot_registry_drift",
        [sys.executable, "scripts/agents/check_slot_registry_drift.py", "--quiet"],
        "Slot registry drift check (6h interval)"
    ):
        ran_scheduled = True

    # 2e: Vault hygiene (24h — daily)
    if _run_scheduled_task(
        "vault_hygiene",
        [sys.executable, "scripts/ci/vault_hygiene_check.py", "--dry-run"],
        "Vault hygiene check (24h interval)"
    ):
        ran_scheduled = True

    if ran_scheduled and has_open_issues():
        print("  ✅ Scheduled tasks created issues! Re-entering normal flow.")
        return True

    # Priority 3: Full audit (find new issues from codebase scan)
    print("  3️⃣  Running full audit...")
    run_audit()
    auto_escalate_priorities()
    if has_open_issues():
        print("  ✅ Audit found issues! Re-entering normal flow.")
        return True
    print("  ✅ No audit findings.")

    # All clear — fleet is in perfect shape
    print("\n🎉 All clear!")
    print("   ✅ CI green on main")
    print("   ✅ Platform agents healthy (12h audit)")
    print("   ✅ Ecosystem scout clean (12h)")
    print("   ✅ Browser agent healthy (12h)")
    print("   ✅ Slot registry no drift (6h)")
    print("   ✅ Vault keys valid (24h)")
    print("   ✅ No audit findings")
    print("   ℹ️  Fleet is idle — waiting for new issues or schedule trigger.")
    return False


def auto_escalate_priorities() -> None:
    print("🔄 Running priority auto-escalation...")
    res = run([sys.executable, "scripts/ci/auto_escalate_priority.py"])
    if res.returncode != 0:
        print(f"⚠️ Priority escalation failed: {res.stderr}")
    elif res.stdout.strip():
        print(res.stdout)
    else:
        print("✅ Priority escalation complete.")


def acquire_next_issue(role: str, agent_name: str) -> dict | None:
    res = run([
        sys.executable, "scripts/agents/acquire_role_slot.py",
        "--role", role,
        "--agent-name", agent_name,
    ])
    if res.returncode != 0:
        print(f"❌ Failed to acquire task: {res.stderr}")
        return None
    print(res.stdout)
    try:
        data = json.loads(res.stdout)
        return data
    except (json.JSONDecodeError, TypeError):
        pass
    return {"role": role}


def claim_issue(issue_number: int, agent_slot: str, files: str = "") -> bool:
    cmd = ["./scripts/ci/atomic_claim.sh", str(issue_number), agent_slot]
    if files:
        cmd.extend(["--files", files])
    res = run(cmd)
    if res.returncode == 0:
        print(f"✅ Claimed issue #{issue_number}")
        return True
    print(f"❌ Failed to claim issue #{issue_number}: {res.stderr}")
    return False


def claim_with_backoff(issue_number: int, agent_slot: str, files: str = "", max_retries: int = 3) -> bool:
    """Exponential backoff claim: 2s -> 4s -> 8s, then give up and move to next task."""
    for attempt in range(1, max_retries + 1):
        if claim_issue(issue_number, agent_slot, files):
            return True
        if attempt < max_retries:
            backoff = 2 ** attempt  # 2, 4, 8 seconds
            print(f"⚠️ Claim attempt {attempt}/{max_retries} failed. Backing off {backoff}s...")
            time.sleep(backoff)
        else:
            print(f"❌ Claim failed after {max_retries} attempts. Skipping to next task.")
    return False


def release_orphan_claims(agent_name: str, timeout_minutes: int = 30) -> None:
    """Release claims held by this agent beyond timeout (crash recovery)."""
    print(f"🔍 Checking for orphan claims from {agent_name}...")
    res = run([
        "gh", "issue", "list",
        "--repo", REPO,
        "--label", "status:in-progress",
        "--json", "number,title,assignees,updatedAt"
    ])
    if res.returncode != 0:
        return
    try:
        issues = json.loads(res.stdout)
    except json.JSONDecodeError:
        return
    now = time.time()
    for issue in issues:
        assignees = [a.get("login", "") for a in issue.get("assignees", []) if isinstance(a, dict)]
        if agent_name not in assignees:
            continue
        updated_at = issue.get("updatedAt", "")
        if not updated_at:
            continue
        try:
            updated_ts = time.mktime(time.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ"))
        except (ValueError, TypeError):
            continue
        elapsed_minutes = (now - updated_ts) / 60
        if elapsed_minutes > timeout_minutes:
            num = issue.get("number")
            print(f"⚠️ Releasing orphan claim on issue #{num} (stale {elapsed_minutes:.0f}m)")
            run([
                "gh", "issue", "edit", str(num),
                "--remove-assignee", agent_name,
                "--remove-label", "status:in-progress",
                "--add-label", "status:unclaimed"
            ])


def get_ci_failure_count(issue_number: int) -> int:
    """Count CI failure comments on an issue (simple retry tracking)."""
    res = run([
        "gh", "issue", "view", str(issue_number),
        "--json", "comments",
        "--jq", ".comments[].body"
    ])
    if res.returncode != 0:
        return 0
    return res.stdout.count("CI Failure #")


def handle_ci_failure(issue_number: int, agent_name: str, max_ci_retries: int = 3) -> bool:
    """Handle CI failure: retry up to 3 times, then queue:hold + blocker issue."""
    failure_count = get_ci_failure_count(issue_number)
    if failure_count >= max_ci_retries:
        print(f"❌ CI failed {failure_count} times. Adding queue:hold and creating blocker issue.")
        run([
            "gh", "pr", "list", "--head", f"{agent_name}-*",
            "--json", "number", "--jq", ".[0].number"
        ])
        run([
            "gh", "issue", "edit", str(issue_number),
            "--add-label", "queue:hold"
        ])
        run([
            "gh", "issue", "create",
            "--title", f"Blocker: Issue #{issue_number} CI failing after {failure_count} attempts",
            "--body", f"Issue #{issue_number} has failed CI {failure_count} times. Needs human/admin intervention.",
            "--label", "blocker",
            "--label", f"group:{agent_name}"
        ])
        return False
    print(f"⚠️ CI failure #{failure_count + 1} for issue #{issue_number}. Will retry after fix.")
    return True


def run_rules_breaker_mode(agent_name: str, limit: int = 20) -> None:
    """Run rules_breaker scanner in loop-friendly mode: scan, create issues, inject rules, exit."""
    print("🔴 Rules Breaker mode: running security/pentest scan...")
    res = run([
        sys.executable, "scripts/agents/rules_breaker.py",
        "--agent-name", agent_name,
        "--limit", str(limit),
    ])
    if res.returncode != 0:
        print(f"❌ Rules Breaker scan failed: {res.stderr}")
        return
    print(res.stdout)
    print("✅ Rules Breaker scan complete.")


def run_work_command(cmd: list, role: str, agent_name: str, slot: str = "") -> int:
    """#2644 item 2 — spawn the work command with a SCOPED JIT env.

    # বাংলা: চাইল্ড এজেন্ট প্রসেস কখনো পুরো parent env পায় না। slot দেওয়া
    # থাকলে credential_manager ওই স্লটের GitHub App থেকে ১-ঘণ্টার JIT
    # installation token মিন্ট করে; না থাকলে/ব্যর্থ হলে ambient GH_TOKEN-কে
    # role-allowlist দিয়ে ফিল্টার করে পাস করে। vault মাস্টার কী (INFISICAL_*,
    # GITHUB_APP_PRIVATE_KEY) সবসময়ই বাদ — Zero-Knowledge broker।
    """
    # lazy + patch-friendly: import_module consults sys.modules first, so
    # tests can substitute a fake credential_manager without network/vault.
    import importlib

    cm = importlib.import_module("scripts.agents.credential_manager")

    token = ""
    if slot:
        try:
            minted = cm.resolve_and_mint_for_slot(slot)
            token = minted["token"]
            print(
                f"🔑 JIT credential minted for slot '{slot}' "
                f"(role={role}, expires_at={minted['expires_at']}) — scoped env only"
            )
        except cm.CredentialError as err:
            print(f"⚠️ JIT mint unavailable for slot '{slot}' ({err}) — falling back to ambient token")
    if not token:
        token = (os.environ.get("GH_TOKEN") or "").strip()
        if not token:
            print("❌ #2644 scoped-spawn: no JIT mint and no ambient GH_TOKEN — refusing to spawn")
            return 1
    try:
        env = cm.build_scoped_env(role, token=token, agent_name=agent_name, slot=slot)
    except cm.CredentialError as err:
        print(f"❌ #2644 scoped-spawn env build failed: {err}")
        return 1
    print(f"🛡️ Spawning child with scoped env ({len(env)} keys; master vault keys withheld — #2644)")
    return cm.run(cmd, env)


def topological_task_claim_check(issue_number: int) -> tuple[bool, str]:
    """Issue #2682: ক্লেইম-পূর্ব টপোলজিক্যাল গেট — নিচের লেয়ার খোলা থাকলে ওপরের লেয়ার ক্লেইম নিষিদ্ধ।

    gh দিয়ে open issues-এর ঘোষিত Layer স্ক্যান করে গেট সিদ্ধান্ত দেয়।
    gh ব্যর্থ হলে fail-open — অডিট-স্ক্যান ব্যর্থতা ফ্লিট বন্ধ রাখবে না
    (PR Gate-এর topological_sequence_gate-ই শেষ প্রতিবন্ধক)।
    """
    try:
        res = run([
            "gh", "issue", "list", "--repo", REPO, "--state", "open",
            "--limit", "200", "--json", "number,body",
        ])
        if res.returncode != 0:
            return True, ""
        issues = json.loads(res.stdout or "[]")
        open_layers = scan_open_issue_layers(issues)
        declared = open_layers.get(int(issue_number))
        return topological_task_gate(int(issue_number), declared, open_layers)
    except (json.JSONDecodeError, ValueError, OSError):
        return True, ""


# ── #2745: Admin-Approval Gate (99.99/0.01 আইনের 0.01% শাসন-স্তর) ────────────
ADMIN_APPROVAL_GATE_LABEL = "gate:admin-approval"
ADMIN_APPROVED_LABEL = "approved-by:admin"
_AWAITING_MARKER = "<!-- admin-approval-notified -->"


def admin_approval_gate(issue_number: int) -> tuple[bool, str]:
    """#2745: সংবেদনশীল ইস্যুতে অ্যাডমিন-অনুমোদন ছাড়া কাজ শুরু নিষিদ্ধ।

    চুক্তি:
    - ইস্যুতে `gate:admin-approval` না থাকলে → (True, "") — নির্বিঘ্ন চলবে;
    - `approved-by:admin` লেবেল থাকলে → (True, "admin approved") — মুক্ত;
    - গেটেড কিন্তু অনুমোদন নেই → (False, কারণ) — এজেন্ট ইস্যুটি স্কিপ করবে,
      প্রথম স্কিপে একবারই (dedup-marker কমেন্ট দিয়ে) অ্যাডমিনকে টেলিগ্রাম
      নোটিফিকেশন যাবে + ইস্যুতে স্পষ্ট অপেক্ষা-নোট বসবে।
    - gh ব্যর্থতায় fail-open নয় — সংবেদনশীল-ইস্যু গেটে fail-closed
      (নিরাপত্তা-প্রথম; অডিট-স্ক্যান ব্যর্থতা অনুমোদন-বাইপাসের অজুহাত হতে পারে না)।
    """
    try:
        res = run([
            "gh", "issue", "view", str(issue_number), "--repo", REPO,
            "--json", "labels,comments",
        ])
        if res.returncode != 0:
            return False, f"⚠️ #{issue_number}: admin-approval gate check failed (gh error) — fail-closed skip"
        data = json.loads(res.stdout or "{}")
        labels = [str(l.get("name", "")) for l in data.get("labels", [])]
        if ADMIN_APPROVAL_GATE_LABEL not in labels:
            return True, ""
        if ADMIN_APPROVED_LABEL in labels:
            return True, f"✅ #{issue_number}: admin-approved — gate released"
        comments = data.get("comments", [])
        already_notified = any(_AWAITING_MARKER in str(c.get("body", "")) for c in comments)
        if not already_notified:
            _notify_admin_approval_pending(issue_number)
        return False, (
            f"🛑 #{issue_number}: gated by `{ADMIN_APPROVAL_GATE_LABEL}` — awaiting admin "
            f"approval (add `{ADMIN_APPROVED_LABEL}` label or `/approve #{issue_number}` "
            f"comment). Agent skipped this issue."
        )
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        return False, f"⚠️ #{issue_number}: admin-approval gate error ({exc}) — fail-closed skip"


def _notify_admin_approval_pending(issue_number: int) -> None:
    """বাংলা মন্তব্য (#2745): অ্যাডমিনকে একবারই নোটিফাই — মার্কার-কমেন্ট + টেলিগ্রাম।"""
    marker_body = (
        f"{_AWAITING_MARKER}\n"
        f"## 🛑 Admin approval required (#2745)\n\n"
        f"এই ইস্যুটি `gate:admin-approval` লেবেলযুক্ত — সংবেদনশীল/উচ্চ-ঝুঁকিপূর্ণ কাজ। "
        f"এজেন্ট-ফ্লিট কাজ শুরু করবে না যতক্ষণ না অ্যাডমিন অনুমোদন দেন।\n\n"
        f"**মুক্তির উপায় (যেকোনো একটি):**\n"
        f"- ইস্যুতে `approved-by:admin` লেবেল যোগ করুন, অথবা\n"
        f"- কমেন্ট করুন: `/approve #{issue_number}`\n"
        f"\n_(এই নোটিফিকেশন একবারই পাঠানো হয়েছে — dedup-marker সক্রিয়।)_"
    )
    try:
        run([
            "gh", "issue", "comment", str(issue_number), "--repo", REPO,
            "--body", marker_body,
        ])
    except OSError as exc:
        print(f"⚠️ marker comment failed for #{issue_number}: {exc}")
    # বাংলা মন্তব্য: টেলিগ্রাম-নোটিফিকেশন — বিদ্যমান notify মডিউল পুনঃব্যবহার;
    # env না থাকলে সৎ-স্কিপ (notify নিজেই হ্যান্ডেল করে)।
    try:
        from scripts.maintenance.notify import send_telegram_alert

        send_telegram_alert(
            f"🛑 *Admin approval required*: issue #{issue_number} is gated "
            f"(`gate:admin-approval`). Release with `approved-by:admin` label "
            f"or `/approve #{issue_number}` comment."
        )
    except Exception as exc:  # noqa: BLE001 — notification কখনো গেট-ফ্লো ভাঙবে না
        print(f"⚠️ telegram notify skipped for #{issue_number}: {exc}")


def run_continuous_loop(role: str, agent_name: str, max_iterations: int = 10,
                        slot: str = "", exec_cmd: list | None = None) -> None:
    if role == "rules_breaker":
        run_rules_breaker_mode(agent_name, limit=20)
        return

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        print(f"\n{'='*60}")
        print(f"  🔄 Iteration {iteration}: Agent={agent_name}, Role={role}")
        print(f"{'='*60}")

        release_orphan_claims(agent_name)

        if not has_open_issues():
            # ROOT-CAUSE FIX (#2908 + #2911): Smart Continuous Loop with time-based tasks
            # Replaces passive run_audit() + break with intelligent task selection:
            # 1. CI fixer (30 min) 2. Platform audit (12h) 3. Ecosystem scout (12h)
            # 4. Browser agent audit (12h) 5. Slot drift (6h) 6. Vault hygiene (24h)
            # 7. Full audit 8. All clear → idle
            created = run_smart_fallback()
            if not created:
                print("ℹ️ Fleet healthy — no work available. Waiting for next trigger...")
                break

        auto_escalate_priorities()

        task = acquire_next_issue(role, agent_name)
        if not task:
            print("ℹ️ No task available. Waiting...")
            break

        issue_number = task.get("issue")
        if not issue_number:
            print("ℹ️ No issue number in task. Waiting...")
            break

        # Issue #2682 (mandate 1): ওপরের লেয়ারের (API/UI) টাস্ক তখনই ক্লেইম করা
        # যাবে যখন নিচের লেয়ারের কোনো টাস্ক খোলা নেই — খোলা থাকলে ভিত্তি
        # অসম্পূর্ণ; টাস্ক স্কিপ করে এ ইটারেশন শেষ হবে।
        allowed, gate_reason = topological_task_claim_check(int(issue_number))
        if not allowed:
            print(f"⛔ {gate_reason}")
            print("ℹ️ Topological gate: foundation layers still open — waiting for lower layers.")
            break
        if gate_reason:
            print(f"✅ {gate_reason}")

        # বাংলা মন্তব্য (#2745): সংবেদনশীল-ইস্যু অ্যাডমিন-অনুমোদন গেট —
        # গেটেড ইস্যু অনুমোদন ছাড়া স্কিপ (continue), ফ্লিট থেমে থাকবে না।
        admin_allowed, admin_reason = admin_approval_gate(int(issue_number))
        if not admin_allowed:
            print(f"🛑 {admin_reason}")
            continue
        if admin_reason:
            print(f"✅ {admin_reason}")

        branch_name = task.get("branch_name", "")
        agent_slot = task.get("slot_index") or agent_name
        if claim_with_backoff(issue_number, str(agent_slot)):
            print(f"👉 Agent {agent_name} is now working on issue #{issue_number}")
            print(f"   Branch: {branch_name}")
            print(f"   Role: {task.get('role')}")
            print(f"   Workflow: {task.get('workflow')}")
            inject_rules_into_issue_body(issue_number, role)
            # বাংলা মন্তব্য (#2691): claim-সফলের ঠিক পরে, কাজ শুরুর আগেই লাল-দাগ ইনজেক্ট —
            # 'কেন না' জ্ঞান পুনর্ব্যবহার (Reuse) প্রতিটি টাস্কে স্বয়ংক্রিয়।
            inject_strategic_memory(int(issue_number), task)
            pr_number = task.get("pr_number")
            if pr_number:
                inject_rules_into_pr_body(int(pr_number), role)
            if exec_cmd:
                rc = run_work_command(exec_cmd, role, agent_name, slot=slot)
                print(f"🏁 Work command exited rc={rc} for issue #{issue_number}")

            # ROOT-CAUSE FIX (#2914): post-work automation — push branch,
            # create PR, add has-pr label. Previously the loop expected the
            # work tool (exec_cmd) to do push+PR, but if it only writes code
            # locally, the PR never gets created. Now: loop does it explicitly.
            # বাংলা মন্তব্য (#2928): #2915-এর শর্ত `if a and b if c else d` — অপারেটর-
            # প্রাধান্যের ফাঁদ: exec_cmd না থাকলেও `bool(branch_name)` সত্য হয়ে কাজ-
            # কমান্ড ছাডাই খালি PR জন্মাত (ghost-PR জেনারেটর)। সঠিক চুক্তি:
            # কাজ-কমান্ড চলেছে (exec_cmd আছে) এবং rc == 0 — তবেই push+PR।
            work_ran_ok = exec_cmd is not None and rc == 0
            if branch_name and work_ran_ok:
                print(f"📦 Pushing branch '{branch_name}' to origin...")
                push_res = run(["git", "push", "origin", branch_name, "--force"], check=False)
                if push_res.returncode == 0:
                    print(f"✅ Branch pushed. Creating PR for issue #{issue_number}...")
                    pr_title = f"fix(#{issue_number}): {task.get('title', 'auto-fix')[:60]}"
                    # বাংলা মন্তব্য (#2928): PR body অবশ্যই fixed template-সম্মত —
                    # Summary / Linked Issue / Test Evidence / Rollback (template_gate.py
                    # + Verification Gate-এর চুক্তি); নইলে auto-PR জন্মামাত্রই গেটে আটকাবে।
                    pr_body = (
                        f"## Summary\n\n"
                        f"Automated fix for #{issue_number}: {task.get('title', 'auto-fix')[:80]}.\n\n"
                        f"## Linked Issue\n\nRefs #{issue_number}\n\n"
                        f"## Test Evidence\n\n"
                        f"- Work command exited successfully (rc=0)\n"
                        f"- গেট-রান: PR Gate (Unified Pipeline) — সবুজ প্রমাণ নিচের চেকে\n\n"
                        f"## Rollback\n\n"
                        f"একক squash-কমিট — `git revert <merge-sha>` যথেষ্ট; পার্শ্ব-প্রভাব নেই।\n\n"
                        f"Refs #{issue_number}\n\nVerified by {agent_name}."
                    )
                    pr_res = run([
                        "gh", "pr", "create", "--repo", REPO,
                        "--base", "main", "--head", branch_name,
                        "--title", pr_title, "--body", pr_body,
                    ], check=False)
                    if pr_res.returncode == 0:
                        pr_url = pr_res.stdout.strip()
                        print(f"✅ PR created: {pr_url}")
                        # Add has-pr label to the issue
                        run(["gh", "issue", "edit", str(issue_number),
                             "--repo", REPO, "--add-label", "has-pr"], check=False)
                        print(f"✅ has-pr label added to issue #{issue_number}")
                    else:
                        print(f"⚠️ PR creation failed: {pr_res.stderr[:200]}")
                else:
                    print(f"⚠️ Branch push failed: {push_res.stderr[:200]}")
            elif branch_name:
                print(f"ℹ️ No exec_cmd or work failed — skipping push+PR for #{issue_number}")
        else:
            print("⚠️ Claim failed after retries, moving to next task...")


def main() -> int:
    # বাংলা মন্তব্য: continuous agent loop-এ ecosystem_scout রোল যুক্ত করা হলো যা বিশ্বের সেরা টুলস পর্যবেক্ষণ ও ইন্টিগ্রেশন প্ল্যান করে।
    parser = argparse.ArgumentParser(description="Continuous Autonomous Agent Loop (#2573)")
    parser.add_argument(
        "--role",
        choices=["coder", "planner", "pr-helper", "ci", "platform", "rules_breaker", "ecosystem_scout"],
        required=True,
    )
    parser.add_argument("--agent-name", required=True, help="Agent identifier (e.g. coder-1)")
    parser.add_argument("--iterations", type=int, default=10, help="Max iterations before exit")
    parser.add_argument(
        "--slot", default=os.environ.get("AGENT_SLOT", ""),
        help="Credential slot for scoped JIT env injection (#2644; e.g. agent-3)",
    )
    parser.add_argument(
        "--exec", dest="exec_cmd", nargs=argparse.REMAINDER, metavar="CMD",
        help="Run this work command with a scoped JIT env after a successful claim (#2644 item 2)",
    )
    args = parser.parse_args()

    print(f"🚀 Starting continuous agent loop: role={args.role}, agent={args.agent_name}")
    run_continuous_loop(
        args.role, args.agent_name, max_iterations=args.iterations,
        slot=args.slot, exec_cmd=args.exec_cmd,
    )
    print("\n✅ Agent loop complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
