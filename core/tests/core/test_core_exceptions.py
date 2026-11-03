# tests/test_core_exceptions.py
"""Tests for the core SupremeAI exception hierarchy."""

import pytest

from core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ExecutionError,
    LLMProviderError,
    ProviderExhaustedError,
    QuotaExceededError,
    RateLimitError,
    ResourceNotFoundError,
    SupremeAIError,
    SupremeAIException,
    ThirdPartyServiceError,
    ValidationError,
)


def test_base_defaults():
    exc = SupremeAIException("msg")
    assert exc.message == "msg"
    assert exc.error_code == "INTERNAL_ERROR"
    assert exc.status_code == 500
    assert exc.details == {}
    assert exc.original_error is None
    payload = exc.to_dict()
    assert payload["success"] is False
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["error"]["message"] == "msg"
    assert payload["error"]["details"] == {}


def test_base_custom_fields():
    orig = ValueError("orig")
    exc = SupremeAIException(
        "m",
        error_code="X",
        status_code=418,
        details={"a": 1},
        original_error=orig,
    )
    assert exc.error_code == "X"
    assert exc.status_code == 418
    assert exc.details == {"a": 1}
    assert exc.original_error is orig


@pytest.mark.parametrize(
    "cls,code,status",
    [
        (AuthenticationError, "AUTHENTICATION_FAILED", 401),
        (AuthorizationError, "PERMISSION_DENIED", 403),
        (ResourceNotFoundError, "RESOURCE_NOT_FOUND", 404),
        (ValidationError, "VALIDATION_ERROR", 422),
        (ExecutionError, "EXECUTION_FAILED", 500),
        (RateLimitError, "RATE_LIMIT_EXCEEDED", 429),
        (ThirdPartyServiceError, "UPSTREAM_SERVICE_ERROR", 502),
        (ProviderExhaustedError, "PROVIDER_EXHAUSTED", 503),
    ],
)
def test_subclass_codes(cls, code, status):
    exc = cls()
    assert exc.error_code == code
    assert exc.status_code == status
    assert isinstance(exc, SupremeAIException)


def test_alias_matches_base():
    assert SupremeAIError is SupremeAIException


def test_llm_provider_error():
    exc = LLMProviderError("boom")
    assert exc.error_code == "LLM_PROVIDER_ERROR"
    assert exc.status_code == 502
    assert isinstance(exc, SupremeAIException)


def test_quota_exceeded_defaults():
    exc = QuotaExceededError()
    assert exc.status_code == 429
    assert exc.error_code == "QUOTA_EXCEEDED"
    assert isinstance(exc, SupremeAIException)
