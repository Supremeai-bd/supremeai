#!/usr/bin/env python3
"""Workflow Orchestrator (#2573).

Defines and executes predefined task chains (workflows) that automatically
progress through the task lifecycle.

Workflows:
- audit_chain: InitialAudit -> IssueCreation -> FixIssues -> PR -> CI -> Review -> Merge
- security_chain: SecurityScan -> SecurityFix -> PR -> CI -> Merge
- ci_fix_chain: CIFailure -> Diagnosis -> Fix -> PR -> CI
- group_verification_chain: GroupVerify -> Merge -> Cleanup

Each workflow defines:
- Trigger conditions
- Task sequence
- Next-task rules
- Exit conditions
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ci.task_state_machine import (
    Task,
    TaskPriority,
    TaskType,
    create_task,
)

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


@dataclass
class WorkflowStep:
    step_id: str
    task_type: TaskType
    priority: TaskPriority
    title_template: str
    description_template: str
    required_capabilities: list[str]
    next_step: str | None = None
    exit_conditions: list[str] = field(default_factory=list)


@dataclass
class Workflow:
    workflow_id: str
    name: str
    description: str
    steps: list[WorkflowStep]
    trigger_conditions: list[str]
    exit_conditions: list[str]


WORKFLOWS: dict[str, Workflow] = {}


def _register_workflows() -> None:
    audit_steps = [
        WorkflowStep(
            step_id="audit",
            task_type=TaskType.AUDIT,
            priority=TaskPriority.P0_CRITICAL,
            title_template="Initial repository audit",
            description_template="Perform comprehensive audit of repository state, architecture, and issues.",
            required_capabilities=["analysis", "coding"],
            next_step="issue_creation",
        ),
        WorkflowStep(
            step_id="issue_creation",
            task_type=TaskType.FIX,
            priority=TaskPriority.P1_HIGH,
            title_template="Create issues from audit findings",
            description_template="Create GitHub issues based on audit findings.",
            required_capabilities=["coding"],
            next_step="fix_issues",
        ),
        WorkflowStep(
            step_id="fix_issues",
            task_type=TaskType.FIX,
            priority=TaskPriority.P1_HIGH,
            title_template="Fix issues from audit",
            description_template="Fix issues identified during audit.",
            required_capabilities=["coding", "debugging"],
            next_step="pr_creation",
        ),
        WorkflowStep(
            step_id="pr_creation",
            task_type=TaskType.REVIEW,
            priority=TaskPriority.P1_HIGH,
            title_template="Create PR for fixes",
            description_template="Create pull request with audit fixes.",
            required_capabilities=["git", "coding"],
            next_step="ci_validation",
        ),
        WorkflowStep(
            step_id="ci_validation",
            task_type=TaskType.CI_FIX,
            priority=TaskPriority.P1_HIGH,
            title_template="Validate CI pipeline",
            description_template="Ensure CI pipeline passes after fixes.",
            required_capabilities=["ci", "devops"],
            next_step="group_verification",
        ),
        WorkflowStep(
            step_id="group_verification",
            task_type=TaskType.VERIFICATION,
            priority=TaskPriority.P1_HIGH,
            title_template="Group verification",
            description_template="Verify all group tasks are complete.",
            required_capabilities=["testing", "coding"],
            next_step="merge",
        ),
        WorkflowStep(
            step_id="merge",
            task_type=TaskType.MERGE,
            priority=TaskPriority.P1_HIGH,
            title_template="Merge group PR",
            description_template="Merge verified PR into main branch.",
            required_capabilities=["git", "merge"],
            next_step=None,
        ),
    ]
    WORKFLOWS["audit_chain"] = Workflow(
        workflow_id="audit_chain",
        name="Audit to Merge Chain",
        description="Full audit → fix → PR → CI → verify → merge workflow",
        steps=audit_steps,
        trigger_conditions=["manual", "schedule", "no_active_workflow"],
        exit_conditions=["all_steps_complete", "critical_failure"],
    )
    security_steps = [
        WorkflowStep(
            step_id="security_scan",
            task_type=TaskType.SECURITY,
            priority=TaskPriority.P0_CRITICAL,
            title_template="Security scan: {target}",
            description_template="Run security scan on {target}.",
            required_capabilities=["security", "coding"],
            next_step="security_fix",
        ),
        WorkflowStep(
            step_id="security_fix",
            task_type=TaskType.SECURITY,
            priority=TaskPriority.P0_CRITICAL,
            title_template="Security fix: {finding}",
            description_template="Fix security finding: {finding}.",
            required_capabilities=["security", "coding"],
            next_step="pr_creation",
        ),
        WorkflowStep(
            step_id="pr_creation",
            task_type=TaskType.REVIEW,
            priority=TaskPriority.P0_CRITICAL,
            title_template="Security fix PR",
            description_template="Create PR for security fixes.",
            required_capabilities=["git", "coding"],
            next_step="ci_validation",
        ),
        WorkflowStep(
            step_id="ci_validation",
            task_type=TaskType.CI_FIX,
            priority=TaskPriority.P0_CRITICAL,
            title_template="Validate CI after security fix",
            description_template="Validate CI after security fix.",
            required_capabilities=["ci", "devops"],
            next_step="merge",
        ),
        WorkflowStep(
            step_id="merge",
            task_type=TaskType.MERGE,
            priority=TaskPriority.P0_CRITICAL,
            title_template="Merge security fix PR",
            description_template="Merge security fix PR.",
            required_capabilities=["git", "merge"],
            next_step=None,
        ),
    ]
    WORKFLOWS["security_chain"] = Workflow(
        workflow_id="security_chain",
        name="Security Fix Chain",
        description="Security scan → fix → PR → CI → merge workflow",
        steps=security_steps,
        trigger_conditions=["security_finding", "manual"],
        exit_conditions=["all_steps_complete", "critical_failure"],
    )
    ci_fix_steps = [
        WorkflowStep(
            step_id="ci_diagnosis",
            task_type=TaskType.CI_FIX,
            priority=TaskPriority.P1_HIGH,
            title_template="Diagnose CI failure: {workflow}",
            description_template="Diagnose CI failure in {workflow}.",
            required_capabilities=["ci", "devops", "coding"],
            next_step="ci_fix",
        ),
        WorkflowStep(
            step_id="ci_fix",
            task_type=TaskType.CI_FIX,
            priority=TaskPriority.P1_HIGH,
            title_template="Fix CI: {workflow}",
            description_template="Fix CI failure in {workflow}.",
            required_capabilities=["ci", "coding"],
            next_step="pr_creation",
        ),
        WorkflowStep(
            step_id="pr_creation",
            task_type=TaskType.REVIEW,
            priority=TaskPriority.P1_HIGH,
            title_template="CI fix PR",
            description_template="Create PR for CI fix.",
            required_capabilities=["git", "coding"],
            next_step="ci_validation",
        ),
        WorkflowStep(
            step_id="ci_validation",
            task_type=TaskType.CI_FIX,
            priority=TaskPriority.P1_HIGH,
            title_template="Validate CI after fix",
            description_template="Validate CI after fix.",
            required_capabilities=["ci", "devops"],
            next_step="merge",
        ),
        WorkflowStep(
            step_id="merge",
            task_type=TaskType.MERGE,
            priority=TaskPriority.P1_HIGH,
            title_template="Merge CI fix PR",
            description_template="Merge CI fix PR.",
            required_capabilities=["git", "merge"],
            next_step=None,
        ),
    ]
    WORKFLOWS["ci_fix_chain"] = Workflow(
        workflow_id="ci_fix_chain",
        name="CI Fix Chain",
        description="CI failure → diagnose → fix → PR → CI → merge workflow",
        steps=ci_fix_steps,
        trigger_conditions=["ci_failure", "manual"],
        exit_conditions=["all_steps_complete", "ci_passing"],
    )


def get_workflow(workflow_id: str) -> Workflow | None:
    if not WORKFLOWS:
        _register_workflows()
    return WORKFLOWS.get(workflow_id)


def get_next_workflow_step(workflow: Workflow, current_step_id: str | None) -> WorkflowStep | None:
    if not WORKFLOWS:
        _register_workflows()
    step_map = {s.step_id: s for s in workflow.steps}
    if not current_step_id:
        return workflow.steps[0] if workflow.steps else None
    current_step = step_map.get(current_step_id)
    if not current_step or not current_step.next_step:
        return None
    return step_map.get(current_step.next_step)


def create_workflow_task(
    workflow: Workflow,
    step: WorkflowStep,
    group_name: str = "",
    metadata: dict[str, Any] | None = None,
) -> Task:
    title = step.title_template
    description = step.description_template
    if metadata:
        for key, value in metadata.items():
            placeholder = f"{{{key}}}"
            title = title.replace(placeholder, str(value))
            description = description.replace(placeholder, str(value))
    return create_task(
        task_id=f"task-{workflow.workflow_id}-{step.step_id}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        task_type=step.task_type,
        priority=step.priority,
        title=title,
        description=description,
        group_name=group_name,
        capabilities_required=step.required_capabilities,
        metadata={
            "workflow_id": workflow.workflow_id,
            "step_id": step.step_id,
            "next_step": step.next_step,
            "source": "workflow_orchestrator",
        },
    )


def advance_workflow(workflow: Workflow, current_step_id: str | None, group_name: str = "", metadata: dict[str, Any] | None = None) -> Task | None:
    next_step = get_next_workflow_step(workflow, current_step_id)
    if not next_step:
        return None
    return create_workflow_task(workflow, next_step, group_name=group_name, metadata=metadata)


def execute_workflow_step(workflow: Workflow, step: WorkflowStep, group_name: str = "", metadata: dict[str, Any] | None = None) -> Task:
    task = create_workflow_task(workflow, step, group_name=group_name, metadata=metadata)
    print(f"🔧 Workflow '{workflow.name}' step '{step.step_id}': {task.title}")
    return task


def main() -> int:
    parser = argparse.ArgumentParser(description="Workflow Orchestrator (#2573)")
    parser.add_argument("--workflow", help="Workflow ID to execute")
    parser.add_argument("--list", action="store_true", help="List available workflows")
    parser.add_argument("--step", help="Specific step to execute")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()
    
    if not WORKFLOWS:
        _register_workflows()
    
    if args.list:
        if args.format == "json":
            print(json.dumps({k: {"name": v.name, "description": v.description, "steps": len(v.steps)} for k, v in WORKFLOWS.items()}, indent=2))
        else:
            print("📋 Available workflows:")
            for wf_id, wf in WORKFLOWS.items():
                print(f"   {wf_id}: {wf.name} ({len(wf.steps)} steps)")
        return 0
    
    if args.workflow:
        workflow = WORKFLOWS.get(args.workflow)
        if not workflow:
            print(f"❌ Workflow '{args.workflow}' not found.", file=sys.stderr)
            return 1
        if args.step:
            step = next((s for s in workflow.steps if s.step_id == args.step), None)
            if not step:
                print(f"❌ Step '{args.step}' not found in workflow '{args.workflow}'.", file=sys.stderr)
                return 1
            task = execute_workflow_step(workflow, step)
            print(json.dumps(task.to_dict(), indent=2))
        else:
            print(f"🔧 Workflow '{workflow.name}': {workflow.description}")
            for i, step in enumerate(workflow.steps, 1):
                print(f"   {i}. {step.step_id}: {step.title_template}")
        return 0
    
    print("✅ Workflow orchestrator ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
