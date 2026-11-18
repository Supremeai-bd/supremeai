"""Tests for HybridTopAIDetector (30-min proactive probe + instant reactive failover)."""

import pytest

from core.llm.top_ai_detector import HybridTopAIDetector


@pytest.mark.asyncio
async def test_proactive_probe_ranks_by_latency_and_caches(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")

    calls = []

    async def fake_prober(provider_id: str, _key: str):
        calls.append(provider_id)
        latencies = {"groq": 120.0, "gemini": 80.0, "deepseek": 250.0}
        return True, latencies.get(provider_id, 500.0), None

    detector = HybridTopAIDetector(probe_interval_seconds=1800, custom_prober=fake_prober)

    top = await detector.refresh_if_stale()
    assert top == ["gemini", "groq", "deepseek"]
    initial_calls = len(calls)

    # Second call within 30 mins should use cache (no extra probes)
    top_cached = await detector.refresh_if_stale()
    assert top_cached == ["gemini", "groq", "deepseek"]
    assert len(calls) == initial_calls


@pytest.mark.asyncio
async def test_instant_reactive_demotion_on_error(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")

    async def fake_prober(provider_id: str, _key: str):
        return True, (50.0 if provider_id == "gemini" else 100.0), None

    detector = HybridTopAIDetector(cooldown_seconds=300, custom_prober=fake_prober)
    assert await detector.refresh_if_stale() == ["gemini", "groq"]

    # Simulate 429 rate limit on gemini during a live user request
    updated = detector.report_error("gemini", "HTTP 429")
    assert updated == ["groq"]

    # Recover gemini
    detector.report_success("gemini", latency_ms=40.0)
    assert detector.get_top_providers() == ["gemini", "groq"]
