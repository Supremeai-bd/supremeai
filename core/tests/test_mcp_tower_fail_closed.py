"""Offline MCP and Render control regressions; no live services contacted."""
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.routes import mcp_tower as tower


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(tower.router)
    app.dependency_overrides[tower.get_current_admin] = lambda: {"id": "test-admin"}
    app.dependency_overrides[tower.get_current_user_token] = lambda: "test-user"
    monkeypatch.setattr(tower, "TOWER_URL", "https://example.test/mcp")
    monkeypatch.setattr(tower, "TOWER_TOKEN", "test-token")
    return TestClient(app)


def use_transport(monkeypatch, handler):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(tower.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))


def test_notification_failure_prevents_tool_call(client, monkeypatch):
    methods = []
    def handler(request):
        import json
        method = json.loads(request.content)["method"]
        methods.append(method)
        if method == "notifications/initialized":
            return httpx.Response(503, text="secret internal detail")
        return httpx.Response(200, json={"result": {}})
    use_transport(monkeypatch, handler)
    response = client.post("/api/mcp-tower/probe")
    assert response.status_code == 502
    assert response.json()["detail"] == "Tower initialization failed"
    assert methods == ["initialize", "notifications/initialized"]


@pytest.mark.parametrize("payload", [
    {"jsonrpc": "2.0", "id": 2, "error": {"message": "secret"}},
    {"jsonrpc": "2.0", "id": 2, "result": {"isError": True, "content": [{"text": "secret"}]}},
    {"jsonrpc": "2.0", "id": 2},
    [],
])
def test_tool_errors_never_become_success(client, monkeypatch, payload):
    def handler(request):
        import json
        method = json.loads(request.content)["method"]
        if method == "tools/call":
            return httpx.Response(200, json=payload)
        return httpx.Response(200, json={"result": {}})
    use_transport(monkeypatch, handler)
    response = client.post("/api/mcp-tower/probe")
    assert response.status_code == 502
    assert "secret" not in response.text


def test_successful_handshake_returns_actual_health(client, monkeypatch):
    methods = []
    def handler(request):
        import json
        method = json.loads(request.content)["method"]
        methods.append(method)
        if method == "tools/call":
            return httpx.Response(200, json={"result": {"content": [{"text": '{"services": []}'}]}})
        return httpx.Response(200, json={"result": {}})
    use_transport(monkeypatch, handler)
    response = client.post("/api/mcp-tower/probe")
    assert response.status_code == 200 and response.json() == {"services": []}
    assert methods == ["initialize", "notifications/initialized", "tools/call"]


def test_reboot_rejects_missing_controls_and_unknown_service(client, monkeypatch):
    fetch = AsyncMock(return_value=[{"id": "render-core"}])
    monkeypatch.setattr(tower, "_fetch_services", fetch)
    monkeypatch.setattr(tower, "RENDER_API_KEY", "")
    for env in ("RENDER_CORE_SERVICE_ID", "RENDER_PRIMARY_SVC_ID", "RENDER_API_KEY_1"):
        monkeypatch.delenv(env, raising=False)
    assert client.post("/api/mcp-tower/reboot", json={"serviceId": "render-core"}).status_code == 503
    assert client.post("/api/mcp-tower/reboot", json={"serviceId": "other"}).status_code == 404
    assert client.post("/api/mcp-tower/reboot-all").status_code == 501
    fetch.assert_not_awaited()


def test_reboot_only_reports_render_acceptance(client, monkeypatch):
    monkeypatch.setenv("RENDER_CORE_SERVICE_ID", "service-test")
    monkeypatch.setenv("RENDER_API_KEY_1", "secret-token")
    fetch = AsyncMock(return_value=[{"id": "render-core"}])
    monkeypatch.setattr(tower, "_fetch_services", fetch)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(202)
    use_transport(monkeypatch, handler)
    response = client.post("/api/mcp-tower/reboot", json={"serviceId": "render-core"})
    assert response.status_code == 200
    assert response.json()["restart_status"] == "accepted"
    assert len(calls) == 1 and calls[0].url.path == "/v1/services/service-test/restart"


def test_reboot_failure_is_redacted_and_not_retried(client, monkeypatch):
    monkeypatch.setenv("RENDER_CORE_SERVICE_ID", "service-test")
    monkeypatch.setenv("RENDER_API_KEY_1", "secret-token")
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(tower, "_fetch_services", fetch)
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret-token", request=request)
    use_transport(monkeypatch, handler)
    response = client.post("/api/mcp-tower/reboot", json={"serviceId": "render-core"})
    assert response.status_code == 502
    assert "secret-token" not in response.text
    assert len(calls) == 1
    fetch.assert_not_awaited()


def test_reboot_requires_real_admin_dependency(client):
    client.app.dependency_overrides.pop(tower.get_current_admin)
    client.app.dependency_overrides.pop(tower.get_current_user_token)
    response = client.post("/api/mcp-tower/reboot-all")
    assert response.status_code in (401, 403)


def test_accepted_restart_with_telemetry_failure_warns_against_retry(client, monkeypatch):
    monkeypatch.setenv("RENDER_CORE_SERVICE_ID", "service-test")
    monkeypatch.setenv("RENDER_API_KEY_1", "test-token")
    monkeypatch.setattr(tower, "_fetch_services", AsyncMock(side_effect=RuntimeError("sensitive")))
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(202)
    use_transport(monkeypatch, handler)
    response = client.post("/api/mcp-tower/reboot", json={"serviceId": "render-core"})
    assert response.status_code == 502
    assert "Restart accepted" in response.text and "reconcile before retry" in response.text
    assert "sensitive" not in response.text
    assert len(calls) == 1


def test_notification_transport_failure_is_redacted_and_stops(client, monkeypatch):
    calls = []
    def handler(request):
        import json
        method = json.loads(request.content)["method"]
        calls.append(method)
        if method == "notifications/initialized":
            raise httpx.ReadTimeout("secret-token", request=request)
        return httpx.Response(200, json={"result": {}})
    use_transport(monkeypatch, handler)
    response = client.get("/api/mcp-tower/services")
    assert response.status_code == 502 and "secret-token" not in response.text
    assert calls == ["initialize", "notifications/initialized"]


def test_non_admin_cannot_restart_even_with_service_id(client):
    client.app.dependency_overrides.pop(tower.get_current_admin)
    client.app.dependency_overrides.pop(tower.get_current_user_token)
    assert client.post("/api/mcp-tower/reboot", json={"serviceId": "render-core"}).status_code in (401, 403)
