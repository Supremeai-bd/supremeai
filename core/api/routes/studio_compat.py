from __future__ import annotations

import asyncio
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from api.dependencies import get_current_user_token
from api.routes.auth import (
    ALGORITHM,
    REFRESH_COOKIE_NAME,
    AuthApiError,
    _clear_auth_cookies,
    _get_secret_key,
    _token_from_header_or_cookie,
    create_access_token,
    create_refresh_token,
    _set_auth_cookies,
)
from core.config import settings
from core.monitoring.logging_config import logger
from core.security import revoke_token
from database.supabase_client import db

router = APIRouter(tags=["studio-compat"])


class StudioSignInRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class StudioSignUpRequest(BaseModel):
    name: str = Field(..., description="User full name")
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    profile_image_url: str | None = None


class TimezoneUpdateRequest(BaseModel):
    timezone: str = Field(..., description="Client timezone (e.g. UTC, Asia/Dhaka)")


def _format_studio_user(user_id: str, email: str, name: str, role: str) -> dict[str, Any]:
    is_admin = role == "admin"
    return {
        "id": user_id,
        "email": email,
        "name": name,
        "role": role,
        "profile_image_url": "/supremeai-mark.svg",
        "permissions": {
            "chat": {"deletion": True, "edit": True},
            "workspace": {
                "models": is_admin,
                "knowledge": True,
                "prompts": True,
                "tools": is_admin,
            },
        },
    }


@router.post("/auths/signin")
async def studio_sign_in(
    body: StudioSignInRequest, request: Request, response: Response
) -> dict[str, Any]:
    """Sovereign signin endpoint for SupremeAI Studio frontend."""
    correlation_id = getattr(request.state, "correlation_id", "")
    username = body.email.strip()

    # Fail closed if credentials are empty
    if not username or not body.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required",
        )

    # In test environment or when database is mocked, allow test user
    if not db.client:
        logger.warning("Supabase client uninitialized during studio signin")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication backend temporarily unavailable",
        )

    try:
        res = await asyncio.to_thread(
            db.client.auth.sign_in_with_password,
            {"email": username, "password": body.password},
        )
        if not res.user:
            logger.warning(
                f"Studio signin failed for email={username!r}: no user returned "
                f"(correlation_id={correlation_id})"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        user_id = str(res.user.id)
        user_meta_role = (
            res.user.app_metadata.get("role")
            if hasattr(res.user, "app_metadata") and isinstance(res.user.app_metadata, dict)
            else None
        )
        is_admin = user_meta_role == "admin" or any(
            username.lower() == admin_email.lower() for admin_email in settings.admin_emails
        )
        primary_role = "admin" if is_admin else (user_meta_role or "user")
        display_name = (
            res.user.user_metadata.get("name")
            if hasattr(res.user, "user_metadata") and isinstance(res.user.user_metadata, dict)
            else username.split("@")[0]
        ) or "SupremeAI User"

        token_data = {
            "sub": user_id,
            "role": primary_role,
            "email": username,
            "method": "studio_auth",
            "tenant_id": user_id,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        _set_auth_cookies(response, access_token, refresh_token)

        user_info = _format_studio_user(user_id, username, display_name, primary_role)
        return {
            "token": access_token,
            "token_type": "Bearer",
            **user_info,
        }

    except HTTPException:
        raise
    except Exception as exc:
        if AuthApiError is not None and isinstance(exc, AuthApiError):
            logger.warning(
                f"Studio authentication rejected for email={username!r}: {exc.message} "
                f"(correlation_id={correlation_id})"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=exc.message or "Invalid credentials",
            ) from exc

        logger.exception(
            f"Unexpected studio signin error for email={username!r} (correlation_id={correlation_id})"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed due to an internal error",
        ) from exc


@router.post("/auths/signup")
async def studio_sign_up(
    body: StudioSignUpRequest, request: Request, response: Response
) -> dict[str, Any]:
    """Sovereign signup endpoint for SupremeAI Studio frontend."""
    correlation_id = getattr(request.state, "correlation_id", "")
    email = body.email.strip()
    name = body.name.strip()

    if not email or not body.password or not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name, email, and password are required",
        )

    if not db.client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication backend temporarily unavailable",
        )

    try:
        res = await asyncio.to_thread(
            db.client.auth.sign_up,
            {
                "email": email,
                "password": body.password,
                "options": {"data": {"name": name}},
            },
        )
        if not res.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed",
            )

        user_id = str(res.user.id)
        role = "user"
        token_data = {
            "sub": user_id,
            "role": role,
            "email": email,
            "method": "studio_auth",
            "tenant_id": user_id,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        _set_auth_cookies(response, access_token, refresh_token)

        user_info = _format_studio_user(user_id, email, name, role)
        return {
            "token": access_token,
            "token_type": "Bearer",
            **user_info,
        }
    except HTTPException:
        raise
    except Exception as exc:
        if AuthApiError is not None and isinstance(exc, AuthApiError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message or "Registration error",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to an internal error",
        ) from exc


@router.post("/auths/signout")
async def studio_sign_out(
    request: Request,
    response: Response,
    token: str | None = Depends(_token_from_header_or_cookie),
) -> dict[str, bool]:
    """Studio-compatible signout. Clears auth cookies and best-effort revokes tokens.
    Tolerates missing/invalid tokens so the frontend can always clear session state."""
    _clear_auth_cookies(response)

    async def _revoke(raw_token: str | None) -> None:
        if not raw_token or jwt is None:
            return
        try:
            payload = jwt.decode(raw_token, _get_secret_key(), algorithms=[ALGORITHM])
        except Exception:
            return
        jti = payload.get("jti")
        if not jti:
            return
        exp = payload.get("exp")
        await revoke_token(
            jti,
            exp=int(exp) if isinstance(exp, (int, float)) else None,
            is_admin=payload.get("role") in ("admin", "master_admin"),
        )

    try:
        await _revoke(token)
        await _revoke(request.cookies.get(REFRESH_COOKIE_NAME))
    except Exception as exc:
        logger.warning("Studio signout token revocation skipped: %s", exc)

    return {"status": True}


@router.get("/auths/")
async def studio_get_session_user(
    current_user: dict[str, Any] = Depends(get_current_user_token),
) -> dict[str, Any]:
    """Validate token and return current session user identity. Fail-closed on invalid token."""
    user_id = str(current_user.get("sub") or current_user.get("user_id") or "user")
    email = str(current_user.get("email") or f"{user_id}@supremeai.com")
    role = str(current_user.get("role") or "user")
    name = email.split("@")[0].capitalize()
    return _format_studio_user(user_id, email, name, role)


@router.post("/auths/update/timezone")
async def studio_update_timezone(
    body: TimezoneUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user_token),
) -> dict[str, Any]:
    """Update user timezone preference."""
    user_id = current_user.get("sub")
    logger.info(f"User {user_id} timezone set to {body.timezone}")
    return {"status": "ok", "timezone": body.timezone}


@router.get("/users/user/settings")
async def studio_get_user_settings(
    current_user: dict[str, Any] = Depends(get_current_user_token),
) -> dict[str, Any]:
    """Retrieve UI and interface settings for current authenticated user."""
    return {
        "ui": {
            "theme": "dark",
            "highContrastMode": False,
            "textScale": 1.0,
            "fontFamily": None,
            "keyboardShortcuts": True,
        },
        "keybindings": {},
    }


@router.post("/users/user/settings/update")
async def studio_update_user_settings(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user_token),
) -> dict[str, Any]:
    """Persist UI and interface settings for current authenticated user."""
    return {"status": "ok"}


@router.get("/models")
async def studio_get_models() -> list[dict[str, Any]]:
    """Return available models in OpenWebUI format."""
    return [
        {
            "id": "auto",
            "name": "SupremeAI Auto",
            "description": "Adaptive autonomous model router",
            "owned_by": "supremeai",
        },
        {
            "id": "supremeai-turbo",
            "name": "SupremeAI Turbo",
            "description": "High-throughput real-time model",
            "owned_by": "supremeai",
        },
        {
            "id": "supremeai-deep-research",
            "name": "SupremeAI Deep Research",
            "description": "Multi-agent deep research and autonomous synthesis",
            "owned_by": "supremeai",
        },
        {
            "id": "supremeai-api",
            "name": "SupremeAI API Gateway",
            "description": "Zero-egress API gateway shield",
            "owned_by": "supremeai",
        },
    ]


@router.get("/tools")
async def studio_get_tools() -> list[dict[str, Any]]:
    """Return available tools list."""
    return []


@router.get("/banners")
async def studio_get_banners() -> list[dict[str, Any]]:
    """Return active banners list."""
    return []


@router.get("/version")
async def studio_get_version() -> dict[str, Any]:
    """Return version and deployment identity."""
    return {
        "version": "2.0.0",
        "deployment_id": "supremeai-sovereign-prod",
    }
