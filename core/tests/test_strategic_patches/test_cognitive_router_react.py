# tests/test_strategic_patches/test_cognitive_router_react.py
"""#2705 — CognitiveRouter ReAct-routing চুক্তি-পরীক্ষা।

বাংলা মন্তব্য: complex টাস্ক এখন routing_mode="react" + production execution-hint
(ReasoningOrchestrator.decide_and_execute) পায়; simple Q&A direct থাকে;
"analyze"+"implement" decomposed চুক্তি অক্ষুণ্ণ থাকে।
"""

import pytest

from backend.brain.cognitive_router import (
    CognitiveRouter,
    classify_task_complexity,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_complex_task_routes_to_react():
    result = await CognitiveRouter().route(
        "Debug why the worker crashes and plan a root cause fix strategy",
        user_id="react-test-user",
    )

    assert result["routing_mode"] == "react"
    assert result["complexity"] == "complex"
    assert result["execution"] == "reasoning_orchestrator.decide_and_execute"
    assert result["max_iterations"] >= 1
    # provider/model সব মোডে থাকবে (budget-aware chat path)
    assert "provider" in result and "model" in result
    assert result["reasoning_mode"] in ("standard", "cot", "tot_mcts", "direct")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_step_chaining_routes_to_react():
    result = await CognitiveRouter().route(
        "Fetch the report and then validate its schema; after that archive it",
        user_id="react-test-user",
    )
    assert result["routing_mode"] == "react"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simple_qa_stays_direct():
    result = await CognitiveRouter().route(
        "Summarize this request",
        user_id="react-test-user",
    )
    assert result["routing_mode"] == "direct"
    assert set(result.keys()) == {"routing_mode", "provider", "model"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decomposed_contract_unchanged():
    result = await CognitiveRouter().route(
        "Analyze the requirements and implement the change",
        user_id="react-test-user",
    )
    assert result["routing_mode"] == "decomposed"
    assert result["task_graph"]["task_count"] == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_budget_context_direct_route_preserved():
    class Decision:
        provider = "budget-provider"
        model = "budget-model"

    class Optimizer:
        async def optimize_route(self, prompt, task_type, budget_context):
            return Decision()

    result = await CognitiveRouter(Optimizer()).route(
        "Choose the most efficient route",
        user_id="react-test-user",
        budget_context={"monthly_limit": 10},
    )
    assert result == {
        "routing_mode": "direct",
        "provider": "budget-provider",
        "model": "budget-model",
    }


@pytest.mark.unit
def test_classify_task_complexity_deterministic_signals():
    complex_res = classify_task_complexity(
        "Investigate the outage and evaluate the tradeoff between retries and backpressure"
    )
    assert complex_res["complexity"] == "complex"
    assert complex_res["score"] >= 2
    assert "investigate" in complex_res["signals"]["keywords"]

    simple_res = classify_task_complexity("hello there")
    assert simple_res["complexity"] == "simple"

    medium_res = classify_task_complexity("translate this sentence")
    assert medium_res["complexity"] in ("simple", "medium")


@pytest.mark.unit
def test_classify_empty_prompt_safe():
    res = classify_task_complexity("")
    assert res["complexity"] in ("simple", "medium")
    assert res["signals"]["words"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_complex_task_with_budget_context_still_reaches_react():
    """#2705 গুরুত্বপূর্ণ চুক্তি: production API (api/routes/cognitive.py) সবসময়
    BudgetContext পাঠায় — ReAct গেট বাজেট-শাখার আগে থাকতে হবে, নইলে
    main chat path-এ react mode অগম্য হয়ে যায়।"""
    from backend.brain.cognitive_router import BudgetContext  # noqa: F401

    class Decision:
        provider = "budget-provider"
        model = "budget-model"

    class Optimizer:
        async def optimize_route(self, prompt, task_type, budget_context):
            return Decision()

    result = await CognitiveRouter(Optimizer()).route(
        "Investigate the root cause of the outage and plan a fix strategy",
        user_id="react-test-user",
        budget_context={"monthly_limit": 10},
    )

    assert result["routing_mode"] == "react"
    # provider/model এখনো budget-awareভাবে resolve হয়
    assert result["provider"] == "budget-provider"
    assert result["model"] == "budget-model"
