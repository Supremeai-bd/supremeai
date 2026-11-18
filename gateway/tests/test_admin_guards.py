"""Regression tests for admin authorization guards.

Covers two fixes:
1. ``gateway.service.frontend_compat.require_github_admin`` — GitHub
   orchestration routes (approve/merge/rerun/cancel/dispatch) must reject
   ordinary client keys and guest tokens, and accept only admin principals.
2. ``gateway.service.app._is_admin_principal`` — ``/admin-api/logs`` must NOT
   be reachable with a generic client key (the old ``is_client`` bypass).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import service.frontend_compat as fc
from service.app import _is_admin_principal


def _fake_token(token: str, x_supremeai_key: str | None = None):
    """Build a minimal Request-like object exposing headers."""
    headers: dict[str, str] = {}
    if token:
        headers["authorization"] = f"Bearer {token}"
    return SimpleNamespace(headers=headers)


def test_frontend_compat_requires_superadmin_key(monkeypatch):
    monkeypatch.setattr(fc, "_SUPERADMIN_KEY", "super-secret")
    monkeypatch.setattr(fc, "_verify_admin_token", lambda t: False)
    # No key at all -> must fail closed.
    with pytest.raises(fc.HTTPException) as exc:
        import asyncio

        asyncio.run(
            fc.require_github_admin(_fake_token(""), None)
        )
    assert exc.value.status_code == 403


def test_frontend_compat_superadmin_key_passes(monkeypatch):
    import asyncio

    monkeypatch.setattr(fc, "_SUPERADMIN_KEY", "super-secret")
    monkeypatch.setattr(fc, "_verify_admin_token", lambda t: False)
    # Correct superadmin key -> passes (no exception).
    asyncio.run(
        fc.require_github_admin(_fake_token(""), "super-secret")
    )


def test_frontend_compat_admin_token_passes(monkeypatch):
    import asyncio

    monkeypatch.setattr(fc, "_SUPERADMIN_KEY", "super-secret")
    monkeypatch.setattr(fc, "_verify_admin_token", lambda t: t == "sk-supreme-admin")
    asyncio.run(
        fc.require_github_admin(_fake_token("sk-supreme-admin"), None)
    )


def test_frontend_compat_standard_token_denied(monkeypatch):
    import asyncio

    monkeypatch.setattr(fc, "_SUPERADMIN_KEY", "super-secret")
    monkeypatch.setattr(fc, "_verify_admin_token", lambda t: False)
    with pytest.raises(fc.HTTPException) as exc:
        asyncio.run(
            fc.require_github_admin(_fake_token("sk-supreme-standard"), None)
        )
    assert exc.value.status_code == 403


def test_is_admin_principal_superadmin_key(monkeypatch):
    import service.app as app_mod

    monkeypatch.setattr(app_mod, "SUPERADMIN_KEY", "top-secret")
    assert _is_admin_principal(_fake_token(""), None, "top-secret") is True


def test_is_admin_principal_wrong_key_denied(monkeypatch):
    import service.app as app_mod

    monkeypatch.setattr(app_mod, "SUPERADMIN_KEY", "top-secret")
    monkeypatch.setattr(app_mod, "verify_key", lambda k: None)
    assert _is_admin_principal(_fake_token(""), None, "wrong") is False


def test_is_admin_principal_no_token_denied(monkeypatch):
    import service.app as app_mod

    monkeypatch.setattr(app_mod, "SUPERADMIN_KEY", "top-secret")
    assert _is_admin_principal(_fake_token(""), None, None) is False


def test_is_admin_principal_standard_key_denied(monkeypatch):
    import service.app as app_mod

    monkeypatch.setattr(app_mod, "SUPERADMIN_KEY", "top-secret")
    # A standard-quota client key must NOT be treated as admin.
    monkeypatch.setattr(
        app_mod, "verify_key", lambda k: {"client": "usr-1", "quota": "standard"}
    )
    assert _is_admin_principal(_fake_token("sk-supreme-usr"), None, None) is False


def test_is_admin_principal_admin_key_allowed(monkeypatch):
    import service.app as app_mod

    monkeypatch.setattr(app_mod, "SUPERADMIN_KEY", "top-secret")
    # Admin-scoped signed key (studio-admin / unlimited) -> allowed.
    monkeypatch.setattr(
        app_mod, "verify_key", lambda k: {"client": "studio-admin", "quota": "unlimited"}
    )
    assert _is_admin_principal(_fake_token("sk-supreme-admin"), None, None) is True