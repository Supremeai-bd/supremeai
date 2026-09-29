#!/usr/bin/env python3
"""Agent Task Assignment Client (#2573).

This is the primary entry point for agents to get their next task.
It wraps the task engine and provides a simple interface:

    python scripts/agents/agent_task_client.py --agent-name coder-1

Output:
    - Task assignment info (issue number, branch, task type)
    - Or "no task available" message

This replaces direct acquire_role_slot.py calls with task-aware routing.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ci.task_router import get_active_agents, infer_agent_capabilities
from scripts.ci.task_state_machine import Task, TaskState, fetch_tasks_by_state

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")


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


def get_my_current_issue(agent_name: str) -> int | None:
    res = run([
        "gh", "issue", "list",
        "--repo", REPO,
        "--label", "status:in-progress",
        "--json", "number,assignees,title"
    ])
    if res.returncode != 0:
        return None
    try:
        issues = json.loads(res.stdout)
    except json.JSONDecodeError:
        return None
    for issue in issues:
        assignees = [a.get("login", "") for a in issue.get("assignees", []) if isinstance(a, dict)]
        if agent_name in assignees:
            return issue.get("number")
    return None


def claim_task_via_issue(task: Task, agent_name: str) -> dict | None:
    if not task.issue_number:
        return None
    res = run([
        "gh", "issue", "edit", str(task.issue_number),
        "--add-assignee", agent_name,
        "--add-label", "status:in-progress",
        "--remove-label", "status:unclaimed"
    ])
    if res.returncode != 0:
        return None
    return {
        "task_id": task.task_id,
        "issue_number": task.issue_number,
        "title": task.title,
        "priority": task.priority.value,
        "task_type": task.task_type.value,
        "assigned_agent": agent_name,
        "group_name": task.group_name,
        "branch": f"group/{task.group_name}" if task.group_name else None,
    }


def get_next_task(agent_name: str) -> dict | None:
    current_issue = get_my_current_issue(agent_name)
    if current_issue:
        return {
            "status": "already_assigned",
            "issue_number": current_issue,
            "message": f"Agent {agent_name} already has issue #{current_issue} in progress"
        }
    ready_tasks = fetch_tasks_by_state(TaskState.READY)
    if not ready_tasks:
        return {"status": "no_tasks", "message": "No READY tasks available"}
    available_agents = get_active_agents()
    free_agents = [a for a in available_agents if a.get("active_issue") is None]
    if not free_agents:
        return {"status": "no_agents", "message": "No free agents available"}
    best_task = None
    best_score = -1.0
    my_caps = infer_agent_capabilities(agent_name)
    for task in ready_tasks:
        from scripts.ci.task_router import match_capabilities
        score = match_capabilities(task, my_caps)
        if score > best_score:
            best_score = score
            best_task = task
    if not best_task or best_score == 0:
        return {"status": "no_match", "message": "No suitable task found for my capabilities"}
    claim = claim_task_via_issue(best_task, agent_name)
    if not claim:
        return {"status": "claim_failed", "message": f"Failed to claim task {best_task.task_id}"}
    return {
        "status": "assigned",
        "task": claim,
        "capability_score": best_score,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Task Client (#2573)")
    parser.add_argument("--agent-name", required=True, help="Agent identifier (e.g. coder-1)")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()
    result = get_next_task(args.agent_name)
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        if not result:
            print("❌ No task available.")
            return 1
        status = result.get("status", "unknown")
        if status == "assigned":
            task = result.get("task", {})
            print(f"✅ Task assigned to {args.agent_name}:")
            print(f"   Task ID: {task.get('task_id')}")
            print(f"   Issue: #{task.get('issue_number')}")
            print(f"   Title: {task.get('title')}")
            print(f"   Priority: {task.get('priority')}")
            print(f"   Type: {task.get('task_type')}")
            print(f"   Capability Score: {result.get('capability_score', 0):.2f}")
        else:
            print(f"ℹ️ {result.get('message', 'No task')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
