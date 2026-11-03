# tests/api/test_websocket_hitl.py
"""Coverage ramp for api/routes/websocket_hitl.py (0% -> high) + regression
pin for the settings.jwt_algorithm latent crash.

The module is the HITL (human-in-the-loop) WebSocket: connection-cap manager
(DoS guard), event-bus listener that broadcasts review requests, JWT role
verification for ADMIN/SUPERVISOR, and the ping/pong heartbeat endpoint.

Strategy (wire-first): the ONLY owner-code change is the jwt_algorithm fix
documented in the source; everything else is tested as-is. JWTs are really
encoded/decoded with settings.jwt_secret (no jwt mocking in the happy paths);
sockets are fakes modelled on the test_websocket_agent.py pattern extended
with headers/query_params.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import WebSocketDisconnect

import api.routes.websocket_hitl as wh
from core.config import settings
from core.messaging.event_bus import ErrorEvent, error_event_bus

ALG = "HS256"


def make_token(role: str = "admin", expires_in: int = 3600, secret: str | None = None) -> str:
    payload = {
        "sub": "user-1",
        "role": role,
        "exp": datetime.now(UTC) + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, secret or settings.jwt_secret, algorithm=ALG)


class FakeHITLSocket:
    """WebSocket stand-in with header/query access for the auth ladder."""

    def __init__(self, incoming=None, headers=None, query_params=None, fail_sends=False):
        self._incoming = list(incoming or [])
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.sent: list[str] = []
        self.closed: list[tuple[int, str | None]] = []
        self.accepted = False
        self.fail_sends = fail_sends

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000, reason=None):
        self.closed.append((code, reason))

    async def send_text(self, text):
        if self.fail_sends:
            raise RuntimeError("socket gone")
        self.sent.append(text)

    async def receive_text(self):
        if not self._incoming:
            raise WebSocketDisconnect(code=1000)
        item = self._incoming.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def manager():
    return wh.HITLConnectionManager()


@pytest.fixture(autouse=True)
def _clean_module_manager():
    """Keep the module-level singleton clean across tests."""
    ws = wh.manager
    saved_cap = ws.MAX_CONNECTIONS
    ws.active_connections.clear()
    yield
    ws.active_connections.clear()
    ws.MAX_CONNECTIONS = saved_cap


# ---------------------------------------------------------------------------
# HITLConnectionManager — cap / bookkeeping / broadcast
# ---------------------------------------------------------------------------


async def test_connect_under_cap_accepts_and_registers(manager):
    ws = FakeHITLSocket()
    assert await manager.connect(ws) is True
    assert ws.accepted is True
    assert ws in manager.active_connections


async def test_connect_at_cap_rejects_with_1013_and_no_accept(manager):
    manager.MAX_CONNECTIONS = 1
    first = FakeHITLSocket()
    assert await manager.connect(first) is True
    second = FakeHITLSocket()
    assert await manager.connect(second) is False
    assert second.accepted is False
    assert second.closed == [(1013, "Too many connections")]
    assert second not in manager.active_connections


async def test_connect_cap_reads_env_override_at_class_level(monkeypatch):
    monkeypatch.setattr(wh.HITLConnectionManager, "MAX_CONNECTIONS", 2)
    mgr = wh.HITLConnectionManager()
    sockets = [FakeHITLSocket() for _ in range(3)]
    assert [await mgr.connect(s) for s in sockets] == [True, True, False]


async def test_disconnect_removes_and_unknown_disconnect_is_noop(manager):
    ws = FakeHITLSocket()
    await manager.connect(ws)
    await manager.disconnect(ws)
    assert ws not in manager.active_connections
    await manager.disconnect(ws)  # idempotent, no raise


async def test_broadcast_delivers_to_all_healthy(manager):
    sockets = [FakeHITLSocket() for _ in range(3)]
    for s in sockets:
        await manager.connect(s)
    await manager.broadcast("hello-hitl")
    assert all(s.sent == ["hello-hitl"] for s in sockets)


async def test_broadcast_with_no_connections_is_noop(manager):
    await manager.broadcast("into-the-void")  # no raise


async def test_broadcast_prunes_runtime_error_sockets(manager):
    good = FakeHITLSocket()
    bad = FakeHITLSocket(fail_sends=True)
    await manager.connect(good)
    await manager.connect(bad)
    await manager.broadcast("msg")
    assert good.sent == ["msg"]
    assert bad not in manager.active_connections
    assert good in manager.active_connections


async def test_broadcast_prunes_websocket_disconnect_sockets(manager):
    class DisconnectingSocket(FakeHITLSocket):
        async def send_text(self, text):
            raise WebSocketDisconnect(code=1001)

    good = FakeHITLSocket()
    bad = DisconnectingSocket()
    await manager.connect(good)
    await manager.connect(bad)
    await manager.broadcast("msg")
    assert good.sent == ["msg"]
    assert bad not in manager.active_connections


async def test_concurrent_connects_respect_cap_under_race(manager):
    manager.MAX_CONNECTIONS = 5
    sockets = [FakeHITLSocket() for _ in range(20)]

    async def connect(s):
        return await manager.connect(s)

    results = await asyncio.gather(*(connect(s) for s in sockets))
    assert results.count(True) == 5
    assert len(manager.active_connections) == 5


# ---------------------------------------------------------------------------
# hitl_event_listener — bus contract
# ---------------------------------------------------------------------------


async def test_import_registers_listener_on_global_bus():
    listeners = error_event_bus._listeners.get("*", [])
    assert wh.hitl_event_listener in listeners


async def test_listener_broadcasts_review_required_event():
    ws = FakeHITLSocket()
    await wh.manager.connect(ws)  # listener broadcasts via the module singleton
    event = ErrorEvent(
        error_type="HITL_REVIEW_REQUIRED",
        message="needs human",
        context={"task_id": "t-9"},
        severity="HIGH",
        module="orchestrator",
    )
    await wh.hitl_event_listener(event)
    assert len(ws.sent) == 1
    payload = json.loads(ws.sent[0])
    assert payload["type"] == "HITL_REVIEW_REQUIRED"
    assert payload["message"] == "needs human"
    assert payload["context"] == {"task_id": "t-9"}
    assert payload["severity"] == "HIGH"
    assert payload["module"] == "orchestrator"


async def test_listener_ignores_non_hitl_events():
    ws = FakeHITLSocket()
    await wh.manager.connect(ws)
    await wh.hitl_event_listener(ErrorEvent(error_type="SOMETHING_ELSE", message="not for humans"))
    assert ws.sent == []


async def test_listener_survives_non_serializable_context():
    ws = FakeHITLSocket()
    await wh.manager.connect(ws)
    await wh.hitl_event_listener(
        ErrorEvent(
            error_type="HITL_REVIEW_REQUIRED",
            message="bad payload",
            context={"blob": {1, 2, 3}},  # set is not JSON-serializable
        )
    )
    assert ws.sent == []  # nothing broadcast, no crash


async def test_listener_survives_unexpected_broadcast_error(manager, monkeypatch):
    async def explode(message):
        raise RuntimeError("bus down")

    monkeypatch.setattr(wh.manager, "broadcast", explode)
    await wh.hitl_event_listener(
        ErrorEvent(error_type="HITL_REVIEW_REQUIRED", message="x")
    )  # no raise


# ---------------------------------------------------------------------------
# verify_hitl_token — extraction ladder + JWT roles (real round-trips)
# ---------------------------------------------------------------------------


async def test_missing_token_rejected():
    assert await wh.verify_hitl_token(FakeHITLSocket()) is False


async def test_bearer_authorization_header_admin_accepted():
    ws = FakeHITLSocket(headers={"Authorization": f"Bearer {make_token('admin')}"})
    assert await wh.verify_hitl_token(ws) is True


async def test_x_api_key_header_fallback():
    ws = FakeHITLSocket(headers={"X-API-KEY": make_token("supervisor")})
    assert await wh.verify_hitl_token(ws) is True


async def test_query_param_token_fallback():
    ws = FakeHITLSocket(query_params={"token": make_token("admin")})
    assert await wh.verify_hitl_token(ws) is True


async def test_query_param_bearer_prefix_stripped():
    ws = FakeHITLSocket(query_params={"token": f"Bearer {make_token('admin')}"})
    assert await wh.verify_hitl_token(ws) is True


async def test_sec_websocket_protocol_fallback_skips_hitl_placeholder():
    token = make_token("admin")
    ws = FakeHITLSocket(headers={"sec-websocket-protocol": f"hitl, {token}"})
    assert await wh.verify_hitl_token(ws) is True


async def test_sec_websocket_protocol_only_placeholder_rejected():
    ws = FakeHITLSocket(headers={"sec-websocket-protocol": "hitl"})
    assert await wh.verify_hitl_token(ws) is False


async def test_expired_token_rejected():
    ws = FakeHITLSocket(headers={"Authorization": f"Bearer {make_token('admin', expires_in=-60)}"})
    assert await wh.verify_hitl_token(ws) is False


async def test_garbage_token_rejected():
    ws = FakeHITLSocket(headers={"Authorization": "Bearer not-a-jwt"})
    assert await wh.verify_hitl_token(ws) is False


async def test_wrong_role_rejected():
    ws = FakeHITLSocket(headers={"Authorization": f"Bearer {make_token('viewer')}"})
    assert await wh.verify_hitl_token(ws) is False


async def test_role_case_insensitive():
    ws = FakeHITLSocket(headers={"Authorization": f"Bearer {make_token('ADMIN')}"})
    assert await wh.verify_hitl_token(ws) is True


async def test_wrong_signing_secret_rejected():
    ws = FakeHITLSocket(
        headers={"Authorization": f"Bearer {make_token('admin', secret='attacker-key')}"}
    )
    assert await wh.verify_hitl_token(ws) is False


async def test_configured_allowed_hitl_roles_widen_access(monkeypatch):
    ns = SimpleNamespace(jwt_secret=settings.jwt_secret, allowed_hitl_roles=["operator"])
    monkeypatch.setattr(wh, "settings", ns)
    ws = FakeHITLSocket(headers={"Authorization": f"Bearer {make_token('operator')}"})
    assert await wh.verify_hitl_token(ws) is True


async def test_default_roles_when_settings_lacks_attribute(monkeypatch):
    ns = SimpleNamespace(jwt_secret=settings.jwt_secret)  # no allowed_hitl_roles
    monkeypatch.setattr(wh, "settings", ns)
    ws = FakeHITLSocket(headers={"Authorization": f"Bearer {make_token('supervisor')}"})
    assert await wh.verify_hitl_token(ws) is True


async def test_unexpected_decode_error_fail_closed(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("crypto stack exploded")

    monkeypatch.setattr(wh.jwt, "decode", boom)
    ws = FakeHITLSocket(headers={"Authorization": f"Bearer {make_token('admin')}"})
    assert await wh.verify_hitl_token(ws) is False


# ---------------------------------------------------------------------------
# websocket_hitl_endpoint — enforcement + heartbeat + cleanup
# ---------------------------------------------------------------------------


async def test_endpoint_rejects_unauthenticated_with_1008():
    ws = FakeHITLSocket(incoming=["ping"])
    await wh.websocket_hitl_endpoint(ws)
    assert ws.accepted is False
    assert ws.closed == [(1008, None)]


async def test_endpoint_authorized_connects_then_cleans_up_on_disconnect():
    token = make_token("admin")
    ws = FakeHITLSocket(headers={"Authorization": f"Bearer {token}"})
    await wh.websocket_hitl_endpoint(ws)
    assert ws.accepted is True
    assert ws not in wh.manager.active_connections  # finally-block cleanup


async def test_endpoint_ping_pong_heartbeat():
    token = make_token("admin")
    ws = FakeHITLSocket(incoming=["ping", "ping"], headers={"Authorization": f"Bearer {token}"})
    await wh.websocket_hitl_endpoint(ws)
    assert ws.sent == ["pong", "pong"]


async def test_endpoint_non_ping_message_gets_no_reply():
    token = make_token("admin")
    ws = FakeHITLSocket(incoming=["hello"], headers={"Authorization": f"Bearer {token}"})
    await wh.websocket_hitl_endpoint(ws)
    assert ws.sent == []


async def test_endpoint_survives_runtime_error_and_still_cleans_up():
    token = make_token("admin")
    ws = FakeHITLSocket(
        incoming=[RuntimeError("receive blew up")],
        headers={"Authorization": f"Bearer {token}"},
    )
    await wh.websocket_hitl_endpoint(ws)  # no raise
    assert ws not in wh.manager.active_connections


async def test_endpoint_at_capacity_closes_1013_without_loop():
    token = make_token("admin")
    wh.manager.MAX_CONNECTIONS = 0  # every connect is rejected
    ws = FakeHITLSocket(incoming=["ping"], headers={"Authorization": f"Bearer {token}"})
    await wh.websocket_hitl_endpoint(ws)
    assert ws.closed == [(1013, "Too many connections")]
    assert ws.sent == []  # receive loop never started


async def test_endpoint_supervisor_token_reaches_heartbeat():
    token = make_token("supervisor")
    ws = FakeHITLSocket(incoming=["ping"], headers={"Authorization": f"Bearer {token}"})
    await wh.websocket_hitl_endpoint(ws)
    assert ws.sent == ["pong"]
