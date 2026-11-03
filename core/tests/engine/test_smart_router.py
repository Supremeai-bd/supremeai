import pytest

from engine.smart_router import SmartModelRouter


@pytest.mark.asyncio
async def test_smart_router_selection():
    """Verify smart router picks correct model based on task intent without excessive mocks."""
    router = SmartModelRouter()

    # Test simple tasks
    decision = await router.route("Hello world")
    assert decision["detected_intent"] == "general"

    # Test code tasks
    decision_code = await router.route("Can you write a python script for this?")
    assert decision_code["detected_intent"] == "code"

    # Test reasoning tasks
    decision_reasoning = await router.route("What is the tradeoff between REST and GraphQL?")
    assert decision_reasoning["detected_intent"] == "reasoning"

    # Test bengali detection
    decision_bengali = await router.route("আপনি কেমন আছেন?")
    assert decision_bengali["detected_intent"] == "bengali"

    # Ensure selected model is from our real map
    assert "selected_model" in decision_code
