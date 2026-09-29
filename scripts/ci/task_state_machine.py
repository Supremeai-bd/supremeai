#!/usr/bin/env python3
"""Task State Machine (#2573).

Manages task lifecycle using GitHub labels as persistent state.

States:
  READY -> WAITING_FOR_AGENT -> ASSIGNED -> EXECUTING -> VERIFYING -> DONE
                                                       -> FAILED -> BLOCKED

Label mapping:
  task:ready, task:waiting, task:assigned, task:executing, task:verifying,
  task:done, task:failed, task:blocked

Task types (label prefix):
  task-type:audit, task-type:fix, task-type:review, task-type:ci-fix,
  task-type:security, task-type:cleanup, task-type:verification, task-type:merge
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")


class TaskState(Enum):
    READY = "ready"
    WAITING_FOR_AGENT = "waiting"
    ASSIGNED = "assigned"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"


class TaskType(Enum):
    AUDIT = "audit"
    FIX = "fix"
    REVIEW = "review"
    CI_FIX = "ci-fix"
    SECURITY = "security"
    CLEANUP = "cleanup"
    VERIFICATION = "verification"
    MERGE = "merge"


class TaskPriority(Enum):
    P0_CRITICAL = "P0-critical"
    P1_HIGH = "P1-high"
    P2_MEDIUM = "P2-medium"
    P3_LOW = "P3-low"


STATE_LABEL_PREFIX = "task:"
TYPE_LABEL_PREFIX = "task-type:"
PRIORITY_LABELS = {p.value for p in TaskPriority}

VALID_TRANSITIONS = {
    TaskState.READY: {TaskState.WAITING_FOR_AGENT, TaskState.BLOCKED},
    TaskState.WAITING_FOR_AGENT: {TaskState.ASSIGNED, TaskState.BLOCKED},
    TaskState.ASSIGNED: {TaskState.EXECUTING, TaskState.BLOCKED, TaskState.FAILED},
    TaskState.EXECUTING: {TaskState.VERIFYING, TaskState.FAILED, TaskState.BLOCKED},
    TaskState.VERIFYING: {TaskState.DONE, TaskState.FAILED, TaskState.BLOCKED},
    TaskState.DONE: set(),
    TaskState.FAILED: {TaskState.READY, TaskState.BLOCKED},
    TaskState.BLOCKED: {TaskState.READY, TaskState.WAITING_FOR_AGENT},
}


@dataclass
class Task:
    task_id: str
    task_type: TaskType
    state: TaskState
    priority: TaskPriority
    title: str
    description: str = ""
    assigned_agent: str = ""
    group_name: str = ""
    depends_on: list[str] = field(default_factory=list)
    capabilities_required: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    issue_number: int | None = None
    pr_number: int | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "state": self.state.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "assigned_agent": self.assigned_agent,
            "group_name": self.group_name,
            "depends_on": self.depends_on,
            "capabilities_required": self.capabilities_required,
            "metadata": self.metadata,
            "issue_number": self.issue_number,
            "pr_number": self.pr_number,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        return cls(
            task_id=data["task_id"],
            task_type=TaskType(data["task_type"]),
            state=TaskState(data["state"]),
            priority=TaskPriority(data["priority"]),
            title=data.get("title", ""),
            description=data.get("description", ""),
            assigned_agent=data.get("assigned_agent", ""),
            group_name=data.get("group_name", ""),
            depends_on=data.get("depends_on", []),
            capabilities_required=data.get("capabilities_required", []),
            metadata=data.get("metadata", {}),
            issue_number=data.get("issue_number"),
            pr_number=data.get("pr_number"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


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


def state_label(state: TaskState) -> str:
    return f"{STATE_LABEL_PREFIX}{state.value}"


def type_label(task_type: TaskType) -> str:
    return f"{TYPE_LABEL_PREFIX}{task_type.value}"


def parse_task_labels(labels: list[str]) -> tuple[TaskState | None, TaskType | None, TaskPriority | None]:
    state = None
    task_type = None
    priority = None
    for label in labels:
        if label.startswith(STATE_LABEL_PREFIX):
            state_val = label[len(STATE_LABEL_PREFIX):]
            try:
                state = TaskState(state_val)
            except ValueError:
                pass
        elif label.startswith(TYPE_LABEL_PREFIX):
            type_val = label[len(TYPE_LABEL_PREFIX):]
            try:
                task_type = TaskType(type_val)
            except ValueError:
                pass
        elif label in PRIORITY_LABELS:
            try:
                priority = TaskPriority(label)
            except ValueError:
                pass
    return state, task_type, priority


def create_task(
    task_id: str,
    task_type: TaskType,
    priority: TaskPriority,
    title: str,
    description: str = "",
    group_name: str = "",
    depends_on: list[str] | None = None,
    capabilities_required: list[str] | None = None,
    issue_number: int | None = None,
    pr_number: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> Task:
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    return Task(
        task_id=task_id,
        task_type=task_type,
        state=TaskState.READY,
        priority=priority,
        title=title,
        description=description,
        group_name=group_name,
        depends_on=depends_on or [],
        capabilities_required=capabilities_required or [],
        issue_number=issue_number,
        pr_number=pr_number,
        metadata=metadata or {},
        created_at=now,
        updated_at=now,
    )


def transition_task(task: Task, new_state: TaskState, agent_name: str = "") -> Task:
    if new_state not in VALID_TRANSITIONS.get(task.state, set()):
        raise ValueError(
            f"Invalid transition: {task.state.value} -> {new_state.value}. "
            f"Allowed: {VALID_TRANSITIONS.get(task.state, set())}"
        )
    task.state = new_state
    if agent_name:
        task.assigned_agent = agent_name
    from datetime import UTC, datetime
    task.updated_at = datetime.now(UTC).isoformat()
    return task


def apply_task_to_issue(task: Task, issue_number: int) -> None:
    labels_to_add = [
        state_label(task.state),
        type_label(task.task_type),
        task.priority.value,
    ]
    existing_resp = run(["gh", "issue", "view", str(issue_number), "--json", "labels"])
    existing_labels: set[str] = set()
    if existing_resp.returncode == 0:
        try:
            existing_labels = {l.get("name", "") for l in json.loads(existing_resp.stdout).get("labels", [])}
        except (json.JSONDecodeError, AttributeError):
            pass
    old_state_label = None
    old_type_label = None
    old_priority = None
    for label in existing_labels:
        if label.startswith(STATE_LABEL_PREFIX):
            old_state_label = label
        elif label.startswith(TYPE_LABEL_PREFIX):
            old_type_label = label
        elif label in PRIORITY_LABELS:
            old_priority = label
    for label in labels_to_add:
        if label not in existing_labels:
            run(["gh", "issue", "edit", str(issue_number), "--add-label", label])
    for old_label in [old_state_label, old_type_label, old_priority]:
        if old_label and old_label not in labels_to_add:
            run(["gh", "issue", "edit", str(issue_number), "--remove-label", old_label])


def fetch_tasks_by_state(state: TaskState | None = None, repo_dir: Path = ROOT_DIR) -> list[Task]:
    res = run(["gh", "issue", "list", "--repo", REPO, "--state", "open", "--limit", "200", "--json", "number,title,labels,body,createdAt,assignees"])
    if res.returncode != 0 or not res.stdout.strip():
        return []
    tasks = []
    try:
        issues = json.loads(res.stdout)
    except json.JSONDecodeError:
        return []
    for issue in issues:
        labels = [l.get("name", "") if isinstance(l, dict) else str(l) for l in issue.get("labels", [])]
        task_state, task_type, priority = parse_task_labels(labels)
        if not task_state or not task_type or not priority:
            continue
        if state and task_state != state:
            continue
        assignees = [a.get("login", "") for a in issue.get("assignees", []) if isinstance(a, dict)]
        task = Task(
            task_id=f"task-{issue['number']}",
            task_type=task_type,
            state=task_state,
            priority=priority,
            title=issue.get("title", ""),
            description=issue.get("body", "") or "",
            assigned_agent=assignees[0] if assignees else "",
            issue_number=issue.get("number"),
            created_at=issue.get("createdAt", ""),
            updated_at=issue.get("updatedAt", ""),
        )
        tasks.append(task)
    return tasks


def fetch_task_by_issue(issue_number: int) -> Task | None:
    res = run(["gh", "issue", "view", str(issue_number), "--json", "number,title,labels,body,createdAt,assignees"])
    if res.returncode != 0 or not res.stdout.strip():
        return None
    try:
        issue = json.loads(res.stdout)
    except json.JSONDecodeError:
        return None
    labels = [l.get("name", "") if isinstance(l, dict) else str(l) for l in issue.get("labels", [])]
    task_state, task_type, priority = parse_task_labels(labels)
    if not task_state or not task_type or not priority:
        return None
    assignees = [a.get("login", "") for a in issue.get("assignees", []) if isinstance(a, dict)]
    return Task(
        task_id=f"task-{issue['number']}",
        task_type=task_type,
        state=task_state,
        priority=priority,
        title=issue.get("title", ""),
        description=issue.get("body", "") or "",
        assigned_agent=assignees[0] if assignees else "",
        issue_number=issue.get("number"),
        created_at=issue.get("createdAt", ""),
        updated_at=issue.get("updatedAt", ""),
    )
