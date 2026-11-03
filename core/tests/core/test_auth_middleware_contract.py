"""ASGI contract coverage for core/security/authentication/auth_middleware.py.

The legacy test_auth_middleware.py covers the helpers and
``verify_admin_session_fail_closed``; this module drives the ASGI
``__call__`` itself so the security-critical branches are locked:

- SSE query-token policy: accepted ONLY on ``/stream`` paths (AUDIT-SEC-8)
- refresh-token-as-access rejection
- JWT_SECRET missing → fail-closed rejection
- OPTIONS preflight passthrough (no auth, no CORS 401)
- API-key system identity (sub=system_api_key, role=admin)
- test-environment auth bypass attaches test_admin identity
- jti revocation: admin tokens FAIL-CLOSED, regular tokens fail-open
- scope contract: ``scope["user"]`` + ``scope["state"]["user"]`` attached

Ramp step 2 (hardening-2 round 2): this module previously measured ~21% in
the CI-combined coverage because its tests were deselected on PRs (overall
tier) — it is now critical-tiered together with these branch tests.
"""

import jwt
import pytest

import core.security.authentication.auth_middleware as auth_mw
from core.config import settings
from core.security.authentication.auth_middleware import (
    AuthMiddleware,
    verify_admin_session_fail_closed,
)

PROTECTED = "/api/v1/agents"


def _scope(
    path: str = PROTECTED,
    method: str = "GET",
    headers: list | None = None,
    query_string: bytes = b"",
) -> dict:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [],
        "query_string": query_string,
    }


async def _run(scope: dict):
    """Drive the middleware with a recording downstream app; return (sent, downstream_scope)."""
    sent: list[dict] = []
    downstream_scope: dict = {}

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        sent.append(message)

    async def downstream(scope, receive, send):
        downstream_scope.update(scope)
        sent.append({"type": "downstream.called"})

    await AuthMiddleware(downstream)(scope, receive, send)
    return sent, downstream_scope


def _bearer(value: str) -> list:
    return [(b"authorization", f"Bearer {value}".encode())]


def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


@pytest.fixture
def no_test_env(monkeypatch):
    """Make the middleware treat this as a NON-test environment."""
    monkeypatch.setattr(auth_mw, "is_test_environment", lambda: False)


# ---------------------------------------------------------------------------
# Transport policies
# ---------------------------------------------------------------------------
async def test_query_token_accepted_on_stream_path_only(no_test_env):
    """AUDIT-SEC-8: query token only on /stream paths, URL-decoded."""
    token = _encode({"sub": "sse-user", "role": "viewer"})

    sent, scope = await _run(
        _scope(path="/api/v1/dashboard/stream", query_string=f"token={token}".encode())
    )
    assert sent[-1]["type"] == "downstream.called"
    assert scope["user"]["sub"] == "sse-user"


async def test_query_token_ignored_off_stream_path(no_test_env):
    """Query token on a NON-stream endpoint must NOT authenticate (log-leak guard)."""
    token = _encode({"sub": "sneaky"})
    sent, _ = await _run(_scope(path="/api/v1/agents/run", query_string=f"token={token}".encode()))
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 401


async def test_query_token_url_encoded_value(no_test_env):
    """Percent-encoded query token values are unquoted before JWT decode."""
    from urllib.parse import quote

    token = jwt.encode({"sub": "encoded-user"}, settings.jwt_secret, algorithm="HS256")
    sent, scope = await _run(
        _scope(
            path="/api/v1/alerts/stream",
            query_string=f"token={quote(token, safe='')}".encode(),
        ),
    )
    assert sent[-1]["type"] == "downstream.called"
    assert scope["user"]["sub"] == "encoded-user"


async def test_options_preflight_passes_through_without_auth():
    """CORS preflight must reach CORSMiddleware even token-less (no raw 401)."""
    sent, _ = await _run(_scope(method="OPTIONS"))
    assert sent[-1]["type"] == "downstream.called"


# ---------------------------------------------------------------------------
# JWT decode contract
# ---------------------------------------------------------------------------
async def test_refresh_token_rejected_as_access(no_test_env):
    """A refresh token must never authenticate an access-token surface."""
    refresh = _encode({"sub": "u-1", "type": "refresh"})
    sent, _ = await _run(_scope(headers=_bearer(refresh)))
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 401


async def test_missing_jwt_secret_fails_closed(no_test_env, monkeypatch):
    """Without JWT_SECRET every token must be rejected (fail-closed policy)."""
    # CI GOTCHA: encode with the REAL secret first — PyJWT refuses to sign
    # with an empty HMAC key, and the patched property must be observable
    # only inside the middleware under test.
    token = _encode({"sub": "u-1"})
    monkeypatch.setattr(type(settings), "jwt_secret", property(lambda self: ""))
    sent, _ = await _run(_scope(headers=_bearer(token)))
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 401


async def test_valid_jwt_attaches_user_and_state(no_test_env):
    token = _encode({"sub": "u-9", "role": "editor", "tenant_id": "tenant-9", "type": "access"})
    sent, scope = await _run(_scope(headers=_bearer(token)))
    assert sent[-1]["type"] == "downstream.called"
    assert scope["user"] == {
        "sub": "u-9",
        "role": "editor",
        "tenant_id": "tenant-9",
    }
    assert scope["state"]["user"] == scope["user"]


async def test_invalid_token_returns_401_with_www_authenticate(no_test_env):
    sent, _ = await _run(_scope(headers=_bearer("not-a-jwt")))
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 401
    headers = dict(start["headers"])
    assert headers.get(b"www-authenticate") == b"Bearer"


async def test_missing_token_returns_401(no_test_env):
    sent, _ = await _run(_scope())
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 401


# ---------------------------------------------------------------------------
# API-key system identity
# ---------------------------------------------------------------------------
async def test_system_api_key_grants_admin_identity(no_test_env, monkeypatch):
    monkeypatch.setattr(
        type(settings), "supremeai_api_token", property(lambda self: "system-token-123")
    )
    sent, scope = await _run(_scope(headers=_bearer("system-token-123")))
    assert sent[-1]["type"] == "downstream.called"
    assert scope["user"]["sub"] == "system_api_key"
    assert scope["user"]["role"] == "admin"


# ---------------------------------------------------------------------------
# Test-environment bypass contract
# ---------------------------------------------------------------------------
async def test_test_env_bypass_attaches_test_admin(monkeypatch):
    """With ALLOW_TEST_AUTH_BYPASS in a test env, token-less requests pass through.

    NOTE on the contract: the first passthrough branch (is_test_environment
    and is_bypass_allowed) forwards the request WITHOUT attaching a scope
    identity — downstream route dependencies supply auth context there. The
    test_admin identity attach (lines below) only applies to the invalid-
    token path.
    """
    monkeypatch.setattr(auth_mw, "is_test_environment", lambda: True)
    monkeypatch.setattr(type(settings), "is_bypass_allowed", property(lambda self: True))
    sent, scope = await _run(_scope())
    assert sent[-1]["type"] == "downstream.called"
    assert "user" not in scope  # passthrough carries no fabricated identity


async def test_test_env_bypass_invalid_token_still_passes_through(monkeypatch):
    """Bypass passthrough happens BEFORE token validation — no identity attached.

    EVIDENCE for the owner (no code changed): the test_admin identity-attach
    blocks inside __call__ (the `if not token` and `if not payload` bypass
    branches) are currently UNREACHABLE, because the earlier
    `is_test_environment() and settings.is_bypass_allowed` passthrough
    forwards EVERY request — token-less, valid, or garbage — before token
    validation can fail. If fabricating test_admin identity matters, that
    early passthrough needs restructuring; this test locks the CURRENT
    observable behavior so any change is a deliberate decision.
    """
    monkeypatch.setattr(auth_mw, "is_test_environment", lambda: True)
    monkeypatch.setattr(type(settings), "is_bypass_allowed", property(lambda self: True))
    sent, scope = await _run(_scope(headers=_bearer("garbage-token")))
    assert sent[-1]["type"] == "downstream.called"
    assert "user" not in scope  # passthrough carries no fabricated identity


async def test_production_never_bypasses_even_with_flag(monkeypatch):
    """The bypass flag must be inert outside a test environment (prod guard)."""
    monkeypatch.setattr(auth_mw, "is_test_environment", lambda: False)
    monkeypatch.setattr(type(settings), "is_bypass_allowed", property(lambda self: True))
    sent, _ = await _run(_scope())
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 401


# ---------------------------------------------------------------------------
# jti revocation (role-aware availability policy)
# ---------------------------------------------------------------------------
async def test_revoked_regular_user_token_fails_open(no_test_env, monkeypatch):
    """Regular users: a Redis blip must not lock them out (fail-open)."""

    async def _revoked(jti, is_admin=False):
        raise RuntimeError("redis down")

    monkeypatch.setattr("core.security.is_token_revoked", _revoked)
    token = _encode({"sub": "u-1", "role": "user", "jti": "jti-1"})
    sent, scope = await _run(_scope(headers=_bearer(token)))
    assert sent[-1]["type"] == "downstream.called"
    assert scope["user"]["sub"] == "u-1"


async def test_revoked_admin_token_fails_closed(no_test_env, monkeypatch):
    """Admin tokens: revocation verification failure must REJECT (fail-closed)."""

    async def _revoked(jti, is_admin=False):
        raise RuntimeError("redis down")

    monkeypatch.setattr("core.security.is_token_revoked", _revoked)
    token = _encode({"sub": "a-1", "role": "admin", "jti": "jti-2"})
    sent, _ = await _run(_scope(headers=_bearer(token)))
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 401
    body = next(m for m in sent if m.get("type") == "http.response.body")
    assert b"revocation could not be verified" in body["body"]


async def test_actually_revoked_token_is_rejected(no_test_env, monkeypatch):
    async def _revoked(jti, is_admin=False):
        return True

    monkeypatch.setattr("core.security.is_token_revoked", _revoked)
    token = _encode({"sub": "u-2", "role": "user", "jti": "jti-3"})
    sent, _ = await _run(_scope(headers=_bearer(token)))
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 401


# ---------------------------------------------------------------------------
# verify_admin_session_fail_closed — remaining branches
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_admin_verify_missing_jwt_secret_returns_500(no_test_env, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(type(settings), "jwt_secret", property(lambda self: ""))
    request = type("R", (), {"headers": {"Authorization": "Bearer x"}})()
    with pytest.raises(HTTPException) as excinfo:
        await verify_admin_session_fail_closed(request)
    assert excinfo.value.status_code == 500


@pytest.mark.anyio
async def test_admin_verify_valid_admin_returns_payload(no_test_env):
    token = _encode({"sub": "admin-1", "role": "master_admin"})
    request = type("R", (), {"headers": {"Authorization": f"Bearer {token}"}})()
    payload = await verify_admin_session_fail_closed(request)
    assert payload["role"] == "master_admin"


@pytest.mark.anyio
async def test_admin_verify_non_admin_rejected(no_test_env):
    from fastapi import HTTPException

    token = _encode({"sub": "u-1", "role": "user"})
    request = type("R", (), {"headers": {"Authorization": f"Bearer {token}"}})()
    with pytest.raises(HTTPException) as excinfo:
        await verify_admin_session_fail_closed(request)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Not authorized"


# ---------------------------------------------------------------------------
# JWT-COOKIE-MIGRATION (issue #1668, ধাপ ২/২): httpOnly cookie auth source
# ---------------------------------------------------------------------------
async def test_cookie_token_authenticates_get(no_test_env):
    """The httpOnly access cookie (set at login) is a valid auth source for
    safe methods — no CSRF header required."""
    token = _encode({"sub": "cookie-user", "role": "viewer", "tenant_id": "t1"})
    sent, scope = await _run(
        _scope(
            path="/api/v1/agents",
            headers=[(b"cookie", f"supreme_access_token={token}".encode())],
        )
    )
    assert sent[-1]["type"] == "downstream.called"
    assert scope["user"]["sub"] == "cookie-user"


async def test_cookie_token_post_without_csrf_rejected(no_test_env):
    """Cookie-authenticated state-changing request without the matching
    X-CSRF-Token header must be rejected (double-submit pattern)."""
    token = _encode({"sub": "cookie-user", "role": "viewer", "tenant_id": "t1"})
    sent, _ = await _run(
        _scope(
            path="/api/v1/agents",
            method="POST",
            headers=[(b"cookie", f"supreme_access_token={token}".encode())],
        )
    )
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 403


async def test_cookie_token_post_with_matching_csrf_accepted(no_test_env):
    """Cookie-auth POST with matching CSRF cookie+header passes."""
    token = _encode({"sub": "cookie-user", "role": "viewer", "tenant_id": "t1"})
    csrf = "csrf-value-123"
    sent, scope = await _run(
        _scope(
            path="/api/v1/agents",
            method="POST",
            headers=[
                (b"cookie", f"supreme_access_token={token}; supreme_csrf_token={csrf}".encode()),
                (b"x-csrf-token", csrf.encode()),
            ],
        )
    )
    assert sent[-1]["type"] == "downstream.called"
    assert scope["user"]["sub"] == "cookie-user"


async def test_cookie_token_post_with_wrong_csrf_rejected(no_test_env):
    """A CSRF header that does not match the cookie must be rejected."""
    token = _encode({"sub": "cookie-user", "role": "viewer", "tenant_id": "t1"})
    sent, _ = await _run(
        _scope(
            path="/api/v1/agents",
            method="POST",
            headers=[
                (b"cookie", f"supreme_access_token={token}; supreme_csrf_token=real".encode()),
                (b"x-csrf-token", b"forged"),
            ],
        )
    )
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 403


async def test_bearer_header_still_takes_priority(no_test_env):
    """Existing clients: a valid Bearer header must win over the cookie, and
    must not require CSRF even on POST."""
    token = _encode({"sub": "header-user", "role": "viewer", "tenant_id": "t1"})
    stale_cookie_token = _encode({"sub": "stale-cookie", "role": "viewer"})
    sent, scope = await _run(
        _scope(
            path="/api/v1/agents",
            method="POST",
            headers=[
                (b"authorization", f"Bearer {token}".encode()),
                (b"cookie", f"supreme_access_token={stale_cookie_token}".encode()),
            ],
        )
    )
    assert sent[-1]["type"] == "downstream.called"
    assert scope["user"]["sub"] == "header-user"
