from __future__ import annotations

from core.config import Settings


def test_upstash_rest_pool_orders_accounts_and_filters_placeholders(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "rediss://test.upstash.io")
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://primary.upstash.io/")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "primary-token")
    monkeypatch.setenv("UPSTASH_REDIS_SECONDARY_REST_URL", "https://secondary.upstash.io")
    monkeypatch.setenv("UPSTASH_REDIS_SECONDARY_REST_TOKEN", "secondary-token")
    monkeypatch.setenv("UPSTASH_REDIS_TERTIARY_REST_URL", "https://example.com")
    monkeypatch.setenv("UPSTASH_REDIS_TERTIARY_REST_TOKEN", "ignored-token")
    monkeypatch.delenv("UPSTASH_REDIS_QUATERNARY_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_QUATERNARY_REST_TOKEN", raising=False)

    settings = Settings()

    assert settings.upstash_redis_rest_pool == [
        ("https://primary.upstash.io", "primary-token"),
        ("https://secondary.upstash.io", "secondary-token"),
    ]
    assert settings.upstash_redis_rest_pool_enabled is True


def test_upstash_rest_pool_is_disabled_without_complete_credentials(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "rediss://test.upstash.io")
    for name in (
        "UPSTASH_REDIS_REST_URL",
        "UPSTASH_REDIS_REST_TOKEN",
        "UPSTASH_REDIS_SECONDARY_REST_URL",
        "UPSTASH_REDIS_SECONDARY_REST_TOKEN",
        "UPSTASH_REDIS_TERTIARY_REST_URL",
        "UPSTASH_REDIS_TERTIARY_REST_TOKEN",
        "UPSTASH_REDIS_QUATERNARY_REST_URL",
        "UPSTASH_REDIS_QUATERNARY_REST_TOKEN",
        "UPSTASH_REDIS_QUINARY_REST_URL",
        "UPSTASH_REDIS_QUINARY_REST_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings()

    assert settings.upstash_redis_rest_pool == []
    assert settings.upstash_redis_rest_pool_enabled is False
