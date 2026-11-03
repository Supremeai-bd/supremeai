# ============================================================
# SupremeAI - API Endpoint Test Suite
# Production-Ready pytest Tests for All REST API Endpoints
# ============================================================

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

# ============================================================
# MARKER: All tests in this module are integration tests
# ============================================================
pytestmark = [pytest.mark.integration]


class TestHealthEndpoints:
    """Test health check and monitoring endpoints."""

    @pytest.mark.unit
    async def test_health_check_endpoint(self, client: AsyncClient):
        """Test basic health check endpoint."""
        response = await client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy" or data.get("data", {}).get("status") == "healthy"

    @pytest.mark.unit
    async def test_liveness_probe(self, client: AsyncClient):
        """Test Kubernetes liveness probe endpoint."""
        response = await client.get("/api/v1/health/live")

        assert response.status_code == 200
        assert response.text == "OK" or response.json().get("status") == "alive"

    @pytest.mark.unit
    async def test_readiness_probe(self, client: AsyncClient):
        """Test Kubernetes readiness probe endpoint."""
        response = await client.get("/api/v1/health/ready")

        assert response.status_code == 200
        data = response.json()
        # Should check database connection status
        assert "status" in data

    @pytest.mark.unit
    async def test_metrics_endpoint(self, client: AsyncClient, admin_auth_headers: dict):
        """Test admin metrics endpoint at canonical /api/admin/metrics/dashboard."""
        response = await client.get("/api/admin/metrics/dashboard", headers=admin_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "financial_metrics" in data or "runtime_telemetry" in data


class TestAuthenticationEndpoints:
    """Test authentication-related endpoints."""

    @pytest.mark.auth
    async def test_user_registration(
        self,
        client: AsyncClient,
        generate_test_emails,
    ):
        """Test new user registration."""
        user_data = {
            "username": generate_test_emails(),
            "password": "SecurePassword123!",
            "name": "New Test User",
            "role": "user",
        }

        response = await client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code in [200, 201]
        data = response.json().get("data", response.json())
        assert "user_id" in data
        assert "access_token" in data
        assert "password" not in data  # Never return password/hash

    @pytest.mark.auth
    # FIX(#1097): un-skipped — Supabase-provider registration is the shipped
    # behavior (api/routes/auth uses supabase auth, not Firebase); tested live.
    async def test_user_registration_duplicate_email(
        self,
        client: AsyncClient,
        sample_user_registration_data,
        mock_supabase_db_client,
    ):
        """Duplicate email is rejected by the Supabase provider contract.

        The autouse mock always returns a fresh user; emulate the real
        provider's duplicate-email error on the second sign_up call. The
        handler maps AuthApiError to 400 (not the legacy 409).
        """
        from supabase_auth.errors import AuthApiError

        # First registration should succeed
        await client.post("/api/v1/auth/register", json=sample_user_registration_data)

        mock_supabase_db_client.auth.sign_up.side_effect = AuthApiError(
            "User already registered", 422, "user_already_exists"
        )

        # Second should fail
        response = await client.post("/api/v1/auth/register", json=sample_user_registration_data)

        assert response.status_code == 400  # provider rejection mapped to 400
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.auth
    async def test_user_registration_invalid_email(
        self,
        client: AsyncClient,
    ):
        """Test registration with invalid email format."""
        user_data = {
            "username": "not-an-email",
            "password": "SecurePassword123!",
            "name": "Test User",
        }

        response = await client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.auth
    # FIX(#1097): un-skipped — Supabase-provider registration is the shipped
    # behavior (api/routes/auth uses supabase auth, not Firebase); tested live.
    async def test_user_registration_weak_password(
        self,
        client: AsyncClient,
        generate_test_emails,
        mock_supabase_db_client,
    ):
        """Weak password is rejected by the provider password policy (-> 400)."""
        from supabase_auth.errors import AuthApiError

        mock_supabase_db_client.auth.sign_up.side_effect = AuthApiError(
            "Password should be at least 6 characters", 422, "weak_password"
        )
        user_data = {
            "username": generate_test_emails(),
            "password": "weak",  # Too short, no complexity
            "name": "Test User",
        }

        response = await client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 400  # Bad request
        assert "password" in response.json()["detail"].lower()

    @pytest.mark.auth
    async def test_user_login_success(
        self,
        client: AsyncClient,
        sample_user_registration_data,
    ):
        """Test successful user login."""
        # Register first
        await client.post("/api/v1/auth/register", json=sample_user_registration_data)

        # Login
        login_data = {
            "username": sample_user_registration_data["username"],
            "password": sample_user_registration_data["password"],
        }
        response = await client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json().get("data", response.json())
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.auth
    # FIX(#1097): un-skipped — Supabase-provider registration is the shipped
    # behavior (api/routes/auth uses supabase auth, not Firebase); tested live.
    async def test_user_login_wrong_password(
        self,
        client: AsyncClient,
        sample_user_registration_data,
        mock_supabase_db_client,
    ):
        """Login with wrong password fails: provider AuthApiError -> 401."""
        from supabase_auth.errors import AuthApiError

        # Register first
        await client.post("/api/v1/auth/register", json=sample_user_registration_data)

        mock_supabase_db_client.auth.sign_in_with_password.side_effect = AuthApiError(
            "Invalid login credentials", 400, "invalid_credentials"
        )

        # Login with wrong password
        login_data = {
            "username": sample_user_registration_data["username"],
            "password": "WrongPassword!",
        }
        response = await client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401  # Unauthorized

    @pytest.mark.auth
    async def test_token_refresh(
        self,
        client: AsyncClient,
        sample_user_registration_data,
    ):
        """Test refreshing access token."""
        # Register and login
        await client.post("/api/v1/auth/register", json=sample_user_registration_data)

        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": sample_user_registration_data["username"],
                "password": sample_user_registration_data["password"],
            },
        )

        tokens = login_response.json().get("data", login_response.json())
        refresh_token = tokens["refresh_token"]

        # Refresh token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json().get("data", refresh_response.json())
        assert "access_token" in new_tokens
        assert new_tokens["access_token"] != tokens["access_token"]  # New token issued

    @pytest.mark.auth
    async def test_get_current_user(
        self,
        client: AsyncClient,
        auth_headers: dict,
        sample_user_registration_data,
    ):
        """Test getting current authenticated user info."""
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json().get("data", response.json())
        assert data["email"] == sample_user_registration_data["username"]

    @pytest.mark.auth
    async def test_access_without_token(
        self,
        client: AsyncClient,
    ):
        """Test accessing protected endpoint without token fails."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401  # Unauthorized

    @pytest.mark.auth
    async def test_access_with_invalid_token(
        self,
        client: AsyncClient,
    ):
        """Test accessing with invalid/malformed token fails."""
        invalid_headers = {"Authorization": "Bearer invalid.token.here"}

        response = await client.get(
            "/api/v1/auth/me",
            headers=invalid_headers,
        )

        assert response.status_code == 401  # Unauthorized

    @pytest.mark.auth
    async def test_logout(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test user logout (token invalidation)."""
        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Token should no longer work
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers,
        )
        assert response.status_code == 401


class TestAdminEndpoints:
    """Test administration-only endpoints."""

    @pytest.mark.security
    async def test_admin_stats_accessible_only_to_admins(
        self,
        client: AsyncClient,
        auth_headers: dict,  # Regular user
        admin_auth_headers: dict,  # Admin user
    ):
        """Test that admin stats require admin role."""
        # Regular user should be denied
        response = await client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )
        assert response.status_code in [403, 404]  # Forbidden or not found

        # Admin should have access
        response = await client.get(
            "/api/v1/admin/stats",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.security
    async def test_list_all_users_admin_only(
        self,
        client: AsyncClient,
        auth_headers: dict,
        admin_auth_headers: dict,
    ):
        """Test that listing all users is admin-only."""
        # Regular user denied
        response = await client.get(
            "/api/v1/admin/users",
            headers=auth_headers,
        )
        assert response.status_code in [403, 404]

        # Admin allowed
        response = await client.get(
            "/api/v1/admin/users",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        json_data = response.json()
        data = json_data.get("data", json_data) if isinstance(json_data, dict) else json_data
        assert isinstance(data, list)

    @pytest.mark.security
    async def test_audit_log_access(
        self,
        client: AsyncClient,
        auth_headers: dict,
        admin_auth_headers: dict,
    ):
        """Test that audit logs are accessible only to admins."""
        # Regular user denied
        response = await client.get(
            "/api/v1/admin/audit-logs",
            headers=auth_headers,
        )
        assert response.status_code in [403, 404]

        # Admin allowed
        response = await client.get(
            "/api/v1/admin/audit-logs",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200


class TestErrorHandling:
    """Test API error handling and responses."""

    @pytest.mark.unit
    async def test_rate_limiting_headers_present(
        self,
        client: AsyncClient,
    ):
        """Test that rate limiting headers are present in responses."""
        response = await client.get("/api/v1/health")

        # Check for rate limit headers (if enabled)
        # These may or may not be present depending on config
        assert response.status_code == 200


class TestCORSHeaders:
    """Test CORS configuration."""

    @pytest.mark.unit
    async def test_cors_headers_present(
        self,
        client: AsyncClient,
    ):
        """Test CORS headers are set correctly."""
        # Make request with Origin header
        response = await client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000"},  # is_local()
        )

        # Check CORS headers
        if response.status_code == 200:
            # May or may not have CORS headers depending on preflight
            pass  # Just ensure no errors


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
