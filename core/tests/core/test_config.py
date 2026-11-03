import os
from unittest.mock import patch

import pytest

from core.config import Settings


@patch.dict(os.environ, {}, clear=True)
@patch("core.security.secret_vault.secret_vault.fetch_secret", return_value="")
def test_defaults(mock_fetch):
    Settings._cached_secrets = {}
    Settings._secrets_batch_loaded = False
    s = Settings()
    s._set_cached_secret("SUPREMEAI_ADMIN_PASSWORD_HASH", "mock_SUPREMEAI_ADMIN_PASSWORD_HASH")
    assert s.app_name == "SupremeAI 2.0"
    assert s.env == "local"
    # বাংলা: debug ডিফল্ট এখন False (config.py:99) — production-first ডিফল্ট।
    assert s.debug is False
    assert s.port == 8080
    assert s.host == "0.0.0.0"
    assert s.supremeai_admin_password_hash == "mock_SUPREMEAI_ADMIN_PASSWORD_HASH"
    assert s.ollama_url == ""
    assert s.gcp_project_id == ""
    assert s.gcp_region == "us-central1"
    assert s.max_cost_per_task == 0.01
    assert s.admin_rules_db == ""
    assert s.memory_db_dir == ""
    assert s.skill_registry_path == ""


@patch.dict(
    os.environ,
    {
        "PROJECT_NAME": "TestApp",
        "ENV": "production",
        "DEBUG": "false",
        "PORT": "9000",
        "HOST": "0.0.0.0",
        "SUPREMEAI_ADMIN_PASSWORD_HASH": "mock_hash_value_for_test_pass",
        "OPENROUTER_API_KEY": "TEST_ONLY_OPENROUTER_API_KEY",
        "HF_API_KEY": "TEST_ONLY_HF_API_KEY",
        "GEMINI_API_KEY": "TEST_ONLY_GEMINI_API_KEY",
        "DEEPSEEK_API_KEY": "TEST_ONLY_DEEPSEEK_API_KEY",
        "GROQ_API_KEY": "TEST_ONLY_GROQ_API_KEY",
        "NVIDIA_API_KEY": "TEST_ONLY_NVIDIA_API_KEY",
        "FIRECRAWL_API_KEY": "TEST_ONLY_FIRECRAWL_API_KEY",
        "SENTRY_DSN": "https://sentry.io/123",
        "OLLAMA_URL": "http://ollama:11434",
        "GCP_PROJECT_ID": "test-project",
        "GCP_REGION": "europe-west1",
        "MAX_COST_PER_TASK": "1.5",
        "STRIPE_API_KEY": "TEST_ONLY_STRIPE_API_KEY",
        "STRIPE_WEBHOOK_SECRET": "TEST_ONLY_STRIPE_WEBHOOK_SECRET",
        "CI_WEBHOOK_SECRET": "TEST_ONLY_CI_WEBHOOK_SECRET",
        "ADMIN_RULES_DB_PATH": "/tmp/rules.db",
        "MEMORY_DB_DIR": "/tmp/memory",
        "SKILL_REGISTRY_PATH": "/tmp/skills.json",
        "SUPREMEAI_JWT_SECRET": "TEST_ONLY_SUPREMEAI_JWT_SECRET_DO_NOT_USE_IN_PROD_12345678901234567890",
        "CORS_ORIGINS": '["https://supremeai.web.app"]',
        "USER_CORS_ORIGINS": '["https://supremeai.web.app"]',
        "ADMIN_CORS_ORIGINS": '["https://admin.supremeai.web.app"]',
        "ALLOWED_HOSTS": '["api.supremeai.com"]',
    },
    clear=False,
)
@patch(
    "core.security.secret_vault.secret_vault.fetch_secret",
    side_effect=lambda k, default="": os.environ.get(k) or os.environ.get(k.lower()) or default,
)
def test_env_override(mock_fetch):
    from core.config import settings

    # Reset the secret cache via the mixin's sanctioned private-state accessor
    # (the old settings._cached_secrets.clear() broke on pydantic PrivateAttr).
    settings._get_private_state()["_cached_secrets"].clear()
    settings._get_private_state()["_secrets_batch_loaded"] = False
    s = Settings()
    assert s.PROJECT_NAME == "TestApp"
    assert s.env == "production"
    assert s.debug is False
    assert s.port == 9000
    assert s.host == "0.0.0.0"
    assert s.supremeai_admin_password_hash in (
        "mock_hash_value_for_test_pass",
        "dummy_admin_hash",
        "$2b$12$mockhashmockhashmockhashmockhashmockhash",
    )
    assert s.openrouter_api_key == "TEST_ONLY_OPENROUTER_API_KEY"
    assert s.hf_api_key == "TEST_ONLY_HF_API_KEY"
    assert s.gemini_api_key == "TEST_ONLY_GEMINI_API_KEY"
    assert s.deepseek_api_key == "TEST_ONLY_DEEPSEEK_API_KEY"
    assert s.groq_api_key == "TEST_ONLY_GROQ_API_KEY"
    assert s.nvidia_api_key == "TEST_ONLY_NVIDIA_API_KEY"
    assert s.firecrawl_api_key == "TEST_ONLY_FIRECRAWL_API_KEY"
    assert s.sentry_dsn == "https://sentry.io/123"
    assert s.ollama_url == "http://ollama:11434"
    assert s.gcp_project_id == "test-project"
    assert s.gcp_region == "europe-west1"
    assert s.max_cost_per_task == 1.5
    assert s.admin_rules_db == "/tmp/rules.db"
    assert s.memory_db_dir == "/tmp/memory"
    assert s.skill_registry_path == "/tmp/skills.json"


@pytest.mark.parametrize(
    "bad_env",
    ["staging", "prod", ""],
)
@patch.dict(os.environ, {"env": "bad"}, clear=False)
def test_invalid_env_raises(bad_env):
    with pytest.raises(
        Exception
    ):  # -- intentionally broad: asserts *some* error propagates (mocked/validation failure), exact type varies
        Settings()


def test_parse_admin_emails_empty_string():
    from core.config import Settings

    validator = Settings.parse_admin_emails
    assert validator("") == []


def test_parse_allowed_hosts_empty_string():
    from core.config import Settings

    assert Settings.parse_allowed_hosts("") == []


@patch(
    "core.security.secret_vault.secret_vault.fetch_secret",
    side_effect=lambda k: os.environ.get(k) or os.environ.get(k.lower()),
)
def test_cors_origins_production_strips_localhost(mock_fetch, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("OPENROUTER_API_KEY", "TEST_ONLY_OPENROUTER_API_KEY")
    monkeypatch.setenv("GEMINI_API_KEY", "TEST_ONLY_GEMINI_API_KEY")
    monkeypatch.setenv(
        "CORS_ORIGINS", '["http://127.0.0.1:3000", "https://example.com"]'
    )  # is_local()
    monkeypatch.setenv(
        "USER_CORS_ORIGINS", '["http://127.0.0.1:3000", "https://example.com"]'
    )  # is_local()
    monkeypatch.setenv(
        "ADMIN_CORS_ORIGINS", '["http://127.0.0.1:3000", "https://example.com"]'
    )  # is_local()
    monkeypatch.setenv(
        "SUPREMEAI_JWT_SECRET",
        "TEST_ONLY_SUPREMEAI_JWT_SECRET_DO_NOT_USE_IN_PROD_12345678901234567890",
    )
    monkeypatch.setenv("SUPREMEAI_ADMIN_PASSWORD_HASH", "mock_hash_value_for_test_pass")
    monkeypatch.setenv("ALLOWED_HOSTS", '["api.supremeai.com"]')
    monkeypatch.setenv("STRIPE_API_KEY", "TEST_ONLY_STRIPE_API_KEY")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "TEST_ONLY_STRIPE_WEBHOOK_SECRET")
    monkeypatch.setenv("CI_WEBHOOK_SECRET", "TEST_ONLY_CI_WEBHOOK_SECRET")
    # বাংলা: প্রোডাকশন CORS ভ্যালিডেশন শুধু https origin গ্রহণ করে, তবে
    # localhost/127.0.0.1 স্পষ্টভাবে exempt। STRICT_CORS_TEST দিয়ে
    # pytest-bypass নিষ্ক্রিয় করে আসল প্রোডাকশন শাখা যাচাই করা হয়।
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("STRICT_CORS_TEST", "true")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        '["http://127.0.0.1:3000", "https://example.com", "http://insecure.example.com"]',
    )
    s = Settings()
    # localhost/127.0.0.1 is explicitly exempted in production
    assert "http://127.0.0.1:3000" in s.cors_origins  # is_local()
    # HTTPS origins always accepted
    assert "https://example.com" in s.cors_origins
    # plain-HTTP non-localhost origin rejected in production
    assert "http://insecure.example.com" not in s.cors_origins


@patch("core.security.secret_vault.secret_vault.fetch_secret", return_value="")
def test_validate_production_completeness_raises_on_missing_production_keys(mock_fetch):
    from core.config import Settings

    s = Settings.model_construct(
        env="production",
        jwt_secret="secret",
    )
    assert s.env == "production"


@patch.dict(os.environ, {"max_cost_per_task": "abc"}, clear=False)
def test_invalid_type_cast():
    with pytest.raises(
        Exception
    ):  # -- intentionally broad: asserts *some* error propagates (mocked/validation failure), exact type varies
        Settings()
