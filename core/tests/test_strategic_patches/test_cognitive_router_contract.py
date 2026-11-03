"""Deterministic contract tests for the currently supported cognitive router."""

import pytest

from backend.brain.cognitive_router import CognitiveRouter


@pytest.mark.unit
@pytest.mark.asyncio
async def test_router_decomposes_analysis_and_implementation_prompt():
    result = await CognitiveRouter().route(
        "Analyze the requirements and implement the change",
        user_id="contract-test-user",
    )

    assert result["routing_mode"] == "decomposed"
    assert result["task_graph"] == {
        "task_count": 2,
        "tasks": {
            "task_1": {"type": "analysis", "provider": "google", "depends_on": []},
            "task_2": {
                "type": "implementation",
                "provider": "groq",
                "depends_on": ["task_1"],
            },
        },
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_router_returns_configured_default_model_for_direct_prompt(monkeypatch):
    from backend.brain import cognitive_router

    monkeypatch.setattr(cognitive_router.settings, "model_general", "test-provider/test-model")

    result = await CognitiveRouter().route("Summarize this request", user_id="contract-test-user")

    assert result == {
        "routing_mode": "direct",
        "provider": "test-provider",
        "model": "test-model",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_router_uses_economic_optimizer_when_budget_context_is_present():
    class Decision:
        provider = "budget-provider"
        model = "budget-model"

    class Optimizer:
        async def optimize_route(self, prompt, task_type, budget_context):
            assert prompt == "Choose the most efficient route"
            assert task_type == "general"
            assert budget_context == {"monthly_limit": 10}
            return Decision()

    result = await CognitiveRouter(Optimizer()).route(
        "Choose the most efficient route",
        user_id="contract-test-user",
        budget_context={"monthly_limit": 10},
    )

    assert result == {
        "routing_mode": "direct",
        "provider": "budget-provider",
        "model": "budget-model",
    }


@pytest.mark.unit
def test_router_factory_reuses_singleton():
    from backend.brain.cognitive_router import get_cognitive_router

    first = get_cognitive_router()
    second = get_cognitive_router()

    assert first is second
    assert isinstance(first, CognitiveRouter)
