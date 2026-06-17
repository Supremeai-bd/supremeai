from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from tools.cot_reasoner import ChainOfThoughtReasoner
from memory.long_term_memory import LongTermMemory


class ReasoningOrchestrator:
    def __init__(
        self,
        long_term_memory: Optional[LongTermMemory] = None,
        cot_reasoner: Optional[ChainOfThoughtReasoner] = None,
    ) -> None:
        self.long_term_memory = long_term_memory or LongTermMemory()
        self.cot_reasoner = cot_reasoner or ChainOfThoughtReasoner(max_iterations=2)

    def plan(self, task_description: str, context: Optional[str] = None) -> Dict[str, Any]:
        lowered = (task_description or "").lower()
        is_simple = any(word in lowered for word in ["hello", "hi", "status", "health"])
        is_reasoning = any(
            word in lowered
            for word in ["prove", "proof", "math", "logic", "analyze", "plan", "reason"]
        )
        if is_simple:
            return {
                "mode": "direct",
                "complexity": "simple",
                "reason": "Greeting or status-like request",
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
        parts = [task_description]
        if memory_context:
            parts.append(f"Memory context:\n{memory_context}")
        if plan["mode"] == "cot":
            return self.cot_reasoner.build_prompt("\n\n".join(parts), context)
        return "\n\n".join(parts)

    def route(self, task_description: str, context: Optional[str] = None) -> Dict[str, Any]:
        plan = self.plan(task_description, context)
        logger.info(f"Reasoning plan: {plan}")
        if plan["mode"] == "cot":
            return {
                "use_cot": True,
                "plan": plan,
                "prompt": self.build_enriched_prompt(task_description, context),
            }
        return {
            "use_cot": False,
            "plan": plan,
            "prompt": self.build_enriched_prompt(task_description, context),
        }
