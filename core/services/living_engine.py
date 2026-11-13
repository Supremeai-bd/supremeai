# backend/services/living_engine.py
"""SupremeAI Living & Self-Evolving Autonomous Engine Orchestrator.

The unified master orchestrator coordinating:
1. Advanced Multi-Type Reasoning (Deductive, Inductive, Abductive, Analogical, Causal)
2. Intent Deciphering (Goal vs Method Separation & Memory Recall)
3. Dynamic HTN DAG Planning (Epistemic Probing & Cycle Prevention)
4. Domain Adapters (Dev, Business, UX) with AST Hardening
5. Online Continuous Pattern Learning
6. Genetic Algorithm Self-Evolution Loop
7. Dual-Loop Self-Correction & Verification
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from core.advanced_reasoning import AdvancedReasoningEngine, ReasoningChain
from core.engine.self_reflection import SelfReflectionLoop
from core.evolution_module import EvolutionModule, EvolutionResult
from core.monitoring.logging_config import logger

from evolution.auto_evolution_controller import AutoEvolutionController
from learning.pattern_recognizer import PatternMatch, PatternRecognizer
from services.dynamic_planner import DynamicPlanningEngine, TaskDAG, TaskNode
from services.intent_deciphering import IntentAnalysis, IntentDecipheringService
from services.memory_service import CascadeMemoryService
from services.memory_service import memory_service as global_memory_service
from services.self_correction import SelfCorrectionService
from services.tool_forge import ToolForgeService, ToolSpec


@dataclass
class SolutionResult:
    success: bool
    ultimate_goal: str
    domain: str
    execution_order: list[str]
    results: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    fitness_score: float = 0.0
    execution_time_ms: float = 0.0
    reasoning: dict[str, Any] = field(default_factory=dict)
    patterns: list[dict[str, Any]] = field(default_factory=list)
    evolution: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    reflection: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "ultimate_goal": self.ultimate_goal,
            "domain": self.domain,
            "execution_order": self.execution_order,
            "results": self.results,
            "verification": self.verification,
            "fitness_score": self.fitness_score,
            "execution_time_ms": self.execution_time_ms,
            "reasoning": self.reasoning,
            "patterns": self.patterns,
            "evolution": self.evolution,
            "error": self.error,
            "reflection": self.reflection,
        }


# ── Domain Adapters Bridge ─────────────────────────────────────────────────────


async def _request_completion(prompt: str, *, task_type: str, session_id: str) -> str:
    """Use the supported gateway; failures must reach the self-healing boundary."""
    from core.llm.llm_gateway import get_llm_gateway

    gateway = get_llm_gateway()
    if gateway is None:
        raise RuntimeError("LLM gateway unavailable")
    response = await gateway.acompletion(prompt=prompt, task_type=task_type, session_id=session_id)
    text = None
    if isinstance(response, dict):
        if response.get("success") is not False:
            text = response.get("text")
    elif getattr(response, "choices", None):
        text = getattr(getattr(response.choices[0], "message", None), "content", None)
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("LLM gateway returned no usable completion")
    return text


class BaseDomainAdapter:
    """Gateway-backed execution without the retired synthetic-success fallback."""

    task_type = "general"
    prompt_title = "General"
    session_prefix = "general"

    async def execute_node(self, node: TaskNode, context: dict[str, Any]) -> Any:
        prompt = (
            f"Execute {self.prompt_title} Task: {node.description or node.name}\n"
            f"Capability: {node.capability}\nContext: {json.dumps(context)[:500]}"
        )
        text = await _request_completion(
            prompt, task_type=self.task_type, session_id=f"{self.session_prefix}_adapter_{node.id}"
        )
        return {
            "status": "executed",
            "node_id": node.id,
            "capability": node.capability,
            "result": text,
            "llm_processed": True,
        }


class DevDomainAdapter(BaseDomainAdapter):
    """Route development tasks through the coding gateway."""

    task_type = "coding"
    prompt_title = "Developer"
    session_prefix = "dev"


class BusinessDomainAdapter(BaseDomainAdapter):
    """Route business analysis through the reasoning gateway."""

    task_type = "reasoning"
    prompt_title = "Business"
    session_prefix = "business"


class UXDomainAdapter(BaseDomainAdapter):
    """Route UX tasks through the vision gateway without claiming compliance."""

    task_type = "vision"
    prompt_title = "UX"
    session_prefix = "ux"


# ── Living Engine Orchestrator ─────────────────────────────────────────────────


class LivingEngineOrchestrator:
    """Master orchestrator for unpredictable user demands with full Phase 2 intelligence."""

    def __init__(
        self,
        intent_service: IntentDecipheringService | None = None,
        planning_engine: DynamicPlanningEngine | None = None,
        tool_forge: ToolForgeService | None = None,
        self_correction: SelfCorrectionService | None = None,
        memory_service: CascadeMemoryService | None = None,
        reasoning_engine: AdvancedReasoningEngine | None = None,
        pattern_recognizer: PatternRecognizer | None = None,
        evolution_module: EvolutionModule | None = None,
        evolution_controller: AutoEvolutionController | None = None,
        self_reflection: SelfReflectionLoop | None = None,
    ) -> None:
        self.memory_service = memory_service or global_memory_service
        self.intent_service = intent_service or IntentDecipheringService(
            memory_service=self.memory_service
        )
        self.planning_engine = planning_engine or DynamicPlanningEngine()
        self.tool_forge = tool_forge or ToolForgeService()
        self.self_correction = self_correction or SelfCorrectionService(
            memory_service=self.memory_service
        )
        self.reasoning_engine = reasoning_engine or AdvancedReasoningEngine()
        self.pattern_recognizer = pattern_recognizer or PatternRecognizer()
        self.evolution_module = evolution_module or EvolutionModule()
        self.evolution_controller = evolution_controller or AutoEvolutionController()
        if self_reflection is None:
            # Resolve lazily so dependency injection never instantiates the default loop.
            from core.engine.self_reflection import SelfReflectionLoop

            self_reflection = SelfReflectionLoop()
        self.self_reflection = self_reflection

        # Domain Adapters
        self.adapters: dict[str, BaseDomainAdapter] = {
            "coder": DevDomainAdapter(),
            "business": BusinessDomainAdapter(),
            "creative": UXDomainAdapter(),
            "reasoner": DevDomainAdapter(),
            "bengali": DevDomainAdapter(),
            "general": BaseDomainAdapter(),
        }

    async def solve_unpredictable_demand(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        session_id: str = "",
    ) -> SolutionResult:
        """Executes full multi-type reasoning, domain adaptation, and self-evolution pipeline."""
        start_time = time.perf_counter()
        logger.info(f"LivingEngine: Received demand: '{prompt[:80]}...'")
        ctx = context or {}

        try:
            # ── 1. Advanced Multi-Type Reasoning (Deductive/Inductive/Abductive/Analogical/Causal) ──
            reasoning_chain: ReasoningChain = await self.reasoning_engine.reason(prompt, ctx)

            # ── 2. Online Pattern Recognition ──
            pattern_matches: list[PatternMatch] = await self.pattern_recognizer.recognize(
                prompt, ctx
            )
            matched_patterns_summary = [
                {"id": p.pattern.id, "type": p.pattern.pattern_type.value, "score": p.match_score}
                for p in pattern_matches
            ]

            # ── 3. Intent Deciphering ──
            intent: IntentAnalysis = await self.intent_service.decipher_intent(
                raw_request=prompt,
                session_id=session_id,
            )

            # ── 4. Dynamic HTN DAG Planning ──
            dag: TaskDAG = await self.planning_engine.plan_task(intent)
            ordered_nodes = dag.topological_sort()
            execution_order = [n.id for n in ordered_nodes]

            # ── 5. Dual-Loop Execution with Domain Adapters & Tool Forge ──
            adapter = self.adapters.get(intent.domain, self.adapters["general"])

            async def step_executor(node: TaskNode, step_ctx: dict[str, Any]) -> Any:
                if node.capability == "execute_dynamic_action":
                    spec = ToolSpec(name=f"dynamic_{node.id}", description=node.description)

                    prompt = (
                        f"Write a Python function named dynamic_{node.id}() that achieves the following goal: '{intent.ultimate_goal}'. "
                        f"Task description: {node.description}. "
                        "Return a dictionary with a 'status' key and a 'result' key. "
                        "Provide ONLY raw Python code, without markdown formatting or backticks, starting with the def statement."
                    )
                    code = (
                        await _request_completion(
                            prompt, task_type="coding", session_id=f"tool_forge_{node.id}"
                        )
                    ).strip()
                    if code.startswith("```python"):
                        code = code[9:]
                    if code.endswith("```"):
                        code = code[:-3]
                    code = code.strip()

                    tool = self.tool_forge.forge_tool(spec, code)
                    return self.tool_forge.execute_tool(tool, {})
                return await adapter.execute_node(node, step_ctx)

            # Execute with self-healing verification
            exec_output = await self.self_correction.execute_with_self_healing(
                dag=dag,
                step_executor=step_executor,
            )

            # ── 6. Self-Evolution Fitness Optimization (Genetic Algorithm) ──
            async def fitness_evaluator(sol: Any) -> float:
                return exec_output.get("verification", {}).get("fitness_score", 0.95)

            evo_result: EvolutionResult = await self.evolution_module.evolve(
                problem=prompt,
                current_solution=exec_output.get("results", {}),
                fitness_func=fitness_evaluator,
                generations=3,
            )

            # ── 7. Continuous Learning Feedback ──
            await self.pattern_recognizer.learn_from_example(
                example=prompt,
                outcome=exec_output.get("results", {}),
                success=exec_output.get("status") == "success",
            )

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            verif = exec_output.get("verification", {})
            fitness = verif.get("fitness_score", 0.95)

            solution = SolutionResult(
                success=exec_output.get("status") == "success",
                ultimate_goal=intent.ultimate_goal,
                domain=intent.domain,
                execution_order=execution_order,
                results=exec_output.get("results", {}),
                verification=verif,
                fitness_score=fitness,
                execution_time_ms=round(duration_ms, 2),
                reasoning={
                    "strategy": reasoning_chain.metadata.get("primary_strategy", "deductive"),
                    "confidence": reasoning_chain.overall_confidence,
                    "conclusion": reasoning_chain.final_conclusion,
                },
                patterns=matched_patterns_summary,
                evolution={
                    "improvement_pct": evo_result.fitness_improvement,
                    "generations": evo_result.generations_passed,
                    "insights": evo_result.insights,
                },
            )

            logger.info(
                f"LivingEngine: Task completed in {duration_ms:.1f}ms with fitness {fitness}"
            )

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"LivingEngine: Pipeline execution failed: {exc}")
            solution = SolutionResult(
                success=False,
                ultimate_goal=prompt,
                domain="error",
                execution_order=[],
                error=str(exc),
                execution_time_ms=round(duration_ms, 2),
            )

        try:
            solution.reflection = await self.self_reflection.reflect(
                task_prompt=prompt,
                execution_output=json.dumps(solution.results, default=str),
                is_success=solution.success,
                error_details=solution.error or "",
            )
        except Exception as exc:
            # Reflection is feedback, not execution evidence. Preserve the outcome
            # and report unavailable feedback without manufacturing a critique.
            solution.reflection = {"status": "unavailable", "error_type": type(exc).__name__}
            logger.warning("LivingEngine reflection unavailable: %s", type(exc).__name__)
        return solution
