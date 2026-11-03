from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


def test_health_endpoint_returns_json(client):
    resp = client.get("/health")
    assert resp.headers.get("content-type") == "application/json"


def test_health_endpoint_keys(client):
    resp = client.get("/health")
    data = resp.json()
    assert "status" in data


def test_health_endpoint_status_values(client):
    resp = client.get("/health")
    data = resp.json()
    assert data["status"] in ("ok", "healthy", "degraded")


def test_health_endpoint_degraded_status(client, monkeypatch):
    # FIX(#1097): rewritten for the current checks-registry architecture.
    # The old approach patched core.app.settings (module no longer exposes it);
    # degraded is now computed by _compute_overall from registered checks —
    # a failing NON-critical check yields overall "degraded" (503 body says so).
    import core.health_routes as hr
    from core.health_routes import HealthCheck

    monkeypatch.setattr(
        hr,
        "_checks",
        [HealthCheck(name="always-failing-noncritical", check_fn=lambda: False, critical=False)],
        raising=True,
    )
    monkeypatch.setattr(hr, "_health_cache_payload", None, raising=True)

    resp = client.get("/health")
    data = resp.json()
    assert data["status"] == "degraded"
    # Contract: non-critical failure degrades but is honestly reported as 503.
    assert resp.status_code == 503
    assert any(
        c["name"] == "always-failing-noncritical" and c["critical"] is False for c in data["checks"]
    )
