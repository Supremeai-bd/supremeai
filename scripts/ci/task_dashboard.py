#!/usr/bin/env python3
"""Task Dashboard (#2573).

Real-time view of all tasks in the system:
- Task states
- Assignments
- Priorities
- Agent workload

Usage:
    python scripts/ci/task_dashboard.py
    python scripts/ci/task_dashboard.py --json
    python scripts/ci/task_dashboard.py --state task:ready
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ci.task_state_machine import Task, TaskState, fetch_tasks_by_state

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")
STATE_LABEL_PREFIX = "task:"
TYPE_LABEL_PREFIX = "task-type:"


def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        **kwargs,
    )


def get_all_tasks() -> list[Task]:
    tasks: list[Task] = []
    for state in TaskState:
        tasks.extend(fetch_tasks_by_state(state))
    return tasks


def get_agent_workload() -> dict[str, int]:
    res = run(["gh", "issue", "list", "--repo", REPO, "--label", "status:in-progress", "--state", "open", "--json", "assignees"])
    if res.returncode != 0:
        return {}
    try:
        issues = json.loads(res.stdout)
    except json.JSONDecodeError:
        return {}
    workload: dict[str, int] = defaultdict(int)
    for issue in issues:
        for assignee in issue.get("assignees", []):
            if isinstance(assignee, dict):
                workload[assignee.get("login", "")] += 1
    return dict(workload)


def render_dashboard(tasks: list[Task], agent_workload: dict[str, int]) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("  📊 Task Dashboard — SupremeAI Task Engine")
    lines.append("=" * 70)
    lines.append("")
    by_state: dict[str, list[Task]] = defaultdict(list)
    for t in tasks:
        by_state[t.state.value].append(t)
    lines.append(f"Total Tasks: {len(tasks)}")
    lines.append("")
    lines.append("─" * 70)
    lines.append("  Tasks by State")
    lines.append("─" * 70)
    for state in TaskState:
        state_tasks = by_state.get(state.value, [])
        lines.append(f"  {state.value.upper():<20} {len(state_tasks):>3}")
    lines.append("")
    lines.append("─" * 70)
    lines.append("  Task Details")
    lines.append("─" * 70)
    for state in TaskState:
        state_tasks = by_state.get(state.value, [])
        if not state_tasks:
            continue
        lines.append(f"\n  [{state.value.upper()}]")
        for task in sorted(state_tasks, key=lambda t: t.priority.value):
            priority = task.priority.value
            task_type = task.task_type.value
            agent = task.assigned_agent or "unassigned"
            issue_ref = f"#{task.issue_number}" if task.issue_number else "no-issue"
            lines.append(f"    {issue_ref:<10} [{priority:<12}] [{task_type:<15}] {agent:<20} {task.title[:40]}")
    lines.append("")
    lines.append("─" * 70)
    lines.append("  Agent Workload")
    lines.append("─" * 70)
    if agent_workload:
        for agent, count in sorted(agent_workload.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {agent:<30} {count:>3} active task(s)")
    else:
        lines.append("  No active agent assignments found.")
    lines.append("")
    lines.append("=" * 70)
    return "\n".join(lines)


def dashboard_to_json(tasks: list[Task], agent_workload: dict[str, int]) -> dict[str, Any]:
    by_state: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in tasks:
        by_state[t.state.value].append(t.to_dict())
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_tasks": len(tasks),
        "by_state": dict(by_state),
        "agent_workload": agent_workload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Task Dashboard (#2573)")
    parser.add_argument("--state", help="Filter by state label (e.g. task:ready)")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()
    
    if args.state:
        state_label = args.state
        state_val = state_label.replace(STATE_LABEL_PREFIX, "")
        try:
            target_state = TaskState(state_val)
            tasks = fetch_tasks_by_state(target_state)
        except ValueError:
            tasks = get_all_tasks()
    else:
        tasks = get_all_tasks()
    
    agent_workload = get_agent_workload()
    
    if args.format == "json":
        print(json.dumps(dashboard_to_json(tasks, agent_workload), indent=2))
    else:
        print(render_dashboard(tasks, agent_workload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
