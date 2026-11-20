"""Tests for web-surface SSOT (H1), runbook (H4), guards (H6), and runtime controls (S1, S2, S4, S6, S8)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from browser.surface_controls import (
    EngineConcurrencyLimiter,
    TenantSemanticCache,
    TenantSessionAffinity,
    load_surface_concurrency,
    score_response_quality,
)
from gateway.service.providers.web_engines import WEB_ENGINES

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_web_surfaces_yaml_ssot_parity():
    cfg_path = REPO_ROOT / "config" / "web_surfaces.yaml"
    assert cfg_path.exists(), "H1: config/web_surfaces.yaml must exist"
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    surfaces = data.get("surfaces") or {}
    assert set(surfaces.keys()) == {"duck", "gemini"}

    yaml_providers = set()
    for spec in surfaces.values():
        assert spec["fallback_only"] is True
        assert spec["max_concurrency"] >= 1
        yaml_providers.update(spec["providers"])

    code_providers = {engine.provider for engine in WEB_ENGINES}
    assert yaml_providers == code_providers


def test_web_surfaces_runbook_exists():
    runbook = REPO_ROOT / "docs" / "runbooks" / "web_surfaces.md"
    assert runbook.exists(), "H4: docs/runbooks/web_surfaces.md must exist"
    text = runbook.read_text(encoding="utf-8")
    assert "free_route_policy_tool.py" in text
    assert "/admin/engines" in text


@pytest.mark.asyncio
async def test_s1_concurrency_limiter_caps_in_flight():
    limiter = EngineConcurrencyLimiter({"duck": 2})
    assert limiter.limit_for("duck") == 2
    peak = 0
    current = 0

    async def worker():
        nonlocal peak, current
        async with limiter.acquire("duck"):
            current += 1
            peak = max(peak, current)
            await asyncio.sleep(0.02)
            current -= 1

    await asyncio.gather(*(worker() for _ in range(5)))
    assert peak == 2
    assert limiter.in_flight("duck") == 0


def test_s2_s4_tenant_session_affinity_isolated_and_expires():
    aff = TenantSessionAffinity(ttl_s=60.0)
    aff.set("tenant-a", "sess-1", "duck", now=100.0)
    aff.set("tenant-b", "sess-1", "gemini", now=100.0)

    assert aff.get("tenant-a", "sess-1", now=120.0) == "duck"
    assert aff.get("tenant-b", "sess-1", now=120.0) == "gemini"
    assert aff.get("tenant-a", "sess-1", now=161.0) is None


def test_s6_s4_semantic_cache_isolated_per_tenant_and_ttl():
    cache = TenantSemanticCache(ttl_s=30.0)
    cache.set("t1", "duck-claude", "Hello   World", "resp-t1", now=10.0)
    cache.set("t2", "duck-claude", "hello world", "resp-t2", now=10.0)

    assert cache.get("t1", "duck-claude", "hello world", now=20.0) == "resp-t1"
    assert cache.get("t2", "duck-claude", "HELLO WORLD", now=20.0) == "resp-t2"
    assert cache.get("t1", "duck-claude", "hello world", now=41.0) is None


def test_s8_quality_scorer_flags_bad_responses():
    assert score_response_quality("") == 0.0
    assert score_response_quality("ok") == 0.2
    assert score_response_quality("Cloudflare access denied") == 0.3
    assert score_response_quality("Here is a complete, helpful answer.") == 1.0


def test_load_surface_concurrency_reads_yaml():
    limits = load_surface_concurrency(REPO_ROOT / "config" / "web_surfaces.yaml")
    assert limits == {"duck": 4, "gemini": 2}
