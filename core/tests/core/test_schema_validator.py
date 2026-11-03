"""
Tests for core/schema_validator.py — SchemaValidator
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from core.schema_validator import SchemaValidationError, SchemaValidator


class TestModel(BaseModel):
    name: str
    age: int


class NestedModel(BaseModel):
    items: list[str]
    enabled: bool = True


@pytest.fixture
def validator():
    v = SchemaValidator()
    v.register("test", TestModel)
    v.register("nested", NestedModel)
    return v


class TestSchemaValidator:
    def test_register_and_validate_success(self, validator):
        result = validator.validate("test", {"name": "Alice", "age": 30})
        assert result["status"] == "ok"
        assert result["schema"] == "test"
        assert result["data"]["name"] == "Alice"
        assert result["data"]["age"] == 30

    def test_validate_missing_required_field(self, validator):
        with pytest.raises(SchemaValidationError) as exc:
            validator.validate("test", {"name": "Alice"})
        assert exc.value.model_name == "test"
        assert len(exc.value.errors) > 0

    def test_validate_wrong_type(self, validator):
        with pytest.raises(SchemaValidationError) as exc:
            validator.validate("test", {"name": "Alice", "age": "not_a_number"})
        assert exc.value.model_name == "test"

    def test_validate_unregistered_schema(self, validator):
        with pytest.raises(KeyError) as exc:
            validator.validate("nonexistent", {})
        assert "nonexistent" in str(exc.value)

    def test_validate_empty_payload(self, validator):
        with pytest.raises(SchemaValidationError):
            validator.validate("test", {})

    def test_validate_nested_model(self, validator):
        result = validator.validate("nested", {"items": ["a", "b"]})
        assert result["status"] == "ok"
        assert result["data"]["items"] == ["a", "b"]
        assert result["data"]["enabled"] is True

    def test_validate_with_defaults(self, validator):
        result = validator.validate("nested", {"items": []})
        assert result["data"]["enabled"] is True

    def test_validate_extra_fields_ignored(self, validator):
        result = validator.validate("test", {"name": "Bob", "age": 25, "extra": "ignored"})
        assert result["status"] == "ok"
        assert "extra" not in result["data"]

    def test_register_duplicate_overwrites(self, validator):
        class NewModel(BaseModel):
            x: int

        validator.register("test", NewModel)
        result = validator.validate("test", {"x": 42})
        assert result["status"] == "ok"

    def test_schema_validation_error_message_format(self, validator):
        with pytest.raises(SchemaValidationError) as exc:
            validator.validate("test", {})
        assert "Validation failed for test" in str(exc.value)
        assert isinstance(exc.value.errors, list)

    def test_multiple_errors_reported(self, validator):
        with pytest.raises(SchemaValidationError) as exc:
            validator.validate("test", {"age": "wrong", "name": 123})
        # May get multiple errors
        assert len(exc.value.errors) >= 1


def test_schema_validation_error_init():
    error = SchemaValidationError("test_model", [{"loc": "name", "msg": "required"}])
    assert error.model_name == "test_model"
    assert error.errors == [{"loc": "name", "msg": "required"}]
    assert "test_model" in str(error)
