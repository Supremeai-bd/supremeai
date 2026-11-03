"""Admin routes tests for SupremeAI 2.0."""

import base64
import hashlib
import hmac
import os
import struct
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


class TestHelperFunctions:
    """Tests for admin route helper functions — rewritten for Firebase auth (#1010).

    Old tests tested _hash_password/_verify_password/_get_admin_credentials which
    were removed when migrating to Firebase auth. New tests cover the actual
    helper functions that exist in admin_routes.py today.
    """

    def test_trusted_browser_key_is_deterministic(self):
        """_trusted_browser_key returns same key for same token."""
        from api.routes.admin_routes import _trusted_browser_key

        key1 = _trusted_browser_key("token-abc-123")
        key2 = _trusted_browser_key("token-abc-123")
        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) > 0

    def test_trusted_browser_key_differs_for_different_tokens(self):
        """Different tokens produce different keys."""
        from api.routes.admin_routes import _trusted_browser_key

        key1 = _trusted_browser_key("token-A")
        key2 = _trusted_browser_key("token-B")
        assert key1 != key2

    def test_mock_token_allowed_returns_bool(self):
        """_mock_token_allowed returns a boolean."""
        from api.routes.admin_routes import _mock_token_allowed

        result = _mock_token_allowed()
        assert isinstance(result, bool)

    def test_ensure_admin_authorized_raises_for_empty_uid(self):
        """_ensure_admin_authorized raises HTTPException for empty uid."""
        from fastapi import HTTPException

        from api.routes.admin_routes import _ensure_admin_authorized

        with pytest.raises(HTTPException) as exc_info:
            _ensure_admin_authorized("", "test@example.com")
        assert exc_info.value.status_code in (401, 403)

    def test_ensure_admin_authorized_raises_for_empty_email(self):
        """_ensure_admin_authorized raises HTTPException for empty email when uid is non-admin."""
        from fastapi import HTTPException

        from api.routes.admin_routes import _ensure_admin_authorized

        with pytest.raises(HTTPException) as exc_info:
            _ensure_admin_authorized("non-admin-uid", "")
        assert exc_info.value.status_code in (401, 403)

    def test_reject_mock_token_raises_when_mock_not_allowed(self):
        """_reject_mock_token raises HTTPException when mock tokens are not allowed."""
        from fastapi import HTTPException

        from api.routes.admin_routes import _mock_token_allowed, _reject_mock_token

        # Only test the raise behavior if mock is not allowed
        if not _mock_token_allowed():
            with pytest.raises(HTTPException):
                _reject_mock_token()


class TestVerifyTotpCode:
    """Tests for TOTP verification functions."""

    def test_verify_totp_code_valid(self):
        """বৈধ TOTP কোড ভেরিফিকেশন."""
        from api.routes.admin_routes import verify_totp_code

        secret = base64.b32encode(os.urandom(10)).decode("utf-8")

        current_time = int(time.time() // 30)
        msg = struct.pack(">Q", current_time)
        key = base64.b32decode(secret.upper())
        h = hmac.new(key, msg, hashlib.sha1).digest()
        o = h[19] & 15
        h_num = struct.unpack(">I", h[o : o + 4])[0] & 0x7FFFFFFF
        valid_otp = f"{h_num % 1000000:06d}"

        assert verify_totp_code(valid_otp, secret) is True

    def test_verify_totp_code_invalid(self):
        """অবৈধ TOTP কোড রিজেক্স করা হচ্ছে।"""
        from api.routes.admin_routes import verify_totp_code

        secret = base64.b32encode(os.urandom(10)).decode("utf-8")
        assert verify_totp_code("000000", secret) is False

    def test_check_totp_valid(self):
        """check_totp বৈধ কোড ভেরিফাই করে."""
        from api.routes.admin_routes import check_totp

        secret = base64.b32encode(os.urandom(10)).decode("utf-8")

        current_time = int(time.time() // 30)
        msg = struct.pack(">Q", current_time)
        key = base64.b32decode(secret.upper())
        h = hmac.new(key, msg, hashlib.sha1).digest()
        o = h[19] & 15
        h_num = struct.unpack(">I", h[o : o + 4])[0] & 0x7FFFFFFF
        valid_otp = f"{h_num % 1000000:06d}"

        assert check_totp(valid_otp, secret) is True

    def test_check_totp_invalid(self):
        """check_totp অবৈধ কোড রিজেক্স করে."""
        from api.routes.admin_routes import check_totp

        secret = base64.b32encode(os.urandom(10)).decode("utf-8")
        assert check_totp("123456", secret) is False

    def test_verify_totp_code_bad_secret(self):
        """খারাপ সিক্রেটে TOTP False রিটার্ন করে।"""
        from api.routes.admin_routes import verify_totp_code

        assert verify_totp_code("1234567", "not-valid-base32-!@#$") is False


class TestAdminRoutes:
    """Tests for admin FastAPI routes using TestClient."""

    @pytest.fixture
    def client(self):
        """TestClient with mocked dependencies and auth header."""
        from core.app import app as fastapi_app

        return TestClient(fastapi_app, headers={"Authorization": "Bearer test-admin-token"})

    def test_health(self, client):
        """Health endpoint."""
        response = client.get("/health")
        assert response.status_code in [200, 503]

    def test_actuator_health(self, client):
        """Actuator health check."""
        response = client.get("/health/aggregated")
        assert response.status_code == 200

    def test_admin_firebase_login_no_token(self, client):
        """Firebase login with no token returns 422."""
        response = client.post("/api/admin/firebase-login", json={})
        assert response.status_code == 422

    def test_admin_firebase_login_mock_token_non_production(self, client):
        """মক ফায়ারবেস টোকেন লগইন non-production (TOTP required by default unless trusted browser)."""
        with patch("core.config.settings.env", "local"):
            response = client.post(
                "/api/admin/firebase-login", json={"id_token": "mock-test-token"}
            )
            assert response.status_code in [200, 403]
            if response.status_code == 200:
                data = response.json()
                # With TOTP enforced by default, initial login prompts for TOTP setup/verification
                assert data.get("status") in [
                    "totp_setup_required",
                    "otp_required",
                    "trusted_browser",
                    "authenticated",
                ]

    def test_admin_firebase_login_trusted_browser_bypasses_totp(self, client):
        """Trusted browser (Remember me for 7 days) TOTP বাইপাস করে সরাসরি টোকেন দেয়।"""
        with (
            patch("core.config.settings.env", "local"),
            patch("api.routes.admin_routes._trusted_browser_uid", return_value="mock-admin-uid"),
        ):
            response = client.post(
                "/api/admin/firebase-login", json={"id_token": "mock-test-token"}
            )
            assert response.status_code in [200, 403]
            if response.status_code == 200:
                data = response.json()
                assert data.get("status") == "trusted_browser"
                assert "token" in data

    def test_admin_firebase_login_mock_token_production(self, client):
        """মক টোকেন প্রোডাকশন নিষিদ্ধ."""
        # বাংলা মন্তব্য: প্রোডাকশনে JWT সিক্রেট পেতে _get_cached_secret এবং রেট লিমিটার বাইপাস করতে acquire মক করা হচ্ছে।
        from core.config import settings

        orig_secret = settings._get_cached_secret

        def mock_secret(key):
            if key == "SUPREMEAI_JWT_SECRET":
                return "a" * 64
            return orig_secret(key)

        with (
            patch("core.config.settings.env", "production"),
            patch.object(settings, "_get_cached_secret", side_effect=mock_secret),
            patch("middleware.rate_limiter.AsyncRateLimiter.acquire", return_value=True),
        ):
            response = client.post(
                "/api/admin/firebase-login", json={"id_token": "mock-test-token"}
            )
            assert response.status_code == 403

    def test_admin_firebase_totp_setup_no_token(self, client):
        """TOTP setup missing token returns 422."""
        response = client.post("/api/admin/firebase-totp-setup", json={})
        assert response.status_code == 422

    def test_admin_firebase_totp_verify_no_token(self, client):
        """TOTP verify missing token returns 422."""
        response = client.post("/api/admin/firebase-totp-verify", json={})
        assert response.status_code == 422

    def test_cloud_distribution(self, client):
        """Cloud distribution endpoint."""
        with patch("api.routes.admin_routes.services") as mock_services:
            mock_provider = {"status": "active", "current_requests": 0}
            mock_services.parallel_router.PROVIDERS = {"provider1": mock_provider}
            mock_services.parallel_router.get_distribution_stats = MagicMock(return_value={})

            response = client.get("/admin/cloud-distribution")
            assert response.status_code == 200

    def test_free_tier_status(self, client):
        """Free tier status endpoint."""
        mock_tracker = MagicMock()
        mock_tracker.get_status.return_value = {"status": "active"}

        with patch("api.routes.admin_routes.services") as mock_services:
            mock_services.get_tracker = MagicMock(return_value=mock_tracker)
            with patch.dict(
                "sys.modules",
                {
                    "core.free_tier_tracker": MagicMock(
                        get_tracker=MagicMock(return_value=mock_tracker)
                    )
                },
            ):
                response = client.get("/admin/free-tier-status")
                assert response.status_code == 200

    def test_free_tier_provider_status_not_found(self, client):
        """অন tracked provider."""
        mock_tracker = MagicMock()
        mock_tracker.get_provider_status.return_value = None

        with patch.dict(
            "sys.modules",
            {"core.free_tier_tracker": MagicMock(get_tracker=MagicMock(return_value=mock_tracker))},
        ):
            response = client.get("/admin/free-tier-status/nonexistent")
            assert response.status_code == 404

    def test_free_tier_pause_provider(self, client):
        """Free tier pause provider endpoint."""
        mock_tracker = MagicMock()
        mock_tracker.mark_rate_limited.return_value = None

        with patch.dict(
            "sys.modules",
            {"core.free_tier_tracker": MagicMock(get_tracker=MagicMock(return_value=mock_tracker))},
        ):
            response = client.post("/admin/free-tier-pause/provider1")
            assert response.status_code == 200

    def test_free_tier_override_limits(self, client):
        """free tier override limits."""
        mock_tracker = MagicMock()
        mock_tracker.override_limits.return_value = None

        with patch.dict(
            "sys.modules",
            {"core.free_tier_tracker": MagicMock(get_tracker=MagicMock(return_value=mock_tracker))},
        ):
            response = client.post("/admin/free-tier-override/provider1", json={"limit": 100})
            assert response.status_code == 200

    def test_token_budget_stats(self, client):
        """Token budget stats endpoint."""
        mock_manager = MagicMock()
        mock_manager.get_stats.return_value = {"total": 1000}

        with patch.dict(
            "sys.modules",
            {
                "core.token_budget": MagicMock(
                    get_budget_manager=MagicMock(return_value=mock_manager)
                )
            },
        ):
            response = client.get("/admin/token-budget-stats")
            assert response.status_code == 200

    def test_gcp_health(self, client):
        """GCP health endpoint."""
        with patch("api.routes.admin_routes.services") as mock_services:
            mock_services.gcp_router.health_check.return_value = {"status": "ok"}
            mock_services.verification_queue.provider = "firestore"
            mock_services.gcp_pubsub_queue.provider = "pubsub"
            mock_services.cloud_function_client.get_config.return_value = {}

            response = client.get("/gcp/health")
            assert response.status_code == 200

    def test_gcp_verification_queue_stats(self, client):
        """GCP verification queue stats."""
        with patch("api.routes.admin_routes.services") as mock_services:
            mock_services.verification_queue.stats.return_value = {"total": 0}
            response = client.get("/gcp/verification-queue/stats")
            assert response.status_code == 200

    def test_gcp_pubsub_stats(self, client):
        """GCP pubsub stats."""
        with patch("api.routes.admin_routes.services") as mock_services:
            mock_services.gcp_pubsub_queue.stats.return_value = {"messages": 0}
            response = client.get("/gcp/pubsub/stats")
            assert response.status_code == 200

    def test_get_admin_rules(self, client):
        """Get admin rules endpoint."""
        with patch("api.routes.admin_routes.services") as mock_services:
            mock_services.rules_engine.rules = {"test": "rule"}
            response = client.get("/admin/rules")
            assert response.status_code == 200

    def test_post_admin_rules(self, client):
        """Post admin rules endpoint."""
        with patch("api.routes.admin_routes.services") as mock_services:
            mock_services.rules_engine.save_rules.return_value = True
            response = client.post("/admin/rules", json={"rules": {"new": "rule"}})
            assert response.status_code == 200

    def test_post_admin_rules_failure(self, client):
        """Post admin rules failure."""
        with patch("api.routes.admin_routes.services") as mock_services:
            mock_services.rules_engine.save_rules.return_value = False
            response = client.post("/admin/rules", json={"rules": {"new": "rule"}})
            assert response.status_code == 200

    def test_get_skills(self, client):
        """Skills endpoint."""
        response = client.get("/skills")
        assert response.status_code == 200


class TestGetCurrentAdminGuard:
    """Regression tests for get_current_admin() — previously referenced an
    undefined HTTP_403_FORBIDDEN name, so a non-admin request crashed with an
    unhandled NameError (-> 500) instead of a clean 403. See api/routes/admin_routes.py.
    """

    def test_non_admin_role_raises_403(self):
        """অ-এডমিন role হলে পরিষ্কার 403 HTTPException রেইজ হওয়া উচিত, NameError না।"""
        from api.routes.admin_routes import get_current_admin

        with pytest.raises(HTTPException) as exc_info:
            get_current_admin({"role": "user", "sub": "someone@example.com"})

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail

    def test_missing_role_raises_403(self):
        """payload-এ role কী-ই না থাকলেও 403 হওয়া উচিত।"""
        from api.routes.admin_routes import get_current_admin

        with pytest.raises(HTTPException) as exc_info:
            get_current_admin({"sub": "someone@example.com"})

        assert exc_info.value.status_code == 403

    def test_admin_role_passes_through(self):
        """role == 'admin' হলে payload অপরিবর্তিত রিটার্ন হবে, কোনো exception ছাড়াই।"""
        from api.routes.admin_routes import get_current_admin

        payload = {"role": "admin", "sub": "admin@example.com"}
        result = get_current_admin(payload)
        assert result == payload
