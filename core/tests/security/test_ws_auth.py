"""WebSocket auth helper contract tests (owner P1 auth surface).

বাংলা: core/security/ws_auth.py হলো fail-closed WebSocket handshake — FastAPI
AuthMiddleware শুধু http scope রক্ষা করে, তাই প্রতিটি WS endpoint-এর শেষ
প্রতিরোধ এই helper। AUD-2.1/2.6 অনুযায়ী কোনো শাখা fail-open হওয়া চলবে না।
এই স্যুট প্রতিটি arc লক করে: query token / httpOnly cookie / first-message
handshake / malformed message / invalid token / disconnect propagation /
require_admin role gate (case-insensitive) / close codes।

Fake WebSocket:
    cookies dict + scripted receive_json + close() recorder — বাস্তব
    WebSocket ছাড়াই handshake-এর সব শাখা deterministic ভাবে চালানো হয়।
    verify_token module attribute দুই alias-এ patch করা হয় (gotcha w)।
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from fastapi import status
from fastapi.websockets import WebSocketDisconnect


class FakeWebSocket:
    """Scripted WS double: cookies + receive_json + close recorder."""

    def __init__(
        self,
        *,
        cookies: dict[str, str] | None = None,
        incoming: list[Any] | None = None,
    ) -> None:
        self.cookies: dict[str, str] = cookies or {}
        self._incoming: list[Any] = incoming if incoming is not None else []
        self.closed: list[dict[str, Any]] = []

    async def receive_json(self) -> Any:
        if not self._incoming:
            raise WebSocketDisconnect(code=1000)
        item = self._incoming.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed.append({"code": code, "reason": reason})


def _patch_verify(monkeypatch: pytest.MonkeyPatch, behavior: Any) -> None:
    """Patch verify_token on both module aliases (gotcha w)."""
    for name in ("core.security.ws_auth", "backend.core.security.ws_auth"):
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        if callable(behavior) and not isinstance(behavior, type):
            monkeypatch.setattr(mod, "verify_token", behavior, raising=False)
        else:
            # exception class or instance factory
            def raiser(token: str, _exc=behavior):
                raise _exc

            monkeypatch.setattr(mod, "verify_token", raiser, raising=False)


VALID_PAYLOAD = {"sub": "user-1", "role": "user", "tenant_id": "t-1"}
ADMIN_PAYLOAD = {"sub": "root", "role": "ADMIN", "tenant_id": "t-0"}


# -------------------------------------------------- token supply paths ----


class TestQueryTokenPath:
    async def test_valid_query_token_returns_payload(self, monkeypatch):
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: {**VALID_PAYLOAD, "tok": token})
        ws = FakeWebSocket()
        payload = await authenticate_websocket(ws, token="jwt-abc")
        assert payload == {**VALID_PAYLOAD, "tok": "jwt-abc"}
        assert ws.closed == []

    async def test_invalid_query_token_closes_1008_unauthorized(self, monkeypatch):
        from core.security import ws_auth as mod

        _patch_verify(monkeypatch, ValueError("bad token"))
        ws = FakeWebSocket()
        payload = await mod.authenticate_websocket(ws, token="garbage")
        assert payload is None
        assert ws.closed == [{"code": status.WS_1008_POLICY_VIOLATION, "reason": "Unauthorized"}]

    async def test_cookie_fallback_used_when_no_query_token(self, monkeypatch):
        """JWT-COOKIE-MIGRATION: query token না থাকলে httpOnly cookie।"""
        from core.security.ws_auth import authenticate_websocket

        seen: list[str] = []

        def fake_verify(token: str) -> dict:
            seen.append(token)
            return VALID_PAYLOAD

        _patch_verify(monkeypatch, fake_verify)
        ws = FakeWebSocket(cookies={"supreme_access_token": "cookie-jwt"})
        payload = await authenticate_websocket(ws)
        assert payload == VALID_PAYLOAD
        assert seen == ["cookie-jwt"]  # cookie value reached verify_token
        assert ws.closed == []


# ------------------------------------------- first-message handshake ----


class TestFirstMessageHandshake:
    async def test_valid_auth_handshake_returns_payload(self, monkeypatch):
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: {**VALID_PAYLOAD, "tok": token})
        ws = FakeWebSocket(incoming=[{"type": "auth", "token": "hs-jwt"}])
        payload = await authenticate_websocket(ws)
        assert payload == {**VALID_PAYLOAD, "tok": "hs-jwt"}
        assert ws.closed == []

    async def test_wrong_message_type_rejected(self, monkeypatch):
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: VALID_PAYLOAD)
        ws = FakeWebSocket(incoming=[{"type": "ping", "token": "hs-jwt"}])
        payload = await authenticate_websocket(ws)
        assert payload is None
        assert ws.closed[0]["code"] == status.WS_1008_POLICY_VIOLATION

    async def test_auth_type_with_empty_token_rejected(self, monkeypatch):
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: VALID_PAYLOAD)
        ws = FakeWebSocket(incoming=[{"type": "auth", "token": ""}])
        payload = await authenticate_websocket(ws)
        assert payload is None
        assert len(ws.closed) == 1

    async def test_non_dict_message_rejected(self, monkeypatch):
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: VALID_PAYLOAD)
        ws = FakeWebSocket(incoming=["hello-plain-text"])
        payload = await authenticate_websocket(ws)
        assert payload is None
        assert ws.closed[0]["reason"] == "Unauthorized"

    async def test_handshake_invalid_token_closes_unauthorized(self, monkeypatch):
        """Handshake token present but verify_token raises → 1008."""
        from core.security import ws_auth as mod

        _patch_verify(monkeypatch, ValueError("expired"))
        ws = FakeWebSocket(incoming=[{"type": "auth", "token": "stale-jwt"}])
        payload = await mod.authenticate_websocket(ws)
        assert payload is None
        assert ws.closed == [{"code": status.WS_1008_POLICY_VIOLATION, "reason": "Unauthorized"}]

    async def test_websocket_disconnect_propagates_without_close(self, monkeypatch):
        """Disconnect is re-raised (caller must not double-close)."""
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: VALID_PAYLOAD)
        ws = FakeWebSocket(incoming=[WebSocketDisconnect(code=1001)])
        with pytest.raises(WebSocketDisconnect):
            await authenticate_websocket(ws)
        assert ws.closed == []  # fail-closed, not fail-silent: no stray close


# ----------------------------------------------------- admin gate ----


class TestRequireAdminGate:
    async def test_admin_role_allowed_case_insensitive(self, monkeypatch):
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: ADMIN_PAYLOAD)  # role="ADMIN"
        ws = FakeWebSocket()
        payload = await authenticate_websocket(ws, token="jwt", require_admin=True)
        assert payload is not None
        assert payload["role"] == "ADMIN"

    async def test_non_admin_rejected_1008_forbidden(self, monkeypatch):
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: VALID_PAYLOAD)  # role="user"
        ws = FakeWebSocket()
        payload = await authenticate_websocket(ws, token="jwt", require_admin=True)
        assert payload is None
        assert ws.closed == [{"code": status.WS_1008_POLICY_VIOLATION, "reason": "Forbidden"}]

    async def test_missing_role_treated_as_non_admin(self, monkeypatch):
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: {"sub": "user-2"})  # no role key
        ws = FakeWebSocket()
        payload = await authenticate_websocket(ws, token="jwt", require_admin=True)
        assert payload is None
        assert ws.closed[0]["reason"] == "Forbidden"

    async def test_require_admin_false_skips_role_check(self, monkeypatch):
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: VALID_PAYLOAD)  # plain user
        ws = FakeWebSocket()
        payload = await authenticate_websocket(ws, token="jwt", require_admin=False)
        assert payload == VALID_PAYLOAD
        assert ws.closed == []


# ------------------------------------------------- fail-closed sweep ----


class TestFailClosedSweep:
    @pytest.mark.parametrize(
        "incoming",
        [
            [{"type": "auth", "token": None}],
            [{"type": "AUTH", "token": "x"}],  # case-sensitive type match
            [{}],
            [42],
        ],
        ids=["null-token", "uppercase-type", "empty-dict", "numeric-message"],
    )
    async def test_every_malformed_handshake_closes_1008(self, monkeypatch, incoming):
        from core.security.ws_auth import authenticate_websocket

        _patch_verify(monkeypatch, lambda token: VALID_PAYLOAD)
        ws = FakeWebSocket(incoming=incoming)
        payload = await authenticate_websocket(ws)
        assert payload is None
        assert ws.closed and ws.closed[0]["code"] == status.WS_1008_POLICY_VIOLATION

    async def test_module_exports_single_entrypoint(self):
        """Contract: helpers import from exactly one canonical location."""
        from core.security import ws_auth as mod

        assert mod.authenticate_websocket.__name__ == "authenticate_websocket"
        assert mod.authenticate_websocket.__module__ == "core.security.ws_auth"
