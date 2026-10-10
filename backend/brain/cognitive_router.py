# বাংলা মন্তব্য: Cognitive Router — main chat path-এর সিদ্ধান্ত-গ্রহণ কেন্দ্র।
# #2705: আগে শুধু substring-routing ("analyze"+"implement" → decomposed) + direct LLM
# ছিল — ReAct কোথাও ব্যবহৃত হতো না। এখন deterministic complexity-classifier যোগ হলো:
# complex টাস্ক (multi-step reasoning) → routing_mode="react" + production execution-hint
# (ReasoningOrchestrator.decide_and_execute)। simple Q&A → আগের মতো direct।
from typing import Any

from brain.economic_optimizer import BudgetContext, EconomicOptimizer
from core.config import settings
from core.logging_config import logger

# বাংলা মন্তব্য: ReAct-লুপ প্রার্থী হওয়ার deterministic সিগন্যাল-শব্দ (কোনো LLM খরচ নেই)।
_REACT_SIGNAL_KEYWORDS: tuple[str, ...] = (
    "plan",
    "design",
    "debug",
    "investigate",
    "research",
    "compare",
    "evaluate",
    "optimize",
    "optimise",
    "analyze",
    "analyse",
    "prove",
    "strategy",
    "tradeoff",
    "trade-off",
    "root cause",
    "refactor",
    "architect",
    "step-by-step",
    "multi-step",
    "why does",
    "how does",
    "what if",
)

# বাংলা মন্তব্য: সিগন্যাল-সংযোজক শব্দ — একাধিক ধাপ/স্তর নির্দেশ করে।
_CHAINING_CONNECTORS: tuple[str, ...] = (" and then ", " then ", "; after that ", " next, ")

# বাংলা মন্তব্য: simple Q&A guard — এই অভিপ্রায়ের ছোট বার্তা direct থাকবে।
_SIMPLE_INTENT_PREFIXES: tuple[str, ...] = (
    "hello",
    "hi",
    "hey",
    "summarize",
    "summarise",
    "thanks",
    "thank you",
    "status",
    "health",
    "ping",
)


def classify_task_complexity(prompt: str) -> dict[str, Any]:
    """বাংলা মন্তব্য: deterministic complexity classifier — ReAct লাগবে কি না সেই সিদ্ধান্ত।

    সিগন্যাল: (১) reasoning/multi-step কীওয়ার্ড, (২) শব্দ-সংখ্যা, (৩) ধাপ-সংযোজক,
    (৪) একাধিক বাক্য। ফলাফল সম্পূর্ণ deterministic — zero-cost (Rule #4 CostGuard)।
    """
    text = (prompt or "").strip()
    lowered = text.lower()
    words = lowered.split()
    word_count = len(words)

    matched_keywords = sorted({kw for kw in _REACT_SIGNAL_KEYWORDS if kw in lowered})
    chaining_hits = sum(1 for c in _CHAINING_CONNECTORS if c in lowered)
    sentence_count = sum(1 for s in ("?", "!", ". ") if s in lowered) or (1 if text else 0)

    # বাংলা মন্তব্য: scoring — কীওয়ার্ড ২ পয়েন্ট, চেইনিং ২, দীর্ঘতা/বাক্য ১ করে।
    score = 2 * len(matched_keywords) + 2 * chaining_hits
    if word_count > 25:
        score += 1
    if sentence_count >= 2:
        score += 1

    is_simple_intent = word_count <= 6 and lowered.startswith(_SIMPLE_INTENT_PREFIXES)

    # বাংলা মন্তব্য: simple Q&A guard সবার আগে — "summarize this" জাতীয় ছোট অনুরোধ direct।
    if is_simple_intent and not chaining_hits:
        return {
            "complexity": "simple",
            "score": score,
            "signals": {
                "keywords": matched_keywords,
                "chaining": chaining_hits,
                "words": word_count,
                "sentences": sentence_count,
            },
            "reason": "Simple Q&A intent — direct path",
        }

    if score >= 2:
        return {
            "complexity": "complex",
            "score": score,
            "signals": {
                "keywords": matched_keywords,
                "chaining": chaining_hits,
                "words": word_count,
                "sentences": sentence_count,
            },
            "reason": (
                f"Multi-step reasoning signals detected "
                f"(keywords={matched_keywords}, chaining={chaining_hits}, words={word_count})"
            ),
        }

    return {
        "complexity": "medium",
        "score": score,
        "signals": {
            "keywords": matched_keywords,
            "chaining": chaining_hits,
            "words": word_count,
            "sentences": sentence_count,
        },
        "reason": "Default task routing — direct path",
    }


class CognitiveRouter:
    def __init__(self, economic_optimizer: EconomicOptimizer = None):
        self.economic_optimizer = economic_optimizer

    async def route(
        self, prompt: str, user_id: str, budget_context: BudgetContext = None
    ) -> dict[str, Any]:
        # বাংলা মন্তব্য: (চুক্তি-সংরক্ষণ) decomposed চেক সবার আগে — বিদ্যমান
        # test_cognitive_router_contract চুক্তি অক্ষুণ্ণ থাকবে।
        if "analyze" in prompt.lower() and "implement" in prompt.lower():
            # Decompose
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

        # বাংলা মন্তব্য (#2705): deterministic complexity classification — complex
        # টাস্ক এখন ReAct লুপে যাবে (Thought → Tool → Observation), direct LLM-এ নয়।
        complexity = classify_task_complexity(prompt)

        # বাংলা মন্তব্য: provider/model resolution সব মোডে একই থাকবে (budget-aware)।
        provider, model = await self._resolve_provider_model(prompt, budget_context)

        if complexity["complexity"] == "complex":
            # বাংলা মন্তব্য: reasoning sub-mode — ReasoningOrchestrator-এর deterministic
            # plan() (cot/tot_mcts/standard) দিয়ে sub-hint; ব্যর্থ হলে graceful fallback।
            reasoning_mode = "standard"
            try:
                from brain.reasoning_orchestrator import ReasoningOrchestrator

                plan = ReasoningOrchestrator.get_instance().plan(prompt)
                reasoning_mode = plan.get("mode", "standard")
            except Exception as exc:
                logger.debug(f"ReAct plan sub-hint unavailable, fallback=standard: {exc}")

            return {
                "routing_mode": "react",
                "complexity": "complex",
                "reason": complexity["reason"],
                "complexity_score": complexity["score"],
                "reasoning_mode": reasoning_mode,
                "provider": provider,
                "model": model,
                # বাংলা মন্তব্য: production execution contract — chat path এই হিন্ট দিয়ে
                # ReasoningOrchestrator.decide_and_execute() (governed ReAct) চালাবে।
                "execution": "reasoning_orchestrator.decide_and_execute",
                "max_iterations": 3,
            }

        # Direct route
        return {"routing_mode": "direct", "provider": provider, "model": model}

    async def _resolve_provider_model(
        self, prompt: str, budget_context: BudgetContext = None
    ) -> tuple[str, str]:
        """বাংলা মন্তব্য: budget-aware provider/model resolution — direct ও react উভয়ের শেয়ার্ড পথ।"""
        if self.economic_optimizer and budget_context:
            decision = await self.economic_optimizer.optimize_route(
                prompt, "general", budget_context
            )
            return decision.provider, decision.model

        default_model = getattr(settings, "model_general", "groq/llama-3.3-70b-versatile")
        if "/" in default_model:
            prov, mod = default_model.split("/", 1)
        else:
            prov, mod = "groq", default_model
        return prov, mod


_cognitive_router_instance = None


def get_cognitive_router(economic_optimizer: EconomicOptimizer = None) -> CognitiveRouter:
    global _cognitive_router_instance
    if _cognitive_router_instance is None:
        _cognitive_router_instance = CognitiveRouter(economic_optimizer)
    return _cognitive_router_instance
