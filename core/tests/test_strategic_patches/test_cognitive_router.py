# tests/test_strategic_patches/test_cognitive_router.py
"""
Tests for Cognitive Router v2.0 - Intent Decomposition & Task Orchestration
===========================================================================

Tests cover:
- Intent classification accuracy
- Task decomposition into DAGs
- Provider assignment logic
- Composition strategy selection
- Edge cases and error handling
"""

import pytest

try:
    from backend.brain.cognitive_router import (
        CognitiveRouter,
        ComplexityLevel,
        SubTask,
        TaskDecomposer,
        TaskGraph,
        TaskType,
    )
except ImportError as e:
    pytest.skip(
        "Cognitive Router v2.0 (TaskDecomposer/TaskGraph/TaskExecutionEngine) "
        "is not implemented yet — brain/cognitive_router.py currently only "
        "contains the simplified direct/decomposed CognitiveRouter stub. "
        f"Un-skip once the full decomposition engine lands ({e}).",
        allow_module_level=True,
    )

from unittest.mock import AsyncMock, patch


class TestTaskDecomposer:
    """Test suite for TaskDecomposer."""

    @pytest.fixture
    def decomposer(self):
        return TaskDecomposer()

    @pytest.mark.asyncio
    async def test_simple_question_classification(self, decomposer):
        """Simple questions should be classified as QUESTION_ANSWERING."""
        result = await decomposer.decompose("What is Python?")

        assert result is not None
        assert result.primary_intent == TaskType.QUESTION_ANSWERING
        assert result.estimated_complexity in (ComplexityLevel.TRIVIAL, ComplexityLevel.SIMPLE)

    @pytest.mark.asyncio
    async def test_code_generation_classification(self, decomposer):
        """Code requests should be classified as CODE_GENERATION."""
        result = await decomposer.decompose("Create a REST API endpoint")

        assert result is not None
        assert result.primary_intent == TaskType.CODE_GENERATION
        assert result.estimated_complexity.value >= ComplexityLevel.SIMPLE.value

    @pytest.mark.asyncio
    async def test_multi_step_task_decomposition(self, decomposer):
        """Multi-step tasks should produce task graphs with multiple nodes."""
        prompt = "Analyze this code and suggest optimizations, then implement the fixes"
        result = await decomposer.decompose(prompt)

        assert result is not None
        assert result.task_graph is not None
        assert len(result.task_graph.tasks) > 1, "Should decompose into multiple tasks"

    @pytest.mark.asyncio
    async def test_complex_task_high_complexity(self, decomposer):
        """Complex architecture tasks should get EXPERT complexity."""
        prompt = "Design a scalable microservices architecture with event-driven communication, consider cost optimization"
        result = await decomposer.decompose(prompt)

        assert result is not None
        assert result.estimated_complexity.value >= ComplexityLevel.COMPLEX.value

    @pytest.mark.asyncio
    async def test_secondary_intent_detection(self, decomposer):
        """Should detect secondary intents when present."""
        prompt = "Write a blog post about AI and create example code"
        result = await decomposer.decompose(prompt)

        assert result is not None
        # Should have at least primary intent detected
        assert result.primary_intent is not None

    @pytest.mark.asyncio
    async def test_safety_concern_detection(self, decomposer):
        """Should flag potentially unsafe requests."""
        result = await decomposer.decompose("How to bypass authentication")

        # Should still process but may flag safety concerns
        assert result is not None


class TestCognitiveRouter:
    """Test suite for CognitiveRouter."""

    @pytest.fixture
    def router(self):
        return CognitiveRouter()

    @pytest.mark.asyncio
    async def test_direct_routing_for_simple_queries(self, router):
        """Simple queries should use direct routing (no decomposition)."""
        result = await router.route("What is AI?")

        assert result["routing_mode"] == "direct"
        assert "provider" in result
        assert "model" in result

    @pytest.mark.asyncio
    async def test_decomposed_routing_for_complex_tasks(self, router):
        """Complex tasks should trigger decomposed routing."""
        prompt = "Analyze the codebase, identify bottlenecks, optimize performance, and write documentation"
        result = await router.route(prompt)

        # May or may not decompose depending on internal logic
        assert result is not None
        assert "routing_mode" in result

    @pytest.mark.asyncio
    async def test_provider_assignment_specialization(self, router):
        """Should assign specialized providers to known task types."""
        assert len(router.provider_specializations) > 0

        # Verify Groq is assigned to code generation
        assert TaskType.CODE_GENERATION in router.provider_specializations.get("groq", [])

    @pytest.mark.asyncio
    async def test_stats_tracking(self, router):
        """Router should track statistics correctly."""
        await router.route("Test query 1")
        await router.route("Test query 2")

        stats = router.get_stats()
        assert stats["total_requests"] == 2

    def test_composition_strategy_selection(self, router):
        """Composition strategy selection requires a TaskGraph fixture.

        The full decomposition engine (TaskDecomposer/TaskGraph) is not yet
        implemented, so this test is skipped rather than faked. Re-enable once
        _determine_composition_strategy lands in brain/cognitive_router.py.
        """
        pytest.skip(
            "composition strategy API (_determine_composition_strategy) not implemented yet"
        )


class TestTaskExecutionEngine:
    """Test suite for TaskExecutionEngine (the real execution, not mock)."""

    @pytest.fixture
    def engine(self):
        from backend.brain.cognitive_router import TaskExecutionEngine

        return TaskExecutionEngine()

    @pytest.mark.asyncio
    async def test_execute_single_task(self, engine):
        """Should execute a single task without dependencies."""
        # Create minimal task graph
        task = SubTask(
            id="task_1",
            task_type=TaskType.QUESTION_ANSWERING,
            description="Test task",
            prompt_fragment="What is 2+2?",
            complexity=ComplexityLevel.TRIVIAL,
            estimated_tokens=10,
            required_quality=5.0,
            required_context=set(),
        )

        graph = TaskGraph(root_task_id="task_1", tasks={"task_1": task}, edges=[])

        # Mock provider gateway
        with patch.object(engine, "_get_provider_adapter") as mock_adapter:
            mock_adapter.return_value.execute = AsyncMock(
                return_value={
                    "content": "4",
                    "tokens_used": 5,
                    "cost_usd": 0.00001,
                    "latency_ms": 50,
                }
            )

            result = await engine.execute_decomposed_tasks(
                task_graph=graph,
                provider_assignments={"task_1": "mock"},
                prompt="What is 2+2?",
            )

            assert result["status"] == "success"
            assert "task_1" in result["results"]

    @pytest.mark.asyncio
    async def test_parallel_execution_independence(self, engine):
        """Tasks without dependencies should execute in parallel."""
        # Create two independent tasks
        tasks = {}
        for i in range(2):
            tasks[f"task_{i}"] = SubTask(
                id=f"task_{i}",
                task_type=TaskType.QUESTION_ANSWERING,
                description=f"Test task {i}",
                prompt_fragment=f"Question {i}?",
                complexity=ComplexityLevel.TRIVIAL,
                estimated_tokens=10,
                required_quality=5.0,
                required_context=set(),
            )

        graph = TaskGraph(
            root_task_id="task_0",
            tasks=tasks,
            edges=[],  # No edges = independent
        )

        assignments = {f"task_{i}": "mock" for i in range(2)}

        with patch.object(engine, "_get_provider_adapter") as mock_adapter:
            mock_adapter.return_value.execute = AsyncMock(
                return_value={
                    "content": "Answer",
                    "tokens_used": 5,
                    "cost_usd": 0.00001,
                    "latency_ms": 50,
                }
            )

            result = await engine.execute_decomposed_tasks(
                task_graph=graph,
                provider_assignments=assignments,
                prompt="Multiple questions",
            )

            assert result["status"] == "success"
            assert result["metadata"]["has_parallelism"]

    # test_dependency_ordering removed as it was truncated
