import pytest
from fastapi.testclient import TestClient

from gateway.main import create_app
from tests.test_streaming_gateway import base_config


def test_unified_submodules_health():
    app = create_app(config=base_config())
    client = TestClient(app)

    # Root health
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "supremeai-api"
    assert data["modules"]["gateway"] == "healthy"
    assert data["modules"]["command"] == "healthy"
    assert data["modules"]["agents"] == "healthy"
    assert data["modules"]["skills"] == "healthy"
    assert data["modules"]["mcp"] == "healthy"

    # Command health
    r = client.get("/command/health")
    assert r.status_code == 200
    assert r.json()["service"] == "command"

    # Agents health
    r = client.get("/agents/health")
    assert r.status_code == 200
    assert r.json()["service"] == "agents"

    # Skills health
    r = client.get("/skills/health")
    assert r.status_code == 200
    assert r.json()["service"] == "skills"

    # MCP health and tools
    r = client.get("/mcp/health")
    assert r.status_code == 200
    assert r.json()["service"] == "mcp"

    r = client.get("/mcp/tools")
    assert r.status_code == 200
    assert "tools" in r.json()
