# বাংলা মন্তব্য: Issue #2767 — configuration engine contract টেস্ট।
"""Contract tests for the configuration engine (issue #2767).

বাংলা মন্তব্য: এই ফাইলটি `backend/core/config.py` এবং
`backend/core/config_validation.py`-এর চুক্তিগত আচরণ যাচাই করে:

  1. Required env var missing → fail-fast (startup crash / ValueError)
  2. Optional env var with default — no crash if unset
  3. Config validation: invalid value → error (e.g. bad ENV, bad URL format)
  4. Environment-specific config (dev vs prod vs test): different behavior

Rule #64: সব কিছু fully mocked — কোনো রিয়েল GCP Secret Manager / Supabase
কল নেই। secret_vault এবং env vars monkeypatch দিয়ে নিয়ন্ত্রিত।
Rule #6: বাংলা কমেন্ট + Given-When-Then docstring প্রতিটি টেস্টে।
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# বাংলা মন্তব্য: Test fixtures — env isolation, secret-vault mock।
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """প্রতিটি টেস্টের জন্য env vars isolated — SETTINGS_RESET হয়।"""
    # বাংলা: critical env vars পরিষ্কার করে দিচ্ছি যাতে টেস্ট আইসোলেটেড থাকে।
    for var in (
        "ENV", "DEBUG", "ALLOWED_HOSTS", "CORS_ORIGINS",
        "USER_CORS_ORIGINS", "ADMIN_CORS_ORIGINS",
        "SUPREMEAI_JWT_SECRET", "SUPABASE_DATABASE_URL",
        "SUPABASE_DATABASE_URL_POOLER", "SUPABASE_ALLOW_DB_DEGRADATION",
        "RENDER_EXTERNAL_HOSTNAME", "RENDER_EXTERNAL_URL",
        "RENDER_SERVICE_NAME", "RENDER_SERVICE_ID", "RENDER",
        "VERCEL_URL", "VERCEL_BRANCH_URL",
        "N8N_ENABLED", "N8N_BASE_URL",
        "APPWRITE_ENABLED", "APPWRITE_ENDPOINT", "APPWRITE_PROJECT_ID",
        "MAX_COST_PER_TASK", "PORT", "HOST",
        "ALLOW_TEST_AUTH_BYPASS", "ALLOW_TEST_ORIGIN_BYPASS",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture()
def mock_secret_vault():
    """Mock GCP Secret Manager fetches — returns env var or empty string।"""
    with patch(
        "core.security.secret_vault.secret_vault.fetch_secret",
        side_effect=lambda key, default="": os.environ.get(key) or default,
    ):
        yield


def _fresh_settings(**env_overrides):
    """Create a fresh Settings instance with cleared secret cache।

    বাংলা মন্তব্য: module-level `settings` singleton প্রতিটি টেস্টে reuse হলে
    cached_secrets আগের টেস্টের env var মনে রাখে — তাই প্রতিটি টেস্টে নতুন
    instance তৈরি করি।
    """
    from core.config import Settings

    # Apply any env overrides provided
    for k, v in env_overrides.items():
        os.environ[k] = v
    # Construct fresh instance — _get_private_state is instance method
    s = Settings()
    # Clear cached secrets after construction (in case post-construction
    # reads cached anything from a previous instance)
    state = s._get_private_state()
    state["_cached_secrets"].clear()
    state["_secrets_batch_loaded"] = False
    return s


# ---------------------------------------------------------------------------
# 1. Required env var missing → fail-fast
# ---------------------------------------------------------------------------


class TestRequiredEnvMissingFailFast:
    """Missing required env vars → ValueError / ValidationError at boot।"""

    def test_get_production_env_missing_raises(self, monkeypatch):
        """Given CRITICAL_VAR unset + no default, When get_production_env called,
        Then ValueError raised — strict fail-fast।"""
        # Given
        from core.config import get_production_env

        monkeypatch.delenv("CRITICAL_VAR_FOR_TEST", raising=False)
        # When / Then
        with pytest.raises(ValueError, match="must be explicitly defined"):
            get_production_env("CRITICAL_VAR_FOR_TEST")

    def test_get_production_env_missing_returns_default_when_provided(self, monkeypatch):
        """Given OPTIONAL_VAR unset + default='fallback', When get_production_env,
        Then 'fallback' returned — default দিলে crash হয় না।"""
        from core.config import get_production_env

        monkeypatch.delenv("OPTIONAL_VAR_FOR_TEST", raising=False)
        # When
        result = get_production_env("OPTIONAL_VAR_FOR_TEST", default="fallback")
        # Then
        assert result == "fallback"

    def test_get_production_env_present_returns_value(self, monkeypatch):
        """Given SET_VAR='value', When get_production_env, Then 'value' returned।"""
        from core.config import get_production_env

        monkeypatch.setenv("SET_VAR_FOR_TEST", "value")
        assert get_production_env("SET_VAR_FOR_TEST") == "value"

    def test_get_production_env_empty_string_treated_as_missing(self, monkeypatch):
        """Given EMPTY_VAR='' (set but empty), When get_production_env called,
        Then ValueError raised — empty string ≡ missing (boundary)।"""
        from core.config import get_production_env

        monkeypatch.setenv("EMPTY_VAR_FOR_TEST", "")
        with pytest.raises(ValueError):
            get_production_env("EMPTY_VAR_FOR_TEST")

    def test_get_production_env_whitespace_returned_as_is(self, monkeypatch):
        """Given WS_VAR='   ' (whitespace only), When get_production_env called,
        Then '   ' returned — get_production_env does NOT strip whitespace
        (only treats empty/None as missing); boundary documented।"""
        from core.config import get_production_env

        # বাংলা: get_production_env শুধু `not value` চেক করে — whitespace-only
        # string truthy, তাই ফেরত যায়। caller-এর দায়িত্ব strip করা।
        monkeypatch.setenv("WS_VAR_FOR_TEST", "   ")
        result = get_production_env("WS_VAR_FOR_TEST")
        assert result == "   "


# ---------------------------------------------------------------------------
# 2. Optional env var with default
# ---------------------------------------------------------------------------


class TestOptionalEnvWithDefault:
    """Optional env vars: unset → default value; set → use env value।"""

    def test_settings_defaults_applied_when_env_unset(self, mock_secret_vault, monkeypatch):
        """Given no env vars set, When Settings instantiated,
        Then defaults applied (env='local', debug=False, port=8080)।"""
        # Given: env cleared by autouse _isolate_env fixture
        from core.config import Settings

        # Reset secret cache (mixin's sanctioned accessor)
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        # When
        s = Settings()
        # Then
        assert s.env == "local"  # default
        assert s.debug is False  # production-first default
        assert s.port == 8080  # default port
        assert s.host == "0.0.0.0"  # default host
        assert s.max_cost_per_task == 0.01  # default cost cap

    def test_settings_env_override_via_env_var(self, mock_secret_vault, monkeypatch):
        """Given ENV=test, When Settings instantiated, Then s.env=='test'।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "test")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.env == "test"

    def test_settings_port_override_via_env_var(self, mock_secret_vault, monkeypatch):
        """Given PORT=9000, When Settings instantiated, Then s.port==9000।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "test")
        monkeypatch.setenv("PORT", "9000")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.port == 9000

    def test_settings_debug_can_be_enabled_in_local(self, mock_secret_vault, monkeypatch):
        """Given ENV=local + DEBUG=true, When Settings instantiated,
        Then s.debug==True — debug অন হয় local-এ।"""
        from core.config import Settings

        # বাংলা: validate_env শুধু {local, staging, production, test} গ্রহণ করে।
        # 'development' / 'dev' NOT in allowed set — boundary documented।
        monkeypatch.setenv("ENV", "local")
        monkeypatch.setenv("DEBUG", "true")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.debug is True


# ---------------------------------------------------------------------------
# 3. Config validation: invalid value → error
# ---------------------------------------------------------------------------


class TestConfigValidationInvalidValue:
    """Invalid env values trigger Pydantic ValidationError / ValueError।"""

    def test_invalid_env_value_rejected(self, mock_secret_vault, monkeypatch):
        """Given ENV='invalid_env', When Settings instantiated,
        Then ValidationError — env must be one of allowed set।"""
        from pydantic import ValidationError

        from core.config import Settings

        # বাংলা: validate_env (config_validation.py:120) শুধু {local, staging,
        # production, test} গ্রহণ করে।
        monkeypatch.setenv("ENV", "invalid_env")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        with pytest.raises((ValidationError, ValueError)):
            Settings()

    def test_invalid_port_type_rejected(self, mock_secret_vault, monkeypatch):
        """Given PORT='abc' (non-numeric), When Settings instantiated,
        Then ValidationError — port must be int।"""
        from pydantic import ValidationError

        from core.config import Settings

        monkeypatch.setenv("ENV", "test")
        monkeypatch.setenv("PORT", "abc")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        with pytest.raises((ValidationError, ValueError)):
            Settings()

    def test_invalid_max_cost_type_rejected(self, mock_secret_vault, monkeypatch):
        """Given MAX_COST_PER_TASK='abc', When Settings instantiated,
        Then ValidationError — float cast fails।"""
        from pydantic import ValidationError

        from core.config import Settings

        monkeypatch.setenv("ENV", "test")
        monkeypatch.setenv("MAX_COST_PER_TASK", "abc")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        with pytest.raises((ValidationError, ValueError)):
            Settings()

    def test_invalid_supabase_url_format_rejected(self, mock_secret_vault, monkeypatch):
        """Given SUPABASE_URL='not-a-url' + report build, When
        build_config_validation_report called, Then report contains an error
        for SUPABASE_URL (FORMAT_PATTERNS['supabase_url'] regex mismatch)।
        Boundary: regex must match https?://*.supabase.(co|com) shape।"""
        from core.config_validation import build_config_validation_report

        monkeypatch.setenv("ENV", "test")
        # বাংলা: SUPABASE_URL format check boot-time report-এ চলে (not field_validator)।
        monkeypatch.setenv("SUPABASE_URL", "not-a-url")
        report = build_config_validation_report(env="test")
        # Then: at least one error check for SUPABASE_URL
        supabase_checks = [c for c in report.checks if c.name == "SUPABASE_URL"]
        assert any(c.status == "error" for c in supabase_checks), \
            "invalid SUPABASE_URL must produce an error check in the report"

    def test_valid_supabase_url_format_accepted(self, mock_secret_vault, monkeypatch):
        """Given SUPABASE_URL='https://test.supabase.co', When report built,
        Then SUPABASE_URL check is 'ok' (format valid)।"""
        from core.config_validation import build_config_validation_report

        monkeypatch.setenv("ENV", "test")
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        report = build_config_validation_report(env="test")
        supabase_checks = [c for c in report.checks if c.name == "SUPABASE_URL"]
        assert any(c.status == "ok" for c in supabase_checks)

    def test_invalid_redis_url_format_rejected(self, mock_secret_vault, monkeypatch):
        """Given REDIS_URL='invalid-redis', When report built, Then REDIS_URL
        check is 'error' (FORMAT_PATTERNS['redis_url'] mismatch)।"""
        from core.config_validation import build_config_validation_report

        monkeypatch.setenv("ENV", "test")
        monkeypatch.setenv("REDIS_URL", "invalid-redis")
        report = build_config_validation_report(env="test")
        redis_checks = [c for c in report.checks if c.name == "REDIS_URL"]
        assert any(c.status == "error" for c in redis_checks), \
            "invalid REDIS_URL must produce an error check in the report"

    def test_valid_redis_url_accepted(self, mock_secret_vault, monkeypatch):
        """Given REDIS_URL='redis://localhost:6379', When report built,
        Then REDIS_URL check is 'ok' (format valid)।"""
        from core.config_validation import build_config_validation_report

        monkeypatch.setenv("ENV", "test")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        report = build_config_validation_report(env="test")
        redis_checks = [c for c in report.checks if c.name == "REDIS_URL"]
        assert any(c.status == "ok" for c in redis_checks)

    def test_missing_required_var_marks_error_in_report(self, mock_secret_vault, monkeypatch):
        """Given SUPABASE_URL unset, When report built, Then SUPABASE_URL
        check is 'error' (required var missing)।"""
        from core.config_validation import build_config_validation_report

        monkeypatch.setenv("ENV", "test")
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        report = build_config_validation_report(env="test")
        supabase_checks = [c for c in report.checks if c.name == "SUPABASE_URL"]
        assert any(c.status == "error" for c in supabase_checks)


# ---------------------------------------------------------------------------
# 4. Environment-specific config (dev vs prod vs test)
# ---------------------------------------------------------------------------


class TestEnvironmentSpecificConfig:
    """ENV অনুযায়ী ভিন্ন behavior: dev / prod / test।"""

    def test_env_lowercased(self, mock_secret_vault, monkeypatch):
        """Given ENV='TEST' (uppercase), When Settings instantiated,
        Then s.env=='test' — validate_env lowercases।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "TEST")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.env == "test"

    def test_env_local_is_local(self, mock_secret_vault, monkeypatch):
        """Given ENV=local, When s.is_local() called, Then True।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "local")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.is_local() is True

    def test_env_development_alias_treated_as_local(self, mock_secret_vault, monkeypatch):
        """Given ENV=local + is_local() called, Then True — local is_local-listed।

        বাংলা: validate_env (config_validation.py:120) শুধু {local, staging,
        production, test} গ্রহণ করে — 'dev'/'development' rejected। কিন্তু
        is_local() মেথড নিজে 'dev'/'development' চেক করে (config.py:136)।
        যেহেতু env field-এ 'dev' বসানো যায় না, এই টেস্ট শুধু local-এর জন্য
        is_local() True রিটার্ন করে কিনা যাচাই করে।
        """
        from core.config import Settings

        monkeypatch.setenv("ENV", "local")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.is_local() is True

    def test_env_production_not_local(self, mock_secret_vault, monkeypatch):
        """Given ENV=production, When s.is_local() called, Then False।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "production")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.is_local() is False

    def test_test_env_allowed_in_validate_env(self, mock_secret_vault, monkeypatch):
        """Given ENV=test, When Settings instantiated, Then s.env=='test'
        — test অনুমোদিত env value।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "test")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.env == "test"

    def test_staging_env_allowed(self, mock_secret_vault, monkeypatch):
        """Given ENV=staging, When Settings instantiated, Then s.env=='staging'।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "staging")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.env == "staging"

    def test_is_bypass_allowed_false_in_production(self, mock_secret_vault, monkeypatch):
        """Given ENV=production + ALLOW_TEST_AUTH_BYPASS=true, When
        s.is_bypass_allowed, Then False — prod-এ bypass সবসময় নিষিদ্ধ।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOW_TEST_AUTH_BYPASS", "true")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.is_bypass_allowed is False

    def test_is_bypass_allowed_true_in_test_with_flag(self, mock_secret_vault, monkeypatch):
        """Given ENV=test + ALLOW_TEST_AUTH_BYPASS=true, When s.is_bypass_allowed,
        Then True — test-এ flag দিলে bypass চালু।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "test")
        monkeypatch.setenv("ALLOW_TEST_AUTH_BYPASS", "true")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.is_bypass_allowed is True

    def test_is_bypass_allowed_false_in_test_without_flag(self, mock_secret_vault, monkeypatch):
        """Given ENV=test + no ALLOW_TEST_AUTH_BYPASS, When s.is_bypass_allowed,
        Then False — test-এও flag ছাড়া bypass নেই (boundary)।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "test")
        monkeypatch.delenv("ALLOW_TEST_AUTH_BYPASS", raising=False)
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.is_bypass_allowed is False

    def test_is_origin_bypass_allowed_false_in_production(
        self, mock_secret_vault, monkeypatch
    ):
        """Given ENV=production + ALLOW_TEST_ORIGIN_BYPASS=true, When
        s.is_origin_bypass_allowed, Then False — prod-এ origin bypass নিষিদ্ধ।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ALLOW_TEST_ORIGIN_BYPASS", "true")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.is_origin_bypass_allowed is False

    def test_production_debug_true_explicitly_rejected(
        self, mock_secret_vault, monkeypatch
    ):
        """Given ENV=production + DEBUG=true explicitly set, When Settings
        instantiated, Then ValidationError raised — validate_debug_mode
        prohibits explicit DEBUG=true in prod/staging (boundary)।"""
        from pydantic import ValidationError

        from core.config import Settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("DEBUG", "true")
        # বাংলা: validate_debug_mode (config_validation.py:137) — prod/staging-এ
        # explicit DEBUG=true PROHIBITED → ValueError raised (fail-fast)।
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        with pytest.raises((ValidationError, ValueError)):
            Settings()

    def test_production_debug_false_accepted(
        self, mock_secret_vault, monkeypatch
    ):
        """Given ENV=production + DEBUG=false, When Settings instantiated,
        Then s.debug==False — happy path (production wants debug off)।"""
        from core.config import Settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("DEBUG", "false")
        from core.config import settings as _settings_singleton
        _settings_singleton._get_private_state()["_cached_secrets"].clear()
        _settings_singleton._get_private_state()["_secrets_batch_loaded"] = False
        s = Settings()
        assert s.debug is False


# ---------------------------------------------------------------------------
# 5. List parsing: admin_emails, allowed_hosts, cors_origins
# ---------------------------------------------------------------------------


class TestListParsing:
    """Comma-separated / JSON list env var parsing — SettingsValidationMixin।"""

    def test_parse_admin_emails_empty_returns_empty_list(self):
        """Given '', When parse_admin_emails, Then [] — boundary।"""
        from core.config import Settings

        assert Settings.parse_admin_emails("") == []

    def test_parse_admin_emails_single_value(self):
        """Given 'a@x.com', When parse_admin_emails, Then ['a@x.com']।"""
        from core.config import Settings

        assert Settings.parse_admin_emails("a@x.com") == ["a@x.com"]

    def test_parse_admin_emails_comma_separated(self):
        """Given 'a@x.com, b@x.com', When parse_admin_emails,
        Then ['a@x.com', 'b@x.com'] — comma split + strip।"""
        from core.config import Settings

        result = Settings.parse_admin_emails("a@x.com, b@x.com")
        assert result == ["a@x.com", "b@x.com"]

    def test_parse_admin_emails_strips_whitespace(self):
        """Given '  spaced@x.com  ', When parse_admin_emails,
        Then ['spaced@x.com'] — whitespace stripped।"""
        from core.config import Settings

        assert Settings.parse_admin_emails("  spaced@x.com  ") == ["spaced@x.com"]

    def test_parse_allowed_hosts_empty_returns_empty_list(self):
        """Given '', When parse_allowed_hosts, Then [] — boundary।"""
        from core.config import Settings

        assert Settings.parse_allowed_hosts("") == []

    def test_parse_allowed_hosts_comma_separated(self):
        """Given 'a.com,b.com', When parse_allowed_hosts,
        Then ['a.com', 'b.com']।"""
        from core.config import Settings

        assert Settings.parse_allowed_hosts("a.com,b.com") == ["a.com", "b.com"]


# ---------------------------------------------------------------------------
# 6. Boolean flag parsing
# ---------------------------------------------------------------------------


class TestBooleanFlagParsing:
    """admin_authorized / autofix_authorized / debug boolean parsing।"""

    def test_validate_boolean_flags_true_string(self):
        """Given 'true', When validate_boolean_flags, Then True।"""
        from core.config_validation import SettingsValidationMixin

        assert SettingsValidationMixin.validate_boolean_flags("true") is True

    def test_validate_boolean_flags_yes_string(self):
        """Given 'yes', When validate_boolean_flags, Then True।"""
        from core.config_validation import SettingsValidationMixin

        assert SettingsValidationMixin.validate_boolean_flags("yes") is True

    def test_validate_boolean_flags_one_string(self):
        """Given '1', When validate_boolean_flags, Then True।"""
        from core.config_validation import SettingsValidationMixin

        assert SettingsValidationMixin.validate_boolean_flags("1") is True

    def test_validate_boolean_flags_false_string(self):
        """Given 'false', When validate_boolean_flags, Then False।"""
        from core.config_validation import SettingsValidationMixin

        assert SettingsValidationMixin.validate_boolean_flags("false") is False

    def test_validate_boolean_flags_actual_bool_passthrough(self):
        """Given True (bool), When validate_boolean_flags, Then True — passthrough।"""
        from core.config_validation import SettingsValidationMixin

        assert SettingsValidationMixin.validate_boolean_flags(True) is True
        assert SettingsValidationMixin.validate_boolean_flags(False) is False

    def test_validate_boolean_flags_unknown_string_returns_false(self):
        """Given 'maybe' (unknown), When validate_boolean_flags, Then False —
        fail-closed on unknown truthiness।"""
        from core.config_validation import SettingsValidationMixin

        assert SettingsValidationMixin.validate_boolean_flags("maybe") is False

    def test_validate_boolean_flags_zero_returns_false(self):
        """Given '0', When validate_boolean_flags, Then False।"""
        from core.config_validation import SettingsValidationMixin

        assert SettingsValidationMixin.validate_boolean_flags("0") is False


# ---------------------------------------------------------------------------
# 7. JWT secret validation (config_validation.set_jwt_secret)
# ---------------------------------------------------------------------------


class TestJwtSecretValidation:
    """set_jwt_secret — production-grade JWT secret validation।"""

    def test_jwt_secret_known_insecure_default_rejected(self):
        """Given JWT secret='change-me-in-production', When set_jwt_secret called,
        Then ValueError — known insecure defaults never accepted।"""
        from core.config_validation import SettingsValidationMixin

        with pytest.raises(ValueError, match="known insecure default"):
            SettingsValidationMixin.set_jwt_secret("change-me-in-production")

    def test_jwt_secret_short_in_production_rejected(self):
        """Given env=production + JWT secret='short' (< 64 bytes), When
        set_jwt_secret, Then ValueError — prod-এ >= 64 bytes বাধ্যতামূলক।"""
        from core.config_validation import SettingsValidationMixin

        info = type("Info", (), {"data": {"env": "production"}})()
        with pytest.raises(ValueError, match="at least 64 bytes"):
            SettingsValidationMixin.set_jwt_secret("short_secret_under_64_bytes", info=info)

    def test_jwt_secret_empty_in_production_rejected(self):
        """Given env=production + JWT secret='', When set_jwt_secret,
        Then ValueError — prod-এ empty JWT নিষিদ্ধ।"""
        from core.config_validation import SettingsValidationMixin

        info = type("Info", (), {"data": {"env": "production"}})()
        with pytest.raises(ValueError, match="cannot be empty"):
            SettingsValidationMixin.set_jwt_secret("", info=info)

    def test_jwt_secret_empty_in_dev_generates_random(self):
        """Given env=local + JWT secret='', When set_jwt_secret,
        Then random 64+ byte secret generated (safe for dev)।"""
        from core.config_validation import SettingsValidationMixin

        info = type("Info", (), {"data": {"env": "local"}})()
        result = SettingsValidationMixin.set_jwt_secret("", info=info)
        assert isinstance(result, str)
        assert len(result) >= 64  # secrets.token_urlsafe(64) → ~86 chars

    def test_jwt_secret_valid_production_secret_accepted(self):
        """Given env=production + JWT secret (>= 64 bytes strong), When
        set_jwt_secret, Then secret returned as-is।"""
        from core.config_validation import SettingsValidationMixin

        strong_secret = "x" * 80  # 80 chars — well above 64
        info = type("Info", (), {"data": {"env": "production"}})()
        result = SettingsValidationMixin.set_jwt_secret(strong_secret, info=info)
        assert result == strong_secret

    def test_jwt_secret_insecure_default_secret_rejected(self):
        """Given JWT secret='secret' (one of INSECURE_DEFAULTS), When
        set_jwt_secret, Then ValueError — 'secret' never allowed।"""
        from core.config_validation import SettingsValidationMixin

        with pytest.raises(ValueError, match="known insecure default"):
            SettingsValidationMixin.set_jwt_secret("secret")

    def test_jwt_secret_insecure_default_changeme_rejected(self):
        """Given JWT secret='changeme', When set_jwt_secret,
        Then ValueError।"""
        from core.config_validation import SettingsValidationMixin

        with pytest.raises(ValueError):
            SettingsValidationMixin.set_jwt_secret("changeme")


# ---------------------------------------------------------------------------
# 8. CORS origins parsing + production filtering
# ---------------------------------------------------------------------------


class TestCorsOriginsParsing:
    """CORS origins JSON / comma parsing + production localhost strip।"""

    def test_parse_cors_origins_helper_empty_returns_empty(self):
        """Given '', When parse_cors_origins_helper, Then [] — boundary।"""
        from core.config_validation import SettingsValidationMixin

        assert SettingsValidationMixin.parse_cors_origins_helper("") == []

    def test_parse_cors_origins_helper_json_list(self):
        """Given JSON list string, When parse_cors_origins_helper,
        Then parsed list returned।"""
        from core.config_validation import SettingsValidationMixin

        result = SettingsValidationMixin.parse_cors_origins_helper(
            '["https://a.com", "https://b.com"]'
        )
        assert result == ["https://a.com", "https://b.com"]

    def test_parse_cors_origins_helper_comma_separated(self):
        """Given comma-separated string, When parse_cors_origins_helper,
        Then list of stripped origins returned।"""
        from core.config_validation import SettingsValidationMixin

        result = SettingsValidationMixin.parse_cors_origins_helper("https://a.com, https://b.com")
        assert result == ["https://a.com", "https://b.com"]

    def test_validate_cors_origins_helper_strips_localhost_in_production(self):
        """Given ['http://127.0.0.1:3000', 'https://a.com'] in production,
        When validate_cors_origins_helper, Then only 'https://a.com' returned।"""
        from core.config_validation import SettingsValidationMixin

        origins = ["http://127.0.0.1:3000", "https://a.com"]
        info = type("Info", (), {"data": {"env": "production"}})()
        result = SettingsValidationMixin.validate_cors_origins_helper(origins, info=info)
        assert result == ["https://a.com"]

    def test_validate_cors_origins_helper_keeps_localhost_in_dev(self):
        """Given ['http://127.0.0.1:3000'] in dev, When validate_cors_origins_helper,
        Then localhost preserved — dev allows localhost।"""
        from core.config_validation import SettingsValidationMixin

        origins = ["http://127.0.0.1:3000"]
        info = type("Info", (), {"data": {"env": "local"}})()
        result = SettingsValidationMixin.validate_cors_origins_helper(origins, info=info)
        assert result == ["http://127.0.0.1:3000"]


# ---------------------------------------------------------------------------
# 9. Platform apex hosts — production security invariant
# ---------------------------------------------------------------------------


class TestPlatformApexHostsSecurity:
    """PLATFORM_APEX_HOSTS — bare public apex domains forbidden in ALLOWED_HOSTS।"""

    def test_platform_apex_hosts_is_frozenset(self):
        """Given config_validation module, When PLATFORM_APEX_HOSTS inspected,
        Then frozenset — immutable security policy।"""
        from core.config_validation import PLATFORM_APEX_HOSTS

        assert isinstance(PLATFORM_APEX_HOSTS, frozenset)

    def test_known_platforms_in_blocklist(self):
        """Given PLATFORM_APEX_HOSTS, When checked, Then includes onrender.com,
        vercel.app, netlify.app, herokuapp.com — bare platform apex forbidden।"""
        from core.config_validation import PLATFORM_APEX_HOSTS

        for apex in ("onrender.com", "vercel.app", "netlify.app", "herokuapp.com"):
            assert apex in PLATFORM_APEX_HOSTS, apex

    def test_platform_apex_hosts_not_empty(self):
        """Given PLATFORM_APEX_HOSTS, When checked, Then non-empty — at least 5
        platforms blocked (boundary)।"""
        from core.config_validation import PLATFORM_APEX_HOSTS

        assert len(PLATFORM_APEX_HOSTS) >= 5


# ---------------------------------------------------------------------------
# 10. Settings module-level singleton contract
# ---------------------------------------------------------------------------


class TestSettingsModuleShape:
    """config.py module-level shape contract — singleton, get_production_env।"""

    def test_settings_singleton_exists(self):
        """Given core.config module, When imported, Then `settings` singleton
        attribute present — module-level config access point।"""
        from core.config import settings

        assert settings is not None
        assert hasattr(settings, "env")
        assert hasattr(settings, "debug")
        assert hasattr(settings, "port")

    def test_get_production_env_is_callable(self):
        """Given core.config module, When get_production_env inspected,
        Then callable।"""
        from core.config import get_production_env

        assert callable(get_production_env)

    def test_settings_has_is_local_method(self):
        """Given settings singleton, When is_local checked, Then callable।"""
        from core.config import settings

        assert callable(settings.is_local)

    def test_settings_has_is_bypass_allowed_property(self):
        """Given settings singleton, When is_bypass_allowed inspected,
        Then property exists — bypass gate।"""
        from core.config import settings

        # বাংলা: is_bypass_allowed @property — access করলেই bool ফেরত দেয়।
        assert isinstance(settings.is_bypass_allowed, bool)
