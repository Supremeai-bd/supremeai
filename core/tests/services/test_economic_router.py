"""Tests for the canonical EconomicRouter (core/optimization/economic_optimizer.py).

This replaces the deprecated SmartRouter test that was skipped because
services.smart_model_router was refactored away during Phase 1 Router
Consolidation. The new canonical cost-quality router lives in
core/optimization/economic_optimizer.py.
"""

import pytest

from core.optimization.economic_optimizer import (
    BudgetContext,
    EconomicRouter,
    ModelConfig,
    RoutingDecision,
)


@pytest.fixture
def registry():
    """Populate MODEL_REGISTRY with two models and restore it after the test."""
    models = {
        "economy-gpt": ModelConfig(
            name="economy-gpt",
            provider="openai",
            quality_score=8.0,
            cost_per_1k_input=0.001,
            cost_per_1k_output=0.002,
            tier="STANDARD",
        ),
        "premium-gpt": ModelConfig(
            name="premium-gpt",
            provider="openai",
            quality_score=9.8,
            cost_per_1k_input=0.03,
            cost_per_1k_output=0.06,
            tier="PREMIUM",
        ),
    }
    return models


@pytest.fixture(autouse=True)
def patch_registry(monkeypatch, registry):
    monkeypatch.setattr("core.optimization.economic_optimizer.MODEL_REGISTRY", registry)
    return registry


class TestEstimateCost:
    def test_char_based_token_estimation(self, registry):
        router = EconomicRouter()
        model = registry["economy-gpt"]
        # 400 chars -> ~100 input tokens; ratio 1.5 -> ~150 output tokens
        cost = router.estimate_cost("a" * 400, model)
        expected = (100 / 1000) * 0.001 + (150 / 1000) * 0.002
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_token_estimation_ratio_affects_output(self, registry):
        router_low = EconomicRouter(token_estimation_ratio=1.0)
        router_high = EconomicRouter(token_estimation_ratio=2.0)
        model = registry["economy-gpt"]
        prompt = "x" * 400
        assert router_high.estimate_cost(prompt, model) > router_low.estimate_cost(prompt, model)


class TestFindViableProviders:
    async def test_filters_by_quality_floor(self, registry):
        router = EconomicRouter()
        candidates = await router.find_viable_providers("anything", quality_floor=9.0)
        names = {c.name for c in candidates}
        assert "premium-gpt" in names
        assert "economy-gpt" not in names

    async def test_empty_when_nothing_meets_floor(self, registry):
        router = EconomicRouter()
        candidates = await router.find_viable_providers("anything", quality_floor=99.0)
        assert candidates == []


class TestBudgetContext:
    def test_remaining_clamps_to_zero(self):
        ctx = BudgetContext(user_id="u", monthly_budget=10.0, used_budget=14.0)
        assert ctx.remaining == 0.0

    def test_deduct_reduces_used_budget(self):
        ctx = BudgetContext(user_id="u", monthly_budget=10.0, used_budget=2.0)
        ctx.deduct(3.0)
        assert ctx.used_budget == 5.0
        assert ctx.remaining == 5.0


class TestRouteWithBudget:
    def _budget(self, remaining: float) -> BudgetContext:
        return BudgetContext(user_id="u", monthly_budget=100.0, used_budget=100.0 - remaining)

    async def test_reject_when_no_model_meets_floor(self, registry):
        router = EconomicRouter()
        decision = await router.route_with_budget("prompt", self._budget(100.0), quality_floor=99.0)
        assert isinstance(decision, RoutingDecision)
        assert decision.action == "reject"
        assert decision.model_config is None
        assert decision.is_affordable is False
        assert "quality floor" in decision.reason

    async def test_selects_cheapest_affordable_model(self, registry):
        router = EconomicRouter()
        # Both models fit; economy is cheaper -> chosen.
        decision = await router.route_with_budget("prompt", self._budget(100.0), quality_floor=7.0)
        assert decision.action == "optimal"
        assert decision.is_affordable is True
        assert decision.model_config.name == "economy-gpt"
        assert decision.estimated_cost_usd > 0
        assert decision.candidates  # at least one viable candidate

    async def test_suggest_upgrade_when_over_budget(self, registry):
        router = EconomicRouter()
        # Budget too small for even the cheapest model but a model exists.
        decision = await router.route_with_budget(
            "x" * 4000, self._budget(0.0001), quality_floor=7.0
        )
        assert decision.action == "suggest_upgrade"
        assert decision.is_affordable is False
        assert decision.model_config is None
        assert decision.candidates  # viable candidates exist, just unaffordable

    async def test_returns_real_model_config_reference(self, registry):
        router = EconomicRouter()
        decision = await router.route_with_budget("x" * 40, self._budget(100.0), quality_floor=7.0)
        assert decision.model_config is registry["economy-gpt"]
