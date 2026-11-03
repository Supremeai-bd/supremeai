"""
Regression tests for services/dynamic_ai/learning_engine.py

CONTEXT (do not remove without reading): commit 0f4482b6a8 fixed a
production-breaking bug where `DynamicAIOrchestrator.generate()` (called by
`LLMRouter.route()`, the main non-streaming LLM entry point) invoked four
methods on `self.learning_engine` --
`load_learning_data`, `detect_task_type`, `get_best_providers_for_task`,
`record_interaction` -- that only existed on a *dead-code* stub class
defined inside orchestrator.py's `except ImportError` fallback branch. The
real `LearningEngine` class in this module never had them, so every
non-streaming LLM request raised `AttributeError` unconditionally.

These tests exist so that if any of the four methods is ever removed,
renamed, or its signature is changed incompatibly with how orchestrator.py
calls it, CI fails loudly instead of only failing silently in production.
No live DB/network is needed: `UnifiedLearningEngine` (core/unified_learning.py)
is an in-memory singleton, so these are pure unit tests.
"""

import inspect

import pytest

from services.dynamic_ai.learning_engine import LearningEngine
from services.dynamic_ai.orchestrator import DynamicAIOrchestrator, TaskType


@pytest.fixture
def engine():
    return LearningEngine(storage_path="/tmp/unused-for-test.json")


class TestLearningEngineShimMethodsExist:
    """Guards against the exact bug fixed in 0f4482b6a8: methods silently
    missing from the real (non-stub) LearningEngine class."""

    def test_has_load_learning_data(self, engine):
        assert hasattr(engine, "load_learning_data")
        assert inspect.iscoroutinefunction(engine.load_learning_data)

    def test_has_detect_task_type(self, engine):
        assert hasattr(engine, "detect_task_type")

    def test_has_get_best_providers_for_task(self, engine):
        assert hasattr(engine, "get_best_providers_for_task")
        assert inspect.iscoroutinefunction(engine.get_best_providers_for_task)

    def test_has_record_interaction(self, engine):
        assert hasattr(engine, "record_interaction")


class TestLoadLearningData:
    @pytest.mark.asyncio
    async def test_does_not_raise(self, engine):
        # orchestrator.initialize() awaits this unconditionally
        result = await engine.load_learning_data()
        assert result is None


class TestDetectTaskType:
    def test_returns_string(self, engine):
        result = engine.detect_task_type("hello there")
        assert isinstance(result, str)

    def test_matches_orchestrator_task_type_values(self, engine):
        """The returned string must be usable as a TaskType-equivalent value
        because orchestrator.py uses it directly as `detected_task` without
        wrapping in TaskType(...) when task_type is not explicitly passed,
        and later does `task_specialty_map.get(task, [])` lookups against
        TaskType enum members."""
        result = engine.detect_task_type("please write a python function")
        assert result in {t.value for t in TaskType}

    def test_code_generation_keywords(self, engine):
        assert engine.detect_task_type("write a python function to sort a list") == (
            "code_generation"
        )

    def test_summarization_keywords(self, engine):
        assert engine.detect_task_type("please summarize this article") == "summarization"

    def test_unknown_prompt_falls_back_to_general(self, engine):
        assert engine.detect_task_type("asdkjfh qwoeiruqwoe") == "general"

    def test_empty_prompt_does_not_raise(self, engine):
        assert engine.detect_task_type("") == "general"

    def test_none_prompt_does_not_raise(self, engine):
        assert engine.detect_task_type(None) == "general"


class TestGetBestProvidersForTask:
    @pytest.mark.asyncio
    async def test_empty_providers_returns_empty_list(self, engine):
        result = await engine.get_best_providers_for_task(
            prompt="hi", available_providers=[], context={}
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_provider_id_confidence_tuples(self, engine):
        """orchestrator.generate() does:
        `for provider_id, confidence_score in ranked_providers[:max_retries]`
        so the return shape must be list[tuple[str, float]]."""

        class FakeProvider:
            provider_id = "gemini"

        result = await engine.get_best_providers_for_task(
            prompt="hi", available_providers=[FakeProvider()], context={}
        )
        assert len(result) == 1
        provider_id, confidence = result[0]
        assert provider_id == "gemini"
        assert isinstance(confidence, float)

    @pytest.mark.asyncio
    async def test_accepts_plain_string_providers(self, engine):
        result = await engine.get_best_providers_for_task(
            prompt="hi", available_providers=["openai"], context={}
        )
        assert result == [("openai", 1.0)]


class TestRecordInteraction:
    @pytest.mark.asyncio
    async def test_does_not_raise_with_running_loop(self, engine):
        # orchestrator.py calls this synchronously (not awaited) from
        # inside async methods -- must not raise even though it schedules
        # a background task via asyncio.create_task.
        engine.record_interaction(
            provider_id="gemini",
            task_type=TaskType.CHAT,
            success=True,
            latency_ms=42.0,
            estimated_cost=0.0001,
        )

    def test_does_not_raise_without_running_loop(self, engine):
        # e.g. called from a sync test/context with no event loop -- must
        # degrade gracefully rather than crash the caller.
        engine.record_interaction(provider_id="gemini", task_type=TaskType.CHAT, success=False)


class TestOrchestratorWiring:
    """End-to-end guard that DynamicAIOrchestrator's __init__/initialize can
    actually drive the real LearningEngine without AttributeError -- this is
    the exact call path that was broken in production before 0f4482b6a8."""

    @pytest.mark.asyncio
    async def test_initialize_does_not_raise(self):
        orchestrator = DynamicAIOrchestrator(auto_validate_keys=False, ollama_enabled=False)
        await orchestrator.initialize()
        assert orchestrator._initialized is True

    @pytest.mark.asyncio
    async def test_generate_does_not_raise_attributeerror(self):
        """With zero configured providers this can't succeed, but it must
        fail gracefully (GenerationResult(success=False, ...)) rather than
        raising AttributeError from a missing learning_engine method."""
        orchestrator = DynamicAIOrchestrator(auto_validate_keys=False, ollama_enabled=False)
        result = await orchestrator.generate("hello")
        assert result.success is False
        assert result.error is not None
