"""
SupremeAI 2.0 — API Key Authentication Middleware
Validates API keys on every request, enforces rate limits, and attaches user context.
"""
import time
from typing import Optional, Tuple
from uuid import UUID

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from loguru import logger

from core.database import get_db_session
from core.rate_limiter import get_rate_limiter, RateLimitStatus
from core.security import extract_prefix_from_key, validate_key_format, mask_key
from models.api_key import APIKey, KeyStatus


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates API keys and enforces rate limits.

    Supports two auth modes:
    1. Bearer token (JWT) — for user-facing endpoints
    2. API key (sk_live_xxx) — for programmatic access

    Priority: If both are present, API key takes precedence for inference endpoints.
    """

    def __init__(self, app: ASGIApp, exempt_paths: Optional[list] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/health",
            "/actuator/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/admin/login",
            "/api/admin/verify",
            "/api/admin/easy-login",
            "/api/admin/firebase-login",
            "/api/v1/auth",  # Auth endpoints
        ]
        self.bearer_prefix = "Bearer "
        self.key_prefix = "sk_"

    async def dispatch(self, request: Request, call_next):
        """Process each request through API key validation."""

        # Skip exempt paths
        path = request.url.path
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            return await call_next(request)

        # Extract auth header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header:
            # Allow anonymous for some endpoints (will be checked by endpoint decorator)
            request.state.api_key = None
            request.state.user = None
            return await call_next(request)

        # Determine auth type
        if auth_header.startswith(self.bearer_prefix):
            token = auth_header[len(self.bearer_prefix):]

            # Check if it's an API key (starts with sk_)
            if token.startswith(self.key_prefix):
                await self._authenticate_api_key(request, token)
            else:
                # JWT token — let other middleware handle it
                request.state.api_key = None
                request.state.user = None

        return await call_next(request)

    async def _authenticate_api_key(self, request: Request, full_key: str):
        """Authenticate using API key."""
        start_time = time.time()

        # Validate format
        if not validate_key_format(full_key):
            logger.warning(f"Invalid API key format: {mask_key(full_key)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key format",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract prefix for lookup
        prefix = extract_prefix_from_key(full_key)

        # Get DB session
        db = next(get_db_session())

        try:
            # Lookup key by prefix
            api_key = db.query(APIKey).filter(
                APIKey.key_prefix == prefix,
                APIKey.status.in_([KeyStatus.ACTIVE.value, KeyStatus.SUSPENDED.value])
            ).first()

            if not api_key:
                logger.warning(f"API key not found: {mask_key(full_key)}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Verify hash
            if not api_key.verify_key(full_key):
                logger.warning(f"API key hash mismatch: {mask_key(full_key)}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Check status
            if api_key.status == KeyStatus.SUSPENDED.value:
                logger.warning(f"Suspended API key used: {api_key.id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API key is suspended. Please check your email or contact support.",
                )

            # Check expiration
            if api_key.expires_at and api_key.expires_at <= datetime.utcnow():
                api_key.status = KeyStatus.EXPIRED.value
                db.commit()
                logger.info(f"API key expired: {api_key.id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API key has expired. Please rotate your key.",
                )

            # Check IP whitelist
            if api_key.ip_whitelist:
                client_ip = request.client.host
                if not self._ip_in_whitelist(client_ip, api_key.ip_whitelist):
                    logger.warning(f"IP not in whitelist: {client_ip} for key {api_key.id}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Request IP not in key whitelist",
                    )

            # Check rate limits
            rate_limiter = get_rate_limiter()
            rate_status = await rate_limiter.check_rate_limit(
                key_id=str(api_key.id),
                rpm_limit=api_key.rate_limit_rpm,
                rpd_limit=api_key.rate_limit_rpd,
            )

            if not rate_status.allowed:
                logger.warning(
                    f"Rate limit exceeded for key {api_key.id}: "
                    f"RPM={rate_status.current_rpm}/{rate_status.rpm_limit}, "
                    f"RPD={rate_status.current_rpd}/{rate_status.rpd_limit}"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "message": "Rate limit exceeded",
                        "current_rpm": rate_status.current_rpm,
                        "rpm_limit": rate_status.rpm_limit,
                        "current_rpd": rate_status.current_rpd,
                        "rpd_limit": rate_status.rpd_limit,
                        "retry_after_ms": rate_status.retry_after_ms,
                    },
                    headers={
                        "X-RateLimit-Limit": str(rate_status.rpm_limit),
                        "X-RateLimit-Remaining": str(max(0, rate_status.rpm_limit - rate_status.current_rpm)),
                        "X-RateLimit-Reset": str(rate_status.retry_after_ms),
                        "Retry-After": str(rate_status.retry_after_ms // 1000),
                    },
                )

            # Attach key info to request state
            request.state.api_key = api_key
            request.state.user = {"uid": str(api_key.user_id)}
            request.state.scopes = api_key.scopes
            request.state.rate_limit_status = rate_status.to_dict()

            # Update last used
            api_key.last_used_at = datetime.utcnow()
            db.commit()

            # Log successful auth (async)
            latency = int((time.time() - start_time) * 1000)
            logger.debug(f"API key auth success: {api_key.id} in {latency}ms")

        finally:
            db.close()

    def _ip_in_whitelist(self, client_ip: str, whitelist: list) -> bool:
        """Check if client IP is in whitelist (supports CIDR)."""
        import ipaddress

        try:
            client = ipaddress.ip_address(client_ip)
            for entry in whitelist:
                if "/" in entry:
                    # CIDR notation
                    network = ipaddress.ip_network(entry, strict=False)
                    if client in network:
                        return True
                else:
                    # Single IP
                    if client == ipaddress.ip_address(entry):
                        return True
            return False
        except ValueError:
            return False


# Dependency for endpoints that require API key auth
def require_api_key(request: Request) -> APIKey:
    """Dependency to require API key authentication."""
    api_key = getattr(request.state, "api_key", None)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key


def require_scope(scope: str):
    """Dependency factory to require a specific scope."""
    def checker(request: Request):
        api_key = getattr(request.state, "api_key", None)
        if api_key and scope in api_key.scopes:
            return True
        # Also check JWT scopes if present
        jwt_scopes = getattr(request.state, "scopes", [])
        if scope in jwt_scopes:
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required scope: {scope}",
        )
    return checker
