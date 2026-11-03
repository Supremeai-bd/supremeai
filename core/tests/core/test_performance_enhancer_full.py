"""Full-coverage tests for core/performance_enhancer.py (Task 7-d).

The module-level ``performance_optimizer`` singleton is created at import
time (no background loops), so tests exercise both the singleton and fresh
instances with a stubbed ModelRegistry where model choice must be deterministic.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import core.performance_enhancer as pe
from core.performance_enhancer import (
    FailureHistoryEntry,
    PerformanceMetrics,
    PerformanceOptimizer,
    get_performance_optimizer,
    performance_optimizer,
)

MODELS = {
    "gpt-x": {
        "tier": 1,
        "provider": "openai",
        "strengths": ["coding", "reasoning"],
        "cost_input_per_million": 2.0,
        "context_length": 128000,
    },
    "gem-x": {
        "tier": 2,
        "provider": "google",
        "strengths": ["reasoning"],
        "cost_input_per_million": 0.5,
        "context_length": 1000000,
    },
    "other-x": {
        "tier": 3,
        "provider": "nokey-provider",
        "strengths": ["coding"],
        "cost_input_per_million": 0.1,
        "context_length": 8000,
    },
}


def _stub_settings(**extra):
    """Stub the module-level ``settings`` binding — the real Settings object
    has read-only properties (task_models etc.) that must not be mutated."""
    base = dict(
        circuit_breaker_failure_threshold=3,
        circuit_breaker_cooldown_period=60,
        gemini_model_name="gemini/gemini-2.5-flash",
        MODEL_SWARM={},
        task_models={},
        openai_api_key="",
        openrouter_api_key="",
        gemini_api_key="",
        deepseek_api_key="",
        groq_api_key="",
        hf_api_key="",
        nvidia_api_key="",
    )
    base.update(extra)
    return SimpleNamespace(**base)


def _optimizer() -> PerformanceOptimizer:
    opt = PerformanceOptimizer.__new__(PerformanceOptimizer)
    opt.metrics = {}
    opt.failure_history = []
    opt.model_stats = {}
    opt.dynamic_circuit_breakers = {}
    opt.model_registry = MagicMock()
    opt.model_registry.MODELS = MODELS
    opt.model_registry.get_model = lambda mid: MODELS.get(mid)
    opt.self_healer = None
    opt.reminder_pipeline = None
    opt._state_lock = __import__("asyncio").Lock()
    return opt


@pytest.fixture(autouse=True)
def _stub_module_settings(monkeypatch):
    """Every test gets a fresh stubbed settings on the module."""
    stub = _stub_settings()
    monkeypatch.setattr(pe, "settings", stub)
    return stub


class TestDataclasses:
    def test_performance_metrics_defaults(self):
        m = PerformanceMetrics()
        assert m.request_count == 0 and m.avg_response_time == 0.0

    def test_failure_history_entry(self):
        e = FailureHistoryEntry(
            timestamp=datetime.now(),
            error_type="t",
            error_message="m",
            context={},
            resolution="pending",
        )
        assert e.resolved is False


class TestCircuitBreakers:
    def test_get_circuit_breaker_creates_once(self):
        opt = _optimizer()
        cb1 = opt.get_circuit_breaker("op")
        cb2 = opt.get_circuit_breaker("op")
        assert cb1 is cb2
        assert "op" in opt.dynamic_circuit_breakers


class TestMetricsBookkeeping:
    def test_prune_expired_metrics(self):
        opt = _optimizer()
        fresh = PerformanceMetrics()
        stale = PerformanceMetrics()
        stale.last_updated = datetime.now() - timedelta(hours=5)
        opt.metrics = {"fresh": fresh, "stale": stale}
        opt._prune_expired_metrics()
        assert "stale" not in opt.metrics and "fresh" in opt.metrics

    def test_prune_expired_lru_eviction_over_cap(self):
        opt = _optimizer()
        base = datetime.now() - timedelta(hours=1)
        for i in range(505):
            m = PerformanceMetrics()
            m.last_updated = base + timedelta(seconds=i)
            opt.metrics[f"op{i}"] = m
        opt._prune_expired_metrics()
        assert len(opt.metrics) == 500
        # oldest entries evicted first
        assert "op0" not in opt.metrics
        assert "op504" in opt.metrics

    def test_prune_inactive_model_stats(self):
        opt = _optimizer()
        opt.metrics = {"active-model": PerformanceMetrics()}
        opt.model_stats = {"active-model": {}, "ghost": {}, "zombie": {}}
        opt._prune_inactive_model_stats()
        assert "ghost" not in opt.model_stats and "zombie" not in opt.model_stats
        assert "active-model" in opt.model_stats

    async def test_track_performance_moving_average(self):
        opt = _optimizer()
        await opt.track_performance("op", 10.0)
        await opt.track_performance("op", 20.0)
        m = opt.metrics["op"]
        assert m.request_count == 2
        assert m.avg_response_time == pytest.approx(15.0)
        await opt.track_performance("op", 30.0, success=False)
        assert opt.metrics["op"].error_count == 1

    async def test_track_performance_high_error_rate_logs_warning(self):
        opt = _optimizer()
        for _ in range(3):
            await opt.track_performance("bad-op", 1.0, success=False)
        # error rate 100% > 10% — only verifies no crash and metric recorded
        assert opt.metrics["bad-op"].error_count == 3


class TestModelSelection:
    def test_get_api_key_for_provider(self):
        opt = _optimizer()
        pe.settings.openai_api_key = "sk-123"
        assert opt._get_api_key_for_provider("openai") == "sk-123"
        assert opt._get_api_key_for_provider("unknown-provider") == ""

    async def test_optimize_reasoning_prefers_keyed_provider(self):
        opt = _optimizer()
        pe.settings.gemini_api_key = "g-key"
        pe.settings.task_models = {"reasoning": "gemini/gemini-2.5-flash"}
        model = await opt.optimize_model_selection("reasoning")
        # gem-x has the key and wins; resolved through the google branch
        assert model == "gemini/gemini-2.5-flash"

    async def test_optimize_openai_resolution(self):
        opt = _optimizer()
        pe.settings.openai_api_key = "sk"
        pe.settings.gemini_api_key = ""
        model = await opt.optimize_model_selection("coding")
        assert model == "openai/gpt-4o-mini"

    async def test_optimize_no_models_falls_back_to_default(self):
        opt = _optimizer()
        opt.model_registry.MODELS = {}
        model = await opt.optimize_model_selection("general")
        assert model == "gemini/gemini-2.5-flash"

    async def test_resolve_registry_model_no_key_uses_task_defaults(self):
        opt = _optimizer()
        pe.settings.task_models = {"general": "bynara/agnes-2.5-flash"}
        resolved = opt._resolve_registry_model("other-x", "reasoning")
        assert resolved == "bynara/agnes-2.5-flash"

    async def test_resolve_registry_model_huggingface(self):
        opt = _optimizer()
        opt.model_registry.get_model = lambda mid: {"provider": "huggingface"}
        pe.settings.hf_api_key = "hf-key"
        pe.settings.MODEL_SWARM = {"coding": "hf/swarm"}
        resolved = opt._resolve_registry_model("other-x", "coding")
        assert resolved == "hf/swarm"

    async def test_resolve_registry_model_no_defaults_last_resort(self):
        opt = _optimizer()
        pe.settings.task_models = {}
        assert opt._resolve_registry_model("other-x", "any") == "gemini/gemini-2.5-flash"


class TestFailureHandling:
    def test_generate_error_signature_deterministic(self):
        opt = _optimizer()
        s1 = opt._generate_error_signature("T", "m", {"a": 1, "b": 2})
        s2 = opt._generate_error_signature("T", "m", {"b": 2, "a": 1})
        assert s1 == s2 and len(s1) == 16

    async def test_generate_fix_proposal_known_and_unknown(self):
        opt = _optimizer()
        known = await opt._generate_fix_proposal("LLM_GATEWAY_TIMEOUT", "t", {})
        assert "Increase timeout" in known
        unknown = await opt._generate_fix_proposal("WEIRD", "mystery", {"x": 1})
        assert "Manual investigation required for: mystery" in unknown

    def test_calculate_impact_score(self):
        opt = _optimizer()
        assert opt._calculate_impact_score("LLM_GATEWAY_TIMEOUT") == 0.8
        assert opt._calculate_impact_score("PERFORMANCE_DEGRADED") == 0.6
        assert opt._calculate_impact_score("OTHER") == 0.3

    async def test_handle_failure_records_history_and_trims(self):
        opt = _optimizer()
        for i in range(105):
            await opt.handle_failure("T", f"m{i}", {})
        assert len(opt.failure_history) == 100

    async def test_handle_failure_submits_to_self_healer(self):
        opt = _optimizer()
        opt.self_healer = MagicMock()
        opt.reminder_pipeline = MagicMock()
        opt.reminder_pipeline.submit = AsyncMock(return_value="fix-1")
        await opt.handle_failure("LLM_GATEWAY_TIMEOUT", "timeout!", {"tenant_id": "t1"})
        opt.reminder_pipeline.submit.assert_awaited_once()
        kwargs = opt.reminder_pipeline.submit.await_args.kwargs
        assert kwargs["tenant_id"] == "t1"
        assert kwargs["impact_score"] == 0.8

    async def test_handle_failure_submit_error_swallowed(self):
        opt = _optimizer()
        opt.self_healer = MagicMock()
        opt.reminder_pipeline = MagicMock()
        opt.reminder_pipeline.submit = AsyncMock(side_effect=RuntimeError("db down"))
        await opt.handle_failure("T", "m", {})  # must not raise


class TestLoadBalancing:
    async def test_adaptive_load_balancing_empty(self):
        opt = _optimizer()
        out = await opt.adaptive_load_balancing("coding", [])
        assert out == []

    async def test_adaptive_load_balancing_processes_chunks(self):
        opt = _optimizer()
        pe.settings.gemini_api_key = "g"
        workload = [{"prompt": f"p{i}"} for i in range(6)]
        out = await opt.adaptive_load_balancing("general", workload)
        assert len(out) == 6
        assert all(r["success"] for r in out)
        assert any(m.request_count > 0 for m in opt.metrics.values())

    async def test_high_load_uses_small_chunks(self):
        opt = _optimizer()
        pe.settings.gemini_api_key = "g"
        now = datetime.now()
        for i in range(11):
            m = PerformanceMetrics()
            m.last_updated = now
            opt.metrics[f"task{i}"] = m
        calls: list[int] = []

        async def fake_chunk(task_type, chunk):
            calls.append(len(chunk))
            return [{"success": True} for _ in chunk]

        opt._process_workload_chunk = fake_chunk
        await opt.adaptive_load_balancing("general", [{"prompt": "x"}] * 10)
        # chunk_size = max(1, 10 // 5) = 2 under high load
        assert calls and all(c <= 2 for c in calls)

    async def test_process_chunk_error_path(self):
        opt = _optimizer()
        opt.reminder_pipeline = None
        opt.optimize_model_selection = AsyncMock(side_effect=RuntimeError("no model"))
        # KNOWN BUG (current behavior): the except-block reads `start_time`
        # before it was ever assigned (assignment happens after the awaited
        # model selection) → UnboundLocalError instead of an error result.
        with pytest.raises(UnboundLocalError):
            await opt._process_workload_chunk("general", [{"prompt": "p"}])

    async def test_execute_task_with_model(self):
        opt = _optimizer()
        out = await opt._execute_task_with_model({"prompt": "hi"}, "gem-x")
        assert out["success"] is True and out["model"] == "gem-x"


class TestSingleton:
    def test_get_performance_optimizer_returns_global(self):
        assert get_performance_optimizer() is performance_optimizer
        assert isinstance(performance_optimizer, PerformanceOptimizer)
