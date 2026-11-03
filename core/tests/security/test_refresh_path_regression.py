"""Regression guard: /api/v1/auth/refresh must be reachable (auth-middleware bypass).

Audit session (2026-08-30) found that ``POST /api/v1/auth/refresh`` was blocked
by the access-token auth middleware with 401 because the path was missing from
``SUPREMEAI_PUBLIC_PATHS``. The refresh endpoint authenticates via the
refresh-token JWT carried in the JSON body (``type=refresh`` enforced,
fail-closed inside the endpoint) — a Bearer *access* token is neither available
nor required by design. With the path gated, clients could never renew sessions
(token refresh was fully broken in production; previously misclassified as an
sqlite/JSONB env-specific test failure).

These tests lock the fix in:
  1. the default public-path config contains the refresh path;
  2. the middleware classifies the path as public (unit level);
  3. the refresh endpoint still fails closed without a valid refresh token
     (401/422) — making it public must NOT make it unauthenticated.
"""

from __future__ import annotations

import pytest


class TestRefreshPathReachability:
    """AUD follow-up: token refresh must not be 401'd by the access middleware."""

    def test_refresh_path_in_default_public_paths(self):
        from core.config import settings

        assert "/api/v1/auth/refresh" in settings.supremeai_public_paths

    def test_middleware_classifies_refresh_as_public(self):
        from core.security.authentication.auth_middleware import _is_public_path

        assert _is_public_path("/api/v1/auth/refresh") is True
        # sanity: a protected route must stay protected
        assert _is_public_path("/api/v1/conversations") is False

    def test_refresh_route_keeps_fail_closed_validation(self):
        """Making the path public bypasses only the access-token middleware.

        The route handler itself must still reject invalid refresh tokens.
        """
        # Handler validates the JWT and rejects garbage — fail closed
        import asyncio
        from unittest.mock import MagicMock

        from fastapi import Request, Response

        from api.routes.auth import RefreshRequest, refresh_token_endpoint

        request_mock = MagicMock(spec=Request)
        request_mock.cookies = {}
        response_mock = MagicMock(spec=Response)

        bad = RefreshRequest(refresh_token="not-a-valid-jwt")
        with pytest.raises(Exception) as exc_info:
            asyncio.run(
                refresh_token_endpoint(body=bad, request=request_mock, response=response_mock)
            )
        assert getattr(exc_info.value, "status_code", None) == 401
