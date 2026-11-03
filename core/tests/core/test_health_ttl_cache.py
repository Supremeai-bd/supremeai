"""Tests for the #468 health TTL cache.

বাংলা: হেলথ ক্যাশ শুধু সম্পূর্ণ HEALTHY (200) ফল ক্যাশ করে — degraded/
unhealthy ফল কখনোই ক্যাশ হয় না, তাই incident detection কখনো দেরিতে হয় না।
Hit হলে cache_hit/cache_age_seconds সৎভাবে জানায়।

These tests import the route module directly (importlib) so they can
drive `_checks` and the cache deterministically without a live DB.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "backend" / "core" / "health_routes.py"

_spec = importlib.util.spec_from_file_location("health_routes_468", MODULE_PATH)
health_routes = importlib.util.module_from_spec(_spec)
sys.modules["health_routes_468"] = health_routes
_spec.loader.exec_module(health_routes)


@pytest.fixture(autouse=True)
def _reset_state():
    health_routes.reset_health_cache()
    health_routes._checks.clear()
    health_routes._liveness_status = True
    yield
    health_routes.reset_health_cache()
    health_routes._checks.clear()


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_routes.router, prefix="/api/v1/health")
    return app


def _client() -> TestClient:
    return TestClient(_app())


def test_first_call_is_uncached_second_is_hit() -> None:
    calls = {"n": 0}

    async def db_ok() -> bool:
        calls["n"] += 1
        return True

    health_routes.register_check("database", db_ok, critical=True)
    client = _client()

    r1 = client.get("/api/v1/health")
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["cache_hit"] is False
    assert body1["status"] == "healthy"

    r2 = client.get("/api/v1/health")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["cache_hit"] is True
    assert body2["cache_age_seconds"] >= 0.0
    # The check function must NOT have been re-executed on the cache hit.
    assert calls["n"] == 1
    # Cached payload must not carry stale honest-marker fields inside it.
    assert "cache_hit" not in health_routes._health_cache_payload


def test_unhealthy_result_is_never_cached() -> None:
    healthy = {"v": True}

    async def flaky_db() -> bool:
        return healthy["v"]

    health_routes.register_check("database", flaky_db, critical=True)
    client = _client()

    ok = client.get("/api/v1/health")
    assert ok.status_code == 200
    assert ok.json()["cache_hit"] is False

    # A fully-healthy response IS cached — verify hit, then flip to failure.
    hit = client.get("/api/v1/health")
    assert hit.json()["cache_hit"] is True

    healthy["v"] = False
    # TTL still valid, but the cached entry was healthy; the next call MUST
    # NOT serve stale healthy data after the cache is invalidated by the
    # failing outcome path. Force expiry to simulate the monitor window.
    health_routes._health_cache_monotonic -= health_routes._HEALTH_CACHE_TTL_SECONDS + 1

    down = client.get("/api/v1/health")
    assert down.status_code == 503
    assert down.json()["cache_hit"] is False
    assert down.json()["status"] == "unhealthy"

    # Recovery: healthy again — and the failing response was NOT cached, so
    # the fresh run detects recovery immediately.
    healthy["v"] = True
    recovered = client.get("/api/v1/health")
    assert recovered.status_code == 200
    assert recovered.json()["cache_hit"] is False
    # And now the healthy result is cached again.
    assert client.get("/api/v1/health").json()["cache_hit"] is True


def test_cache_control_headers_present() -> None:
    health_routes.register_check("database", lambda: True, critical=True)
    client = _client()
    r1 = client.get("/api/v1/health")
    r2 = client.get("/api/v1/health")
    # বাংলা: রাউট কনস্ট্যান্ট থেকেই হেডার তৈরি হয় — টেস্টও সেই সত্য-উৎস থেকেই
    # দাবি করুক (#468: TTL 10s→15s হলেও এই টেস্ট আর ভাঙবে না)।
    ttl = int(health_routes._HEALTH_CACHE_TTL_SECONDS)
    for r in (r1, r2):
        assert f"max-age={ttl}" in r.headers["Cache-Control"]
        assert f"stale-while-revalidate={ttl * 2}" in r.headers["Cache-Control"]


def test_expired_cache_reruns_checks() -> None:
    calls = {"n": 0}

    async def db_ok() -> bool:
        calls["n"] += 1
        return True

    health_routes.register_check("database", db_ok, critical=True)
    client = _client()
    client.get("/api/v1/health")
    # Expire the entry manually (no real sleep in tests).
    health_routes._health_cache_monotonic -= health_routes._HEALTH_CACHE_TTL_SECONDS + 1
    client.get("/api/v1/health")
    assert calls["n"] == 2


def test_reset_health_cache_forces_fresh_run() -> None:
    calls = {"n": 0}

    async def db_ok() -> bool:
        calls["n"] += 1
        return True

    health_routes.register_check("database", db_ok, critical=True)
    client = _client()
    client.get("/api/v1/health")
    health_routes.reset_health_cache()
    body = client.get("/api/v1/health").json()
    assert calls["n"] == 2
    assert body["cache_hit"] is False
