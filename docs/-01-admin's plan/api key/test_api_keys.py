"""
SupremeAI 2.0 — API Key Management Tests
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base, get_db
from core.security import generate_api_key, hash_api_key, verify_api_key, validate_key_format
from core.rate_limiter import APIKeyRateLimiter
from models.api_key import APIKey, KeyStatus, KeyScope
from main import app


# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_api_keys.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestKeyGeneration:
    """Test API key generation and validation."""

    def test_generate_key_format(self):
        key, prefix = generate_api_key(env="live")
        assert key.startswith("sk_live_")
        assert len(key.split("_")) == 5  # sk, live, prefix, random, checksum
        assert validate_key_format(key) is True

    def test_generate_key_uniqueness(self):
        keys = set()
        for _ in range(100):
            key, _ = generate_api_key()
            assert key not in keys
            keys.add(key)

    def test_invalid_key_format(self):
        assert validate_key_format("invalid") is False
        assert validate_key_format("sk_live_abc") is False
        assert validate_key_format("sk_invalid_abc123de_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx_xxxx") is False

    def test_hash_and_verify(self):
        key, _ = generate_api_key()
        hashed = hash_api_key(key)
        assert verify_api_key(key, hashed) is True
        assert verify_api_key("wrong_key", hashed) is False


class TestRateLimiter:
    """Test Redis-based rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_limit(self):
        limiter = APIKeyRateLimiter()
        status = await limiter.check_rate_limit(
            key_id="test-key-1",
            rpm_limit=10,
            rpd_limit=100,
        )
        assert status.allowed is True
        assert status.current_rpm == 1

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_over_limit(self):
        limiter = APIKeyRateLimiter()
        # Make 10 requests (at limit)
        for _ in range(10):
            await limiter.check_rate_limit(
                key_id="test-key-2",
                rpm_limit=10,
                rpd_limit=100,
            )

        # 11th request should be blocked
        status = await limiter.check_rate_limit(
            key_id="test-key-2",
            rpm_limit=10,
            rpd_limit=100,
        )
        assert status.allowed is False
        assert status.retry_after_ms > 0


class TestAPIEndpoints:
    """Test FastAPI endpoints."""

    def test_create_key_unauthorized(self):
        response = client.post("/api/v1/keys", json={"name": "Test Key"})
        assert response.status_code == 401

    def test_create_key_success(self, monkeypatch):
        # Mock auth
        def mock_get_current_user():
            return {"uid": str(uuid4()), "max_api_keys": 5}

        monkeypatch.setattr("api.keys.get_current_user", mock_get_current_user)

        response = client.post("/api/v1/keys", json={
            "name": "Test Key",
            "scopes": ["inference"],
            "environment": "live",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Key"
        assert data["key"].startswith("sk_live_")
        assert "key_prefix" in data

    def test_list_keys(self, monkeypatch):
        user_id = str(uuid4())

        def mock_get_current_user():
            return {"uid": user_id, "max_api_keys": 5}

        monkeypatch.setattr("api.keys.get_current_user", mock_get_current_user)

        # Create a key first
        client.post("/api/v1/keys", json={
            "name": "Test Key",
            "scopes": ["inference"],
            "environment": "live",
        })

        response = client.get("/api/v1/keys")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["keys"]) >= 1

    def test_revoke_key(self, monkeypatch):
        user_id = str(uuid4())

        def mock_get_current_user():
            return {"uid": user_id, "max_api_keys": 5}

        monkeypatch.setattr("api.keys.get_current_user", mock_get_current_user)

        # Create key
        create_resp = client.post("/api/v1/keys", json={
            "name": "Key to Revoke",
            "scopes": ["inference"],
            "environment": "live",
        })
        key_id = create_resp.json()["id"]

        # Revoke key
        response = client.post(f"/api/v1/keys/{key_id}/revoke")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify key is revoked
        get_resp = client.get(f"/api/v1/keys/{key_id}")
        assert get_resp.json()["status"] == "revoked"


class TestSecurity:
    """Test security features."""

    def test_key_never_stored_plaintext(self, monkeypatch):
        user_id = str(uuid4())

        def mock_get_current_user():
            return {"uid": user_id, "max_api_keys": 5}

        monkeypatch.setattr("api.keys.get_current_user", mock_get_current_user)

        response = client.post("/api/v1/keys", json={
            "name": "Security Test",
            "scopes": ["inference"],
            "environment": "live",
        })

        data = response.json()
        # Full key should only be returned on creation
        assert "key" in data

        # List should NOT contain full key
        list_resp = client.get("/api/v1/keys")
        for key in list_resp.json()["keys"]:
            assert "key" not in key  # Full key never in list
            assert key["key_prefix"].endswith("...") or len(key["key_prefix"]) < 20

    def test_quota_enforcement(self, monkeypatch):
        user_id = str(uuid4())

        def mock_get_current_user():
            return {"uid": user_id, "max_api_keys": 5}

        monkeypatch.setattr("api.keys.get_current_user", mock_get_current_user)

        # Create key with tiny quota
        create_resp = client.post("/api/v1/keys", json={
            "name": "Quota Test",
            "scopes": ["inference"],
            "environment": "live",
            "monthly_quota": 100,
        })
        key_id = create_resp.json()["id"]

        # Simulate quota exhaustion
        db = next(override_get_db())
        key = db.query(APIKey).filter(APIKey.id == key_id).first()
        key.quota_used = 100
        db.commit()

        # Key should be suspended
        get_resp = client.get(f"/api/v1/keys/{key_id}")
        assert get_resp.json()["status"] == "suspended"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
