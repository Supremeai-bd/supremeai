#!/usr/bin/env python3
"""Task Detector (#2573).

Watches GitHub events, CI status, schedules, and manual triggers to detect
and create tasks automatically.

Event sources:
- GitHub Issues (opened, closed, reopened, labeled, unlabeled)
- GitHub PRs (opened, merged, closed, ready_for_review)
- GitHub Actions / CI (workflow_run.completed with failure/success)
- Schedule (periodic audit, cleanup)
- Manual dispatch (workflow_dispatch)

Each detector emits a Task object with:
- task_type
- priority
- required capabilities
- dependencies
- source event
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

from scripts.ci.task_state_machine import Task, TaskPriority, TaskType, create_task

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")


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


def get_open_issues(limit: int = 300) -> list[dict[str, Any]]:
    res = run(["gh", "issue", "list", "--repo", REPO, "--state", "open", "--limit", str(limit), "--json", "number,title,body,labels,createdAt"])
    if res.returncode == 0 and res.stdout.strip():
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError:
            pass
    return []


def get_open_prs(limit: int = 100) -> list[dict[str, Any]]:
    res = run(["gh", "pr", "list", "--repo", REPO, "--state", "open", "--limit", str(limit), "--json", "number,title,headRefName,body,labels,createdAt,author,mergeable,mergeStateStatus"])
    if res.returncode == 0 and res.stdout.strip():
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError:
            pass
    return []


def get_recent_workflow_runs(limit: int = 20) -> list[dict[str, Any]]:
    res = run(["gh", "run", "list", "--repo", REPO, "--limit", str(limit), "--json", "conclusion,event,status,workflowName,headBranch,createdAt"])
    if res.returncode == 0 and res.stdout.strip():
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError:
            pass
    return []


def detect_tasks_from_issues(issues: list[dict[str, Any]]) -> list[Task]:
    tasks: list[Task] = []
    for issue in issues:
        labels = [l.get("name", "") if isinstance(l, dict) else str(l) for l in issue.get("labels", [])]
        has_task = any(l.startswith(("task:", "task-type:")) for l in labels)
        if has_task:
            continue
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        priority = TaskPriority.P3_LOW
        if "P0-critical" in labels:
            priority = TaskPriority.P0_CRITICAL
        elif "P1-high" in labels:
            priority = TaskPriority.P1_HIGH
        elif "P2-medium" in labels:
            priority = TaskPriority.P2_MEDIUM
        task_type = TaskType.FIX
        capabilities = ["coding"]
        if any(k in (title + body).lower() for k in ["security", "vulnerability", "cve", "owasp"]):
            task_type = TaskType.SECURITY
            capabilities = ["security", "coding"]
        elif any(k in (title + body).lower() for k in ["ci", "workflow", "pipeline", "github-actions"]):
            task_type = TaskType.CI_FIX
            capabilities = ["ci", "coding"]
        elif any(k in (title + body).lower() for k in ["audit", "architecture", "review"]):
            task_type = TaskType.AUDIT
            capabilities = ["analysis", "coding"]
        elif any(k in (title + body).lower() for k in ["cleanup", "remove", "delete", "prune"]):
            task_type = TaskType.CLEANUP
            capabilities = ["coding"]
        elif any(k in (title + body).lower() for k in ["verify", "validation", "test"]):
            task_type = TaskType.VERIFICATION
            capabilities = ["testing", "coding"]
        group = ""
        for label in labels:
            if label.startswith("group:"):
                group = label.split(":", 1)[1]
                break
        task = create_task(
            task_id=f"task-{issue['number']}",
            task_type=task_type,
            priority=priority,
            title=title,
            description=body[:500],
            group_name=group,
            capabilities_required=capabilities,
            issue_number=issue.get("number"),
            metadata={"source": "issue", "labels": labels},
        )
        tasks.append(task)
    return tasks


def detect_tasks_from_failed_ci() -> list[Task]:
    tasks: list[Task] = []
    runs = get_recent_workflow_runs(limit=20)
    for run in runs:
        if run.get("conclusion") != "failure":
            continue
        workflow_name = run.get("workflowName", "")
        branch = run.get("headBranch", "")
        if not workflow_name or not branch:
            continue
        task = create_task(
            task_id=f"task-ci-failure-{workflow_name.lower().replace(' ', '-')}-{branch}",
            task_type=TaskType.CI_FIX,
            priority=TaskPriority.P1_HIGH,
            title=f"CI Fix: {workflow_name} failed on {branch}",
            description=f"Workflow '{workflow_name}' failed on branch '{branch}'.",
            group_name=branch,
            capabilities_required=["ci", "coding"],
            metadata={"source": "ci", "workflow": workflow_name, "branch": branch},
        )
        tasks.append(task)
    return tasks


def detect_tasks_from_prs(prs: list[dict[str, Any]]) -> list[Task]:
    tasks: list[Task] = []
    for pr in prs:
        labels = [l.get("name", "") if isinstance(l, dict) else str(l) for l in pr.get("labels", [])]
        has_task = any(l.startswith(("task:", "task-type:")) for l in labels)
        if has_task:
            continue
        mergeable = pr.get("mergeable")
        merge_state = pr.get("mergeStateStatus", "")
        if mergeable == "CONFLICTING" or merge_state == "dirty":
            task = create_task(
                task_id=f"task-pr-conflict-{pr['number']}",
                task_type=TaskType.CI_FIX,
                priority=TaskPriority.P1_HIGH,
                title=f"PR #{pr['number']} has merge conflicts",
                description=f"PR #{pr['number']} ('{pr.get('title', '')}') has merge conflicts and needs resolution.",
                capabilities_required=["coding", "git"],
                pr_number=pr.get("number"),
                metadata={"source": "pr", "pr_number": pr.get("number"), "mergeable": mergeable},
            )
            tasks.append(task)
    return tasks


def detect_all_tasks() -> list[Task]:
    tasks: list[Task] = []
    tasks.extend(detect_tasks_from_issues(get_open_issues()))
    tasks.extend(detect_tasks_from_failed_ci())
    tasks.extend(detect_tasks_from_prs(get_open_prs()))
    return tasks


def main() -> int:
    parser = argparse.ArgumentParser(description="Task Detector (#2573)")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()
    
    tasks = detect_all_tasks()
    if args.format == "json":
        print(json.dumps([t.to_dict() for t in tasks], indent=2))
    else:
        if not tasks:
            print("✅ No new tasks detected.")
        else:
            print(f"🔍 Detected {len(tasks)} tasks:")
            for task in tasks:
                print(f"   [{task.priority.value}] {task.task_id}: {task.title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
