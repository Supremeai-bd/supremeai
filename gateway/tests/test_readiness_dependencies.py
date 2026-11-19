"""Readiness truthfulness contract for the deployed gateway (audit 2026-11-19 #2).

/healthz stays a process-liveness probe, but /readyz must not report "ready"
while a configured L2 cache dependency (Upstash REST) is unreachable or out of
quota. The probe result is TTL-cached and never exposes dependency addresses.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from gateway.service import app as edge

_REDIS_URL = "https://example-redis.upstash.io"
_REDIS_TOKEN = "fixture-redis-token"


@pytest.fixture(autouse=True)
def _reset_readiness_state(monkeypatch):
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    edge._upstash_readiness_state.update(ok=None, checked_at=0.0)
    yield
    edge._upstash_readiness_state.update(ok=None, checked_at=0.0)


def _configure_upstash(monkeypatch) -> None:
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", _REDIS_URL)
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", _REDIS_TOKEN)


def _make_chat_capable(monkeypatch) -> None:
    monkeypatch.setattr(edge, "squad", None)
    monkeypatch.setattr(edge, "STEALTH_WEBHOOK_URL", "https://stealth.internal/v1/generate")
    monkeypatch.setattr(
        edge,
        "_stealth_dns_snapshot",
        AsyncMock(return_value={"ok": True, "checked_at": 1.0, "detail": "resolved"}),
    )


def _get_readyz() -> tuple[int, dict]:
    with TestClient(edge.app) as client:
        resp = client.get("/readyz")
    return resp.status_code, resp.json()


def test_readyz_ignores_unconfigured_cache(monkeypatch):
    _make_chat_capable(monkeypatch)
    probe = AsyncMock(return_value=False)
    monkeypatch.setattr(edge, "_probe_upstash_redis", probe)

    status, body = _get_readyz()

    assert status == 200
    assert body["status"] == "ready"
    probe.assert_not_awaited()


def test_readyz_degrades_when_configured_cache_is_unreachable(monkeypatch):
    _configure_upstash(monkeypatch)
    _make_chat_capable(monkeypatch)
    probe = AsyncMock(return_value=False)
    monkeypatch.setattr(edge, "_probe_upstash_redis", probe)

    status, body = _get_readyz()

    assert status == 503
    assert body["status"] == "degraded"
    assert body["chat_ready"] is False
    assert body["reason"] == "configured cache dependency unavailable"
    assert "upstash" not in body["reason"].lower()
    assert "http" not in body["reason"].lower()
    probe.assert_awaited_once()


def test_readyz_stays_ready_when_configured_cache_answers(monkeypatch):
    _configure_upstash(monkeypatch)
    _make_chat_capable(monkeypatch)
    probe = AsyncMock(return_value=True)
    monkeypatch.setattr(edge, "_probe_upstash_redis", probe)

    status, body = _get_readyz()

    assert status == 200
    assert body["status"] == "ready"
    assert body["chat_ready"] is True
    probe.assert_awaited_once()


def test_readyz_caches_the_dependency_verdict(monkeypatch):
    _configure_upstash(monkeypatch)
    _make_chat_capable(monkeypatch)
    probe = AsyncMock(return_value=True)
    monkeypatch.setattr(edge, "_probe_upstash_redis", probe)

    assert _get_readyz()[0] == 200
    assert _get_readyz()[0] == 200

    probe.assert_awaited_once()
