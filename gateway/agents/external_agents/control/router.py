"""
backend/external_agents/control/router.py
=========================================
ISSUE-1573 (Part 4): the Parallel Planner & Architect Router.

Given a ``TaskContract`` the router:
  1. picks the delivery channel per provider through the Policy Engine —
     native MCP for ZCode, policy-checked browser channel for ChatGPT/Gemini;
  2. dispatches the Planner (ChatGPT) and the Architect (Gemini)
     CONCURRENTLY (asyncio.gather);
  3. synthesizes both outputs into a unified :class:`ImplementationBrief`
     the Coder agent executes.

Policy-blocked dispatches fail CLOSED — the router never fabricates a brief.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from external_agents.contracts.architecture_artifact import ArchitectureArtifact
from external_agents.contracts.planner_artifact import PlannerArtifact
from external_agents.contracts.task_contract import AgentProvider, TaskContract
from external_agents.control.policy_engine import (
    PolicyDecision,
    PolicyEngine,
    PolicyVerdict,
)
from external_agents.providers.chatgpt import ChatGPTProvider
from external_agents.providers.gemini import GeminiProvider
from external_agents.providers.registry import ExecutionMode, ProviderRegistry

__all__ = ["ImplementationBrief", "PlannerArchitectRouter", "RouteOutcome"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ImplementationBrief(BaseModel):
    """The unified, coder-ready synthesis of planner + architect outputs."""

    task_id: str
    goal: str
    plan: PlannerArtifact
    architecture: ArchitectureArtifact | None = None
    coder_constraints: dict[str, Any] = Field(default_factory=dict)
    target_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    planner_provider: str | None = None
    architect_provider: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def actionable(self) -> bool:
        return self.architecture is None or self.architecture.is_actionable


class RouteOutcome(BaseModel):
    brief: ImplementationBrief | None = None
    policy_verdicts: dict[str, PolicyVerdict] = Field(default_factory=dict)
    elapsed_ms: float = 0.0
    errors: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.brief is not None and not self.errors


class PlannerArchitectRouter:
    """Concurrency-preserving planner/architect dispatcher with policy gates."""

    PLANNER_PROVIDER = AgentProvider.CHATGPT
    ARCHITECT_PROVIDER = AgentProvider.GEMINI

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        policy_engine: PolicyEngine | None = None,
        planner: ChatGPTProvider | None = None,
        architect: GeminiProvider | None = None,
    ) -> None:
        self.registry = registry or ProviderRegistry()
        self.policy_engine = policy_engine or PolicyEngine(self.registry)
        self.planner = planner or ChatGPTProvider()
        self.architect = architect or GeminiProvider()

    # ------------------------------------------------------------------
    # Channel selection (issue acceptance: native MCP for ZCode, browser
    # channel for ChatGPT/Gemini) — always policy-evaluated first.
    # ------------------------------------------------------------------
    def select_channel(
        self, provider: AgentProvider, task: TaskContract | None = None
    ) -> PolicyVerdict:
        mode = self.registry.preferred_mode(provider)
        return self.policy_engine.evaluate(provider.value, mode, task)

    def plan_architect_channels(self, task: TaskContract) -> tuple[PolicyVerdict, PolicyVerdict]:
        return (
            self.select_channel(self.PLANNER_PROVIDER, task),
            self.select_channel(self.ARCHITECT_PROVIDER, task),
        )

    # ------------------------------------------------------------------
    async def route(self, task: TaskContract) -> RouteOutcome:
        started = time.monotonic()
        planner_verdict, architect_verdict = self.plan_architect_channels(task)
        verdicts = {
            self.PLANNER_PROVIDER.value: planner_verdict,
            self.ARCHITECT_PROVIDER.value: architect_verdict,
        }
        errors: list[str] = []

        # Fail-closed: any blocked channel aborts BEFORE dispatch.
        for name, verdict in verdicts.items():
            if verdict.decision is PolicyDecision.POLICY_BLOCKED:
                return RouteOutcome(
                    policy_verdicts=verdicts,
                    elapsed_ms=(time.monotonic() - started) * 1000,
                    errors=[f"{name}: {verdict.reason}"],
                )
            if verdict.decision is PolicyDecision.HITL_REQUIRED:
                errors.append(f"{name}: {verdict.reason} (status=HITL_REQUIRED)")

        if errors and all("HITL_REQUIRED" in e for e in errors):
            # Both channels demand human approval — no dispatch at all.
            return RouteOutcome(
                policy_verdicts=verdicts,
                elapsed_ms=(time.monotonic() - started) * 1000,
                errors=errors,
            )

        # Parallel dispatch — planner and architect run CONCURRENTLY.
        # (Concurrent dispatch is the issue's explicit acceptance criterion,
        # so the architect reviews the TASK itself; synthesis merges both.)
        planner_placeholder = PlannerArtifact(
            task_id=task.task_id,
            summary="concurrent dispatch — architect reviews the task, not a finished plan",
        )
        plan, architecture = await asyncio.gather(
            self.planner.plan(task),
            self.architect.review(task, planner_placeholder),
            return_exceptions=True,
        )

        for label, res in (("planner", plan), ("architect", architecture)):
            if isinstance(res, BaseException):
                errors.append(f"{label} failed: {res}")

        brief = (
            self.synthesize(task, plan, architecture)
            if not isinstance(plan, BaseException)
            else None
        )

        return RouteOutcome(
            brief=brief,
            policy_verdicts=verdicts,
            elapsed_ms=(time.monotonic() - started) * 1000,
            errors=errors,
        )

    # ------------------------------------------------------------------
    def synthesize(
        self,
        task: TaskContract,
        plan: PlannerArtifact,
        architecture: ArchitectureArtifact | BaseException | None,
    ) -> ImplementationBrief:
        """Merge planner + architect outputs into the coder's brief."""
        arch = architecture if isinstance(architecture, ArchitectureArtifact) else None
        warnings: list[str] = []
        if isinstance(architecture, BaseException):
            warnings.append(f"architect unavailable — proceeding without review: {architecture}")
        if arch is not None and not arch.is_actionable:
            warnings.append(
                f"architecture review is blocking (verdict={arch.verdict}, "
                f"required_changes={len(arch.required_changes)})"
            )

        coder_constraints = dict(task.constraints)
        target_files = plan.step_targets()
        if arch is not None:
            coder_constraints["required_changes"] = list(arch.required_changes)
            coder_constraints["architecture_verdict"] = arch.verdict
        if not target_files:
            warnings.append("planner produced no explicit target files")

        return ImplementationBrief(
            task_id=task.task_id,
            goal=task.goal,
            plan=plan,
            architecture=arch,
            coder_constraints=coder_constraints,
            target_files=target_files,
            warnings=warnings,
            planner_provider=plan.provider,
            architect_provider=arch.provider if arch else None,
        )
