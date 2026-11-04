from __future__ import annotations

import re
from typing import Any

from brain.economic_optimizer import BudgetContext, EconomicOptimizer
from core.config import settings

COMPLEX_KEYWORDS = (
    "investigate",
    "evaluate",
    "tradeoff",
    "retries",
    "backpressure",
    "debug",
    "architecture",
    "benchmark",
    "root cause",
    "fix strategy",
    "strategy",
)


def classify_task_complexity(prompt: str) -> dict[str, Any]:
    text = (prompt or "").strip().lower()
    words = re.findall(r"\b\w+\b", text) if text else []

    found_keywords = [kw for kw in COMPLEX_KEYWORDS if kw in text]
    has_chaining = bool(re.search(r"\b(and then|after that)\b", text))

    score = len(found_keywords) + (2 if has_chaining else 0)

    is_complex = (
        score >= 2
        or any(k in text for k in ("investigate", "evaluate", "tradeoff", "root cause"))
        or has_chaining
    )

    if is_complex and text:
        complexity = "complex"
    elif any(w in text for w in ("translate", "explain")) and len(words) >= 3:
        complexity = "medium"
    else:
        complexity = "simple"

    return {
        "complexity": complexity,
        "score": score,
        "signals": {
            "keywords": found_keywords,
            "words": len(words),
            "chaining": has_chaining,
        },
    }


class CognitiveRouter:
    def __init__(self, economic_optimizer: EconomicOptimizer | None = None):
        self.economic_optimizer = economic_optimizer

    async def route(
        self, prompt: str, user_id: str, budget_context: BudgetContext | None = None
    ) -> dict[str, Any]:
        prompt_lower = (prompt or "").lower()

        # Simple heuristic to determine if decomposed
        if "analyze" in prompt_lower and "implement" in prompt_lower:
            return {
                "routing_mode": "decomposed",
                "task_graph": {
                    "task_count": 2,
                    "tasks": {
                        "task_1": {"type": "analysis", "provider": "google", "depends_on": []},
                        "task_2": {
                            "type": "implementation",
                            "provider": "groq",
                            "depends_on": ["task_1"],
                        },
                    },
                },
            }

        classification = classify_task_complexity(prompt)

        # Complex tasks route to react
        if classification["complexity"] == "complex":
            provider = "groq"
            model = "groq/llama-3.3-70b-versatile"
            if self.economic_optimizer and budget_context:
                decision = await self.economic_optimizer.optimize_route(
                    prompt, "general", budget_context
                )
                provider = decision.provider
                model = decision.model
            elif "/" in getattr(settings, "model_general", "groq/llama-3.3-70b-versatile"):
                provider, model = getattr(settings, "model_general", "groq/llama-3.3-70b-versatile").split("/", 1)

            return {
                "routing_mode": "react",
                "complexity": "complex",
                "execution": "reasoning_orchestrator.decide_and_execute",
                "max_iterations": 5,
                "provider": provider,
                "model": model,
                "reasoning_mode": "cot",
            }

        # Direct route
        if self.economic_optimizer and budget_context:
            decision = await self.economic_optimizer.optimize_route(
                prompt, "general", budget_context
            )
            return {
                "routing_mode": "direct",
                "provider": decision.provider,
                "model": decision.model,
            }

        default_model = getattr(settings, "model_general", "groq/llama-3.3-70b-versatile")
        if "/" in default_model:
            prov, mod = default_model.split("/", 1)
        else:
            prov, mod = "groq", default_model
        return {"routing_mode": "direct", "provider": prov, "model": mod}


_cognitive_router_instance: CognitiveRouter | None = None


def get_cognitive_router(economic_optimizer: EconomicOptimizer | None = None) -> CognitiveRouter:
    global _cognitive_router_instance
    if _cognitive_router_instance is None:
        _cognitive_router_instance = CognitiveRouter(economic_optimizer)
    return _cognitive_router_instance
