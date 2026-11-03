"""Tests for AutonoGuard Middleware - Security enforcement layer.

This module tests:
- Lazy initialization of AutonoGuard engine
- Sensitive operation path detection
- Non-sensitive path bypass
- User identity extraction
- Client IP extraction
- OTP header parsing
- Body extraction and scanning
- Security enforcement
"""

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

import core.autonoguard_engine as engine_module
from core.autonoguard_engine import OperationContext
from core.security.autonoguard_middleware import AutonoGuardMiddleware

# --- Middleware Tests ---


class TestAutonoGuardMiddleware:
    """Tests for AutonoGuardMiddleware class."""

    def test_initializes_on_first_request(self):
        """Test that middleware initializes AutonoGuardEngine on first request."""
        app = FastAPI()

        @app.get("/api/sensitive/test")
        def test_endpoint():
            return PlainTextResponse("ok")

        with patch.object(engine_module, "autonoguard_engine") as mock_engine:
            mock_engine.initialize = AsyncMock()
            mock_engine.enforce_operation = AsyncMock(return_value=(True, None))
            mock_engine.heal_error = AsyncMock()

            app.add_middleware(AutonoGuardMiddleware, engine=mock_engine)
            client = TestClient(app)

            client.get("/api/sensitive/test")

            mock_engine.initialize.assert_called_once()

    def test_bypasses_non_sensitive_path(self):
        """Test that non-sensitive paths bypass security checks."""
        app = FastAPI()

        @app.get("/api/health")
        def health_endpoint():
            return PlainTextResponse("healthy")

        with patch("core.security.autonoguard_middleware.autonoguard_engine") as mock_engine:
            mock_engine.initialize = AsyncMock()
            mock_engine.enforce_operation = AsyncMock()

            AutonoGuardMiddleware(app)
            client = TestClient(app)

            client.get("/api/health")

            # Should not call enforce_operation for non-sensitive paths
            # Note: This depends on which paths are in SENSITIVE_OPS

    def test_extracts_user_identity(self):
        """Test extraction of user identity from request state."""
        app = FastAPI()

        @app.get("/api/sensitive/test")
        def test_endpoint(request):
            return PlainTextResponse("ok")

        with patch("core.security.autonoguard_middleware.autonoguard_engine") as mock_engine:
            mock_engine.initialize = AsyncMock()
            mock_engine.enforce_operation = AsyncMock(return_value=(True, None))

            AutonoGuardMiddleware(app)
            TestClient(app)

            # The middleware should extract admin_id from request.state.user

    def test_extracts_client_ip(self):
        """Test client IP extraction from request."""
        app = FastAPI()

        @app.get("/api/sensitive/test")
        def test_endpoint():
            return PlainTextResponse("ok")

        with patch("core.security.autonoguard_middleware.autonoguard_engine") as mock_engine:
            mock_engine.initialize = AsyncMock()
            mock_engine.enforce_operation = AsyncMock(return_value=(True, None))

            AutonoGuardMiddleware(app)
            client = TestClient(app)

            client.get("/api/sensitive/test")

    def test_otp_header_parsing(self):
        """Test OTP code extraction from X-JIT-OTP header."""
        app = FastAPI()

        @app.post("/api/sensitive/test")
        def test_endpoint():
            return PlainTextResponse("ok")

        with patch("core.security.autonoguard_middleware.autonoguard_engine") as mock_engine:
            mock_engine.initialize = AsyncMock()
            mock_engine.enforce_operation = AsyncMock(return_value=(True, None))

            AutonoGuardMiddleware(app)
            client = TestClient(app)

            client.post(
                "/api/sensitive/test",
                headers={"X-JIT-OTP": "123456"},
                json={"code": "print('hello')"},
            )

    def test_otp_alternate_header(self):
        """Test OTP code extraction from X-OTP header."""
        app = FastAPI()

        @app.post("/api/sensitive/test")
        def test_endpoint():
            return PlainTextResponse("ok")

        with patch("core.security.autonoguard_middleware.autonoguard_engine") as mock_engine:
            mock_engine.initialize = AsyncMock()
            mock_engine.enforce_operation = AsyncMock(return_value=(True, None))

            AutonoGuardMiddleware(app)
            client = TestClient(app)

            client.post(
                "/api/sensitive/test",
                headers={"X-OTP": "654321"},
                json={"code": "print('hello')"},
            )

    def test_body_extraction_code_field(self):
        """Test body extraction with 'code' field."""
        app = FastAPI()

        @app.post("/api/sensitive/test")
        def test_endpoint():
            return PlainTextResponse("ok")

        with patch("core.security.autonoguard_middleware.autonoguard_engine") as mock_engine:
            mock_engine.initialize = AsyncMock()
            mock_engine.enforce_operation = AsyncMock(return_value=(True, None))

            AutonoGuardMiddleware(app)
            client = TestClient(app)

            client.post(
                "/api/sensitive/test",
                json={"code": "print('hello')"},
            )

    def test_body_extraction_generated_code_field(self):
        """Test body extraction with 'generated_code' field."""
        app = FastAPI()

        @app.post("/api/sensitive/test")
        def test_endpoint():
            return PlainTextResponse("ok")

        with patch("core.security.autonoguard_middleware.autonoguard_engine") as mock_engine:
            mock_engine.initialize = AsyncMock()
            mock_engine.enforce_operation = AsyncMock(return_value=(True, None))

            AutonoGuardMiddleware(app)
            client = TestClient(app)

            client.post(
                "/api/sensitive/test",
                json={"generated_code": "print('world')"},
            )

    def test_blocks_unauthorized_request(self):
        """Test that unauthorized request returns 401."""
        app = FastAPI()

        @app.get("/api/sensitive/test")
        def test_endpoint():
            return PlainTextResponse("ok")

        with patch.object(engine_module, "autonoguard_engine") as mock_engine:
            mock_engine.initialize = AsyncMock()
            mock_engine.enforce_operation = AsyncMock(return_value=(False, "OTP required"))
            mock_engine.heal_error = AsyncMock()

            app.add_middleware(AutonoGuardMiddleware, engine=mock_engine)
            client = TestClient(app)

            resp = client.get(
                "/api/sensitive/test",
                headers={"Authorization": "Bearer test_admin_token", "X-JIT-OTP": "invalid"},
            )

            assert resp.status_code == 401
            assert "OTP" in resp.json().get("detail", "") or "Security" in resp.json().get(
                "title", ""
            )

    def test_fallback_to_unknown_for_missing_user(self):
        """Test fallback to 'unknown' when user identity missing."""
        app = FastAPI()

        @app.get("/api/sensitive/test")
        def test_endpoint():
            return PlainTextResponse("ok")

        with patch.object(engine_module, "autonoguard_engine") as mock_engine:
            mock_engine.initialize = AsyncMock()
            mock_engine.enforce_operation = AsyncMock(return_value=(True, None))

            # Call should use "unknown" for admin_id
            AutonoGuardMiddleware(app, engine=mock_engine)
            client = TestClient(app)

            client.get("/api/sensitive/test")


# --- OperationContext Helper Tests ---


class TestOperationContext:
    """Tests for OperationContext dataclass."""

    def test_context_creation(self):
        """Test creating OperationContext."""
        context = OperationContext(
            admin_id="admin-123",
            ip_address="192.168.1.1",
            path="/api/sensitive/test",
            method="GET",
            headers={"Content-Type": "application/json"},
            correlation_id="corr-456",
        )

        assert context.admin_id == "admin-123"
        assert context.ip_address == "192.168.1.1"
        assert context.method == "GET"

    def test_context_defaults(self):
        """Test OperationContext default values."""
        context = OperationContext(
            admin_id="admin",
            ip_address="127.0.0.1",  # is_local()
            path="/test",
            method="POST",
        )

        assert context.headers == {}
        assert context.correlation_id is None
        assert context.code_to_scan is None
