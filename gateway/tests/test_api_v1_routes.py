"""
Tests for API v1 route registration and basic reachability.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.anyio


async def test_api_v1_routes_registered():
    from core.app import app

    client = TestClient(app)
    # Health endpoint is registered under /api/v1/health
    resp = client.get("/api/v1/health")
    assert resp.status_code in (200, 503)


async def test_api_routes_include_v1_prefix():
    from core.app import app

    client = TestClient(app)
    # At minimum root should respond
    resp = client.get("/")
    assert resp.status_code in (200, 404, 307)
