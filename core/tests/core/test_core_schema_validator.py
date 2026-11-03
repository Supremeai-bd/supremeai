# tests/test_core_schema_validator.py
"""Tests for the core pydantic SchemaValidator."""

import pytest
from pydantic import BaseModel, Field

from core.schema_validator import (
    SchemaValidationError,
    SchemaValidator,
    validator,
)


class SampleModel(BaseModel):
    name: str
    age: int = Field(ge=0)


def test_register_and_validate_ok():
    v = SchemaValidator()
    v.register("sample", SampleModel)
    result = v.validate("sample", {"name": "alice", "age": 30})
    assert result["status"] == "ok"
    assert result["schema"] == "sample"
    assert result["data"]["name"] == "alice"


def test_validate_unregistered_raises_key_error():
    v = SchemaValidator()
    with pytest.raises(KeyError):
        v.validate("missing", {"name": "x"})


def test_validate_invalid_payload_raises_schema_error():
    v = SchemaValidator()
    v.register("sample", SampleModel)
    with pytest.raises(SchemaValidationError) as exc_info:
        v.validate("sample", {"name": "bob", "age": -5})
    assert exc_info.value.model_name == "sample"
    assert isinstance(exc_info.value.errors, list)
    assert len(exc_info.value.errors) >= 1


def test_try_parse_ok():
    v = SchemaValidator()
    v.register("sample", SampleModel)
    out = v.try_parse("sample", {"name": "x", "age": 1})
    assert out["status"] == "ok"


def test_try_parse_error_returns_dict():
    v = SchemaValidator()
    v.register("sample", SampleModel)
    out = v.try_parse("sample", {"age": -1})
    assert out["status"] == "error"
    assert "sample" in out["schema"]


def test_try_parse_unknown_returns_error():
    v = SchemaValidator()
    out = v.try_parse("nope", {})
    assert out["status"] == "error"


def test_validate_with_retry_ok_on_valid():
    v = SchemaValidator()
    v.register("sample", SampleModel)
    out = v.validate_with_retry("sample", {"name": "ok", "age": 1})
    assert out["status"] == "ok"


def test_validate_with_retry_error_on_invalid():
    v = SchemaValidator()
    v.register("sample", SampleModel)
    out = v.validate_with_retry("sample", {"age": -1}, max_attempts=2)
    assert out["status"] == "error"
    assert out["attempts"] == 2


def test_module_level_validator_exists():
    assert isinstance(validator, SchemaValidator)
