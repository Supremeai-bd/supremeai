# backend/brain/expert_router.py
"""
SupremeAI Mixture of Experts (MoE) Router — Facade Bridge to AdvancedModelRouter.
"""

from __future__ import annotations

from core.config import settings
from core.llm.advanced_model_router import (
    DomainExpertAnalyzer,
    ExpertType,
    get_advanced_router,
)


class SupremeMoERouter:
    """Backward-compatible facade bridging to core.llm.advanced_model_router."""

    # 2026-11-17 (#645 follow-up): every Groq id below is verified live on
    # Groq's /models. llama-3.3-70b-versatile, llama-3.1-8b-instant,
    # qwen-2.5-coder-32b and deepseek-r1-distill-llama-70b all 404/400 — routing
    # to them wasted a full attempt. Gateway uses separate operator approvals.
    EXPERT_MODEL_MAP: dict[ExpertType, list[str]] = {
        ExpertType.BENGALI: [
            "hf_space/supreme-hybrid-8b",
            "groq/openai/gpt-oss-20b",
            "gemini/gemini-2.5-flash",
        ],
        ExpertType.CODER: [
            "deepseek/deepseek-coder",
            "groq/qwen/qwen3.8-27b",
            "openai/gpt-4o",
        ],
        ExpertType.REASONER: [
            "deepseek/deepseek-chat",
            "groq/openai/gpt-oss-120b",
            "gemini/gemini-2.5-pro",
        ],
        ExpertType.CREATIVE: [
            "gemini/gemini-2.5-flash",
            "openai/gpt-4o",
            "groq/openai/gpt-oss-20b",
        ],
        ExpertType.GENERAL: [
            "gemini/gemini-2.5-flash",
            "groq/allam-2-7b",
            "openai/gpt-4o-mini",
        ],
    }

    def __init__(self):
        self.router = get_advanced_router()
        self.analyzer = DomainExpertAnalyzer()

    @classmethod
    def classify_prompt(cls, prompt: str) -> ExpertType:
        return DomainExpertAnalyzer.classify_domain(prompt)

    @classmethod
    def get_model_chain(cls, prompt: str) -> list[str]:
        expert = cls.classify_prompt(prompt)
        return cls.EXPERT_MODEL_MAP.get(expert, cls.EXPERT_MODEL_MAP[ExpertType.GENERAL])

    def route(self, prompt: str) -> tuple[str, list[str]]:
        models = self.get_model_chain(prompt)
        default_fallback = getattr(settings, "model_general", "groq/openai/gpt-oss-20b")
        primary = models[0] if models else default_fallback
        fallbacks = models[1:] if len(models) > 1 else []
        return primary, fallbacks
