"""P0 — Canonical health endpoint contract tests.

বাংলা: ক্যানোনিক্যাল প্রোডাকশন হেলথ কন্ট্রাক্ট —

    GET /health          → aggregate health (compose scraper probe, docs)
    GET /health/live     → liveness  (Dockerfile HEALTHCHECK, compose core)
    GET /health/ready    → readiness (compose worker, Render dashboard)

/api/v1/health/* রাউটগুলো লিগ্যাসি অ্যালায়েস — সাপোর্ট থাকবে, কিন্তু
অপারেশনাল source of truth হলো /health/*। এই টেস্ট দুই প্রিফিক্সের
কন্ট্রাক্ট লক করে যাতে ভবিষ্যতে রিফ্যাক্টরে কেউ ভাঙতে না পারে।

আরও দেখুন: docs/deployment/HEALTH_CONTRACT.md
"""

import pytest
from fastapi.testclient import TestClient

from core.app import app


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Canonical: /health, /health/live, /health/ready
# ---------------------------------------------------------------------------


def test_canonical_health_root(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "status" in resp.json()


def test_canonical_liveness(client):
    resp = client.get("/health/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["alive"] is True
    assert data["status"] == "alive"


def test_canonical_readiness(client):
    resp = client.get("/health/ready")
    assert resp.status_code in (200, 503)  # 503 is valid readiness semantics
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("ready", "degraded", "not_ready", "unhealthy")


def test_canonical_full_health(client):
    resp = client.get("/health/full")
    assert resp.status_code == 200
    assert "status" in resp.json()


# ---------------------------------------------------------------------------
# Legacy alias: /api/v1/health/* (documented, kept for backward compat)
# ---------------------------------------------------------------------------


def _contract_fields(body: dict) -> dict:
    """Payload minus the wall-clock timestamp.

    The health payloads embed a timestamp with 1-second resolution; two
    separate requests (canonical + legacy) can straddle a second boundary
    (seen live on CI run 34825462035), so full-body dict equality is racy.
    Equality is asserted on the contract fields; timestamp presence is
    asserted separately — the timestamp FORMAT contract is locked by the
    canonical-endpoint tests above.
    """
    return {k: v for k, v in body.items() if k != "timestamp"}


def test_legacy_alias_liveness_equivalent(client):
    canonical = client.get("/health/live")
    legacy = client.get("/api/v1/health/live")
    assert legacy.status_code == canonical.status_code
    assert _contract_fields(legacy.json()) == _contract_fields(canonical.json())
    assert "timestamp" in legacy.json()
    assert "timestamp" in canonical.json()


def test_legacy_alias_readiness_equivalent(client):
    canonical = client.get("/health/ready")
    legacy = client.get("/api/v1/health/ready")
    assert legacy.status_code == canonical.status_code
    assert _contract_fields(legacy.json()) == _contract_fields(canonical.json())
    assert "timestamp" in legacy.json()
    assert "timestamp" in canonical.json()


def test_legacy_alias_full_equivalent(client):
    canonical = client.get("/health/full")
    legacy = client.get("/api/v1/health/full")
    assert legacy.status_code == canonical.status_code


def test_legacy_alias_root_equivalent(client):
    # বাংলা (#4223): bare alias-ও চুক্তির অংশ — deploy-train/cloudflare-জাতীয়
    # consumer আগে bare /api/v1/health প্রোব করত; এই টেস্ট ছাড়া bare-alias
    # equivalence লক ছিল না (শুধু /live /ready /full ছিল) — drift-শ্রেণির ফাঁক।
    # aggregate /health-এর cache_hit/cache_age_seconds রানটাইম-অবস্থা (দ্বিতীয়
    # কলে cache-hit) — timestamp-রেস-শ্রেণির মতোই চুক্তি-ফিল্ড নয়, বাদ যায়।
    def _strip_volatile(body: dict) -> dict:
        volatile = ("timestamp", "cache_age_seconds", "cache_hit")
        return {k: v for k, v in body.items() if k not in volatile}

    canonical = client.get("/health")
    legacy = client.get("/api/v1/health")
    assert legacy.status_code == canonical.status_code
    assert _strip_volatile(legacy.json()) == _strip_volatile(canonical.json())
    assert "timestamp" in legacy.json()
    assert "cache_hit" in legacy.json()  # চুক্তি-আকৃতিতে ক্যাশ-ফিল্ডও থাকে


# ---------------------------------------------------------------------------
# Root metadata must advertise the canonical path
# ---------------------------------------------------------------------------


def test_root_advertises_canonical_health(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json().get("health_check") == "/health"
