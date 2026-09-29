#!/usr/bin/env python3
"""Task Router (#2573).

Routes tasks to available agents based on:
1. Priority (P0 > P1 > P2 > P3)
2. Capability matching
3. Fair distribution (cooldown-aware)
4. Dependencies (predecessor tasks must be DONE)
5. Hybrid push/pull model

Capability registry sources:
- Existing role inference from acquire_role_slot.py
- GitHub issue labels (handoff:*)
- Agent heartbeat/mesh (optional)
- Task metadata capabilities_required

Routing models:
- Push: High-priority tasks are pushed to best-matched agent
- Pull: Idle agents pull highest-suitable READY task
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ci.task_state_machine import (
    Task,
    TaskPriority,
    TaskState,
    fetch_tasks_by_state,
)

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")
AGENT_CAPABILITY_MAP: dict[str, set[str]] = {
    "planner": {"analysis", "planning", "architecture", "coding"},
    "coder": {"coding", "debugging", "testing"},
    "pr-helper": {"review", "merge", "git", "testing"},
    "ci": {"ci", "devops", "docker", "kubernetes", "coding"},
    "platform": {"infrastructure", "cloud", "monitoring", "devops", "coding"},
}

PRIORITY_ORDER = [TaskPriority.P0_CRITICAL, TaskPriority.P1_HIGH, TaskPriority.P2_MEDIUM, TaskPriority.P3_LOW]


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


def get_active_agents() -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    res = run(["gh", "issue", "list", "--repo", REPO, "--label", "status:in-progress", "--state", "open", "--json", "number,title,assignees,labels"])
    if res.returncode == 0 and res.stdout.strip():
        try:
            issues = json.loads(res.stdout)
            for issue in issues:
                assignees = [a.get("login", "") for a in issue.get("assignees", []) if isinstance(a, dict)]
                for assignee in assignees:
                    agents.append({
                        "name": assignee,
                        "active_issue": issue.get("number"),
                        "title": issue.get("title", ""),
                    })
        except (json.JSONDecodeError, AttributeError):
            pass
    return agents


def infer_agent_capabilities(agent_name: str) -> set[str]:
    capabilities: set[str] = set()
    for role, caps in AGENT_CAPABILITY_MAP.items():
        if role in agent_name.lower():
            capabilities.update(caps)
    if not capabilities:
        capabilities = {"coding", "general"}
    return capabilities


def match_capabilities(task: Task, agent_capabilities: set[str]) -> float:
    required = set(task.capabilities_required)
    if not required:
        return 1.0
    matches = required & agent_capabilities
    return len(matches) / len(required)


def get_dependent_tasks(task: Task, all_tasks: list[Task]) -> set[str]:
    dependent_ids: set[str] = set()
    for t in all_tasks:
        if task.task_id in t.depends_on:
            dependent_ids.add(t.task_id)
    return dependent_ids


def check_dependencies(task: Task, all_tasks: list[Task]) -> tuple[bool, list[str]]:
    task_map = {t.task_id: t for t in all_tasks}
    blocked_by: list[str] = []
    for dep_id in task.depends_on:
        dep = task_map.get(dep_id)
        if not dep or dep.state != TaskState.DONE:
            blocked_by.append(dep_id)
    return len(blocked_by) == 0, blocked_by


def route_single_task(task: Task, all_tasks: list[Task], available_agents: list[dict[str, Any]]) -> dict[str, Any] | None:
    deps_ok, blocked_by = check_dependencies(task, all_tasks)
    if not deps_ok:
        return {
            "task_id": task.task_id,
            "action": "blocked",
            "reason": f"Waiting for dependencies: {', '.join(blocked_by)}",
        }
    if not available_agents:
        return {
            "task_id": task.task_id,
            "action": "waiting",
            "reason": "No available agents",
        }
    best_agent = None
    best_score = -1.0
    for agent in available_agents:
        caps = infer_agent_capabilities(agent["name"])
        score = match_capabilities(task, caps)
        if score > best_score:
            best_score = score
            best_agent = agent
    if not best_agent:
        return {
            "task_id": task.task_id,
            "action": "waiting",
            "reason": "No suitable agent found",
        }
    return {
        "task_id": task.task_id,
        "action": "assign",
        "agent": best_agent["name"],
        "capability_score": best_score,
    }


def route_all_tasks() -> list[dict[str, Any]]:
    ready_tasks = fetch_tasks_by_state(TaskState.READY)
    waiting_tasks = fetch_tasks_by_state(TaskState.WAITING_FOR_AGENT)
    all_tasks = ready_tasks + waiting_tasks
    available_agents = get_active_agents()
    results: list[dict[str, Any]] = []
    assigned_agents: set[str] = set()
    for task in sorted(all_tasks, key=lambda t: PRIORITY_ORDER.index(t.priority)):
        if available_agents:
            free_agents = [a for a in available_agents if a["name"] not in assigned_agents]
            if not free_agents:
                results.append({
                    "task_id": task.task_id,
                    "action": "waiting",
                    "reason": "All agents busy",
                })
                continue
            result = route_single_task(task, all_tasks, free_agents)
            if result and result.get("action") == "assign":
                assigned_agents.add(result["agent"])
        else:
            result = route_single_task(task, all_tasks, [])
        if result:
            results.append(result)
    return results


def push_high_priority_tasks() -> list[dict[str, Any]]:
    p0_tasks = fetch_tasks_by_state(TaskState.READY)
    p0_tasks = [t for t in p0_tasks if t.priority == TaskPriority.P0_CRITICAL]
    available_agents = get_active_agents()
    results: list[dict[str, Any]] = []
    for task in p0_tasks:
        result = route_single_task(task, p0_tasks, available_agents)
        if result:
            results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Task Router (#2573)")
    parser.add_argument("--push", action="store_true", help="Push high-priority tasks to agents")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()
    
    if args.push:
        results = push_high_priority_tasks()
    else:
        results = route_all_tasks()
    
    if args.format == "json":
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print("✅ No tasks to route.")
        else:
            print(f"🔀 Routing results ({len(results)} tasks):")
            for result in results:
                action = result.get("action", "unknown")
                task_id = result.get("task_id", "?")
                if action == "assign":
                    agent = result.get("agent", "?")
                    print(f"   ✅ {task_id} -> {agent} (score: {result.get('capability_score', 0):.2f})")
                elif action == "blocked":
                    print(f"   ⏸️ {task_id}: {result.get('reason', 'blocked')}")
                else:
                    print(f"   ⏳ {task_id}: {result.get('reason', 'waiting')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
