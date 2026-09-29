#!/usr/bin/env python3
"""Task Timeout & Recovery Engine (#2573).

Detects tasks that have been stuck in non-terminal states beyond their
timeout threshold and automatically releases them back to READY.

Timeout thresholds:
- ASSIGNED: 30 minutes (agent claimed but never started)
- EXECUTING: 2 hours (agent working but no progress)
- VERIFYING: 30 minutes (verification stuck)
- FAILED: immediate (re-queue)

Recovery actions:
1. Remove agent assignment
2. Reset state to READY
3. Add comment to issue explaining timeout
4. Optionally add backoff label

This prevents:
- Crashed agents holding tasks forever
- Zombie claims from dead sessions
- Workflow deadlocks
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ci.task_state_machine import (
    Task,
    TaskState,
    apply_task_to_issue,
    fetch_tasks_by_state,
    transition_task,
)

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")
TIMEOUTS = {
    TaskState.ASSIGNED: 30 * 60,  # 30 minutes
    TaskState.EXECUTING: 2 * 60 * 60,  # 2 hours
    TaskState.VERIFYING: 30 * 60,  # 30 minutes
}
STATE_LABEL_PREFIX = "task:"


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


def get_issue_updated_at(issue_number: int) -> datetime | None:
    res = run(["gh", "issue", "view", str(issue_number), "--json", "updatedAt"])
    if res.returncode != 0 or not res.stdout.strip():
        return None
    try:
        data = json.loads(res.stdout)
        ts = data.get("updatedAt", "")
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (json.JSONDecodeError, ValueError):
        return None


def add_timeout_comment(issue_number: int, task: Task, reason: str) -> None:
    body = (
        f"⚠️ **Task Timeout Recovery**\n\n"
        f"Task `{task.task_id}` was in `{task.state.value}` state for too long "
        f"and has been automatically reset to `READY`.\n\n"
        f"**Reason:** {reason}\n"
        f"**Previous assignee:** {task.assigned_agent or 'none'}\n"
        f"**Recovered at:** {datetime.now(UTC).isoformat()}\n\n"
        f"This task is now available for reassignment."
    )
    run(["gh", "issue", "comment", str(issue_number), "--body", body])


def recover_timeout_tasks(dry_run: bool = False) -> list[dict[str, Any]]:
    recovered: list[dict[str, Any]] = []
    for state, timeout_seconds in TIMEOUTS.items():
        tasks = fetch_tasks_by_state(state)
        now = datetime.now(UTC)
        for task in tasks:
            if not task.issue_number:
                continue
            updated = get_issue_updated_at(task.issue_number)
            if not updated:
                continue
            elapsed = (now - updated).total_seconds()
            if elapsed < timeout_seconds:
                continue
            reason = f"Stuck in {state.value} for {elapsed/60:.0f} minutes (threshold: {timeout_seconds/60:.0f} minutes)"
            if not dry_run:
                add_timeout_comment(task.issue_number, task, reason)
                transition_task(task, TaskState.READY)
                apply_task_to_issue(task, task.issue_number)
            recovered.append({
                "task_id": task.task_id,
                "issue_number": task.issue_number,
                "previous_state": state.value,
                "elapsed_minutes": elapsed / 60,
                "reason": reason,
            })
    return recovered


def main() -> int:
    parser = argparse.ArgumentParser(description="Task Timeout & Recovery Engine (#2573)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be recovered without making changes")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()
    
    recovered = recover_timeout_tasks(dry_run=args.dry_run)
    if args.format == "json":
        print(json.dumps(recovered, indent=2))
    else:
        if not recovered:
            print("✅ No timed-out tasks found.")
        else:
            print(f"🔄 Recovered {len(recovered)} timed-out tasks:")
            for item in recovered:
                print(f"   #{item['issue_number']}: {item['task_id']} (stuck {item['elapsed_minutes']:.0f}m in {item['previous_state']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
