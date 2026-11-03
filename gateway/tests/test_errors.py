import pytest
from fastapi import HTTPException

from api.errors import (
    APIErrorDetail,
    ErrorResponse,
    raise_bad_request,
    raise_conflict,
    raise_forbidden,
    raise_internal,
    raise_not_found,
    raise_unauthorized,
)


def test_error_models():
    detail = APIErrorDetail(
        title="Bad Request",
        detail="Invalid payload",
        instance="/api/test",
        code="INVALID_INPUT",
    )
    envelope = ErrorResponse(error=detail)
    assert envelope.error.title == "Bad Request"
    assert envelope.error.detail == "Invalid payload"
    assert envelope.error.code == "INVALID_INPUT"


def test_raise_bad_request():
    with pytest.raises(HTTPException) as exc_info:
        raise_bad_request("invalid data")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "invalid data"


def test_raise_unauthorized():
    with pytest.raises(HTTPException) as exc_info:
        raise_unauthorized()
    assert exc_info.value.status_code == 401
    assert "authentication token" in exc_info.value.detail


def test_raise_forbidden():
    with pytest.raises(HTTPException) as exc_info:
        raise_forbidden()
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Insufficient permissions"


def test_raise_not_found():
    with pytest.raises(HTTPException) as exc_info:
        raise_not_found("item not found")
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "item not found"


def test_raise_conflict():
    with pytest.raises(HTTPException) as exc_info:
        raise_conflict("already exists")
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "already exists"


def test_raise_internal():
    with pytest.raises(HTTPException) as exc_info:
        raise_internal("unexpected error")
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "unexpected error"
