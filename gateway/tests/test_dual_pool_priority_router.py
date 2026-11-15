"""Unit tests for gateway.dual_pool_priority_router."""

from __future__ import annotations

from gateway.dual_pool_priority_router import (
    DualPoolPriorityRouter,
    KeySlot,
    PoolModelEntry,
)


def _sample_models() -> list[PoolModelEntry]:
    return [
        PoolModelEntry(
            model_id="api-spark",
            provider="groq",
            pool="supremeai-api",
            capabilities=("spark", "general"),
            active_model_name="qwen/qwen3.8-27b",
            latency_ms=300.0,
            keys=[KeySlot("groq_1", "GROQ_API_KEY_1"), KeySlot("groq_2", "GROQ_API_KEY_2")],
        ),
        PoolModelEntry(
            model_id="api-reasoning",
            provider="openrouter",
            pool="supremeai-api",
            capabilities=("reasoning", "general"),
            active_model_name="nvidia/nemotron-3.5-lightning:free",
            latency_ms=500.0,
            keys=[KeySlot("or_1", "OPENROUTER_API_KEY_1")],
        ),
        PoolModelEntry(
            model_id="web-architect",
            provider="claude_web",
            pool="supremeai-web",
            capabilities=("reasoning", "design"),
            active_model_name="core-architect",
            latency_ms=900.0,
            keys=[KeySlot("stealth_1", "STEALTH_WEBHOOK_URL")],
        ),
    ]


def test_task_fit_and_lowest_latency_selection():
    router = DualPoolPriorityRouter(models=_sample_models())
    # Spark picks api-spark (300ms)
    pick_spark = router.select_best_model("spark")
    assert pick_spark is not None
    assert pick_spark[0].model_id == "api-spark"

    # Reasoning picks api-reasoning (500ms < 900ms)
    pick_reason = router.select_best_model("reasoning")
    assert pick_reason is not None
    assert pick_reason[0].model_id == "api-reasoning"


def test_multi_key_rotation_and_instant_promotion():
    now = [1000.0]
    router = DualPoolPriorityRouter(models=_sample_models(), clock=lambda: now[0])

    # Exhaust groq_1 -> rotates to groq_2, api-spark stays Rank 1
    router.report_outcome("api-spark", "groq_1", success=False, latency_ms=300.0, status_code=429)
    pick = router.select_best_model("spark")
    assert pick is not None
    assert pick[0].model_id == "api-spark"
    assert pick[1].alias == "groq_2"

    # Exhaust groq_2 -> all keys exhausted, api-reasoning (500ms) promoted to Rank 1
    router.report_outcome("api-spark", "groq_2", success=False, latency_ms=300.0, status_code=429)
    telemetry = router.get_live_telemetry()
    assert telemetry["priority_list"][0]["model_id"] == "api-reasoning"
    assert telemetry["priority_list"][0]["status"] == "ACTIVE_TOP"
    assert telemetry["priority_list"][-1]["model_id"] == "api-spark"
    assert telemetry["priority_list"][-1]["status"] == "RATE_LIMITED"


def test_background_recheck_recovers_to_top():
    now = [1000.0]
    router = DualPoolPriorityRouter(models=_sample_models(), clock=lambda: now[0])

    # Exhaust both keys of api-spark
    router.report_outcome("api-spark", "groq_1", False, 300.0, 429)
    router.report_outcome("api-spark", "groq_2", False, 300.0, 429)
    assert router.get_live_telemetry()["priority_list"][0]["model_id"] == "api-reasoning"

    # Advance past cooldown and run background recheck with fast latency (250ms)
    now[0] += 400.0
    router.run_background_recheck(lambda m, s: (True, 250.0 if m.model_id == "api-spark" else 600.0, 200, None))
    telemetry = router.get_live_telemetry()
    assert telemetry["priority_list"][0]["model_id"] == "api-spark"
    assert telemetry["priority_list"][0]["status"] == "ACTIVE_TOP"
    assert telemetry["key_pool_health"]["api-spark"]["healthy_keys"] == 2
