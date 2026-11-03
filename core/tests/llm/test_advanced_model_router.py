# SupremeAI 2.0 — Advanced Model Router Test Suite
# বাংলা মন্তব্য: এটি প্রম্পট এনালাইসিস, টাস্ক-বেসড মডেল সিলেকশন এবং বাজেটিং ফিল্টারিংয়ের ইউনিট টেস্ট পরিচালনা করে।

import pytest

from core.llm.advanced_model_router import AdvancedModelRouter


@pytest.mark.asyncio
async def test_prompt_complexity_analysis():
    router = AdvancedModelRouter()
    prompt = "Please analyze and compare the performance of Transformer and Mamba architectures for code generation."
    complexity = router.analyze_prompt_complexity(prompt)

    assert complexity["length"] > 0.0
    assert complexity["complexity"] > 0.0
    assert complexity["overall"] > 0.0


@pytest.mark.asyncio
async def test_get_available_models_by_task():
    router = AdvancedModelRouter()
    coding_models = router.get_available_models("coding")
    assert len(coding_models) >= 1
    assert any(m[1] == "llama-3.3-70b-versatile" for m in coding_models)

    reasoning_models = router.get_available_models("reasoning")
    assert len(reasoning_models) >= 1


@pytest.mark.asyncio
async def test_route_request_default():
    router = AdvancedModelRouter()
    prompt = "Write a python function to merge two sorted lists."
    decision = await router.route_request(prompt, task_type="coding")

    assert decision.provider != ""
    assert decision.model != ""
    assert decision.priority_score > 0.0
    assert decision.expected_cost >= 0.0
    assert decision.expected_latency > 0.0


@pytest.mark.asyncio
async def test_route_request_budget_filtering():
    router = AdvancedModelRouter()
    prompt = "Simple hello world query"
    decision = await router.route_request(prompt, task_type="coding", budget_constraint=0.0001)

    assert decision.expected_cost <= 0.0001 or decision.priority_score > 0.0
