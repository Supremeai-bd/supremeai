from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from tools.cot_reasoner import ChainOfThoughtReasoner
from memory.long_term_memory import LongTermMemory
from memory.episodic_memory import EpisodicMemory


class ReasoningOrchestrator:
    def __init__(
        self,
        long_term_memory: Optional[LongTermMemory] = None,
        cot_reasoner: Optional[ChainOfThoughtReasoner] = None,
        episodic_memory: Optional[EpisodicMemory] = None,
    ) -> None:
        self.long_term_memory = long_term_memory or LongTermMemory()
        self.cot_reasoner = cot_reasoner or ChainOfThoughtReasoner(max_iterations=2)
        self.episodic_memory = episodic_memory or EpisodicMemory()

    def plan(self, task_description: str, context: Optional[str] = None) -> Dict[str, Any]:
        lowered = (task_description or "").lower()
        words = lowered.split()
        is_simple = len(words) <= 2 and any(w in {"hello", "hi", "hey", "status", "health"} for w in words)
        is_reasoning = any(
            word in lowered
            for word in ["prove", "proof", "math", "logic", "analyze", "plan", "reason", "optimize"]
        )
        is_advanced_reasoning = any(
            word in lowered
            for word in ["tree", "mcts", "monte carlo", "multi-step", "strategy", "tradeoff"]
        )
        if is_simple:
            return {
                "mode": "direct",
                "complexity": "simple",
                "reason": "Greeting or status-like request",
            }
        if is_advanced_reasoning:
            return {
                "mode": "tot_mcts",
                "complexity": "complex",
                "reason": "Detected advanced reasoning keywords",
            }
        if is_reasoning:
            return {
                "mode": "cot",
                "complexity": "complex",
                "reason": "Detected reasoning keywords",
            }
        return {
            "mode": "standard",
            "complexity": "medium",
            "reason": "Default task routing",
        }

    def build_enriched_prompt(self, task_description: str, context: Optional[str] = None) -> str:
        plan = self.plan(task_description, context)
        memory_context = self.long_term_memory.build_context()
        episodic_context = self.episodic_memory.summarize_recent(limit=3)
        parts = [task_description]
        if memory_context:
            parts.append(f"Memory context:\n{memory_context}")
        if episodic_context:
            parts.append(f"Recent interaction memory:\n{episodic_context}")
        if plan["mode"] in {"cot", "tot_mcts"}:
            return self.cot_reasoner.build_prompt("\n\n".join(parts), context)
        return "\n\n".join(parts)

    def route(self, task_description: str, context: Optional[str] = None) -> Dict[str, Any]:
        plan = self.plan(task_description, context)
        logger.info(f"Reasoning plan: {plan}")
        reasoning_trace = None
        if plan["mode"] in {"cot", "tot_mcts"}:
            reasoning_trace = self.cot_reasoner.tree_search(
                problem=task_description,
                branches=3,
                depth=2,
                context=context,
            )
            if plan["mode"] == "tot_mcts":
                reasoning_trace["mcts"] = self.cot_reasoner.monte_carlo_search(
                    problem=task_description,
                    branches=3,
                    depth=3,
                    simulations=8,
                    context=context,
                )
        return {
            "use_cot": plan["mode"] in {"cot", "tot_mcts"},
            "plan": plan,
            "prompt": self.build_enriched_prompt(task_description, context),
            "reasoning_trace": reasoning_trace,
        }
