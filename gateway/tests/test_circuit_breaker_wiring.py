"""Circuit-breaker wiring regressions for the provider failover chain.

Before 2026-11-19 ``execute_chain(..., circuit_breaker=...)`` accepted the
argument and never read it (``gateway/circuit_breaker.py`` was dead code with
zero callers), so a provider that was down cost the full transport timeout on
every single request.

Contract under test:
1. A provider whose breaker is OPEN is skipped *without* calling the transport.
2. The breaker is **fail-open**: when every endpoint is open, the chain is
   retried once with the breaker ignored instead of guaranteeing a 502.
3. Success closes the breaker and resets the failure counter.
4. ``create_app`` owns a per-app breaker (never a process-global singleton).
"""

from __future__ import annotations

import json

import pytest

from gateway.circuit_breaker import CircuitBreaker, CircuitState
from gateway.config import Endpoint, parse_routing_policy
from gateway.main import create_app
from gateway.provider_chain import AttemptResult, ProviderChainExhausted, execute_chain

PAYLOAD = json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode()


def _ok(endpoint: Endpoint) -> AttemptResult:
    return AttemptResult(
        endpoint,
        200,
        {},
        b'{"choices":[{"message":{"content":"ok"}}]}',
        1,
    )


def _fail(endpoint: Endpoint, status: int = 503) -> AttemptResult:
    return AttemptResult(endpoint, status, {}, b"{}", 1)


@pytest.mark.asyncio
async def test_open_provider_is_skipped_without_touching_the_transport():
    breaker = CircuitBreaker(failure_threshold=2, cooldown_s=600)
    calls: list[str] = []

    async def attempt(endpoint: Endpoint, _payload: bytes) -> AttemptResult:
        calls.append(endpoint.provider)
        return _fail(endpoint)

    dead = (Endpoint(provider="groq", model="llama-3.1-8b-instant"),)
    for _ in range(2):
        with pytest.raises(ProviderChainExhausted):
            await execute_chain(dead, PAYLOAD, attempt_fn=attempt, circuit_breaker=breaker)

    assert breaker.state_of("groq") is CircuitState.OPEN
    calls.clear()

    async def healthy(endpoint: Endpoint, _payload: bytes) -> AttemptResult:
        calls.append(endpoint.provider)
        return _ok(endpoint)

    chain = (Endpoint(provider="groq", model="llama-3.1-8b-instant"), Endpoint(provider="openai", model="gpt-4o-mini"))
    result = await execute_chain(chain, PAYLOAD, attempt_fn=healthy, circuit_breaker=breaker)

    assert result.endpoint.provider == "openai"
    assert calls == ["openai"], "the open provider must be skipped, not retried"


@pytest.mark.asyncio
async def test_all_providers_open_fails_open_instead_of_502():
    """A stale breaker must never convert a recoverable upstream into a hard 502."""
    breaker = CircuitBreaker(failure_threshold=1, cooldown_s=600)
    chain = (Endpoint(provider="groq", model="llama-3.1-8b-instant"),)

    async def failing(endpoint: Endpoint, _payload: bytes) -> AttemptResult:
        return _fail(endpoint)

    with pytest.raises(ProviderChainExhausted):
        await execute_chain(chain, PAYLOAD, attempt_fn=failing, circuit_breaker=breaker)
    assert breaker.state_of("groq") is CircuitState.OPEN

    attempted: list[str] = []

    async def recovered(endpoint: Endpoint, _payload: bytes) -> AttemptResult:
        attempted.append(endpoint.provider)
        return _ok(endpoint)

    result = await execute_chain(chain, PAYLOAD, attempt_fn=recovered, circuit_breaker=breaker)
    assert result.status == 200
    assert attempted == ["groq"], "fail-open retry must attempt the open provider again"


@pytest.mark.asyncio
async def test_success_closes_breaker_and_resets_failures():
    breaker = CircuitBreaker(failure_threshold=3, cooldown_s=600)
    chain = (Endpoint(provider="groq", model="llama-3.1-8b-instant"),)

    async def flaky(endpoint: Endpoint, _payload: bytes) -> AttemptResult:
        return _fail(endpoint)

    with pytest.raises(ProviderChainExhausted):
        await execute_chain(chain, PAYLOAD, attempt_fn=flaky, circuit_breaker=breaker)
    assert breaker.snapshot()["groq"]["failures"] == 1

    async def healthy(endpoint: Endpoint, _payload: bytes) -> AttemptResult:
        return _ok(endpoint)

    await execute_chain(chain, PAYLOAD, attempt_fn=healthy, circuit_breaker=breaker)
    assert breaker.state_of("groq") is CircuitState.CLOSED
    assert breaker.snapshot()["groq"]["failures"] == 0


def test_create_app_owns_a_per_app_breaker(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_GUEST_DAILY_MAX", "0")
    policy = {
        "schema_version": "gateway-routing/1",
        "chains": {"auto": [{"provider": "groq", "model": "llama-3.1-8b-instant"}]},
        "default_chain": "auto",
        "rate_limit": {"window_seconds": 60, "max_requests": 10},
        "api_keys": {},
    }
    cfg = parse_routing_policy(policy, env={})
    app_a = create_app(cfg)
    app_b = create_app(cfg)

    assert app_a.state.circuit_breaker is not None
    assert app_a.state.circuit_breaker is not app_b.state.circuit_breaker


# --------------------------------------------------------------------------- #
# request bounding (413 before the payload is buffered)                        #
# --------------------------------------------------------------------------- #

def _policy():
    return {
        "schema_version": "gateway-routing/1",
        "chains": {"auto": [{"provider": "groq", "model": "llama-3.1-8b-instant"}]},
        "default_chain": "auto",
        "rate_limit": {"window_seconds": 60, "max_requests": 1000},
        "api_keys": {},
    }


def _client(app):
    from fastapi.testclient import TestClient

    return TestClient(app, raise_server_exceptions=False)


def test_oversized_body_is_rejected_with_413(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_ALLOW_ANONYMOUS", "1")
    monkeypatch.setenv("GATEWAY_MAX_REQUEST_BYTES", "256")
    app = create_app(parse_routing_policy(_policy(), env={}))
    payload = {"messages": [{"role": "user", "content": "x" * 4096}]}
    resp = _client(app).post("/v1/chat/completions", json=payload)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "request_too_large"


def test_too_many_messages_is_rejected(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_ALLOW_ANONYMOUS", "1")
    monkeypatch.setenv("GATEWAY_MAX_MESSAGES", "2")
    app = create_app(parse_routing_policy(_policy(), env={}))
    payload = {"messages": [{"role": "user", "content": f"m{i}"} for i in range(5)]}
    resp = _client(app).post("/v1/chat/completions", json=payload)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "too_many_messages"


def test_normal_sized_request_is_not_rejected_by_the_guard(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_ALLOW_ANONYMOUS", "1")
    app = create_app(parse_routing_policy(_policy(), env={}))
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    resp = _client(app).post("/v1/chat/completions", json=payload)
    # No transport is configured in this offline app, so the chain 502s — the
    # point is that the *guard* let the request through (no 413/400).
    assert resp.status_code not in (400, 413)
