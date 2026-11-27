"""Durable WebAuthn passkey persistence for the Studio gateway.

Why this exists
    ``storage.py`` keeps passkeys in a SQLite file under the OS temp dir. On Render
    that directory is wiped on every redeploy, so users silently lost their
    passkeys ("No passkey devices registered" after a deploy).

Behaviour
    * ``SUPABASE_URL`` + ``SUPABASE_SERVICE_ROLE_KEY`` configured -> the
      ``public.user_passkeys`` table (service role only, RLS on, no policies) is the
      single source of truth. A failed query raises :class:`PasskeyStoreUnavailable`
      (HTTP 503) -- it is never replaced by an empty list or a stale local row,
      because a stale row could resurrect a revoked credential.
    * Not configured (local dev / tests) -> the existing SQLite helpers.
    * A credential id that already belongs to another account is never re-bound
      (:class:`PasskeyConflict`): attestation is ``none``, so a client could
      otherwise submit someone else's credential id and take over its row.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import httpx

try:
    from gateway.service import storage as _local
except ImportError:  # pragma: no cover - flat deploy layout
    from service import storage as _local  # type: ignore[no-redef]

logger = logging.getLogger("supremeai.passkey_store")

_TABLE = "user_passkeys"
_LIST_COLUMNS = "credential_id,user_id,role,device_name,created_at,last_used_at"
_FULL_COLUMNS = _LIST_COLUMNS + ",public_key_spki,counter,revoked"


class PasskeyStoreUnavailable(RuntimeError):
    """The durable passkey store is configured but could not be reached."""


class PasskeyConflict(RuntimeError):
    """The credential id is already bound to a different account."""


def _durable_config() -> Optional[tuple[str, str]]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not url or not key:
        return None
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.path or parsed.query or parsed.fragment:
        logger.error("SUPABASE_URL is not a bare https origin; passkeys use the local store")
        return None
    return url, key


def is_durable() -> bool:
    return _durable_config() is not None


def _rest(method: str, params: Dict[str, str], body: Optional[Dict[str, Any]] = None,
          prefer: str = "return=representation") -> List[Dict[str, Any]]:
    cfg = _durable_config()
    if cfg is None:  # pragma: no cover - callers check is_durable() first
        raise PasskeyStoreUnavailable("Durable passkey store is not configured.")
    url, key = cfg
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    if method != "GET":
        headers["Prefer"] = prefer
    try:
        with httpx.Client(timeout=httpx.Timeout(6.0, connect=3.0), follow_redirects=False) as client:
            res = client.request(method, f"{url}/rest/v1/{_TABLE}", params=params, headers=headers, json=body)
        if res.status_code == 409:
            raise PasskeyConflict("Passkey credential already exists.")
        res.raise_for_status()
        if not res.content:
            return []
        rows = res.json()
    except PasskeyConflict:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        # Never log the URL/key; the status code is enough to diagnose.
        status = getattr(getattr(exc, "response", None), "status_code", None)
        logger.error("Passkey store request failed (%s %s)", method, status or type(exc).__name__)
        raise PasskeyStoreUnavailable("Passkey storage is temporarily unavailable.") from None
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise PasskeyStoreUnavailable("Invalid passkey storage response.")
    return rows


def _normalise(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    if "revoked" in out:
        out["revoked"] = 1 if out["revoked"] else 0
    return out


# ── Public API (same shape as the storage.py helpers) ────────────────────────

def save_user_passkey(credential_id: str, user_id: str, role: str, public_key_spki: str,
                      device_name: str, counter: int = 0) -> Dict[str, Any]:
    if not is_durable():
        existing = _local.get_user_passkey(credential_id)
        if existing and existing.get("user_id") != user_id:
            raise PasskeyConflict("Passkey credential already exists.")
        return _local.save_user_passkey(credential_id, user_id, role, public_key_spki, device_name, counter)

    now = time.time()
    current = _rest("GET", {"select": "user_id,revoked", "credential_id": f"eq.{credential_id}"})
    if current:
        if current[0].get("user_id") != user_id or current[0].get("revoked"):
            raise PasskeyConflict("Passkey credential already exists.")
        _rest("PATCH", {"credential_id": f"eq.{credential_id}", "user_id": f"eq.{user_id}"},
              {"device_name": device_name, "last_used_at": now}, prefer="return=minimal")
    else:
        _rest("POST", {}, {
            "credential_id": credential_id, "user_id": user_id, "role": role,
            "public_key_spki": public_key_spki, "counter": max(0, int(counter)),
            "device_name": device_name, "created_at": now, "last_used_at": now, "revoked": False,
        }, prefer="return=minimal")
    return {"credential_id": credential_id, "user_id": user_id, "role": role,
            "device_name": device_name, "created_at": now}


def get_user_passkey(credential_id: str) -> Optional[Dict[str, Any]]:
    if not is_durable():
        return _local.get_user_passkey(credential_id)
    rows = _rest("GET", {"select": _FULL_COLUMNS, "credential_id": f"eq.{credential_id}",
                         "revoked": "is.false", "limit": "1"})
    return _normalise(rows[0]) if rows else None


def update_passkey_usage(credential_id: str, new_counter: int) -> None:
    if not is_durable():
        _local.update_passkey_usage(credential_id, new_counter)
        return
    _rest("PATCH", {"credential_id": f"eq.{credential_id}"},
          {"counter": max(0, int(new_counter)), "last_used_at": time.time()}, prefer="return=minimal")


def list_user_passkeys(user_id: str) -> List[Dict[str, Any]]:
    if not is_durable():
        return _local.list_user_passkeys(user_id)
    return _rest("GET", {"select": _LIST_COLUMNS, "user_id": f"eq.{user_id}",
                         "revoked": "is.false", "order": "created_at.desc", "limit": "100"})


def revoke_user_passkey(credential_id: str, user_id: str) -> bool:
    if not is_durable():
        return _local.revoke_user_passkey(credential_id, user_id)
    rows = _rest("PATCH", {"credential_id": f"eq.{credential_id}", "user_id": f"eq.{user_id}",
                           "revoked": "is.false", "select": "credential_id"}, {"revoked": True})
    return bool(rows)
