"""API-key authentication must not authorize stale cached rows after revocation."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.security import generate_api_key, hash_api_key
from core.security import api_key_middleware as module
from core.cache.redis_manager import redis_manager


def _request(key):
    return Request({
        "type": "http", "method": "GET", "path": "/private/fixture",
        "headers": [(b"x-api-key", key.encode())], "client": ("127.0.0.1", 1234),
        "query_string": b"", "state": {},
    })


def _row(key):
    return {"id": 7, "user_id": "usr-fixture", "key_hash": hash_api_key(key),
            "revoked": False, "rate_limit_rps": 10, "rate_limit_window": 60,
            "expires_at": None, "scopes": ["read"]}


@pytest.fixture
def environment(monkeypatch):
    middleware = module.APIKeyAuthMiddleware(app=MagicMock())
    middleware.limiter.acquire = AsyncMock(return_value=True)
    monkeypatch.setattr(module, "is_test_environment", lambda: False)
    monkeypatch.setattr(module, "record_api_key_usage", AsyncMock())
    pool = AsyncMock()
    monkeypatch.setattr(module, "get_db_pool", AsyncMock(return_value=pool))
    get_cache = AsyncMock(return_value=json.dumps(_row(generate_api_key())))
    set_cache = AsyncMock()
    monkeypatch.setattr(redis_manager, "get_cache", get_cache)
    monkeypatch.setattr(redis_manager, "set_cache", set_cache)
    return middleware, pool, get_cache, set_cache


@pytest.mark.asyncio
@pytest.mark.parametrize("after,status", [("revoked", 403), ("deleted", 401), ("rotated", 401)])
async def test_fresh_db_verdict_after_revoke_delete_or_rotate(environment, after, status):
    middleware, pool, get_cache, set_cache = environment
    key = generate_api_key()
    row = _row(key)
    pool.fetchrow.return_value = row
    next_handler = AsyncMock(return_value=JSONResponse({"ok": True}))
    assert (await middleware.dispatch(_request(key), next_handler)).status_code == 200
    if after == "revoked":
        pool.fetchrow.return_value = {**row, "revoked": True}
    else:
        # Rotation or deletion makes the old hash absent from the database.
        pool.fetchrow.return_value = None
    assert (await middleware.dispatch(_request(key), next_handler)).status_code == status
    assert next_handler.await_count == 1
    assert pool.fetchrow.await_count == 2
    get_cache.assert_not_awaited()
    set_cache.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_failure_never_uses_cached_authorization(environment):
    middleware, pool, get_cache, set_cache = environment
    pool.fetchrow.side_effect = RuntimeError("database unavailable")
    next_handler = AsyncMock(return_value=JSONResponse({"ok": True}))
    response = await middleware.dispatch(_request(generate_api_key()), next_handler)
    assert response.status_code == 503
    assert b"Invalid API key" not in response.body
    next_handler.assert_not_awaited()
    get_cache.assert_not_awaited()
    set_cache.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_key_is_not_confused_with_database_outage(environment):
    middleware, pool, _, _ = environment
    pool.fetchrow.return_value = None
    response = await middleware.dispatch(_request(generate_api_key()), AsyncMock())
    assert response.status_code == 401
    assert b"Invalid API key" in response.body


@pytest.mark.asyncio
async def test_database_scope_updates_take_effect_on_next_request(environment):
    middleware, pool, get_cache, _ = environment
    key = generate_api_key()
    row = _row(key)
    pool.fetchrow.return_value = row
    seen = []

    async def capture(request):
        seen.append(request.state.user["scopes"])
        return JSONResponse({"ok": True})

    assert (await middleware.dispatch(_request(key), capture)).status_code == 200
    pool.fetchrow.return_value = {**row, "scopes": ["chat"]}
    assert (await middleware.dispatch(_request(key), capture)).status_code == 200
    assert seen == [["read"], ["chat"]]
    get_cache.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_database_circuit_stays_fail_closed(environment):
    middleware, pool, get_cache, _ = environment
    pool.fetchrow.side_effect = RuntimeError("database unavailable")
    handler = AsyncMock()
    for _ in range(4):
        response = await middleware.dispatch(_request(generate_api_key()), handler)
        assert response.status_code == 503
    assert pool.fetchrow.await_count == 3  # fourth request is rejected by the breaker
    handler.assert_not_awaited()
    get_cache.assert_not_awaited()
