"""Unified Auth Identity Resolution for Gateway, Studio Data, and Frontend Compat.

Single source of truth for resolving caller identity from HMAC-signed tokens.
Prevents identity resolution drift between general gateway routes, studio_data,
and compat routes.
"""
from __future__ import annotations

import hashlib
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


def verified_guest_claims(token: str) -> dict | None:
    """Accept only signed, expiring guest credentials minted by keygen."""
    try:
        claims = verify_key(token) or {}
    except Exception:
        return None
    entropy = str(claims.get("entropy") or "")
    if (claims.get("client") != "guest" or claims.get("quota") != "guest"
            or not claims.get("exp") or not re.fullmatch(r"[a-f0-9]{32}", entropy)):
        return None
    return claims


def resolve_user_id(request: Request, require_registered: bool = False) -> str:
    """Resolve a verified principal; never share private state under anonymous IDs.

    Guest IDs are scoped to an issued token, not to a client-controlled header.
    Reissuing a guest token deliberately creates a new, isolated session.
    Static API keys can authorize stateless inference but are not user identities.
    """
    token = extract_token(request)
    from_cookie = not token
    if from_cookie:
        token = request.cookies.get("supremeai_guest_session", "").strip()
        if not verified_guest_claims(token):
            raise HTTPException(401, "A verified user or guest session is required for private data.")
    try:
        claims = verify_key(token) or {}
    except Exception:
        claims = {}

    client = str(claims.get("client") or "").strip()
    if client == "guest":
        guest = verified_guest_claims(token)
        if guest and not require_registered:
            digest = hashlib.sha256(("supremeai-guest-v1:" + guest["entropy"]).encode()).hexdigest()
            return "usr-guest-" + digest
        raise HTTPException(401, "A valid guest session or registered account is required.")

    if client == "studio-admin":
        return "usr-admin-primary"
    match = re.fullmatch(r"usr-(usr-[a-f0-9]{12})", client)
    if match:
        return match[1]
    if require_registered:
        raise HTTPException(401, "Sign in with a registered Studio account.")
    entropy = str(claims.get("entropy") or "")
    if not client or client in ("usr-anonymous", "usr-guest") or not re.fullmatch(r"[a-f0-9]{32}", entropy):
        raise HTTPException(401, "A verified user or guest session is required for private data.")
    # Generic service credentials with the same client name are not proof that
    # their bearers are the same end user. Scope them to the issued credential.
    digest = hashlib.sha256(("supremeai-client-v1:" + client + ":" + entropy).encode()).hexdigest()
    return "usr-client-" + digest
