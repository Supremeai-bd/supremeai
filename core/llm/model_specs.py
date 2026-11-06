# backend/core/llm/model_specs.py
# বাংলা মন্তব্য: LLM Model & Provider Specifications — The Single Source of Truth (SSOT)
# Issue #133: ১২টি মডিউলে ছড়িয়ে থাকা মডেল এবং প্রোভাইডার কনস্ট্যান্টগুলোকে একক ক্যাটালগে একীভূতকরণ।
# প্রতিটি মডেলের আইডি, প্রোভাইডার, ক্ষমতা (capabilities), রেটিং/র‍্যাংক এবং রিটায়ারমেন্ট স্ট্যাটাস এখানে ডিফাইন করা।

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    """Canonical model specification record."""
    model_id: str
    provider: str
    tier: int
    context_length: int
    cost_input_per_million: float = 0.0
    cost_output_per_million: float = 0.0
    openrouter_id: str | None = None
    strengths: tuple[str, ...] = field(default_factory=tuple)
    is_retired: bool = False
    is_free_tier: bool = False


# বাংলা মন্তব্য: একক মডেল ক্যাটালগ (Canonical Catalog)
MODEL_SPECS_CATALOG: dict[str, ModelSpec] = {
    # Frontier Models (Tier 1)
    "claude-opus-4.7": ModelSpec(
        model_id="claude-opus-4.7",
        provider="anthropic",
        tier=1,
        context_length=200000,
        cost_input_per_million=15.00,
        cost_output_per_million=75.00,
        openrouter_id="anthropic/claude-3-opus",
        strengths=("complex coding", "agentic workflows", "deep reasoning"),
    ),
    "gpt-5.5": ModelSpec(
        model_id="gpt-5.5",
        provider="openai",
        tier=1,
        context_length=128000,
        cost_input_per_million=5.00,
        cost_output_per_million=15.00,
        openrouter_id="openai/gpt-4o",
        strengths=("general intelligence", "low hallucination", "structured output"),
    ),
    "gemini-2.5-pro": ModelSpec(
        model_id="gemini-2.5-pro",
        provider="gemini",
        tier=1,
        context_length=1000000,
        cost_input_per_million=1.25,
        cost_output_per_million=5.00,
        openrouter_id="google/gemini-pro-1.5",
        strengths=("long context", "multimodal", "fast reasoning"),
        is_free_tier=True,
    ),
    "deepseek-r1": ModelSpec(
        model_id="deepseek-r1",
        provider="deepseek",
        tier=1,
        context_length=64000,
        cost_input_per_million=0.55,
        cost_output_per_million=2.19,
        openrouter_id="deepseek/deepseek-r1",
        strengths=("math", "reasoning", "code synthesis"),
    ),
    # Workhorse & Free-Tier Models (Tier 2 & 3)
    "gemini-2.0-flash": ModelSpec(
        model_id="gemini-2.0-flash",
        provider="gemini",
        tier=2,
        context_length=1000000,
        cost_input_per_million=0.10,
        cost_output_per_million=0.40,
        openrouter_id="google/gemini-2.0-flash-exp:free",
        strengths=("speed", "cost efficiency", "tool calling"),
        is_free_tier=True,
    ),
    "llama-3.3-70b-versatile": ModelSpec(
        model_id="llama-3.3-70b-versatile",
        provider="groq",
        tier=2,
        context_length=128000,
        cost_input_per_million=0.59,
        cost_output_per_million=0.79,
        strengths=("ultra fast inference", "general reasoning"),
        is_free_tier=True,
    ),
    "deepseek-chat": ModelSpec(
        model_id="deepseek-chat",
        provider="deepseek",
        tier=2,
        context_length=64000,
        cost_input_per_million=0.14,
        cost_output_per_million=0.28,
        openrouter_id="deepseek/deepseek-chat",
        strengths=("code generation", "general chat"),
    ),
}

# Derived Views & Helper Mappings
RETIRED_MODELS_SET: set[str] = {
    model_id for model_id, spec in MODEL_SPECS_CATALOG.items() if spec.is_retired
}

FREE_TIER_MODELS_SET: set[str] = {
    model_id for model_id, spec in MODEL_SPECS_CATALOG.items() if spec.is_free_tier
}


def get_model_spec(model_id: str) -> ModelSpec | None:
    """Retrieve canonical ModelSpec by model ID."""
    return MODEL_SPECS_CATALOG.get(model_id)


def is_model_retired(model_id: str) -> bool:
    """Check if model is retired in the SSOT catalog."""
    spec = MODEL_SPECS_CATALOG.get(model_id)
    return spec.is_retired if spec else False
