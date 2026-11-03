# backend/tests/api/test_phase4_api_server.py
"""Comprehensive Test Suite for Phase 4 REST API Server.

Tests:
1. Root endpoint metadata
2. Query processing endpoint (/api/v1/process)
3. Health check endpoint (/api/v1/health)
4. System status endpoint (/api/v1/status)
5. Evolution status and trigger endpoints (/api/v1/evolution/*)
6. Memory stats and consolidate endpoints (/api/v1/memory/*)
7. Dashboard endpoint (/api/v1/dashboard)
"""

import pytest
from httpx import ASGITransport, AsyncClient

from api.server import app
from core.integration_layer import get_integrator


@pytest.fixture(autouse=True)
async def setup_integrator():
    import api.server as server_module

    server_module.ai_integrator = await get_integrator()


@pytest.mark.asyncio
async def test_api_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "SupremeAI API"
        assert "endpoints" in data


@pytest.mark.asyncio
async def test_api_process_endpoint(monkeypatch):
    import api.server as server_module

    class DummyFactory:
        async def safe_process(self, query, context=None):
            return {
                "success": True,
                "answer": "def divide(a, b): return a / b if b != 0 else 0",
                "confidence": 0.99,
                "components_used": ["reasoning_engine", "rate_limiter"],
                "provider_used": "mock",
                "rate_limited": False,
            }

    monkeypatch.setattr(server_module, "factory", DummyFactory())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "Debug Python division: def divide(a, b): return a / b",
            "context": {"env": "test"},
        }
        resp = await client.post("/api/v1/process", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["confidence"] > 0
        assert "reasoning_engine" in data["components_used"]


@pytest.mark.asyncio
async def test_api_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ["healthy", "degraded"]


@pytest.mark.asyncio
async def test_api_status_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["initialized"] is True


@pytest.mark.asyncio
async def test_api_evolution_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Status
        resp = await client.get("/api/v1/evolution/status")
        assert resp.status_code == 200

        # Trigger
        resp = await client.post("/api/v1/evolution/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert "cycle_id" in data


@pytest.mark.asyncio
async def test_api_memory_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Stats
        resp = await client.get("/api/v1/memory/stats")
        assert resp.status_code == 200

        # Consolidate
        resp = await client.post("/api/v1/memory/consolidate")
        assert resp.status_code == 200
        data = resp.json()
        assert "blocks_affected" in data


@pytest.mark.asyncio
async def test_api_dashboard_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "system" in data
