"""Tests for the EconomicOptimizer module."""

import pytest

from brain.economic_optimizer import (
    BudgetContext,
    OptimizationDecision,
    get_economic_optimizer,
)


class TestEconomicOptimizer:
    @pytest.fixture
    async def economic_optimizer(self):
        """Fixture to get an instance of EconomicOptimizer."""
        return await get_economic_optimizer()

    async def test_optimize_route_happy_path(self, economic_optimizer):
        """Test optimize_route with a happy path scenario."""
        budget_context = BudgetContext(
            user_id="user1", monthly_limit=10.0, spent_this_month=2.0, cost_sensitivity=0.3
        )
        prompt = "Optimize my route"
        task_type = "routing"

        decision = await economic_optimizer.optimize_route(prompt, task_type, budget_context)

        assert isinstance(decision, OptimizationDecision)
        assert decision.provider == "huggingface"
        assert decision.model == "zephyr-7b"
        assert decision.estimated_cost == 0.00005
        assert "Selected huggingface" in decision.reasoning

    async def test_optimize_route_edge_case(self, economic_optimizer):
        """Test optimize_route with edge case of budget exactly at threshold."""
        budget_context = BudgetContext(
            user_id="user2", monthly_limit=5.0, spent_this_month=0.0, cost_sensitivity=0.5
        )
        prompt = "Optimize my route"
        task_type = "routing"

        decision = await economic_optimizer.optimize_route(prompt, task_type, budget_context)

        assert isinstance(decision, OptimizationDecision)
        assert decision.provider in ["huggingface", "together", "google"]
        assert decision.estimated_cost <= 0.00025  # Ensure it selects the cheapest available option

    async def test_optimize_route_error_path(self, economic_optimizer):
        """Test optimize_route with insufficient budget."""
        budget_context = BudgetContext(
            user_id="user3", monthly_limit=0.5, spent_this_month=0.0, cost_sensitivity=0.9
        )
        prompt = "Optimize my route"
        task_type = "routing"

        decision = await economic_optimizer.optimize_route(prompt, task_type, budget_context)

        assert isinstance(decision, OptimizationDecision)
        assert decision.provider == "huggingface"  # Should still select the cheapest option
        assert decision.estimated_cost == 0.00005
        assert "due to remaining budget of $0.50" in decision.reasoning

    async def test_get_economic_optimizer(self):
        """Test get_economic_optimizer returns the same instance."""
        optimizer1 = await get_economic_optimizer()
        optimizer2 = await get_economic_optimizer()
        assert optimizer1 is optimizer2  # Ensure the same instance is returned
