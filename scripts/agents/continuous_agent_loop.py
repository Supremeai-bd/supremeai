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
import threading
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


# বাংলা মন্তব্য (#3088 সেশন-আবিষ্কার): AGENT_RULES.md #3095-রির্স্ট্রাকচারের পরে
# লেগেসি `### রোল:` হেডার আর নেই → সব রোল YAML-fallback-এ যায়; কিন্তু
# rules.yml-এর কী-নাম ভিন্ন (ci_devops ইত্যাদি) — ci-fixer (সিস্টেমের
# হাইয়েস্ট-প্রায়োরিটি রোল!) নীরবে শূন্য-রুল পাচ্ছিল। কী-অ্যালায়াস-চেইন
# দিয়ে রুট-ফিক্স: role → underscore-রূপ → নথিভুক্ত অ্যালায়াস।
_YAML_ROLE_KEYS = {
    "ci-fixer": "ci_devops",
    "ci": "ci_devops",
    "platform": "platform",
    "watcher": "platform",  # ROLE_ALIASES: platform লেনের মেশিন-রুল watcher-এ
    "human-eyes": "browser",
    "breaker": "rules_breaker",
    "ecosystem_scout": "ecosystem_scout",
    "pr-helper": "pr_helper",
}


def _load_agent_rules_yaml(role: str) -> tuple[list[str], list[str]]:
    """Fallback: rules.yml উৎস — কী-অ্যালায়াস-চেইনসহ (#3095-রির্স্ট্রাকচার-পরবর্তী একমাত্র মেশিন-উৎস)।"""
    applicable: list[str] = []
    prohibited: list[str] = []
    try:
        import yaml
    except ImportError:
        return applicable, prohibited
    try:
        data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
        agent_rules = data.get("agent_rules") or {}
        key = _YAML_ROLE_KEYS.get(role) or role.replace("-", "_")
        mapping = agent_rules.get(role) or agent_rules.get(key) or {}
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
    # #3088 §6: auditor-triggered continuous loop — claimable==0 হলে
    # controlled auditor evaluation, 30-min anti-storm cooldown।
    "auditor_evaluation": 30 * 60,        # 30 minutes (#3088 anti-storm)
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


# বাংলা মন্তব্য: acquire_role_slot-এর অনুমোদিত ৫টি বেস লেনের সাথে রোল ম্যাপিং
SLOT_ROLE_MAP = {
    "ci-fixer": "ci",
    "ci_devops": "ci",
    "pr_helper": "pr-helper",
    "platform": "platform",
    "watcher": "platform",
    "human-eyes": "coder",
    "browser": "coder",
    "breaker": "coder",
    "rules_breaker": "coder",
    "ecosystem_scout": "planner",
    "auditor": "planner",
}


def get_effective_role(initial_role: str) -> str:
    """বাংলা মন্তব্য: smart_dispatcher ইন্টিগ্রেশন — সিস্টেমের জরুরি অবস্থা (CI red / security) থাকলে অটো-রোল সুইচ।"""
    try:
        from scripts.agents.smart_dispatcher import SmartDispatcher
        dispatcher = SmartDispatcher()
        switched_role, reason = dispatcher._should_switch_role(initial_role)
        if switched_role and switched_role != initial_role:
            print(f"🔀 Smart Dispatcher role-switch: {initial_role} ➔ {switched_role} ({reason})")
            return switched_role
    except Exception as exc:
        print(f"⚠️ Smart Dispatcher check skipped ({exc}) — using requested role {initial_role}")
    return initial_role


# ─────────────────── #2950: Script-Driven Role Assignment ───────────────────
# বাংলা মন্তব্য (#2950 root-cause): script নিজে role ঠিক করবে। সিদ্ধান্তের ভিত্তি:
#   - unclaimed work-issue আছে কিনা → থাকলে coder
#   - না থাকলে → auditor (fleet health check + new issue creation)
# coder ছাড়া বাকি role সব single-agent-per-role lock দিয়ে enforce করা।
from scripts.agents.agent_identity import (  # noqa: E402
    acquire_role_lock,
    is_agent_alive,
    is_cooled_down,
    mark_heartbeat_exited,
    record_cooldown,
    release_role_lock,
    resolve_agent_identity,
    update_heartbeat,
    wait_for_cooldown,
    HEARTBEAT_INTERVAL,
)

AUDITOR_SLEEP_SECONDS = 600  # 10 minutes — auditor already running → wait + retry

# ── #3088 §6: auditor-triggered continuous loop — canonical invariant ──────
# বাংলা মন্তব্য (#3088): Continuous Loop `open issues == 0` দিয়ে সিদ্ধান্ত নেবে না;
# canonical invariant = **agent_claimable_issue_count == 0** → auditor evaluation
# eligible। Anti-storm: audit-cooldown (interval state) + no-issue-when-no-
# actionable-finding (auditor = queue-empty recovery, infinite generator নয়)।


def agent_claimable_issue_count() -> tuple[int, dict[str, int]]:
    """#3088 §6 — claimable কাজ-ইস্যুর সংখ্যা + কেন-অ-claimable-এর সারসংক্ষেপ।

    # বাংলা মন্তব্য (#3088): has_unclaimed_work_issues()-এর সাধারণীকৃত রূপ — শুধু
    bool নয়, count + blocking-reason-বিভাজন (queue-health-চেকের ইনপুট)। শর্তাবলি
    আগের ফাংশনের সাথে হুবহু সামঞ্জস্যপূর্ণ (চালু টেস্ট-চুক্তি অক্ষত)।
    """
    res = run([
        "gh", "issue", "list", "--repo", REPO, "--state", "open",
        "--limit", "200", "--json", "number,labels",
    ])
    if res.returncode != 0:
        return 0, {"lookup_failed": 1}
    try:
        issues = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        return 0, {"lookup_failed": 1}
    claimable = 0
    reasons: dict[str, int] = {}
    for issue in issues:
        names = [str(lbl.get("name", "")) for lbl in issue.get("labels", [])]
        if "type:ledger" in names:
            reasons["ledger"] = reasons.get("ledger", 0) + 1
            continue
        if "template:violating" in names:
            reasons["template_violating"] = reasons.get("template_violating", 0) + 1
            continue
        if "status:in-progress" in names:
            reasons["in_progress"] = reasons.get("in_progress", 0) + 1
            continue
        if "has-pr" in names:
            reasons["has_pr"] = reasons.get("has_pr", 0) + 1
            continue
        if "gate:admin-approval" in names and "approved-by:admin" not in names:
            reasons["admin_gated"] = reasons.get("admin_gated", 0) + 1
            continue
        claimable += 1
    return claimable, reasons


def auditor_evaluation_eligibility() -> dict:
    """#3088 §6 — claimable==0 হলে auditor-মূল্যায়নের যোগ্যতা-সিদ্ধান্ত।

    Flow (spec §6):
      claimable > 0 → eligible=False (কাজ আছে — auditor নয়)
      claimable == 0 → queue-health (blocking-reason breakdown)
                     → anti-storm cooldown চেক (interval state-file)
                     → verdict: queue_empty | blocked_by_admin
    বাংলা মন্তব্য: সব-issue admin-gated হলে auditor নতুন issue খোলে না —
    BLOCKED_BY_ADMIN = বিদ্যমান Admin Decision ইস্যুর আপডেট, ডুপ্লিকেট নয়।
    """
    claimable, reasons = agent_claimable_issue_count()
    if claimable > 0:
        return {
            "eligible": False,
            "claimable": claimable,
            "reason": "claimable_work_exists",
        }
    blocked_by_admin = reasons.get("admin_gated", 0) > 0
    if not _should_run_task("auditor_evaluation"):
        return {
            "eligible": False,
            "claimable": 0,
            "reason": "audit_cooldown_active",
            "blocking_reasons": reasons,
        }
    _mark_task_run("auditor_evaluation")
    return {
        "eligible": True,
        "claimable": 0,
        "reason": "blocked_by_admin" if blocked_by_admin else "queue_empty",
        "blocking_reasons": reasons,
        "verdict_hint": ("BLOCKED_BY_ADMIN — বিদ্যমান Admin Decision ইস্যু আপডেট করুন"
                         if blocked_by_admin
                         else "ACTIONABLE_FINDINGS বা NO_ACTIONABLE_FINDINGS (no-issue হলে evidence-only)"),
    }



def has_unclaimed_work_issues() -> bool:
    """Check if any unclaimed work-issue exists (coder-এর কাজ আছে কিনা).

    # বাংলা মন্তব্য (#2950): unclaimed = status:in-progress বা has-pr লেবেল
    # নেই, type:ledger নয়, gate:admin-approval নয় (যদি approved-by:admin
    # না থাকে)। এই condition-এ coder role assign হবে।
    """
    # (#3088) এখন agent_claimable_issue_count-এর পাতলা wrapper — behavior
    # হুবহু আগের মতোই (existing-test চুক্তি অক্ষত রেখে)।
    claimable, _ = agent_claimable_issue_count()
    return claimable > 0


def decide_role() -> str:
    """#2950: Script autonomously decides the role.

    Decision matrix:
      - unclaimed work-issue exists → "coder"
      - else → "auditor"

    বাংলা মন্তব্য: এই function-টাই #2950-এর মূল সিদ্ধান্ত-কেন্দ্র। প্রতিটি script
    run-এ এটি call হবে — user-এর `--role coder` নয়, সিস্টেম state থেকেই রোল।
    """
    # #2930: Pre-flight PR Awareness — open PR audit আগে।
    # বাংলা মন্তব্য: AGENTS.md Major Rule 2 — "merge-first > duplicate-fix"।
    # যদি কোনো open PR-এ ইতিমধ্যে সমাধান চলমান থাকে, নতুন কাজ না করে সেই PR
    # verify/merge-এর দিকে রাউট করতে হবে।
    open_prs = _count_open_prs()
    if open_prs > 0:
        print(f"👀 Pre-flight: {open_prs} open PR(s) detected — merge-first priority (per #2930)")

    if has_unclaimed_work_issues():
        print("🧭 Role decision: unclaimed work-issue found → coder")
        return "coder"
    print("🧭 Role decision: no unclaimed work-issue → auditor")
    return "auditor"


def _count_open_prs() -> int:
    """#2930: Pre-flight PR Awareness — count open PRs for merge-first routing."""
    try:
        res = run([
            "gh", "pr", "list", "--repo", REPO, "--state", "open",
            "--limit", "50", "--json", "number",
        ])
        if res.returncode == 0:
            import json as _json
            data = _json.loads(res.stdout or "[]")
            return len(data)
    except Exception:
        pass
    return 0


def _heartbeat_thread(agent_name: str, role: str, model: str,
                      stop_event: threading.Event) -> None:
    """#2950-followup: Background heartbeat thread — updates every 10 minutes.

    বাংলা মন্তব্য: এই thread daemon — main loop exit হলে সেও মরে। প্রতি
    HEARTBEAT_INTERVAL (10 min) অন্তর heartbeat registry update করে।
    Fail-safe: যেকোনো exception চুপচাপ swallow হয় — heartbeat কখনো main
    loop থামাবে না। current_issue পেতে _current_issue global read করে।
    """
    while not stop_event.is_set():
        try:
            current = _current_issue_holder.get("issue")
            branch = _current_issue_holder.get("branch", "")
            update_heartbeat(agent_name, role, model=model,
                             current_issue=current, branch=branch, status="working")
        except Exception:
            pass  # heartbeat failure কখনো main loop থামাবে না
        # Wait interval, but wake up early if stop signaled
        stop_event.wait(HEARTBEAT_INTERVAL)


# Module-level holder for current issue (thread-safe enough for our use)
_current_issue_holder: dict = {"issue": None, "branch": ""}


def acquire_role_with_lock(role: str, agent_name: str) -> bool:
    """#2950: Acquire role — coder ছাড়া বাকি role-এ single-agent lock.

    বাংলা মন্তব্য: coder multiple agents allow, বাকি সব role-এ git-push-CAS
    দিয়ে single-agent-per-role lock enforce করা হয় (agent_identity.py)।
    এই lock প্রতিটি script run-এর শুরুতে acquire হবে, শেষে release হবে
    (try/finally — crash হলেও TTL দিয়ে auto-expire হবে)।

    #2950-followup: stale agent detection — lock যদি expired agent-এর নামে
    থাকে (heartbeat 30+ min পুরোনো), সেটা force-release করে নতুন agent নেয়।
    """
    if role == "coder":
        return True  # multiple agents allowed — কোনো lock লাগে না

    # #2950-followup: check existing lock — stale agent?
    from scripts.agents.agent_identity import _read_role_lock_metadata, release_role_lock
    existing = _read_role_lock_metadata(role)
    if existing and existing.agent_name != agent_name and not existing.is_expired():
        # Lock TTL still valid — check if agent is alive via heartbeat
        if is_agent_alive(existing.agent_name):
            print(f"⚠️ Role '{role}' is held by {existing.agent_name} (alive).")
        else:
            # Stale agent (no heartbeat 30+ min) — force release + take over
            print(f"🧹 Stale lock from {existing.agent_name} (no heartbeat 30+ min) — taking over")
            release_role_lock(role, existing.agent_name)
            # Remove from heartbeat registry too
            from scripts.agents.agent_identity import remove_stale_heartbeat
            remove_stale_heartbeat(existing.agent_name)
            # Now try to acquire
            if acquire_role_lock(role, agent_name, ttl=3600):
                return True

    if not acquire_role_lock(role, agent_name, ttl=3600):
        print(f"⚠️ Role '{role}' is already held by another agent.")
        print(f"   Sleeping {AUDITOR_SLEEP_SECONDS}s before retry...")
        time.sleep(AUDITOR_SLEEP_SECONDS)
        # Retry once
        if not acquire_role_lock(role, agent_name, ttl=3600):
            print(f"❌ Role '{role}' still locked after retry — exiting.")
            return False
    return True


def build_task_contract(
    agent_name: str,
    role: str,
    task: dict,
    branch_name: str,
) -> dict:
    """#2950: Build the JSON TaskContract — role + rules + work + credentials.

    বাংলা মন্তব্য (#2950 requirement 2 + 3 + 4):
    এই contract-টাই script-এর output — এজেন্ট এটা দেখে কাজ শুরু করবে।
    চারটি অংশ:
      ১. agent identity (name + machine_id)
      ২. role + applicable_rules + prohibited_rules (AGENT_RULES.md থেকে)
      ৩. scoped_credentials (role-ভিত্তিক JIT token + allowed env keys)
      ৪. mcp_payload (MCP Tower-এ set_role + heartbeat)
    """
    applicable, prohibited = _load_agent_rules(role)
    issue_number = task.get("issue")
    issue_title = task.get("title", "")
    issue_labels = task.get("labels", [])
    contract = {
        "agent": {
            "name": agent_name,
        },
        "role": role,
        "issue": {
            "number": issue_number,
            "title": issue_title,
            "labels": issue_labels,
        },
        "branch": branch_name,
        "applicable_rules": applicable,
        "prohibited_rules": prohibited,
        "scoped_credentials": _build_scoped_credentials_block(role, agent_name),
        "mcp_payload": {
            "role": role,
            "heartbeat_interval": 30,
            "tower_set_role_required": role != "coder",
        },
        "work_command": None,
        "cooldown_after_seconds": 120,
        # #2950-followup: on_complete — AGENT_RULES.md Rule 5 (continuous re-run)
        # বাংলা মন্তব্য: task শেষে স্ক্রিপ্ট কী করবে তা এই field নির্দেশ করে।
        # "rerun_script" = সমজাতীয় কাজ থাকলে অবিলম্বে পরবর্তী task শুরু (continuous)।
        # "wait_and_retry" = fleet idle হলে short wait পরে retry।
        # "exit" = স্পষ্টভাবে শেষ (manual override বা admin stop)।
        "on_complete": {
            "action": "rerun_script",
            "condition": "similar_tasks_remaining",
            "description": "Continuous execution — similar task থাকলে অবিলম্বে পরবর্তী শুরু (per AGENT_RULES.md Rule 5)",
            "idle_wait_seconds": 300,  # fleet idle হলে 5-min wait → retry
        },
    }

    # ── #3088 §1/§8: canonical universal envelope — একই চুক্তি সব role-এ ──
    # বাংলা মন্তব্য: Task type বদলায়, envelope বদলায় না। উপরের legacy ফিল্ডগুলো
    # (agent/role/issue/...) অক্ষত থেকে যাবে (backward-compat); নিচের canonical
    # ব্লক task_contract_schema-র SSOT থেকে আসছে — ভবিষ্যতের সব consumer এটাই পড়বে।
    try:
        from scripts.agents.group_taxonomy import primary_group_of_labels
        from scripts.agents.task_contract_schema import contract_from_issue

        labels = list(issue_labels or [])
        canonical = contract_from_issue(
            issue_number=int(issue_number or 0),
            title=issue_title,
            labels=labels,
            group=primary_group_of_labels(labels) or "pipeline",
            objective=issue_title,
            priority=_priority_from_labels(labels),
            sequence=_seq_from_labels(labels),
            admin_gate_required=("gate:admin-approval" in labels),
        )
        contract["task_contract"] = canonical.to_dict()
        contract["task_contract_hash"] = canonical.contract_hash()
        contract["instruction_envelope"] = canonical.render_envelope()
    except Exception as exc:  # noqa: BLE001 — canonical-ব্লক best-effort, legacy চুক্তি অক্ষত
        contract["task_contract_error"] = f"canonical envelope skipped: {exc}"

    return contract


def _priority_from_labels(labels: list[str]) -> str:
    """লেবেল → canonical priority (#3088 §1: P0..P3)।"""
    for lbl in labels or []:
        if str(lbl).startswith("P") and str(lbl)[1:].split("-", 1)[0] in ("0", "1", "2", "3"):
            return f"P{str(lbl)[1]}" if str(lbl)[1].isdigit() else "P2"
    return "P2"


def _seq_from_labels(labels: list[str]) -> int | None:
    """`seq:N` লেবেল → canonical sequence (#3088 §1)।"""
    for lbl in labels or []:
        m = re.match(r"^seq:(\d+)$", str(lbl))
        if m:
            return int(m.group(1))
    return None


def _build_scoped_credentials_block(role: str, agent_name: str) -> dict:
    """Build a masked scoped-credentials block (no real tokens in contract).

    বাংলা মন্তব্য (#2950 + #2644): contract-এ আসল token কখনো যাবে না — শুধু
    "which env keys are allowed" + masked presence indicator। আসল token
    child process-এ env var হিসেবে inject হয় (credential_manager দিয়ে)।
    """
    # Role → allowed env keys (read from dynamic_credential_broker's ROLE_VAULT_KEYS)
    try:
        from scripts.agents.dynamic_credential_broker import ROLE_VAULT_KEYS
        allowed = sorted(ROLE_VAULT_KEYS.get(role, set()))
    except Exception:
        allowed = []
    return {
        "allowed_env_keys": allowed,
        "token_masked": True,  # actual token injected via env, not in contract
        "broker": "dynamic_credential_broker",
        "note": "Real credentials injected via env vars (not in this JSON).",
    }


def emit_task_contract(contract: dict) -> None:
    """Emit the TaskContract JSON to stdout (machine-readable)."""
    print("\n" + "=" * 60)
    print("  📦 TaskContract (machine-readable JSON below)")
    print("=" * 60)
    print(json.dumps(contract, ensure_ascii=False, indent=2))
    print("=" * 60 + "\n")


def acquire_next_issue(role: str, agent_name: str) -> dict | None:
    slot_role = SLOT_ROLE_MAP.get(role, role)
    # #2949 root-cause fix: use --defer-checkout — branch checkout এখানে হবে না।
    # বাংলা মন্তব্য: আগে acquire_role_slot.py checkout করতো — কিন্তু claim ব্যর্থ
    # হলে branch dirty state এ পড়ে থাকতো। এখন শুধু branch_name রিটার্ন করে,
    # caller (claim_with_backoff সফল হলে) checkout করে।
    res = run([
        sys.executable, "scripts/agents/acquire_role_slot.py",
        "--role", slot_role,
        "--agent-name", agent_name,
        "--format", "json",
        "--defer-checkout",
    ])
    if res.returncode != 0:
        print(f"❌ Failed to acquire task: {res.stderr}")
        return None
    print(res.stdout)
    try:
        raw = res.stdout.strip()
        if "{" in raw and "}" in raw:
            json_str = raw[raw.index("{"):raw.rindex("}") + 1]
            data = json.loads(json_str)
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # বাংলা মন্তব্য: Fail-safe regex fallback — যদি কোনো কারণে টেক্সট ফরম্যাট আউটপুট আসে
    m_issue = re.search(r"Next priority issue:\s*#(\d+)", res.stdout)
    m_branch = re.search(r"(?:Acquired Slot|Group Branch):\s*([^\s\(\)]+)", res.stdout)
    if m_issue:
        return {
            "role": role,
            "issue": int(m_issue.group(1)),
            "branch_name": m_branch.group(1) if m_branch else "",
        }

    return {"role": role}


def _extract_touching_files_from_issue(issue_number: int) -> str:
    """#2950 follow-up: Extract 'Touching files:' declaration from issue body.

    বাংলা মন্তব্য: issue template (#2912)-এ 'Touching Files' section থাকে —
    সেটা পড়ে atomic_claim.sh-কে --files আর্গুমেন্ট হিসেবে পাস করা হয়।
    এটা Scope Gate-কে আগে থেকেই সন্তুষ্ট রাখে — PR-লেভেলে block হয় না।
    """
    try:
        res = run([
            "gh", "issue", "view", str(issue_number), "--repo", REPO,
            "--json", "body", "--jq", ".body",
        ])
        if res.returncode != 0:
            return ""
        body = res.stdout or ""
        # বাংলা মন্তব্য: '### Touching Files' বা 'Touching files:' heading-এর পরের
        # bullet/list লাইনগুলো extract করি (template_gate.py-এর সাথে consistent)।
        lines = body.splitlines()
        files = []
        in_section = False
        for line in lines:
            stripped = line.strip()
            if "touching files" in stripped.lower():
                in_section = True
                # inline format: "Touching files: a.py, b.py"
                if ":" in stripped:
                    inline = stripped.split(":", 1)[1].strip()
                    if inline:
                        files.extend([f.strip().strip("`").strip("*") for f in inline.split(",") if f.strip()])
                continue
            if in_section:
                # bullet/backtick list lines
                if stripped.startswith(("-", "*", "`")):
                    token = stripped.lstrip("-*` ").rstrip("`")
                    if token and ("/" in token or "." in token):
                        files.append(token)
                elif stripped.startswith("#") or (stripped and not stripped.startswith(("-", "*", "`"))):
                    break  # next section
        return ", ".join(files)
    except Exception:
        return ""


def claim_issue(issue_number: int, agent_slot: str, files: str = "",
                skip_assign: bool = True) -> bool:
    """#2950 follow-up: enhanced atomic claim with bot-mode + files + error capture.

    বাংলা মন্তব্য (root-cause fix):
    আগে claim_issue শুধু `atomic_claim.sh <issue> <agent>` পাস করত — কিন্তু:
      ১. GitHub App bot-রা /assignees API-তে 403 পায় → --skip-assign দরকার
      ২. কোনো --files না দিলে Scope Gate পরে PR-কে block করে
      ৩. atomic_claim.sh-এর error message stdout-এ যায় (শুধু stderr নয়)
         তাই `res.stderr` দেখালে empty দেখায় — root cause লুকায়
    এখন: --skip-assign (default True), --files, stdout+stderr দুটোই capture।
    """
    cmd = ["./scripts/ci/atomic_claim.sh", str(issue_number), agent_slot]
    # বাংলা মন্তব্য: উইন্ডোজ পরিবেশে .sh সরাসরি এক্সিকিউট করা যায় না (WinError 193) — bash প্রিফিক্স
    if sys.platform == "win32":
        cmd = ["bash", "./scripts/ci/atomic_claim.sh", str(issue_number), agent_slot]
    # #2950: GitHub App bot-রা assign করতে পারে না (403 Forbidden) — --skip-assign
    # দিয়ে label-based CAS পথ নিতে হয় (#1838 audit-fix)। default True কারণ
    # script-driven agent-রা সবাই bot identity দিয়ে চলে।
    if skip_assign:
        cmd.append("--skip-assign")
    if files:
        cmd.extend(["--files", files])
    res = run(cmd)
    if res.returncode == 0:
        print(f"✅ Claimed issue #{issue_number}")
        return True
    # #2950 follow-up: atomic_claim.sh-এর diagnostic (Rule #13 block, race, etc.)
    # stdout-এ যায় — শুধু stderr দেখালে empty দেখায়, root cause লুকায়।
    error_output = (res.stderr or "").strip()
    if not error_output:
        error_output = (res.stdout or "").strip()[-500:]  # last 500 chars
    print(f"❌ Failed to claim issue #{issue_number}: {error_output[:400]}")
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
    """Release claims held by this agent beyond timeout (crash recovery).

    #3042 root-cause fix: bot-mode claims (--skip-assign) have empty assignees
    → old code skipped all bot claims. Now uses claim-comment **Claimed at:**
    timestamp + heartbeat liveness cross-check.
    """
    print(f"🔍 Checking for orphan claims from {agent_name}...")
    res = run([
        "gh", "issue", "list",
        "--repo", REPO,
        "--label", "status:in-progress",
        "--json", "number,title,assignees,updatedAt,comments"
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
        # #3042: bot mode — assignees empty, check claim comment instead
        comments = issue.get("comments", [])
        claim_found = False
        claim_time_str = ""
        for c in comments:
            body = c.get("body", "") if isinstance(c, dict) else str(c)
            if "Atomic Claim" in body and f"`{agent_name}`" in body:
                claim_found = True
                # Parse "Claimed at:" timestamp from claim comment
                m = re.search(r"Claimed at:\\s*([0-9T:+-]+)", body)
                if m:
                    claim_time_str = m.group(1)
                    break
        # Old behavior: skip if agent_name not in assignees AND no claim comment
        if agent_name not in assignees and not claim_found:
            continue

        # #3042: use claim-comment timestamp (not updatedAt — noise-based)
        timestamp_str = claim_time_str or issue.get("updatedAt", "")
        if not timestamp_str:
            continue
        try:
            # Parse ISO format
            ts_str = timestamp_str.replace("Z", "+00:00") if "Z" in timestamp_str else timestamp_str
            from datetime import datetime as _dt
            try:
                claim_ts = _dt.fromisoformat(ts_str).timestamp()
            except (ValueError, TypeError):
                claim_ts = time.mktime(time.strptime(timestamp_str[:19], "%Y-%m-%dT%H:%M:%S"))
        except (ValueError, TypeError):
            continue
        elapsed_minutes = (now - claim_ts) / 60
        if elapsed_minutes > timeout_minutes:
            num = issue.get("number")
            print(f"⚠️ Releasing orphan claim on issue #{num} (stale {elapsed_minutes:.0f}m)")
            # #3042: use --remove-label (works for bot mode) instead of --remove-assignee
            run([
                "gh", "issue", "edit", str(num),
                "--repo", REPO,
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


def run_continuous_loop(role: str | None = None, agent_name: str | None = None,
                        max_iterations: int = 10,
                        slot: str = "", exec_cmd: list | None = None,
                        model: str | None = None) -> None:
    """#2950: Continuous agent loop — now script-driven (role + agent auto-assigned).

    বাংলা মন্তব্য (#2950 root-cause redesign + #2950-followup dynamic model):
    আগে `--role` আর `--agent-name` required ছিল — এখন তিনটাই optional।
    script নিজে সিদ্ধান্ত নেয়:
      ১. agent_name: persistent identity (~/.supremeai/identity.json) থেকে
         resolve — না থাকলে git-push-as-CAS দিয়ে dynamically assign।
         Name format: {model}-{role}-{index} (e.g. glm5.2-coder-1)।
      ২. role: decide_role() — unclaimed issue থাকলে coder, না থাকলে auditor।
      ৩. single-agent-per-role lock (coder ছাড়া বাকি role-এ)।
    """
    # ─── Step 1: Persistent agent identity resolve (#2950 + #2950-followup) ───
    if not agent_name:
        identity = resolve_agent_identity(preferred=role if role else "coder", model=model)
        agent_name = identity.agent_name
        print(f"🆔 Agent identity resolved: {agent_name} (model={identity.model})")
    else:
        print(f"🆔 Agent identity (explicit): {agent_name}")

    # ─── Step 2: Script-driven role decision (#2950) ───
    if not role:
        role = decide_role()

    # smart_dispatcher system-state override (CI red → ci-fixer, security → breaker)
    active_role = get_effective_role(role)
    if active_role in ("rules_breaker", "breaker"):
        run_rules_breaker_mode(agent_name, limit=20)
        return

    # ─── Step 3: Single-agent-per-role lock (#2950) ───
    # বাংলা মন্তব্য: coder ছাড়া বাকি role-এ git-push-CAS দিয়ে lock।
    # crash-safety: try/finally — exception হলেও release হবে।
    role_lock_acquired = False
    if active_role != "coder":
        if not acquire_role_with_lock(active_role, agent_name):
            return  # অন্য agent ধরে আছে, sleep+retry ব্যর্থ
        role_lock_acquired = True
        print(f"🔒 Role lock acquired: {active_role} → {agent_name}")

    # ─── Step 4: Background heartbeat thread (#2950-followup) ───
    # বাংলা মন্তব্য: daemon thread — প্রতি 10-min-এ heartbeat update করে।
    # main loop exit হলে সেও মরে (daemon=True)। try/finally-তে stop হবে।
    # model নির্ধারণ: identity থেকে আসলে, নাহলে env, নাহলে "unknown"।
    hb_model = "unknown"
    try:
        hb_model = identity.model  # type: ignore[name-defined]
    except NameError:
        hb_model = os.environ.get("AGENT_MODEL", "unknown")
    heartbeat_stop = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_thread,
        args=(agent_name, active_role, hb_model, heartbeat_stop),
        daemon=True,
    )
    heartbeat_thread.start()
    # Initial heartbeat (তাড়াতাড়ি — প্রথম update-এর জন্য 10-min অপেক্ষা না করে)
    try:
        update_heartbeat(agent_name, active_role, model=hb_model, status="working")
    except Exception:
        pass
    print(f"💓 Heartbeat thread started (interval={HEARTBEAT_INTERVAL}s)")

    try:
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"  🔄 Iteration {iteration}: Agent={agent_name}, Role={active_role} (requested={role})")
            print(f"{'='*60}")

            # #2950-followup: refresh GitHub token if stale (50-min TTL)
            # বাংলা মন্তব্য: প্রতি iteration-এ check — token পুরোনো হলে re-mint।
            # এটা দীর্ঘ loop-এ silent API failure prevent করে।
            try:
                from scripts.agents.agent_identity import refresh_token_if_stale
                refresh_token_if_stale()
            except Exception:
                pass  # token refresh failure কখনো loop থামাবে না

            release_orphan_claims(agent_name)

            if not has_open_issues():
                # ROOT-CAUSE FIX (#2908 + #2911): Smart Continuous Loop with time-based tasks
                created = run_smart_fallback()
                if not created:
                    print("ℹ️ Fleet healthy — no work available. Waiting for next trigger...")
                    break

            auto_escalate_priorities()

            task = acquire_next_issue(active_role, agent_name)
            if not task:
                # #3088 §6: canonical invariant — claimable==0 → auditor eligibility
                # বাংলা মন্তব্য: "No task" মানেই থেমে যাওয়া নয়; কেন-অ-claimable
                # তার স্বাস্থ্য-রিপোর্টসহ auditor-মূল্যায়নের যোগ্যতা যাচাই হবে
                # (cooldown-সুরক্ষিত — infinite issue-generator নয়, recovery)।
                try:
                    eligibility = auditor_evaluation_eligibility()
                    print(f"🔍 Auditor-eligibility (#3088): {json.dumps(eligibility, ensure_ascii=False)}")
                    if eligibility.get("eligible"):
                        print("🧭 Auditor evaluation eligible — audit-verdict প্রবাহে প্রবেশ "
                              "(ACTIONABLE_FINDINGS ছাড়া নতুন issue নয়)।")
                except Exception as exc:  # noqa: BLE001 — eligibility-চেক কখনো loop ভাঙবে না
                    print(f"⚠️ auditor-eligibility check skipped: {exc}")
                print("ℹ️ No task available. Waiting...")
                break

            issue_number = task.get("issue")
            if not issue_number:
                print("ℹ️ No issue number in task. Waiting...")
                break

            # Issue #2682 (mandate 1): topological gate — lower layer first
            allowed, gate_reason = topological_task_claim_check(int(issue_number))
            if not allowed:
                print(f"⛔ {gate_reason}")
                print("ℹ️ Topological gate: foundation layers still open — waiting for lower layers.")
                break
            if gate_reason:
                print(f"✅ {gate_reason}")

            # বাংলা মন্তব্য (#2745): admin-approval gate for sensitive issues
            admin_allowed, admin_reason = admin_approval_gate(int(issue_number))
            if not admin_allowed:
                print(f"🛑 {admin_reason}")
                continue
            if admin_reason:
                print(f"✅ {admin_reason}")

            branch_name = task.get("branch_name", "")
            agent_slot = task.get("slot_index") or agent_name

            # #2950: check cooldown before claiming
            if not is_cooled_down(agent_name):
                wait_for_cooldown(agent_name)
                continue

            # #2950 follow-up: pass declared files from task body → Scope Gate prevent
            # বাংলা মন্তব্য: issue body-তে 'Touching files:' section থাকলে সেটা extract
            # করে atomic_claim.sh-কে পাস করা হয়, যাতে Scope Gate PR-লেভেলে আটকায় না।
            declared_files = _extract_touching_files_from_issue(issue_number)

            if claim_with_backoff(issue_number, str(agent_slot), files=declared_files):
                print(f"👉 Agent {agent_name} is now working on issue #{issue_number}")
                print(f"   Branch: {branch_name}")
                print(f"   Role: {task.get('role')}")
                print(f"   Workflow: {task.get('workflow')}")

                # #2949 root-cause fix: now that claim succeeded, perform the deferred checkout.
                # বাংলা মন্তব্য: acquire_role_slot এ --defer-checkout দিয়েছিল, তাই
                # branch checkout এখন claim সফলের পরেই হবে — আগে নয়। যদি claim
                # ব্যর্থ হতো, এই কোডে ঢুকতো না, branch dirty হতো না।
                if task.get("checkout_deferred") and branch_name:
                    from scripts.agents.acquire_role_slot import (
                        checkout_group_branch, checkout_slot_branch, GROUP_BRANCH_PREFIX
                    )
                    if branch_name.startswith(GROUP_BRANCH_PREFIX):
                        grp = branch_name[len(GROUP_BRANCH_PREFIX):]
                        _ok = checkout_group_branch(grp)
                    else:
                        _ok = checkout_slot_branch(branch_name)
                    if _ok:
                        print(f"✅ Branch checked out (post-claim): {branch_name}")
                    else:
                        print(f"⚠️ Post-claim checkout failed: {branch_name}")
                print(f"   Branch: {branch_name}")

                # #2950-followup: update current issue for heartbeat thread
                _current_issue_holder["issue"] = issue_number
                _current_issue_holder["branch"] = branch_name

                # #2950: build + emit JSON TaskContract
                contract = build_task_contract(agent_name, active_role, task, branch_name)
                emit_task_contract(contract)

                inject_rules_into_issue_body(issue_number, active_role)
                # বাংলা মন্তব্য (#2691): claim-সফলের ঠিক পরে, কাজ শুরুর আগেই লাল-দাগ ইনজেক্ট।
                inject_strategic_memory(int(issue_number), task)
                pr_number = task.get("pr_number")
                if pr_number:
                    inject_rules_into_pr_body(int(pr_number), active_role)
                if exec_cmd:
                    rc = run_work_command(exec_cmd, active_role, agent_name, slot=slot)
                    print(f"🏁 Work command exited rc={rc} for issue #{issue_number}")

                # ROOT-CAUSE FIX (#2914): post-work automation — push branch,
                # create PR, add has-pr label, then record cooldown (#2950)।
                # বাংলা মন্তব্য (#2928): #2915-এর শর্ত `if a and b if c else d` — অপারেটর-
                # প্রাধান্যের ফাঁক: exec_cmd না থাকলেও `bool(branch_name)` সত্য হয়ে কাজ-
                # কমান্ড ছাডাই খালি PR জন্মাত (ghost-PR জেনারেটর)। সঠিক চুক্তি:
                # কাজ-কমান্ড চলেছে (exec_cmd আছে) এবং rc == 0 — তবেই push+PR।
                work_ran_ok = exec_cmd is not None and rc == 0
                if branch_name and work_ran_ok:
                    print(f"📦 Pushing branch '{branch_name}' to origin...")
                    push_res = run(["git", "push", "origin", branch_name, "--force"], check=False)
                    if push_res.returncode == 0:
                        print(f"✅ Branch pushed. Creating PR for issue #{issue_number}...")
                        pr_title = f"fix(#{issue_number}): {task.get('title', 'auto-fix')[:60]}"
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
                            run(["gh", "issue", "edit", str(issue_number),
                                 "--repo", REPO, "--add-label", "has-pr"], check=False)
                            print(f"✅ has-pr label added to issue #{issue_number}")
                            # #2950: record 2-min cooldown after successful push
                            record_cooldown(agent_name, seconds=120)
                            print(f"⏳ Recorded 2-min cooldown for {agent_name}")
                        else:
                            print(f"⚠️ PR creation failed: {pr_res.stderr[:200]}")
                    else:
                        print(f"⚠️ Branch push failed: {push_res.stderr[:200]}")
                elif branch_name:
                    print(f"ℹ️ No exec_cmd or work failed — skipping push+PR for #{issue_number}")
            else:
                print("⚠️ Claim failed after retries, moving to next task...")
    finally:
        # #2950: graceful release of role lock on exit (crash-safety)
        if role_lock_acquired:
            release_role_lock(active_role, agent_name)
            print(f"🔓 Role lock released: {active_role}")
        # #2950-followup: stop heartbeat thread + mark exited
        heartbeat_stop.set()
        try:
            mark_heartbeat_exited(agent_name)
        except Exception:
            pass
        print(f"💔 Heartbeat stopped for {agent_name} (marked exited)")
        # #2950-followup: AGENT_RULES.md Rule 5 — continuous re-run
        # বাংলা মন্তব্য: task শেষে on_complete.action check করে পরবর্তী step।
        # "rerun_script" = similar task থাকলে অবিলম্বে পরবর্তী iteration শুরু।
        # এটা AGENT_RULES.md Rule 5 (Graceful Exit + Continuous Re-run) enforce করে।
        try:
            on_complete = contract.get("on_complete", {}) if 'contract' in dir() else {}
            action = on_complete.get("action", "exit")
            if action == "rerun_script":
                # সমজাতীয় কাজ আছে কিনা যাচাই করো
                if has_unclaimed_work_issues():
                    print(f"🔄 Continuous re-run: similar tasks remaining — starting next immediately (per Rule 5)")
                    # Note: পরবর্তী iteration main loop-এর পরবর্তী cycle হবে
                    # (run_continuous_loop-এর while iteration loop এখনও active)
                else:
                    # Fleet idle — short wait পরে retry
                    idle_wait = on_complete.get("idle_wait_seconds", 300)
                    print(f"💤 Fleet idle — no similar tasks. Waiting {idle_wait}s before retry (per Rule 5)")
                    time.sleep(idle_wait)
            elif action == "exit":
                print(f"🚪 on_complete action=exit — clean shutdown (per Rule 5)")
        except Exception as e:
            print(f"⚠️ on_complete check skipped ({e}) — defaulting to exit")



def main() -> int:
    # বাংলা মন্তব্য (#2950 + #2950-followup): script-driven role + agent-name + model
    # — তিনটেই optional। যদি user না দেয়, script নিজে decide করবে: unclaimed issue
    # থাকলে coder, না থাকলে auditor; agent_name persistent identity থেকে resolve
    # হবে; model AGENT_MODEL env বা --model arg থেকে আসবে (default "unknown")।
    parser = argparse.ArgumentParser(description="Continuous Autonomous Agent Loop (#2573, #2950)")
    parser.add_argument(
        "--role",
        choices=["coder", "planner", "pr-helper", "ci", "platform", "rules_breaker",
                  "ecosystem_scout", "auditor", "ci-fixer", "human-eyes", "breaker", "watcher"],
        default=None,
        help="Role override (optional — #2950: if omitted, script auto-decides coder/auditor)",
    )
    parser.add_argument("--agent-name", default=None,
                        help="Agent identifier (optional — #2950: if omitted, persistent identity resolves)")
    parser.add_argument("--model", default=None,
                        help="LLM model name (e.g. glm5.2, sonnet-3.5). Optional — #2950-followup: "
                             "if omitted, AGENT_MODEL env var or 'unknown' is used. Becomes agent name prefix.")
    parser.add_argument("--iterations", type=int, default=10, help="Max iterations before exit")
    parser.add_argument(
        "--slot", default=os.environ.get("AGENT_SLOT", ""),
        help="Credential slot for scoped JIT env injection (#2644; e.g. agent-3)",
    )
    parser.add_argument(
        "--exec", dest="exec_cmd", nargs=argparse.REMAINDER, metavar="CMD",
        help="Run this work command with a scoped JIT env after a successful claim (#2644 item 2)",
    )
    # #3088 §6: canonical claimable-count প্রশ্ন — workflow/agents এটা দিয়ে
    # auditor-trigger যাচাই করবে (open-issue-count নয়, claimable-count)।
    parser.add_argument(
        "--check-claimable", action="store_true",
        help="Print claimable-count + auditor-eligibility as JSON and exit (#3088 §6)",
    )
    args = parser.parse_args()

    if args.check_claimable:
        # বাংলা মন্তব্য: শুধু-পড়া প্রশ্ন-মোড — কোনো claim/lock ছোঁয়া নয়।
        count, reasons = agent_claimable_issue_count()
        print(json.dumps({
            "claimable": count,
            "blocking_reasons": reasons,
            "auditor_eligible_now": count == 0,
        }, ensure_ascii=False))
        return 0

    print(f"🚀 Starting continuous agent loop: role={args.role}, agent={args.agent_name}, model={args.model or os.environ.get('AGENT_MODEL', 'unknown')}")
    run_continuous_loop(
        args.role, args.agent_name, max_iterations=args.iterations,
        slot=args.slot, exec_cmd=args.exec_cmd, model=args.model,
    )
    print("\n✅ Agent loop complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
