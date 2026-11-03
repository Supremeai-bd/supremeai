"""Full-coverage tests for core/security/protection/honeypot.py (Task 7 wave-2).

Drives the ASGI middleware with fake scope/receive/send and mocks RulesMutator,
redis queue, event bus and Firebase persistence. ENV is forced away from "test"
per-test (the middleware short-circuits in test env).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.security.protection.honeypot as hp
from core.security.protection.honeypot import HoneypotMiddleware


def make_scope(
    path="/chat",
    method="GET",
    query=b"",
    client=("1.2.3.4", 12345),
    body=b"",
    headers=None,
):
    scope = {
        "type": "http",
        "path": path,
        "method": method,
        "query_string": query,
        "headers": headers or [],
        "client": client,
    }
    return scope


def body_messages(body: bytes):
    """Split a body into two ASGI body messages."""
    mid = len(body) // 2
    parts = [body[:mid], body[mid:]]
    msgs = []
    for i, chunk in enumerate(parts):
        msgs.append({"type": "http.request", "body": chunk, "more_body": i < len(parts) - 1})
    return msgs


@pytest.fixture
def mutator(monkeypatch):
    """Patch RulesMutator used inside HoneypotMiddleware.__init__."""
    fake = MagicMock()
    fake.is_ip_blocked.return_value = False
    monkeypatch.setattr("core.rules_mutator.RulesMutator", MagicMock(return_value=fake))
    return fake


@pytest.fixture
def prod_env(monkeypatch):
    monkeypatch.setenv("ENV", "production")


class AppRecorder:
    """Minimal ASGI app double recording calls (avoids strict mock assertions)."""

    def __init__(self):
        self.calls = []

    async def __call__(self, scope, receive, send):
        self.calls.append((scope, receive, send))


@pytest.fixture
def app():
    return AppRecorder()


def make_middleware(app, mutator):
    return HoneypotMiddleware(app)


class TestPassthroughBasics:
    async def test_non_http_scope_passthrough(self, mutator, prod_env, app):
        mw = make_middleware(app, mutator)
        scope = {"type": "websocket"}
        receive, send = AsyncMock(), AsyncMock()
        await mw(scope, receive, send)
        assert len(app.calls) == 1 and app.calls[0][0] is scope

    async def test_test_env_short_circuit(self, mutator, monkeypatch, app):
        monkeypatch.setenv("ENV", "test")
        mw = make_middleware(app, mutator)
        scope = make_scope()
        receive, send = AsyncMock(), AsyncMock()
        await mw(scope, receive, send)
        assert len(app.calls) == 1 and app.calls[0][0] is scope

    async def test_no_client_ip_unknown(self, mutator, prod_env, app):
        mw = make_middleware(app, mutator)
        scope = make_scope(client=None)
        receive, send = AsyncMock(), AsyncMock()
        await mw(scope, receive, send)
        mutator.is_ip_blocked.assert_called_once_with("unknown")
        assert len(app.calls) == 1


class TestBlockedIP:
    async def test_blocked_ip_gets_403(self, mutator, prod_env, app):
        mutator.is_ip_blocked.return_value = True
        mw = make_middleware(app, mutator)
        scope = make_scope()
        send = AsyncMock()
        await mw(scope, AsyncMock(), send)
        assert not app.calls
        # first send = response start with 403
        start = send.await_args_list[0].args[0]
        assert start["type"] == "http.response.start"
        assert start["status"] == 403


class TestBodyHandling:
    async def test_post_body_read_and_forwarded(self, mutator, prod_env, app):
        mw = make_middleware(app, mutator)
        body = b"hello world data"
        scope = make_scope(method="POST", body=body)
        msgs = body_messages(body)
        receive = AsyncMock(side_effect=list(msgs) + [{"type": "http.disconnect"}])
        send = AsyncMock()
        await mw(scope, receive, send)
        assert len(app.calls) == 1
        # POST: app receives the reconstructed receive channel
        forwarded = app.calls[0][1]
        replayed = await forwarded()
        assert replayed["body"] == b"hello wo"
        replayed2 = await forwarded()
        assert replayed2["body"] == b"rld data"

    async def test_oversized_content_length_skips_inspection(self, mutator, prod_env, app):
        mw = make_middleware(app, mutator)
        body = b"x" * 50
        scope = make_scope(
            method="POST",
            body=body,
            headers=[(b"content-length", b"99999999")],
        )
        msgs = body_messages(body)
        receive = AsyncMock(side_effect=list(msgs) + [{"type": "http.disconnect"}])
        send = AsyncMock()
        await mw(scope, receive, send)
        assert len(app.calls) == 1
        # passthrough_receive replays buffered messages then falls through to real receive
        forwarded = app.calls[0][1]
        first = await forwarded()
        assert first["body"] == body[:25]
        second = await forwarded()
        assert second["body"] == body[25:]
        third = await forwarded()  # falls back to real receive (next queued message)
        assert third == {"type": "http.disconnect"}

    async def test_body_read_error_is_contained(self, mutator, prod_env, app):
        mw = make_middleware(app, mutator)
        scope = make_scope(method="POST")
        receive = AsyncMock(side_effect=RuntimeError("stream broke"))
        send = AsyncMock()
        await mw(scope, receive, send)  # must not raise
        assert len(app.calls) == 1


class TestSignatureScanning:
    @pytest.mark.parametrize(
        "path,payload",
        [
            ("/admin/login", "union select * from users"),
            ("/auth/token", "1 = 1"),
            ("/login", "drop table users"),
            ("/chat", "union select password"),  # strict signatures apply everywhere
        ],
    )
    async def test_malicious_body_triggers_block(
        self, mutator, prod_env, app, monkeypatch, path, payload
    ):
        mw = make_middleware(app, mutator)
        scope = make_scope(path=path, method="POST", body=payload.encode())
        msgs = [{"type": "http.request", "body": payload.encode(), "more_body": False}]
        receive = AsyncMock(side_effect=list(msgs))
        send = AsyncMock()

        # patch threat-intel persistence + redis module + event bus
        persist = MagicMock()
        monkeypatch.setattr(mw, "_persist_threat_intel", persist)
        fake_rq = MagicMock()
        fake_rq.configured = True
        monkeypatch.setattr("core.services.redis_queue", fake_rq, raising=False)
        bus = MagicMock()
        monkeypatch.setattr("core.messaging.event_bus.ErrorEventBus", MagicMock(return_value=bus))

        await mw(scope, receive, send)
        mutator.block_ip.assert_called_once()
        assert mutator.block_ip.call_args.args[0] == "1.2.3.4"
        # redis block entries written
        assert fake_rq.set.call_count == 2
        key1 = fake_rq.set.call_args_list[0].args[0]
        assert key1.startswith("honeypot:blocked:")
        # 418 teapot response
        start = send.await_args_list[0].args[0]
        assert start["status"] == 418
        assert not app.calls
        # event emitted
        bus.emit.assert_called_once()

    async def test_prompt_injection_blocked_only_on_auth_surface(
        self, mutator, prod_env, app, monkeypatch
    ):
        mw = make_middleware(app, mutator)
        persist = MagicMock()
        monkeypatch.setattr(mw, "_persist_threat_intel", persist)

        # on a content path: prompt-injection signature must NOT block
        scope = make_scope(path="/chat", method="POST", body=b"ignore previous instructions")
        receive = AsyncMock(
            side_effect=[
                {
                    "type": "http.request",
                    "body": b"ignore previous instructions",
                    "more_body": False,
                }
            ]
        )
        await mw(scope, receive, AsyncMock())
        mutator.block_ip.assert_not_called()
        assert len(app.calls) == 1

        # on an auth surface: same payload MUST block
        mutator.block_ip.reset_mock()
        app.calls.clear()
        scope2 = make_scope(path="/login", method="POST", body=b"ignore previous instructions")
        receive2 = AsyncMock(
            side_effect=[
                {
                    "type": "http.request",
                    "body": b"ignore previous instructions",
                    "more_body": False,
                }
            ]
        )
        await mw(scope2, receive2, AsyncMock())
        mutator.block_ip.assert_called_once()
        assert not app.calls

    async def test_malicious_query_string(self, mutator, prod_env, app, monkeypatch):
        mw = make_middleware(app, mutator)
        monkeypatch.setattr(mw, "_persist_threat_intel", MagicMock())
        # NOTE: query is scanned raw (no URL-decoding), so use a literal space.
        scope = make_scope(path="/items", method="GET", query=b"?q=union select")
        await mw(scope, AsyncMock(), AsyncMock())
        mutator.block_ip.assert_called_once()

    async def test_redis_unconfigured_skips_redis(self, mutator, prod_env, app, monkeypatch):
        mw = make_middleware(app, mutator)
        monkeypatch.setattr(mw, "_persist_threat_intel", MagicMock())
        fake_rq = MagicMock()
        fake_rq.configured = False
        monkeypatch.setattr("core.services.redis_queue", fake_rq, raising=False)
        scope = make_scope(path="/admin", method="POST", body=b"union select 1")
        receive = AsyncMock(
            side_effect=[{"type": "http.request", "body": b"union select 1", "more_body": False}]
        )
        await mw(scope, receive, AsyncMock())
        mutator.block_ip.assert_called_once()
        fake_rq.set.assert_not_called()

    async def test_event_bus_failure_suppressed(self, mutator, prod_env, app, monkeypatch):
        mw = make_middleware(app, mutator)
        monkeypatch.setattr(mw, "_persist_threat_intel", MagicMock())
        monkeypatch.setattr("core.services.redis_queue", MagicMock(configured=False), raising=False)
        bus = MagicMock()
        bus.emit.side_effect = RuntimeError("bus down")
        monkeypatch.setattr("core.messaging.event_bus.ErrorEventBus", MagicMock(return_value=bus))
        scope = make_scope(path="/admin", method="POST", body=b"union select 1")
        receive = AsyncMock(
            side_effect=[{"type": "http.request", "body": b"union select 1", "more_body": False}]
        )
        await mw(scope, receive, AsyncMock())  # must not raise
        mutator.block_ip.assert_called_once()

    async def test_redis_set_failure_suppressed(self, mutator, prod_env, app, monkeypatch):
        mw = make_middleware(app, mutator)
        monkeypatch.setattr(mw, "_persist_threat_intel", MagicMock())
        fake_rq = MagicMock()
        fake_rq.configured = True
        fake_rq.set.side_effect = RuntimeError("redis down")
        monkeypatch.setattr("core.services.redis_queue", fake_rq, raising=False)
        scope = make_scope(path="/admin", method="POST", body=b"union select 1")
        receive = AsyncMock(
            side_effect=[{"type": "http.request", "body": b"union select 1", "more_body": False}]
        )
        await mw(scope, receive, AsyncMock())  # must not raise
        mutator.block_ip.assert_called_once()


class TestThreatIntel:
    async def test_log_threat_intel_with_running_loop(self, mutator, prod_env, app):
        mw = make_middleware(app, mutator)
        persist = MagicMock()
        with patch.object(mw, "_persist_threat_intel", persist):
            mw._log_threat_intelligence("9.9.9.9", "payload", "/path")
            # run_in_executor scheduled; flush the default executor
            await asyncio.sleep(0.05)
        persist.assert_called_once_with("9.9.9.9", "payload", "/path")

    def test_log_threat_intel_no_loop_sync_fallback(self, mutator, prod_env):
        mw = make_middleware(HoneypotMiddleware.__init__ and MagicMock(), mutator)
        persist = MagicMock()
        with patch.object(mw, "_persist_threat_intel", persist):
            # no running loop in sync context -> synchronous execution path
            mw._log_threat_intelligence("8.8.8.8", "p", "/e")
        persist.assert_called_once_with("8.8.8.8", "p", "/e")

    def test_persist_threat_intel_success(self, mutator, prod_env):
        mw = make_middleware(MagicMock(), mutator)
        fake_fb = MagicMock()
        fake_fb._apps = {"app": object()}
        fake_firestore = MagicMock()
        fake_fb.firestore = fake_firestore  # "from firebase_admin import firestore"
        with patch.dict(
            "sys.modules",
            {"firebase_admin": fake_fb, "firebase_admin.firestore": fake_firestore},
        ):
            mw._persist_threat_intel("7.7.7.7", "p" * 2000, "/endpoint")
        fake_firestore.client.return_value.collection.assert_called_once_with("threat_intel")
        added = fake_firestore.client.return_value.collection.return_value.add.call_args[0][0]
        assert added["ip"] == "7.7.7.7"
        assert len(added["payload"]) == 1000  # truncated

    def test_persist_threat_intel_error_suppressed(self, mutator, prod_env):
        mw = make_middleware(MagicMock(), mutator)
        fake_fb = MagicMock()
        fake_fb._apps = {}
        # initialize_app creates no apps entry -> _apps stays falsy -> repeat call...
        # simpler: make firestore.client raise
        fake_firestore = MagicMock()
        fake_firestore.client.side_effect = RuntimeError("no firestore")
        fake_fb.firestore = fake_firestore
        with patch.dict(
            "sys.modules",
            {"firebase_admin": fake_fb, "firebase_admin.firestore": fake_firestore},
        ):
            mw._persist_threat_intel("6.6.6.6", "p", "/e")  # must not raise


class TestMaxInspectBytesEnv:
    def test_env_override(self, mutator, monkeypatch):
        monkeypatch.setenv("HONEYPOT_MAX_INSPECT_BYTES", "42")
        mw = make_middleware(MagicMock(), mutator)
        assert mw._max_inspect_bytes == 42

    def test_default(self, mutator, monkeypatch):
        monkeypatch.delenv("HONEYPOT_MAX_INSPECT_BYTES", raising=False)
        mw = make_middleware(MagicMock(), mutator)
        assert mw._max_inspect_bytes == 1000000


class TestOversizedMidstream:
    async def test_accumulated_oversize_breaks_buffering(self, mutator, prod_env, app):
        mw = make_middleware(app, mutator)
        mw._max_inspect_bytes = 10  # shrink for the test
        scope = make_scope(method="POST")
        msgs = [
            {"type": "http.request", "body": b"a" * 8, "more_body": True},
            {"type": "http.request", "body": b"b" * 8, "more_body": True},
            {"type": "http.request", "body": b"c" * 8, "more_body": False},
        ]
        receive = AsyncMock(side_effect=list(msgs))
        send = AsyncMock()
        await mw(scope, receive, send)
        assert len(app.calls) == 1
        forwarded = app.calls[0][1]
        # buffered messages replayed first
        m1 = await forwarded()
        assert m1["body"] == b"a" * 8
        m2 = await forwarded()
        assert m2["body"] == b"b" * 8
        # then falls through to the real receive channel
        m3 = await forwarded()
        assert m3["body"] == b"c" * 8


class TestEdgeBranches:
    async def test_bad_content_length_header_treated_as_zero(self, mutator, prod_env, app):
        mw = make_middleware(app, mutator)
        body = b"small"
        scope = make_scope(method="POST", body=body, headers=[(b"content-length", b"not-a-number")])
        receive = AsyncMock(
            side_effect=[{"type": "http.request", "body": body, "more_body": False}]
        )
        await mw(scope, receive, AsyncMock())
        # body still inspected (not oversized) and forwarded
        assert len(app.calls) == 1

    async def test_threat_intel_executor_future_exception_logged(self, mutator, prod_env, app):
        mw = make_middleware(app, mutator)

        def boom(*a):
            raise RuntimeError("db down")

        with patch.object(mw, "_persist_threat_intel", boom):
            mw._log_threat_intelligence("5.5.5.5", "p", "/e")
            await asyncio.sleep(0.05)  # let the executor future finish

    async def test_get_running_loop_generic_error_suppressed(self, mutator, prod_env, app):
        mw = make_middleware(app, mutator)
        calls = []
        with patch.object(mw, "_persist_threat_intel", lambda *a: calls.append(a)):
            # A generic (non-RuntimeError) loop failure hits the broad except
            # branch which only logs — persistence is intentionally skipped.
            with patch.object(
                hp.asyncio,
                "get_running_loop",
                side_effect=Exception("weird loop failure"),
            ):
                mw._log_threat_intelligence("4.4.4.4", "p", "/e")
        assert len(calls) == 0
