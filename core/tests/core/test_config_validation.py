# SupremeAI 2.0 — Core Configuration & DB Pool Teardown Test Suite
# বাংলা মন্তব্য: এটি কনফিগারেশন ভ্যালিডেশন, প্রোডাকশন JWT সিক্রেট লেন্থ চেক এবং কানেকশন পুল ডিসপোজালের ইউনিট টেস্ট পরিচালনা করে।

import pytest

from core.config import Settings
from database.pgbouncer_pool import dispose_db_pool


def test_jwt_secret_validation_local():
    settings = Settings(env="local")
    assert len(settings.jwt_secret) >= 64


def test_jwt_secret_validation_production_valid(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_JWT_SECRET", "a" * 64)
    settings = Settings(env="production")
    assert len(settings.jwt_secret) >= 64


def test_jwt_secret_validation_production_invalid():
    with pytest.raises(ValueError, match="JWT secret must be at least 64 bytes long in production"):
        Settings.set_jwt_secret(
            "short_prod_key", info=type("Info", (), {"data": {"env": "production"}})()
        )


@pytest.mark.asyncio
async def test_dispose_db_pool_safely():
    # Verify pool disposal executes safely without exceptions
    await dispose_db_pool()
