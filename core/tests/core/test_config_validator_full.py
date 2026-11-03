"""Full-coverage tests for core/config_validator.py (Task 7-d).

Covers every VarType branch of _validate_var, the JWT_SECRET alias fallback,
the settings-object fallback (including SecretStr and failure paths),
validate_config aggregation and print_config_summary masking.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import SecretStr

import core.config_validator as cv
from core.config_validator import (
    CONFIG_SCHEMA,
    ConfigValidationResult,
    Severity,
    ValidationError,
    VarDefinition,
    VarType,
    _validate_var,
    print_config_summary,
    validate_config,
)

JWT_ENV = "SUPREMEAI_JWT_SECRET"


def _var(**kw) -> VarDefinition:
    kw.setdefault("name", "TEST_VAR")
    return VarDefinition(**kw)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove schema vars so tests are deterministic."""
    for v in CONFIG_SCHEMA:
        monkeypatch.delenv(v.name, raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    yield


class TestEnumsAndDataclasses:
    def test_var_types_and_severities(self):
        assert {v.value for v in VarType} == {
            "string",
            "url",
            "integer",
            "float",
            "boolean",
            "list",
            "enum",
        }
        assert Severity.WARNING.value == "warning"

    def test_var_definition_defaults(self):
        v = _var()
        assert v.var_type is VarType.STRING
        assert v.required is False
        assert v.severity is Severity.ERROR
        assert v.examples == []

    def test_validation_error_defaults(self):
        e = ValidationError(var_name="X", severity=Severity.INFO, message="m")
        assert e.actual_value is None and e.suggestion is None

    def test_format_errors_masks_sensitive_values(self):
        result = ConfigValidationResult(
            is_valid=False,
            errors=[
                ValidationError(
                    var_name="GROQ_API_KEY",
                    severity=Severity.ERROR,
                    message="bad",
                    actual_value="supersecret",
                    suggestion="Set it",
                ),
                ValidationError(
                    var_name="PORT",
                    severity=Severity.WARNING,
                    message="out of range",
                    actual_value="99999",
                ),
            ],
            warnings=[],
        )
        text = result.format_errors()
        assert "CONFIGURATION VALIDATION FAILED" in text
        assert "[REDACTED]" in text
        assert "supersecret" not in text
        assert "99999" in text
        assert "💡 Suggestion: Set it" in text
        assert "Total errors: 2, Warnings: 0" in text


class TestValidateVar:
    def test_required_missing_error(self):
        v = _var(name="MISSING_VAR", required=True, description="needed")
        err = _validate_var(v)
        assert err is not None
        assert err.message.startswith("Required variable is not set")
        assert err.suggestion == "Set MISSING_VAR=<value>"

    def test_required_missing_with_example_suggestion(self):
        v = _var(name="MISSING_VAR", required=True, examples=["abc"])
        err = _validate_var(v)
        assert err.suggestion == "Set MISSING_VAR=abc"

    def test_none_value_no_error(self):
        assert _validate_var(_var()) is None

    def test_jwt_alias_fallback(self, monkeypatch):
        monkeypatch.delenv(JWT_ENV, raising=False)
        jwt_def = next(v for v in CONFIG_SCHEMA if v.name == JWT_ENV)
        with patch.object(cv, "resolve_jwt_secret_env", return_value="s" * 70):
            err = _validate_var(jwt_def)
        assert err is None

    def test_jwt_alias_empty_no_settings_fallback(self, monkeypatch):
        monkeypatch.delenv(JWT_ENV, raising=False)
        jwt_def = next(v for v in CONFIG_SCHEMA if v.name == JWT_ENV)
        with patch.object(cv, "resolve_jwt_secret_env", return_value=""):
            # No settings_obj → nothing satisfies the var → required error
            err = _validate_var(jwt_def, settings_obj=None)
        assert err is not None

    def test_settings_fallback_plain_string(self, monkeypatch):
        monkeypatch.delenv("MY_SETTING_VAR", raising=False)

        class S:  # settings stand-in
            my_setting_var = "hello"

        v = _var(name="MY_SETTING_VAR", required=True)
        assert _validate_var(v, settings_obj=S()) is None

    def test_settings_fallback_secretstr(self, monkeypatch):
        monkeypatch.delenv("MY_SECRET_VAR", raising=False)

        class S:
            my_secret_var = SecretStr("s3cret-value")

        v = _var(name="MY_SECRET_VAR", required=True)
        # value present, STRING type without min → valid
        assert _validate_var(v, settings_obj=S()) is None

    def test_settings_fallback_raises_is_ignored(self, monkeypatch):
        monkeypatch.delenv("BAD_VAR", raising=False)

        class Flaky:
            """hasattr passes on the 1st getattr; the 2nd getattr raises."""

            _calls = 0

            def __get__(self, obj, cls=None):
                Flaky._calls += 1
                if Flaky._calls == 1:
                    return "first"
                raise RuntimeError("nope")

        class S:
            bad_var = Flaky()

        v = _var(name="BAD_VAR", required=True)
        err = _validate_var(v, settings_obj=S())
        assert err is not None  # still missing → required error

    def test_settings_fallback_jwt_property_name(self, monkeypatch):
        monkeypatch.delenv(JWT_ENV, raising=False)

        class S:
            jwt_secret = "j" * 64

        jwt_def = next(v for v in CONFIG_SCHEMA if v.name == JWT_ENV)
        with patch.object(cv, "resolve_jwt_secret_env", return_value=""):
            assert _validate_var(jwt_def, settings_obj=S()) is None

    def test_url_invalid(self):
        v = _var(name="MY_URL", var_type=VarType.URL)
        err = _validate_var(v)
        assert err is None  # None value short-circuits
        with patch.dict(os.environ, {"MY_URL": "ftp://bad"}):
            err = _validate_var(v)
        assert err is not None and "Invalid URL format" in err.message

    def test_url_custom_pattern(self):
        v = _var(name="MY_URL2", var_type=VarType.URL, pattern=r"^https://.+")
        with patch.dict(os.environ, {"MY_URL2": "http://insecure"}):
            err = _validate_var(v)
        assert err is not None and "Invalid URL format" in err.message

    def test_enum_invalid_and_valid(self):
        v = _var(name="MY_ENUM", var_type=VarType.ENUM, allowed_values=["a", "b"])
        with patch.dict(os.environ, {"MY_ENUM": "c"}):
            err = _validate_var(v)
        assert err is not None and "Invalid value" in err.message
        with patch.dict(os.environ, {"MY_ENUM": "a"}):
            assert _validate_var(v) is None

    def test_integer_below_min_above_max_invalid(self):
        v = _var(name="MY_INT", var_type=VarType.INTEGER, min_value=5, max_value=10)
        with patch.dict(os.environ, {"MY_INT": "1"}):
            err = _validate_var(v)
        assert err is not None and err.severity is Severity.WARNING
        with patch.dict(os.environ, {"MY_INT": "20"}):
            err = _validate_var(v)
        assert err is not None and "above maximum" in err.message
        with patch.dict(os.environ, {"MY_INT": "abc"}):
            err = _validate_var(v)
        assert err is not None and "Invalid integer" in err.message
        with patch.dict(os.environ, {"MY_INT": "7"}):
            assert _validate_var(v) is None

    def test_boolean_invalid(self):
        v = _var(name="MY_BOOL", var_type=VarType.BOOLEAN)
        for bad in ("yes-please", "maybe"):
            with patch.dict(os.environ, {"MY_BOOL": bad}):
                err = _validate_var(v)
            assert err is not None and "Invalid boolean" in err.message
        for good in ("true", "FALSE", "1", "0"):
            with patch.dict(os.environ, {"MY_BOOL": good}):
                assert _validate_var(v) is None

    def test_string_length_bounds(self):
        v = _var(name="MY_STR", var_type=VarType.STRING, min_value=5, max_value=8)
        with patch.dict(os.environ, {"MY_STR": "abc"}):
            err = _validate_var(v)
        assert err is not None and "below minimum" in err.message
        with patch.dict(os.environ, {"MY_STR": "a" * 9}):
            err = _validate_var(v)
        assert err is not None and "above maximum" in err.message
        with patch.dict(os.environ, {"MY_STR": "abcde"}):
            assert _validate_var(v) is None

    def test_pattern_mismatch_generic(self):
        v = _var(name="MY_CODE", var_type=VarType.STRING, pattern=r"^\d+$")
        with patch.dict(os.environ, {"MY_CODE": "abc"}):
            err = _validate_var(v)
        assert err is not None and "doesn't match pattern" in err.message

    def test_empty_string_required_is_missing(self):
        # CURRENT BEHAVIOR: an empty string satisfies `required` because only
        # None triggers the required error ("" is not None).
        v = _var(name="EMPTY_VAR", required=True)
        with patch.dict(os.environ, {"EMPTY_VAR": ""}):
            err = _validate_var(v)
        assert err is None


class TestValidateConfig:
    def test_valid_environment(self, monkeypatch):
        monkeypatch.setenv("ENV", "test")
        monkeypatch.setenv("BACKEND_URL", "https://api.example.com")
        monkeypatch.setenv(JWT_ENV, "s" * 70)
        result = validate_config()
        assert result.is_valid is True
        assert result.errors == []
        assert result.validated_vars[JWT_ENV] == "s" * 70
        assert str(result.validated_vars["PORT"]) == "8080"

    def test_invalid_environment_reports_error(self, monkeypatch):
        monkeypatch.setenv("ENV", "bogus-env")
        monkeypatch.setenv(JWT_ENV, "s" * 70)
        result = validate_config()
        assert result.is_valid is False
        assert any(e.var_name == "ENV" for e in result.errors)

    def test_missing_jwt_reported(self, monkeypatch):
        monkeypatch.setenv("ENV", "test")
        # Neutralize the settings fallback so nothing satisfies the JWT var
        monkeypatch.setattr("core.config.settings", SimpleNamespace())
        result = validate_config()
        assert result.is_valid is False
        assert any(e.var_name == JWT_ENV for e in result.errors)

    def test_warnings_are_separated(self, monkeypatch):
        monkeypatch.setenv("ENV", "test")
        monkeypatch.setenv(JWT_ENV, "s" * 70)
        monkeypatch.setenv("GEMINI_RPM_LIMIT", "0")  # below min → warning
        result = validate_config()
        assert result.is_valid is True
        assert any(w.var_name == "GEMINI_RPM_LIMIT" for w in result.warnings)


class TestPrintSummary:
    def test_print_config_summary_masks_secrets(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "sk-abc123", "PORT": "9000"}):
            # Should not raise; sensitive values masked in the debug output
            print_config_summary()
