"""Unified Auth Identity Resolution for Gateway, Studio Data, and Frontend Compat.

Single source of truth for resolving caller identity from HMAC-signed tokens.
Prevents identity resolution drift between general gateway routes, studio_data,
and compat routes.
"""
from __future__ import annotations

import re

from fastapi import HTTPException, Request

try:
    from .keygen import verify_key
except ImportError:
    try:
        from gateway.service.keygen import verify_key  # type: ignore[no-redef]
    except ImportError:
        from service.keygen import verify_key  # type: ignore[no-redef]


def extract_token(request: Request) -> str:
    """Extract auth token from Authorization: Bearer or X-SupremeAI-Key header."""
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-supremeai-key", "").strip()


def resolve_user_id(request: Request, require_registered: bool = False) -> str:
    """Consolidated auth identity resolution.

    - When require_registered=False (standard endpoints like chat/conversations):
      unauthenticated callers get 'usr-anonymous'; authenticated clients receive
      'usr-admin-primary' or 'usr-<client>'.
    - When require_registered=True (wallet/billing/account endpoints):
      strictly requires a registered account (usr-usr-<12hex>) or studio-admin;
      raises HTTP 401 otherwise.
    """
    token = extract_token(request)
    if not token:
        if require_registered:
            raise HTTPException(401, "Sign in with a registered Studio account.")
        return "usr-anonymous"

    try:
        claims = verify_key(token) or {}
    except Exception:
        claims = {}

    client = str(claims.get("client") or "").strip()
    if not client:
        if require_registered:
            raise HTTPException(401, "Sign in with a registered Studio account.")
        return "usr-anonymous"

    if client == "studio-admin":
        return "usr-admin-primary"

    # studio_auth_{login,register} sign 'usr-' + the stored 'usr-<12 hex>' id.
    match = re.fullmatch(r"usr-(usr-[a-f0-9]{12})", client)
    if match:
        return match[1]

    if require_registered:
        if client.startswith("usr-") and client not in ("usr-guest", "guest"):
            return client
        raise HTTPException(401, "Sign in with a registered Studio account.")

    return client if client.startswith("usr-") else f"usr-{client}"
