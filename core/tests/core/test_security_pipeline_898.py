# backend/tests/core/test_security_pipeline_898.py
"""Regression tests for SecurityPipelineManager middleware registration (#898).

Issue #898 (P1 SECURITY): `security_pipeline.py`-তে দুটি middlewareই
`try/except ImportError` silent skip দ্বারা fail-open ছিল:

1. `from core.security.origin_validator import OriginValidatorMiddleware` —
   আসল class নাম `TrustedOriginMiddleware` (origin_validator.py:50) —
   ImportError → origin validation কখনো register হয়নি।
2. `from core.security.api_key_limiter import APIKeyLimiter` — এই class একটি
   facade (ASGI middleware নয়); `app.add_middleware(APIKeyLimiter)` প্রকৃতপক্ষে
   কোনো rate limit enforce করত না → silent no-op।

এই test suite যাচাই করে:
    - Origin validation enable করলে `TrustedOriginMiddleware` registered হয়।
    - Rate limiter enable করলে `APIKeyLimiterMiddleware` registered হয়।
    - Pipeline-এ এখন `try/except ImportError` silent skip নেই (fail-loud)।
    - `APIKeyLimiterMiddleware` আসলেই request intercept করে (live integration)।

WIRE-FIRST: pins fixed behavior, adds no deletion. বাংলা মন্তব্য সহ।
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from core.security.api_key_limiter import APIKeyLimiterMiddleware, enforce_api_key_rate_limit
from core.security.origin_validator import TrustedOriginMiddleware
from core.security.security_pipeline import SecurityPipelineManager


def _middleware_class_names(app: FastAPI) -> list[str]:
    """app.user_middleware list থেকে class নামগুলো extract করে।"""
    names: list[str] = []
    for mw in app.user_middleware:
        cls = getattr(mw, "cls", None) or getattr(mw, "middleware_class", None)
        if cls is None:
            continue
        names.append(cls.__name__)
    return names


class TestSecurityPipelineRegistration:
    """Issue #898: pipeline enable → middleware registered assert (happy path)।"""

    def test_origin_validation_registers_trusted_origin_middleware(self):
        """enable_origin_validation=True → TrustedOriginMiddleware registered।"""
        app = FastAPI()
        SecurityPipelineManager.register_security_pipeline(
            app,
            enable_headers=False,
            enable_origin_validation=True,
            enable_rate_limiter=False,
        )
        names = _middleware_class_names(app)
        assert "TrustedOriginMiddleware" in names, (
            f"TrustedOriginMiddleware should be registered when "
            f"enable_origin_validation=True; got: {names}"
        )

    def test_rate_limiter_registers_api_key_limiter_middleware(self):
        """enable_rate_limiter=True → APIKeyLimiterMiddleware registered।"""
        app = FastAPI()
        SecurityPipelineManager.register_security_pipeline(
            app,
            enable_headers=False,
            enable_origin_validation=False,
            enable_rate_limiter=True,
        )
        names = _middleware_class_names(app)
        assert "APIKeyLimiterMiddleware" in names, (
            f"APIKeyLimiterMiddleware should be registered when "
            f"enable_rate_limiter=True; got: {names}"
        )

    def test_origin_validation_disabled_does_not_register(self):
        """enable_origin_validation=False → কোনো origin middleware নয়।"""
        app = FastAPI()
        SecurityPipelineManager.register_security_pipeline(
            app,
            enable_headers=False,
            enable_origin_validation=False,
            enable_rate_limiter=False,
        )
        names = _middleware_class_names(app)
        assert "TrustedOriginMiddleware" not in names
        assert "APIKeyLimiterMiddleware" not in names

    def test_headers_only_pipeline_still_works(self):
        """Pre-existing happy-path (test_core_exceptions_and_pipeline.py) intact।"""
        app = FastAPI()
        SecurityPipelineManager.register_security_pipeline(
            app,
            enable_headers=True,
            enable_origin_validation=False,
            enable_rate_limiter=False,
        )

        @app.get("/pipeline-check")
        def check():
            return {"secured": True}

        client = TestClient(app)
        resp = client.get("/pipeline-check")
        assert resp.status_code == 200
        assert resp.json() == {"secured": True}
        assert "X-Trace-Id" in resp.headers


class TestSecurityPipelineNoSilentSkip:
    """Issue #898 #4: security middleware silent skip বন্ধ করা — fail-loud।"""

    def test_pipeline_source_does_not_swallow_import_error(self):
        """`register_security_pipeline` source-এ `except ImportError` নেই।"""
        import inspect
        import re

        src = inspect.getsource(SecurityPipelineManager.register_security_pipeline)
        # Strip Python comments (# ...) — comment-এ থাকা শব্দ code pattern
        # হিসেবে গণ্য হবে না।
        code_lines = [re.sub(r"#.*$", "", line) for line in src.splitlines()]
        code_only = "\n".join(code_lines)
        assert "except ImportError" not in code_only, (
            "Issue #898: security pipeline silent skip (try/except ImportError) "
            "removed — missing middleware class should propagate as ImportError at startup."
        )

    def test_correct_class_names_resolved(self):
        """OriginValidatorMiddleware নাম নেই, TrustedOriginMiddleware আছে; APIKeyLimiter
        facade ও APIKeyLimiterMiddleware ASGI wrapper আছে।"""
        # Import গুলো সফল হলেই test pass — ImportError হলে আগেই fail।
        from core.security.api_key_limiter import (  # noqa: F401
            APIKeyLimiter,
            APIKeyLimiterMiddleware,
        )
        from core.security.origin_validator import (  # noqa: F401
            TrustedOriginMiddleware,
        )

        assert issubclass(APIKeyLimiterMiddleware, _BaseHTTPMiddlewareClass())
        # APIKeyLimiter facade আগের মতোই callable
        limiter = APIKeyLimiter(max_requests=10)
        assert callable(getattr(limiter, "enforce", None))
        assert callable(limiter)  # __call__


def _BaseHTTPMiddlewareClass():
    """Helper to avoid module-level import of BaseHTTPMiddleware।"""
    from starlette.middleware.base import BaseHTTPMiddleware

    return BaseHTTPMiddleware


class TestAPIKeyLimiterMiddlewareLive:
    """Live integration: APIKeyLimiterMiddleware আসলেই request intercept করে।"""

    def test_request_without_api_key_passes_through(self):
        """API key ছাড়া request এ কোনো rate limit check হয় না → pass-through।"""
        app = FastAPI()
        app.add_middleware(APIKeyLimiterMiddleware, max_requests=10)

        @app.get("/ping")
        def ping():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_request_with_api_key_under_limit_passes(self, monkeypatch):
        """API key সহ request — rate limit অতিক্রম না হলে pass।"""
        # enforce_api_key_rate_limit-কে mock করছি (Redis transport only)।
        calls: list[str] = []

        async def fake_enforce(api_key_hash: str, max_requests: int = 60) -> None:
            calls.append(api_key_hash)

        # Module attribute replace — `enforce_api_key_rate_limit` কে।
        import core.security.api_key_limiter as mod

        monkeypatch.setattr(mod, "enforce_api_key_rate_limit", fake_enforce)

        app = FastAPI()
        # Middleware class এনে রেজিস্টার করি (post-patch)
        app.add_middleware(mod.APIKeyLimiterMiddleware, max_requests=5)

        @app.get("/secured")
        def secured():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/secured", headers={"x-api-key": "sk-test-123"})
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"ok": True}
        # enforce called with hashed API key (sha256 of 'sk-test-123')
        assert len(calls) == 1, f"enforce should be called once, got {len(calls)}"
        assert calls[0] != "sk-test-123", "API key must be hashed before enforce"
        assert len(calls[0]) == 64, "SHA-256 hex digest is 64 chars"

    def test_request_over_limit_returns_429(self, monkeypatch):
        """Rate limit exceeded → enforce 429 raise করে → middleware 429 response দেয়।"""
        from fastapi import HTTPException

        async def fake_enforce_over_limit(api_key_hash: str, max_requests: int = 60) -> None:
            raise HTTPException(status_code=429, detail="API key rate limit exceeded")

        import core.security.api_key_limiter as mod

        monkeypatch.setattr(mod, "enforce_api_key_rate_limit", fake_enforce_over_limit)

        app = FastAPI()
        app.add_middleware(mod.APIKeyLimiterMiddleware, max_requests=1)

        @app.get("/secured")
        def secured():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/secured", headers={"x-api-key": "sk-burst-key"})
        assert resp.status_code == 429, resp.text
        body = resp.json()
        assert body["detail"] == "API key rate limit exceeded"
        # Retry-After header থাকা আবশ্যক
        assert resp.headers.get("Retry-After") == "60"

    def test_bearer_token_authorization_header_also_extracted(self, monkeypatch):
        """`Authorization: Bearer <key>` header থেকেও API key extract হয়।"""
        calls: list[str] = []

        async def fake_enforce(api_key_hash: str, max_requests: int = 60) -> None:
            calls.append(api_key_hash)

        import core.security.api_key_limiter as mod

        monkeypatch.setattr(mod, "enforce_api_key_rate_limit", fake_enforce)

        app = FastAPI()
        app.add_middleware(mod.APIKeyLimiterMiddleware)

        @app.get("/secured")
        def secured():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get(
            "/secured",
            headers={"authorization": "Bearer bearer-token-xyz"},
        )
        assert resp.status_code == 200
        assert len(calls) == 1
        # Hashed version should be SHA-256 of 'bearer-token-xyz'
        import hashlib

        expected_hash = hashlib.sha256(b"bearer-token-xyz").hexdigest()
        assert calls[0] == expected_hash

    def test_enforce_exception_fails_open(self, monkeypatch):
        """enforce নিজে exception ছাড়ালেও request চলবে (fail-open resilience)।"""

        async def fake_enforce_error(api_key_hash: str, max_requests: int = 60) -> None:
            raise RuntimeError("redis down")

        import core.security.api_key_limiter as mod

        monkeypatch.setattr(mod, "enforce_api_key_rate_limit", fake_enforce_error)

        app = FastAPI()
        app.add_middleware(mod.APIKeyLimiterMiddleware)

        @app.get("/secured")
        def secured():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/secured", headers={"x-api-key": "sk-test"})
        assert resp.status_code == 200, (
            "Rate limiter internal failure should fail-open, not block API"
        )
