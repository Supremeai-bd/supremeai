from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.orchestration.agent_orchestrator import (
    AgentCircuitBreaker,
    AsyncTaskManager,
    SmartSemanticRouter,
    budget_aware_route,
    route_request,
)


@pytest.fixture
def circuit_breaker():
    return AgentCircuitBreaker(agent_name="test_agent")


def test_circuit_breaker_initialization(circuit_breaker):
    assert circuit_breaker.agent_name == "test_agent"
    assert circuit_breaker.max_iterations == 5
    assert circuit_breaker.max_tokens == 5000
    assert circuit_breaker._iteration_count == 0
    assert circuit_breaker._token_count == 0
    assert circuit_breaker._locked is False


def test_circuit_breaker_increment_iteration_allowed(circuit_breaker):
    assert circuit_breaker.increment_iteration() is True
    assert circuit_breaker._iteration_count == 1


def test_circuit_breaker_increment_iteration_exceeded(circuit_breaker):
    for _ in range(5):
        assert circuit_breaker.increment_iteration() is True
    assert circuit_breaker.increment_iteration() is False
    assert circuit_breaker._locked is True
    assert "Max iterations" in circuit_breaker._lock_reason


def test_circuit_breaker_add_tokens_allowed(circuit_breaker):
    assert circuit_breaker.add_tokens(1000) is True
    assert circuit_breaker._token_count == 1000


def test_circuit_breaker_add_tokens_exceeded(circuit_breaker):
    assert circuit_breaker.add_tokens(5000) is True
    assert circuit_breaker.add_tokens(1) is False
    assert circuit_breaker._locked is True
    assert "Max tokens" in circuit_breaker._lock_reason


def test_circuit_breaker_check_limits_when_locked(circuit_breaker):
    circuit_breaker._locked = True
    circuit_breaker._lock_reason = "test lock"
    result = circuit_breaker.check_limits()
    assert result["blocked"] is True
    assert result["reason"] == "test lock"


def test_circuit_breaker_check_limits_when_unlocked(circuit_breaker):
    result = circuit_breaker.check_limits()
    assert result["blocked"] is False


def test_circuit_breaker_reset(circuit_breaker):
    circuit_breaker._iteration_count = 10
    circuit_breaker._token_count = 9999
    circuit_breaker._locked = True
    circuit_breaker._lock_reason = "limit exceeded"
    circuit_breaker.reset()
    assert circuit_breaker._iteration_count == 0
    assert circuit_breaker._token_count == 0
    assert circuit_breaker._locked is False
    assert circuit_breaker._lock_reason is None


def test_circuit_breaker_get_status(circuit_breaker):
    circuit_breaker.add_tokens(100)
    circuit_breaker.increment_iteration()
    status = circuit_breaker.get_status()
    assert status["agent_name"] == "test_agent"
    assert status["iterations_used"] == 1
    assert status["tokens_used"] == 100
    assert status["locked"] is False


@pytest.mark.parametrize(
    "prompt,task_type,expected_intent,tier",
    [
        ("code a python function", "general", "coding", 1),
        ("build a react component", "general", "coding", 1),
        ("debug my code", "general", "coding", 1),
        ("refactor the class", "general", "coding", 1),
        ("algorithm optimization", "general", "coding", 1),
        ("reason about the logic", "general", "reasoning", 1),
        ("analyze the math problem", "general", "reasoning", 1),
        ("prove the theorem", "general", "reasoning", 1),
        ("calculate the integral", "general", "reasoning", 1),
        ("search for documentation", "general", "search", 2),
        ("find the best practice", "general", "search", 2),
        ("research the topic", "general", "search", 2),
        ("lookup the API", "general", "search", 2),
        ("query the database", "general", "search", 2),
        ("summarize the article", "general", "search", 2),
        ("translate to spanish", "general", "search", 2),
        ("sentiment analysis", "general", "search", 2),
        ("image recognition task", "general", "vision", 3),
        ("ocr scan this document", "general", "vision", 3),
        ("analyze the photo", "general", "reasoning", 1),
        ("visualize the chart", "general", "vision", 3),
        ("code this file.png", "general", "vision", 3),
    ],
)
def test_route_request_keyword_routing(prompt, task_type, expected_intent, tier):
    result = route_request(prompt, task_type)
    assert isinstance(result, SmartSemanticRouter)
    assert result.intent == expected_intent
    assert result.tier == tier


def test_route_request_explicit_code_task():
    result = route_request("do something", task_type="code")
    assert result.intent == "coding"
    assert result.requires_expensive is True
    assert result.tier == 1


def test_route_request_explicit_reasoning_task():
    result = route_request("do something", task_type="reasoning")
    assert result.intent == "reasoning"
    assert result.requires_expensive is True
    assert result.tier == 1


def test_route_request_vision_task():
    result = route_request("do something", task_type="vision")
    assert result.intent == "vision"
    assert result.requires_expensive is True
    assert result.tier == 3


def test_route_request_file_extension_vision():
    result = route_request("check out this .jpg file")
    assert result.intent == "vision"
    assert result.requires_expensive is True


def test_route_request_translation_task():
    result = route_request("translate this text", task_type="translation")
    assert result.intent == "search"
    assert result.requires_expensive is False
    assert result.tier == 2


def test_route_request_image_task():
    result = route_request("show me an image", task_type="image")
    assert result.intent == "vision"
    assert result.requires_expensive is True
    assert result.tier == 3


def test_route_request_default_fallback():
    result = route_request("random unrelated prompt", task_type="general")
    assert result.intent == "general"
    assert result.requires_expensive is False
    assert result.tier == 5


def test_async_task_manager_create_and_get():
    mgr = AsyncTaskManager()
    task_id = mgr.create_task("test_type", {"key": "value"})
    assert task_id in mgr._tasks
    task = mgr.get_task(task_id)
    assert task is not None
    assert task["type"] == "test_type"
    assert task["status"] == "pending"
    assert task["progress"] == 0


def test_async_task_manager_get_unknown():
    mgr = AsyncTaskManager()
    assert mgr.get_task("nonexistent") is None


def test_async_task_manager_get_stats_empty():
    mgr = AsyncTaskManager()
    stats = mgr.get_stats()
    assert stats["total_tasks"] == 0
    assert stats["by_status"]["pending"] == 0


def test_async_task_manager_get_stats_with_tasks():
    mgr = AsyncTaskManager()
    t1 = mgr.create_task("type_a", {})
    t2 = mgr.create_task("type_b", {})
    mgr._tasks[t1]["status"] = "completed"
    mgr._tasks[t2]["status"] = "failed"
    stats = mgr.get_stats()
    assert stats["total_tasks"] == 2
    assert stats["by_status"]["completed"] == 1
    assert stats["by_status"]["failed"] == 1


def test_async_task_manager_simulate_video():
    mgr = AsyncTaskManager()
    task_id = mgr.create_task("video_generation", {"prompt": "video"})
    task = mgr.get_task(task_id)
    assert task["status"] == "processing"
    assert task["progress"] == 50


def test_async_task_manager_simulate_image():
    mgr = AsyncTaskManager()
    task_id = mgr.create_task("image_generation", {"prompt": "image"})
    task = mgr.get_task(task_id)
    assert task["status"] == "processing"
    assert task["progress"] == 50


def test_smart_semantic_router_model():
    router = SmartSemanticRouter(
        intent="test_intent", requires_expensive=True, tier=2, reasoning="test"
    )
    assert router.intent == "test_intent"
    assert router.requires_expensive is True
    assert router.tier == 2
    assert router.reasoning == "test"


def test_smart_semantic_router_defaults():
    router = SmartSemanticRouter()
    assert router.intent == "general"
    assert router.requires_expensive is False
    assert router.tier == 5
    assert router.reasoning == ""


def test_budget_aware_route_no_free_tier():
    with patch("core.orchestration.agent_orchestrator._free_tier_available", False):
        result = budget_aware_route("some prompt", task_type="general")
    assert result["intent"] == "general"
    assert result["requires_expensive"] is False
    assert result["tier"] == 5
    assert "best_provider" in result


def test_budget_aware_route_free_tier_available():
    mock_tracker = MagicMock()
    mock_tracker.get_best_provider.return_value = "groq"
    with patch("core.orchestration.agent_orchestrator._free_tier_available", True):
        with patch("core.orchestration.agent_orchestrator.get_tracker", return_value=mock_tracker):
            result = budget_aware_route("some prompt", task_type="general")
    assert result["best_provider"] == "groq"
    mock_tracker.get_best_provider.assert_called_once()


def test_budget_aware_route_free_tier_exhausted():
    mock_tracker = MagicMock()
    mock_tracker.get_best_provider.return_value = None
    with patch("core.orchestration.agent_orchestrator._free_tier_available", True):
        with patch("core.orchestration.agent_orchestrator.get_tracker", return_value=mock_tracker):
            result = budget_aware_route("some prompt", task_type="general")
    assert result["best_provider"] is None
