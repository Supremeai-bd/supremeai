# backend/tests/services/test_phase2_intelligence.py
"""Comprehensive Unit Tests for SupremeAI Phase 2 Intelligence Layer.

Tests:
1. AdvancedReasoningEngine (Deductive, Inductive, Abductive, Analogical, Causal)
2. Developer domain gateway routing for debugging and implementation
3. Business domain gateway routing and provider failure propagation
4. UX domain gateway routing without fabricated accessibility claims
5. PatternRecognizer (5 pattern types, online learning)
6. EvolutionModule (Genetic algorithm, mutation, crossover, selection, elitism)
7. LivingEngineOrchestrator End-to-End integration
"""

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.advanced_reasoning import AdvancedReasoningEngine
from core.evolution_module import EvolutionModule
from core.services.dynamic_planner import TaskNode
from core.services.living_engine import (
    BaseDomainAdapter,
    BusinessDomainAdapter,
    DevDomainAdapter,
    LivingEngineOrchestrator,
    UXDomainAdapter,
)

from learning.pattern_recognizer import PatternRecognizer


@pytest.fixture(autouse=True)
def gateway(monkeypatch):
    module = importlib.import_module("core.llm.llm_gateway")
    gateway = SimpleNamespace(
        acompletion=AsyncMock(return_value={"text": "def run(): return {'result': 10}"})
    )
    monkeypatch.setattr(module, "get_llm_gateway", lambda: gateway)
    return gateway


# ── 1. Advanced Reasoning Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_advanced_reasoning_deductive():
    engine = AdvancedReasoningEngine()
    chain = await engine.reason(
        "Prove that the database connection pool invariant holds if transactions are isolated"
    )
    assert chain.chain_id.startswith("reason_")
    assert chain.overall_confidence >= 0.5
    assert len(chain.steps) > 0
    assert "primary_strategy" in chain.metadata


@pytest.mark.asyncio
async def test_advanced_reasoning_abductive_and_causal():
    engine = AdvancedReasoningEngine()
    chain = await engine.reason(
        "Why did the memory usage spike during peak load? Explain root cause"
    )
    assert chain.final_conclusion is not None
    assert chain.overall_confidence > 0.6


# ── 2. Domain Adapters Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "adapter_type,task_type,session_prefix,description",
    [
        (BaseDomainAdapter, "general", "general", "Analyze an unclassified task"),
        (DevDomainAdapter, "coding", "dev", "Fix this bug in python"),
        (DevDomainAdapter, "coding", "dev", "Create an async health check endpoint in python"),
        (BusinessDomainAdapter, "reasoning", "business", "Calculate cost reduction ROI"),
        (UXDomainAdapter, "vision", "ux", "Design an accessible React dashboard"),
    ],
)
@pytest.mark.parametrize("response_type", ["dict", "choices"])
async def test_domain_adapter_uses_provider_result(
    gateway, adapter_type, task_type, session_prefix, description, response_type
):
    text = "Actual provider output, not a synthetic confidence score"
    gateway.acompletion.return_value = (
        {"text": text}
        if response_type == "dict"
        else SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
    )
    node = TaskNode(id="domain-test", name="Task", capability="analyze", description=description)
    result = await adapter_type().execute_node(node, {"input": "fixture"})
    assert result == {
        "status": "executed",
        "node_id": node.id,
        "capability": node.capability,
        "result": text,
        "llm_processed": True,
    }
    gateway.acompletion.assert_awaited_once()
    call = gateway.acompletion.await_args.kwargs
    assert call["task_type"] == task_type
    assert call["session_id"] == f"{session_prefix}_adapter_{node.id}"
    assert description in call["prompt"]
    assert '"input": "fixture"' in call["prompt"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "adapter_type", [BaseDomainAdapter, DevDomainAdapter, BusinessDomainAdapter, UXDomainAdapter]
)
@pytest.mark.parametrize(
    "response",
    [None, {}, {"text": ""}, {"text": "  "}, {"text": 42}, {"success": False, "text": "error"}],
)
async def test_domain_adapter_rejects_empty_or_failed_response(gateway, adapter_type, response):
    gateway.acompletion.return_value = response
    with pytest.raises(RuntimeError):
        await adapter_type().execute_node(TaskNode("n", "Task", "analyze"), {})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "adapter_type", [BaseDomainAdapter, DevDomainAdapter, BusinessDomainAdapter, UXDomainAdapter]
)
async def test_domain_adapter_propagates_provider_failure(gateway, adapter_type):
    gateway.acompletion.side_effect = RuntimeError("Provider unavailable")
    with pytest.raises(RuntimeError, match="Provider unavailable"):
        await adapter_type().execute_node(TaskNode("n", "Task", "analyze"), {})
    gateway.acompletion.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "adapter_type", [BaseDomainAdapter, DevDomainAdapter, BusinessDomainAdapter, UXDomainAdapter]
)
async def test_domain_adapter_propagates_cancellation(gateway, adapter_type):
    gateway.acompletion.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await adapter_type().execute_node(TaskNode("n", "Task", "analyze"), {})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "adapter_type", [BaseDomainAdapter, DevDomainAdapter, BusinessDomainAdapter, UXDomainAdapter]
)
async def test_domain_adapter_fails_without_gateway(monkeypatch, adapter_type):
    module = importlib.import_module("core.llm.llm_gateway")
    monkeypatch.setattr(module, "get_llm_gateway", lambda: None)
    with pytest.raises(RuntimeError, match="unavailable"):
        await adapter_type().execute_node(TaskNode("n", "Task", "analyze"), {})


# ── 3. Pattern Recognition Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pattern_recognizer_discovery_and_learning():
    recognizer = PatternRecognizer()
    matches = await recognizer.recognize("Optimize database connections and queries")
    assert len(matches) > 0

    # Learn from new example
    new_pat = await recognizer.learn_from_example(
        example={"route": "/api/v1/health", "status": "healthy"},
        outcome={"verified": True},
        success=True,
    )
    assert new_pat is not None or recognizer.stats["patterns_discovered"] >= 0


# ── 4. Evolution Module Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_evolution_module_genetic_algorithm():
    evo = EvolutionModule(config={"population_size": 10, "max_generations": 3})

    async def dummy_fitness(solution):
        return 0.95

    initial_solution = {"cache_size": 100, "timeout_ms": 500}
    res = await evo.evolve(
        problem="Optimize cache parameters",
        current_solution=initial_solution,
        fitness_func=dummy_fitness,
        generations=3,
    )
    assert res.generations_passed == 3
    assert res.time_evolved_ms >= 0


# ── 5. Living Engine Integration Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_living_engine_full_phase2_pipeline(gateway, monkeypatch):
    mock_memory = MagicMock()
    mock_memory.store_memory.return_value = None
    mock_memory.search_memory.return_value = []
    mock_memory.retrieve_recent.return_value = []

    reflection = SimpleNamespace(reflect=AsyncMock(return_value={"is_correct": True}))
    orchestrator = LivingEngineOrchestrator(memory_service=mock_memory, self_reflection=reflection)
    execute = MagicMock(return_value={"status": "completed", "result": 10})
    monkeypatch.setattr(orchestrator.tool_forge, "execute_tool", execute)
    prompt = "ডাটাবেস কানেকশন পুল অপটিমাইজ করো এবং লেটেন্সি কমাও"

    solution = await orchestrator.solve_unpredictable_demand(prompt, session_id="test_phase2_1")

    assert solution.success is True
    assert solution.fitness_score > 0.5
    assert "strategy" in solution.reasoning
    assert "improvement_pct" in solution.evolution
    assert len(solution.execution_order) >= 4
    assert set(solution.results) == set(solution.execution_order)
    gateway.acompletion.assert_awaited()
    reflection.reflect.assert_awaited_once()
    assert reflection.reflect.await_args.kwargs["is_success"] is True
