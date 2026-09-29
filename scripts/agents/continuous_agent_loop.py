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
   5. Agent executes the work
   6. Loop back to step 2

Usage:
    python scripts/agents/continuous_agent_loop.py --role coder --agent-name coder-1
    python scripts/agents/continuous_agent_loop.py --role planner --agent-name planner-1
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")
RULES_PATH = ROOT_DIR / ".github" / "constitution" / "rules.yml"


def _load_agent_rules(role: str) -> tuple[list[str], list[str]]:
    """Load applicable rules and prohibited actions for a given agent role from rules.yml."""
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
        f"_Source: `.github/constitution/rules.yml` · Injected by `continuous_agent_loop.py`_"
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
        f"_Source: `.github/constitution/rules.yml` · Injected by `continuous_agent_loop.py`_"
    )
    run([
        "gh", "pr", "edit", str(pr_number),
        "--repo", REPO,
        "--body", body,
    ])


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
    res = run(["gh", "issue", "list", "--repo", REPO, "--state", "open", "--limit", "1"])
    return res.returncode == 0 and bool(res.stdout.strip())


def run_audit() -> None:
    print("🔍 No open issues found. Running full audit...")
    res = run([sys.executable, "scripts/agents/priority_queue_ledger.py", "--limit", "10"])
    if res.returncode != 0:
        print(f"⚠️ Audit ledger failed: {res.stderr}")
    else:
        print("✅ Audit complete. Issues should now be available.")


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


def run_continuous_loop(role: str, agent_name: str, max_iterations: int = 10) -> None:
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
            run_audit()
            auto_escalate_priorities()
            if not has_open_issues():
                print("ℹ️ No issues to process after audit. Waiting...")
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

        branch_name = task.get("branch_name", "")
        agent_slot = task.get("slot_index") or agent_name
        if claim_with_backoff(issue_number, str(agent_slot)):
            print(f"👉 Agent {agent_name} is now working on issue #{issue_number}")
            print(f"   Branch: {branch_name}")
            print(f"   Role: {task.get('role')}")
            print(f"   Workflow: {task.get('workflow')}")
            inject_rules_into_issue_body(issue_number, role)
            pr_number = task.get("pr_number")
            if pr_number:
                inject_rules_into_pr_body(int(pr_number), role)
        else:
            print("⚠️ Claim failed after retries, moving to next task...")


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuous Autonomous Agent Loop (#2573)")
    parser.add_argument("--role", choices=["coder", "planner", "pr-helper", "ci", "platform", "rules_breaker"], required=True)
    parser.add_argument("--agent-name", required=True, help="Agent identifier (e.g. coder-1)")
    parser.add_argument("--iterations", type=int, default=10, help="Max iterations before exit")
    args = parser.parse_args()

    print(f"🚀 Starting continuous agent loop: role={args.role}, agent={args.agent_name}")
    run_continuous_loop(args.role, args.agent_name, max_iterations=args.iterations)
    print("\n✅ Agent loop complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
