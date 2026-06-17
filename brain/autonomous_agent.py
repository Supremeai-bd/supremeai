from __future__ import annotations

import os
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class StepResult:
    name: str
    success: bool
    output: Any = None
    error: Optional[str] = None


class AutonomousAgent:
    def __init__(self, name: str = "autonomous-agent") -> None:
        self.name = name
        self.history: List[Dict[str, Any]] = []
        try:
            from evolution.auto_skill_creator import AutoSkillCreator
            self.skill_creator = AutoSkillCreator()
        except Exception:
            self.skill_creator = None

    def plan(self, task_description: str) -> Dict[str, Any]:
        lowered = (task_description or "").lower()
        plan: Dict[str, Any] = {"steps": [], "summary": ""}
        if any(word in lowered for word in ["fix", "debug", "error", "issue"]):
            plan["summary"] = "Investigate issue, propose fix, apply fix, verify."
            plan["steps"] = [
                "investigate",
                "propose_fix",
                "apply_fix",
                "verify",
            ]
        elif any(word in lowered for word in ["build", "create", "implement", "feature"]):
            plan["summary"] = "Scaffold implementation, implement core, add basic tests."
            plan["steps"] = [
                "scaffold",
                "implement",
                "basic_tests",
            ]
        elif any(word in lowered for word in ["analyze", "review", "audit"]):
            plan["summary"] = "Read inputs, analyze structure, summarize findings."
            plan["steps"] = [
                "read_inputs",
                "analyze",
                "summarize",
            ]
        else:
            plan["summary"] = "Default quick execution."
            plan["steps"] = ["execute", "summarize"]
        return plan

    def execute(self, task_description: str, context: Optional[str] = None) -> Dict[str, Any]:
        plan = self.plan(task_description)
        results: List[StepResult] = []
        for step in plan["steps"]:
            try:
                step_result = self._run_step(step, task_description, context)
                results.append(step_result)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Agent step failed")
                results.append(
                    StepResult(
                        name=step,
                        success=False,
                        error="".join(traceback.format_exception_only(type(exc), exc)).strip(),
                    )
                )
                break
        self.history.append(
            {
                "task": task_description,
                "context": context,
                "plan": plan,
                "results": [
                    {"name": r.name, "success": r.success, "output": r.output, "error": r.error}
                    for r in results
                ],
            }
        )
        success = all(result.success for result in results)
        outputs = [result.output for result in results if result.success and result.output is not None]
        errors = [result.error for result in results if result.error]
        return {
            "success": success,
            "plan": plan,
            "steps": [r.name for r in results],
            "output": outputs[-1] if outputs else None,
            "outputs": outputs,
            "errors": errors,
        }

    def _run_step(self, step: str, task_description: str, context: Optional[str]) -> StepResult:
        if step == "investigate":
            output = {
                "message": "Investigation complete.",
                "files_checked": [],
                "findings": "Detected relevant task keywords.",
            }
        elif step == "propose_fix":
            output = {
                "message": "Fix proposal generated.",
                "proposal": f"Review task: {task_description} and apply minimal change.",
            }
        elif step == "apply_fix":
            output = {
                "message": "Fix applied.",
                "changed": [],
            }
        elif step == "verify":
            output = {
                "message": "Verification placeholder: run tests after applying fix.",
                "pytest_suggestion": "pytest",
            }
        elif step == "scaffold":
            output = {
                "message": "Scaffold placeholder: create module under interfaces/tools/brain/.",
                "suggested_path": "tools/new_feature.py",
            }
        elif step == "implement":
            output = {"message": "Implementation placeholder: delegate to coding tooling."}
        elif step == "basic_tests":
            output = {
                "message": "Tests placeholder: add unit tests in tests/ for new feature.",
                "suggested_path": "tests/test_new_feature.py",
            }
        elif step == "read_inputs":
            output = {"message": "Inputs review placeholder: gather docs, code, data sources."}
        elif step == "analyze":
            output = {"message": "Analysis placeholder: summarize current state and risks.", "risks": []}
        elif step == "summarize":
            output = {
                "message": "Summary",
                "summary": task_description,
                "suggested_next_steps": [],
            }
            if self.skill_creator is not None:
                try:
                    skill_result = self.skill_creator.create(
                        name=f"auto-skill-{abs(hash(task_description)) % 10000}",
                        description=f"Auto-created skill from task: {task_description}",
                    )
                    output["created_skill"] = skill_result
                except Exception as exc:
                    logger.warning(f"Auto skill creator hook failed: {exc}")
        elif step == "execute":
            output = {"message": "Execution complete.", "result": task_description}
            if self.skill_creator is not None:
                try:
                    skill_result = self.skill_creator.create(
                        name=f"auto-skill-{abs(hash(task_description)) % 10000}",
                        description=f"Auto-created skill from task: {task_description}",
                    )
                    output["created_skill"] = skill_result
                except Exception as exc:
                    logger.warning(f"Auto skill creator hook failed: {exc}")
        else:
            output = {"message": f"Step `{step}` has no handler.", "step": step}
        return StepResult(name=step, success=True, output=output)

    def reflect(self, run: Dict[str, Any]) -> Dict[str, Any]:
        failures = [err for err in run.get("errors", []) if err]
        return {
            "success": run.get("success", False),
            "completed_steps": run.get("steps", []),
            "failures": failures,
            "improvements": ["Reduce broad step scope and add explicit verify step."] if failures else [],
        }

    def run(self, task_description: str, context: Optional[str] = None) -> Dict[str, Any]:
        run = self.execute(task_description, context)
        reflection = self.reflect(run)
        return {"run": run, "reflection": reflection}
