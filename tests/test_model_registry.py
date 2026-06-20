import os

os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

import pytest


class TestModelRegistry:
    def test_get_model_returns_entry(self):
        from brain.model_registry import ModelRegistry
        m = ModelRegistry.get_model("deepseek-r1-free")
        assert m["tier"] == 5
        assert m["cost_input_per_million"] == 0.0

    def test_get_model_missing_returns_empty(self):
        from brain.model_registry import ModelRegistry
        m = ModelRegistry.get_model("nonexistent-model")
        assert m == {}

    def test_get_model_has_required_fields(self):
        from brain.model_registry import ModelRegistry
        m = ModelRegistry.get_model("gpt-5.5")
        for key in ["rank", "tier", "provider", "name", "openrouter_id", "context_length"]:
            assert key in m, f"missing key {key}"

    def test_get_by_tier_0(self):
        from brain.model_registry import ModelRegistry
        models = ModelRegistry.get_by_tier(0)
        assert any("local" in mid for mid in models)

    def test_get_by_tier_1(self):
        from brain.model_registry import ModelRegistry
        models = ModelRegistry.get_by_tier(1)
        assert len(models) >= 5

    def test_get_by_tier_5_free(self):
        from brain.model_registry import ModelRegistry
        models = ModelRegistry.get_by_tier(5)
        for mid in models:
            m = ModelRegistry.get_model(mid)
            assert m["cost_input_per_million"] == 0.0

    def test_all_models_have_unique_ranks(self):
        from brain.model_registry import ModelRegistry
        ranks = [m["rank"] for m in ModelRegistry.MODELS.values()]
        assert len(ranks) == len(set(ranks))

    def test_registry_is_sorted_by_rank(self):
        from brain.model_registry import ModelRegistry
        items = list(ModelRegistry.MODELS.items())
        ranks = [m["rank"] for _, m in items]
        assert ranks == sorted(ranks)
