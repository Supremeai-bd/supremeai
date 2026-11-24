"""Gateway proxy contract for the governed agent tool surface (audit item ⑯).

The gateway does not own the tool loop — core does (``core.tool_loop`` +
``core/api/routes/agent_tools.py``) — and it must not import core internals
(``.importlinter`` contract ``gateway-no-core-private``; the gateway image ships
no ``core/`` tree). So ``/v1/agent/*`` is a *transport* only. This suite pins
that behaviour:

* unauthenticated calls are 401 before anything is forwarded;
* ``CORE_API_URL`` unset in production is a 503, never a fabricated manifest;
* a core 4xx/5xx/unreachable core is surfaced honestly (403/502/503);
* a successful forward returns core's payload unchanged;
* ``chatToolCalling`` on the workspace contract is true only when chat
  tool-calling is genuinely reachable (flag ON *and* core URL configured).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx
import pytest
from starlette.testclient import TestClient

BASE = os.path.dirname(os.path.abspath(__file__))
SAT = os.path.abspath(os.path.join(BASE, "..", ".."))
if SAT not in sys.path:
    sys.path.insert(0, SAT)

try:
    from service.app import app
except ImportError:  # pragma: no cover - package layout fallback
    from gateway.service.app import app

GUEST = {"X-Guest-Mode": "true"}


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, *, non_json: bool = False):
        self.status_code = status_code
        self._payload = payload
        self._non_json = non_json

    def json(self) -> Any:
        if self._non_json:
            raise ValueError("not json")
        return self._payload


class _FakeAsyncClient:
    """Stands in for ``httpx.AsyncClient`` inside ``_forward_agent_request``."""

    calls: list[dict[str, Any]] = []
    response: _FakeResponse | None = None
    raises: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request(self, method, url, headers=None, json=None):
        _FakeAsyncClient.calls.append(
            {"method": method, "url": url, "headers": headers or {}, "json": json}
        )
        if _FakeAsyncClient.raises is not None:
            raise _FakeAsyncClient.raises
        assert _FakeAsyncClient.response is not None
        return _FakeAsyncClient.response


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("SUPREMEAI_TEST_GUEST_BYPASS", "1")
    monkeypatch.setenv("CORE_API_URL", "https://core.test")
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.response = None
    _FakeAsyncClient.raises = None
    return TestClient(app)


# ── authentication ──────────────────────────────────────────────────────────


def test_manifest_requires_auth(client, monkeypatch):
    monkeypatch.delenv("SUPREMEAI_TEST_GUEST_BYPASS", raising=False)
    monkeypatch.delenv("SUPREMEAI_API_KEY", raising=False)
    resp = client.get("/v1/agent/tools")
    assert resp.status_code == 401
    assert _FakeAsyncClient.calls == [], "nothing may be forwarded before auth succeeds"


# ── forwarding ──────────────────────────────────────────────────────────────


def test_manifest_is_forwarded_and_returned_unchanged(client):
    _FakeAsyncClient.response = _FakeResponse(
        200, {"enabled": True, "tools": [{"type": "function"}], "availableCount": 1}
    )
    resp = client.get("/v1/agent/tools", headers={**GUEST, "Authorization": "Bearer tok"})

    assert resp.status_code == 200
    assert resp.json()["availableCount"] == 1
    call = _FakeAsyncClient.calls[-1]
    assert call["method"] == "GET"
    assert call["url"] == "https://core.test/api/agent/tools"
    assert call["headers"]["Authorization"] == "Bearer tok"


def test_tool_call_body_is_forwarded_verbatim(client):
    _FakeAsyncClient.response = _FakeResponse(
        200, {"role": "tool", "name": "search_database", "executed": True, "status": "ok"}
    )
    body = {"tool": "search_database", "arguments": {"query": "x"}, "tool_call_id": "c1"}
    resp = client.post("/api/v1/agent/tool-calls", headers=GUEST, json=body)

    assert resp.status_code == 200
    call = _FakeAsyncClient.calls[-1]
    assert call["method"] == "POST"
    assert call["url"] == "https://core.test/api/agent/tool-calls"
    assert call["json"] == body


def test_non_json_body_is_rejected_before_forwarding(client):
    resp = client.post(
        "/v1/agent/tool-calls", headers={**GUEST, "Content-Type": "application/json"}, content=b"[]"
    )
    assert resp.status_code == 400
    assert _FakeAsyncClient.calls == []


# ── failures are honest ─────────────────────────────────────────────────────


def test_core_url_unset_in_production_is_503(client, monkeypatch):
    monkeypatch.delenv("CORE_API_URL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    resp = client.get("/v1/agent/tools", headers=GUEST)

    assert resp.status_code == 503
    assert "CORE_API_URL" in resp.json()["detail"]
    assert _FakeAsyncClient.calls == []


def test_core_403_is_propagated_with_its_detail(client):
    _FakeAsyncClient.response = _FakeResponse(
        403, {"detail": "agent tool calling is disabled"}
    )
    resp = client.post("/v1/agent/tool-calls", headers=GUEST, json={"tool": "x"})

    assert resp.status_code == 403
    assert resp.json()["detail"] == "agent tool calling is disabled"


def test_core_5xx_becomes_502(client):
    _FakeAsyncClient.response = _FakeResponse(500, {"detail": "boom"})
    resp = client.get("/v1/agent/tools", headers=GUEST)
    assert resp.status_code == 502


def test_unreachable_core_is_503(client):
    _FakeAsyncClient.raises = httpx.ConnectError("no route to host")
    resp = client.get("/v1/agent/tools", headers=GUEST)
    assert resp.status_code == 503
    assert "unreachable" in resp.json()["detail"]


def test_non_json_core_response_is_502(client):
    _FakeAsyncClient.response = _FakeResponse(200, None, non_json=True)
    resp = client.get("/v1/agent/tools", headers=GUEST)
    assert resp.status_code == 502


# ── workspace contract honesty ──────────────────────────────────────────────


def test_workspace_reports_tool_calling_only_when_reachable(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("SUPREMEAI_TEST_GUEST_BYPASS", "1")

    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)
    monkeypatch.delenv("CORE_API_URL", raising=False)
    off = TestClient(app).get("/api/v1/connections/my-workspace", headers=GUEST).json()
    assert off["chatToolCalling"] is False
    assert off["chatToolCallingDetail"]["coreApiConfigured"] is False

    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    flag_only = TestClient(app).get("/api/v1/connections/my-workspace", headers=GUEST).json()
    assert flag_only["chatToolCalling"] is False, "flag without a core URL is not reachable"

    monkeypatch.setenv("CORE_API_URL", "https://core.test")
    on = TestClient(app).get("/api/v1/connections/my-workspace", headers=GUEST).json()
    assert on["chatToolCalling"] is True
    assert on["chatToolCallingDetail"] == {
        "transport": "core-http-proxy",
        "requiresFlag": "SUPREMEAI_AGENT_TOOLS=true",
        "coreApiConfigured": True,
        "scope": "governed SUPREME_TOOLS registry only (policy-gated; no browser automation)",
        "manifest": "/v1/agent/tools",
    }
    # Capabilities themselves stay non-chat-invocable: the governed registry does
    # not include browser automation or workspace connections.
    for cap in on["capabilities"]:
        assert cap["invocableFromChat"] is False


def test_payloads_are_json_serialisable(client):
    """Guard against an accidental non-serialisable passthrough."""
    _FakeAsyncClient.response = _FakeResponse(200, {"enabled": False, "tools": []})
    resp = client.get("/v1/agent/tools", headers=GUEST)
    json.dumps(resp.json())
