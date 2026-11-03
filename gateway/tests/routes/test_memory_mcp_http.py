"""Issue #1494 — Memory MCP over HTTP contract tests.

Covers the auth-first, fail-closed contract of the /mcp mount:
  - GET /mcp/sse and POST /mcp/messages/ require `Authorization: Bearer <MCP_ADMIN_KEY>`
  - Missing/mismatched key ⇒ 401 (never an unauthenticated MCP session)
  - With a valid key the request reaches the MCP transport layer (auth passes
    through to SDK session semantics — unknown session ⇒ 4xx from the transport,
    NOT 401)

Live SSE handshakes (initialize/tools listing over the stream) are covered by
the e2e suite; these tests intentionally avoid long-lived streams.
"""

from __future__ import annotations

import pytest

pytest.importorskip("mcp", reason="memory MCP HTTP surface requires the mcp SDK")

from fastapi.testclient import TestClient  # noqa: E402

from api.routes.memory_mcp_http import (  # noqa: E402
    MCP_SESSIONS_PATH,
    create_memory_mcp_asgi_app,
)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("MCP_ADMIN_KEY", "contract-test-key")
    app = create_memory_mcp_asgi_app()
    return TestClient(app)


SUB_APP_MESSAGES_PATH = MCP_SESSIONS_PATH.removeprefix("/mcp")  # sub-app relative


def test_sse_requires_authorization(client):
    resp = client.get("/sse")  # sub-app relative: /mcp prefix comes from the server-side mount
    assert resp.status_code == 401


def test_sse_rejects_wrong_bearer_token(client):
    resp = client.get("/sse", headers={"Authorization": "Bearer not-the-key"})
    assert resp.status_code == 401


def test_messages_reject_missing_key_even_with_header_gap(client, monkeypatch):
    # Fail-closed: an EMPTY configured key must reject every request.
    monkeypatch.setenv("MCP_ADMIN_KEY", "")
    resp = client.post(
        f"{SUB_APP_MESSAGES_PATH}?session_id=nonexistent",
        headers={"Authorization": "Bearer anything"},
        json={"jsonrpc": "2.0", "method": "ping", "id": 1},
    )
    assert resp.status_code == 401


def test_messages_with_valid_key_reaches_transport_layer(client):
    # Auth passes; the SDK transport itself answers for the unknown session —
    # proving the request traversed the auth gate into MCP session semantics.
    resp = client.post(
        f"{SUB_APP_MESSAGES_PATH}?session_id=nonexistent",
        headers={"Authorization": "Bearer contract-test-key"},
        json={"jsonrpc": "2.0", "method": "ping", "id": 1},
    )
    assert resp.status_code in (400, 404)
    assert resp.status_code != 401


def test_transport_paths_are_consistent():
    # The POST mount path must match the endpoint advertised in SSE events.
    assert MCP_SESSIONS_PATH == "/mcp/messages/"
