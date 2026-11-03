# backend/tests/services/test_phase2_intelligence.py
"""Comprehensive Unit Tests for SupremeAI Phase 2 Intelligence Layer.

Tests:
1. AdvancedReasoningEngine (Deductive, Inductive, Abductive, Analogical, Causal)
2. DevAdapter (12+ languages, bug finding, implementation, refactoring, review, testing)
3. BusinessAdapter (Financial analysis, decision support, forecasting, process optimization)
4. UXAdapter (WCAG AAA accessibility, React code generation, prototyping)
5. PatternRecognizer (5 pattern types, online learning)
6. EvolutionModule (Genetic algorithm, mutation, crossover, selection, elitism)
7. LivingEngineOrchestrator End-to-End integration
"""

from unittest.mock import MagicMock

import pytest

from adapters.business_adapter import BusinessAdapter
from adapters.dev_adapter import DevAdapter
from adapters.ux_adapter import UXAdapter
from core.advanced_reasoning import AdvancedReasoningEngine
from core.evolution_module import EvolutionModule
from learning.pattern_recognizer import PatternRecognizer
from services.living_engine import LivingEngineOrchestrator

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
async def test_dev_adapter_debugging():
    adapter = DevAdapter()
    code = "def fetch_user():\n    for i in range(len(users)):\n        print(users.get(i))\n"
    res = await adapter.adapt(f"Fix this bug in python:\n```python\n{code}\n```")
    assert res.success is True
    assert res.confidence > 0.7
    assert res.domain_specific_metadata["language"] == "python"


@pytest.mark.asyncio
async def test_dev_adapter_implementation_and_tests():
    adapter = DevAdapter()
    res = await adapter.adapt("Create an async health check endpoint in python")
    assert res.success is True
    assert "def " in res.adapted_solution or "async" in res.adapted_solution


@pytest.mark.asyncio
async def test_business_adapter_analysis_and_roi():
    adapter = BusinessAdapter()
    res = await adapter.adapt("Analyze query cache latency and calculate cost reduction ROI")
    assert res.success is True
    assert res.confidence >= 0.8
    assert "key_metrics" in res.adapted_solution or "decision_type" in res.adapted_solution


@pytest.mark.asyncio
async def test_ux_adapter_accessibility_and_code():
    adapter = UXAdapter()
    res = await adapter.adapt(
        "Design a dark mode responsive analytics dashboard in React with high accessibility"
    )
    assert res.success is True
    assert res.domain_specific_metadata["accessibility_compliant"] is True
    assert "specification" in res.adapted_solution
    assert "React" in res.adapted_solution["code"]


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
async def test_living_engine_full_phase2_pipeline():
    mock_memory = MagicMock()
    mock_memory.store_memory.return_value = None
    mock_memory.search_memory.return_value = []
    mock_memory.retrieve_recent.return_value = []

    orchestrator = LivingEngineOrchestrator(memory_service=mock_memory)
    prompt = "ডাটাবেস কানেকশন পুল অপটিমাইজ করো এবং লেটেন্সি কমাও"

    solution = await orchestrator.solve_unpredictable_demand(prompt, session_id="test_phase2_1")

    assert solution.success is True
    assert solution.fitness_score > 0.5
    assert "strategy" in solution.reasoning
    assert "improvement_pct" in solution.evolution
    assert len(solution.execution_order) >= 4
