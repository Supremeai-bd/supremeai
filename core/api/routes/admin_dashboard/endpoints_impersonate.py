"""Impersonation endpoints
(POST /admin-api/users/impersonate/{username}, POST /admin-api/impersonate).

বাংলা মন্তব্য (security, Step 0): আগে এই টোকেনে কোনো `exp` ছিল না (চিরস্থায়ী),
`jti` ছিল না (রিভোক অসম্ভব), অস্তিত্বহীন ইউজারের নামেও টোকেন বানাত, আর অ্যাডমিন
ইউজারকে impersonate করলে চিরস্থায়ী অ্যাডমিন টোকেন তৈরি হত। এখন:
  * শুধু বিদ্যমান ইউজার (না থাকলে 404)
  * অ্যাডমিন রোলের ইউজারকে impersonate নিষেধ (403) — privilege laundering বন্ধ
  * টোকেন ১৫ মিনিটে শেষ (`exp`), `iat` + রিভোকযোগ্য `jti` সহ
  * প্রতিটি impersonation WARNING লেভেলে অডিট-লগ হয়
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import jwt
from fastapi import Depends, HTTPException

from api.routes.admin_auth import require_admin_token
from api.routes.admin_dashboard import load_users, router
from api.routes.admin_dashboard._models import ImpersonateRequest
from core.config import settings
from core.monitoring.logging_config import logger

IMPERSONATION_TTL_SECONDS = 15 * 60
_PRIVILEGED_ROLES = frozenset({"admin", "god", "owner", "superadmin"})


def _find_user(identifier: str) -> dict[str, Any] | None:
    users = load_users()
    return next(
        (u for u in users if u.get("username") == identifier or str(u.get("id", "")) == identifier),
        None,
    )


def build_impersonation_claims(
    target: dict[str, Any], impersonator: str, now: int | None = None
) -> dict[str, Any]:
    """Short-lived, revocable claims for a non-privileged target user."""
    issued_at = int(now if now is not None else time.time())
    return {
        "uid": target["username"],
        "role": target.get("role") or "user",
        "impersonator": impersonator,
        "impersonation": True,
        "iat": issued_at,
        "exp": issued_at + IMPERSONATION_TTL_SECONDS,
        "jti": f"imp_{uuid.uuid4().hex}",
    }


def _issue_impersonation_token(identifier: str, current_admin: dict) -> dict[str, Any]:
    target = _find_user(identifier)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if str(target.get("role", "")).lower() in _PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Admin accounts cannot be impersonated")

    impersonator = str(current_admin.get("uid") or current_admin.get("sub") or "admin")
    claims = build_impersonation_claims(target, impersonator)
    token = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")
    logger.warning(
        f"AUDIT admin.impersonate impersonator={impersonator} "
        f"target={target['username']} jti={claims['jti']} "
        f"expires_in={IMPERSONATION_TTL_SECONDS}s"
    )
    return {"token": token, "user": target, "expires_in": IMPERSONATION_TTL_SECONDS}


@router.post("/users/impersonate/{username}")
async def impersonate_user(username: str, current_admin: dict = Depends(require_admin_token)):
    issued = _issue_impersonation_token(username, current_admin)
    return {
        "status": "success",
        "impersonation_token": issued["token"],
        "user": issued["user"],
        "expires_in": issued["expires_in"],
    }


@router.post("/impersonate")
async def impersonate_by_payload(
    payload: ImpersonateRequest, current_admin: dict = Depends(require_admin_token)
):
    """Impersonate user via JSON payload for CommandCenter."""
    return _issue_impersonation_token(payload.user_id, current_admin)
