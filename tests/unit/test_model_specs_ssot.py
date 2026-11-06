# tests/unit/test_model_specs_ssot.py
# বাংলা মন্তব্য: Issue #133-এর জন্য ModelSpec SSOT ভেরিফিকেশন টেস্ট

import pytest
from core.llm.model_specs import (
    MODEL_SPECS_CATALOG,
    FREE_TIER_MODELS_SET,
    get_model_spec,
    is_model_retired,
)


def test_model_specs_catalog_completeness():
    assert len(MODEL_SPECS_CATALOG) >= 5
    for model_id, spec in MODEL_SPECS_CATALOG.items():
        assert spec.model_id == model_id
        assert spec.provider in {"anthropic", "openai", "gemini", "deepseek", "groq", "alibaba"}
        assert spec.tier in {1, 2, 3}
        assert spec.context_length > 0


def test_get_model_spec():
    gemini_spec = get_model_spec("gemini-2.0-flash")
    assert gemini_spec is not None
    assert gemini_spec.provider == "gemini"
    assert gemini_spec.is_free_tier is True
    assert "speed" in gemini_spec.strengths

    unknown_spec = get_model_spec("non-existent-model-xyz")
    assert unknown_spec is None


def test_retired_and_free_tier_sets():
    assert "gemini-2.0-flash" in FREE_TIER_MODELS_SET
    assert is_model_retired("gemini-2.0-flash") is False
