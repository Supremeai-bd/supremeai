"""P0 — Production docs/OpenAPI exposure policy tests.

বাংলা: প্রোডাকশনে /docs, /redoc, openapi.json ডিফল্ট বন্ধ থাকবে;
স্পষ্ট অপট-ইন + শক্তিশালী পাসওয়ার্ড ছাড়া কখনো খোলা থাকবে না —
"dev_password_only" কখনোই প্রোডাকশন ফলব্যাক নয়।
"""

import base64

import pytest

from core.config import Settings
from core.middleware.docs_auth import DocsAuthMiddleware, _is_docs_path

# ---------------------------------------------------------------------------
# Settings policy (effective_docs_enabled)
# ---------------------------------------------------------------------------


def _make_settings(env: str, extra_env: dict | None = None) -> Settings:
    """Build a Settings instance with a controlled ENV and extra overrides."""
    import os
    from unittest.mock import patch

    env_overrides = {"ENV": env}
    env_overrides.update(extra_env or {})
    # বাংলা: বাইরের প্রসেস এনভ থেকে docs-সংক্রান্ত ভেরিয়েবল আইসোলেট করা।
    for var in ("SUPREMEAI_DOCS_ENABLED", "SUPREMEAI_DOCS_PASSWORD", "SUPREMEAI_DOCS_USERNAME"):
        os.environ.pop(var, None)
    with patch.dict(os.environ, env_overrides, clear=False):
        return Settings()


def test_local_docs_enabled_by_default():
    s = _make_settings("local")
    assert s.effective_docs_enabled is True


def test_local_docs_can_be_disabled_explicitly():
    s = _make_settings("local", {"SUPREMEAI_DOCS_ENABLED": "false"})
    assert s.effective_docs_enabled is False


def test_production_docs_disabled_by_default():
    s = _make_settings("production")
    assert s.docs_enabled is None
    assert s.effective_docs_enabled is False


def test_staging_docs_disabled_by_default():
    s = _make_settings("staging")
    assert s.effective_docs_enabled is False


def test_production_optin_requires_strong_password():
    # Opt-in with the dev fallback password → still effectively disabled
    # (and at real boot, config_validation fails fast).
    s = _make_settings(
        "production",
        {"SUPREMEAI_DOCS_ENABLED": "true", "SUPREMEAI_DOCS_PASSWORD": "dev_password_only"},
    )
    assert s.effective_docs_enabled is False
    assert not s.docs_password_ok


def test_production_optin_short_password_still_disabled():
    s = _make_settings(
        "production", {"SUPREMEAI_DOCS_ENABLED": "true", "SUPREMEAI_DOCS_PASSWORD": "short"}
    )
    assert s.effective_docs_enabled is False


def test_production_optin_with_strong_password_enabled():
    s = _make_settings(
        "production",
        {"SUPREMEAI_DOCS_ENABLED": "true", "SUPREMEAI_DOCS_PASSWORD": "x" * 24},
    )
    assert s.effective_docs_enabled is True


# ---------------------------------------------------------------------------
# DocsAuthMiddleware (raw ASGI)
# ---------------------------------------------------------------------------


async def _dummy_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"OK"})


def _basic(user: str, pwd: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode()


def _run(scope: dict):
    """Invoke the middleware and return captured status code."""

    import asyncio

    mw = DocsAuthMiddleware(_dummy_app)
    captured = {}

    async def _receive():
        return {"type": "http.request", "body": b""}

    async def _send(message):
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]

    asyncio.run(mw(scope, _receive, _send))
    return captured.get("status")


def _scope(path: str, authorization: str | None = None) -> dict:
    headers = [(b"host", b"testserver")]
    if authorization:
        headers.append((b"authorization", authorization.encode()))
    return {"type": "http", "method": "GET", "path": path, "headers": headers}


def test_disabled_docs_returns_404(monkeypatch):
    # বাংলা: ফিল্ড প্যাচ — effective_docs_enabled একটি read-only property।
    monkeypatch.setattr("core.middleware.docs_auth.settings.docs_enabled", False)
    monkeypatch.setattr("core.middleware.docs_auth.settings.env", "local")
    assert _run(_scope("/docs")) == 404
    assert _run(_scope("/redoc")) == 404
    assert _run(_scope("/api/v1/openapi.json")) == 404


def test_enabled_local_docs_pass_through(monkeypatch):
    monkeypatch.setattr("core.middleware.docs_auth.settings.docs_enabled", True)
    monkeypatch.setattr("core.middleware.docs_auth.settings.env", "local")
    assert _run(_scope("/docs")) == 200
    assert _run(_scope("/api/v1/openapi.json")) == 200


def test_production_docs_require_basic_auth(monkeypatch):
    monkeypatch.setattr("core.middleware.docs_auth.settings.docs_enabled", True)
    monkeypatch.setattr("core.middleware.docs_auth.settings.env", "production")
    monkeypatch.setattr("core.middleware.docs_auth.settings.docs_username", "admin")
    monkeypatch.setattr(
        "core.middleware.docs_auth.settings.docs_password",
        type("S", (), {"get_secret_value": lambda self: "x" * 24})(),
    )
    # No credentials → 401 + challenge
    status = _run(_scope("/docs"))
    assert status == 401
    # Wrong credentials → 401
    assert _run(_scope("/docs", _basic("admin", "wrong-password"))) == 401
    # Correct credentials → pass through to app (200)
    assert _run(_scope("/docs", _basic("admin", "x" * 24))) == 200
    # OpenAPI JSON is gated by the same gate
    assert _run(_scope("/api/v1/openapi.json")) == 401


def test_non_docs_paths_never_gated(monkeypatch):
    monkeypatch.setattr("core.middleware.docs_auth.settings.env", "production")
    assert _run(_scope("/api/v1/health/ready")) == 200
    assert _run(_scope("/chat")) == 200


def test_is_docs_path_boundaries():
    assert _is_docs_path("/docs")
    assert _is_docs_path("/redoc")
    assert _is_docs_path("/openapi.json")
    assert _is_docs_path("/api/v1/openapi.json")
    assert not _is_docs_path("/docs-something-else")
    assert not _is_docs_path("/api/v1/docs")


@pytest.mark.parametrize("env", ["production", "staging"])
def test_docs_policy_never_uses_dev_fallback(env):
    """dev_password_only must NEVER count as a production docs gate."""
    s = _make_settings(env, {"SUPREMEAI_DOCS_ENABLED": "true"})
    assert s.docs_password_ok is False
    assert s.effective_docs_enabled is False
