"""
Unit Tests for SupremeAI Core Exceptions & Security Pipeline Middleware.
Verifies:
1. Unified SupremeAIException hierarchy, status codes, and structured dictionary export.
2. Security headers middleware injection and correlation trace tracking.
3. Conditional pipeline manager activation.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ExecutionError,
    LLMProviderError,
    QuotaExceededError,
    RateLimitError,
    ResourceNotFoundError,
    SupremeAIException,
    ThirdPartyServiceError,
    ValidationError,
)
from core.security.security_pipeline import (
    SecurityPipelineManager,
    SupremeSecurityHeadersMiddleware,
)


def test_supreme_exception_hierarchy():
    base_err = SupremeAIException("Something went wrong", error_code="GENERIC_ERR", status_code=500)
    assert base_err.status_code == 500
    res_dict = base_err.to_dict()
    assert res_dict["success"] is False
    assert res_dict["error"]["code"] == "GENERIC_ERR"
    assert res_dict["error"]["message"] == "Something went wrong"

    # Test Domain Exceptions
    auth_err = AuthenticationError("Invalid token")
    assert auth_err.status_code == 401
    assert auth_err.error_code == "AUTHENTICATION_FAILED"

    perm_err = AuthorizationError("Admin role required")
    assert perm_err.status_code == 403
    assert perm_err.error_code == "PERMISSION_DENIED"

    not_found = ResourceNotFoundError("Thread not found")
    assert not_found.status_code == 404
    assert not_found.error_code == "RESOURCE_NOT_FOUND"

    val_err = ValidationError("Field missing", details={"field": "task_id"})
    assert val_err.status_code == 422
    assert val_err.details == {"field": "task_id"}

    exec_err = ExecutionError("Step failed in sandbox")
    assert exec_err.status_code == 500
    assert exec_err.error_code == "EXECUTION_FAILED"

    rate_err = RateLimitError("Too many calls")
    assert rate_err.status_code == 429
    assert rate_err.error_code == "RATE_LIMIT_EXCEEDED"

    up_err = ThirdPartyServiceError("Provider timeout")
    assert up_err.status_code == 502
    assert up_err.error_code == "UPSTREAM_SERVICE_ERROR"

    # Test Legacy Backward-Compatible Aliases
    llm_err = LLMProviderError("LLM failed")
    assert isinstance(llm_err, SupremeAIException)
    assert llm_err.status_code == 502

    quota_err = QuotaExceededError()
    assert isinstance(quota_err, SupremeAIException)
    assert quota_err.status_code == 429


def test_security_headers_middleware():
    test_app = FastAPI()
    test_app.add_middleware(SupremeSecurityHeadersMiddleware)

    @test_app.get("/test-headers")
    def get_test():
        return {"status": "ok"}

    client = TestClient(test_app)
    resp = client.get("/test-headers", headers={"X-Correlation-ID": "test-corr-12345"})
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-XSS-Protection"] == "1; mode=block"
    assert resp.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    assert resp.headers["X-Trace-Id"] == "test-corr-12345"
    assert "X-Process-Time" in resp.headers


def test_security_pipeline_manager():
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
