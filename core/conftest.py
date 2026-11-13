# backend/conftest.py
# Test configuration and fixtures for SupremeAI backend
import asyncio
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_CORE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CORE_DIR.parent
for _p in (str(_CORE_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _alias_core_package(pkg_name: str) -> None:
    """Ensure `import <pkg_name>` and `import core.<pkg_name>` resolve to the same module."""
    try:
        import importlib

        core_pkg = importlib.import_module(f"core.{pkg_name}")
        sys.modules.setdefault(pkg_name, core_pkg)
    except Exception:
        pass


_alias_core_package("models")
_alias_core_package("database")


# ROOT-CAUSE FIX: pytest collection phase-এ tests/api/*.py, tests/core/*.py-র
# অনেক ফাইল module-level-এই route/app মডিউল import করে, যেগুলো
# api/routes/api_keys.py-র মতো জায়গায় module-level singleton
# `limiter = AsyncRateLimiter()` তৈরি করে দেয় -- আর AsyncRateLimiter.__init__()
# তখনই os.getenv("RATE_LIMIT_ENABLED") পড়ে নেয়, tests/conftest.py-র `app`
# fixture রান হওয়ারও অনেক আগে। backend/conftest.py হলো pytest rootdir
# (backend/)-এর সবচেয়ে উপরের conftest, তাই এখানে module-level-এই env var
# সেট করা হচ্ছে -- এটাই collection শুরুর আগে guaranteed সবচেয়ে আগে চলে।
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables.

    বাংলা: আগের মান সংরক্ষণ করে টেস্ট শেষে রিস্টোর করা হয়।
    এতে টেস্টের মধ্যে env var 'bleed' হয় না।
    """
    _SENTINEL = object()
    _keys = ("TESTING", "ENV", "DATABASE_URL", "REDIS_URL")
    _defaults = ("True", "test", "sqlite:///./test.db", "redis://mocked-redis-url:6379")

    # Save originals before overriding
    originals = {k: os.environ.get(k, _SENTINEL) for k in _keys}

    for k, v in zip(_keys, _defaults, strict=False):
        os.environ.setdefault(k, v)

    yield

    # Restore exactly what was there before — don't blindly delete
    for k in _keys:
        original = originals[k]
        if original is _SENTINEL:
            os.environ.pop(k, None)
        else:
            os.environ[k] = original


@pytest.fixture
def mock_redis():
    """Provide a mocked Redis instance for tests."""
    with patch("redis.asyncio.from_url") as mock_redis_constructor:
        mock_connection = MagicMock()
        mock_connection.ping = MagicMock(return_value=True)
        mock_connection.set = MagicMock(return_value=True)
        mock_connection.get = MagicMock(return_value=None)
        mock_redis_constructor.return_value = mock_connection
        yield mock_connection


@pytest.fixture
def mock_async_redis():
    """Provide an async Redis mock for async tests."""
    with patch("redis.asyncio.from_url") as mock_redis_constructor:
        mock_instance = MagicMock()
        mock_instance.ping = asyncio.Future()
        mock_instance.ping.set_result(True)
        mock_instance.set = asyncio.Future()
        mock_instance.set.set_result(True)
        mock_instance.get = asyncio.Future()
        mock_instance.get.set_result(None)
        mock_redis_constructor.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_external_apis():
    """Mock external API calls to prevent network requests during tests."""
    try:
        import requests  # noqa: F401
    except ImportError:
        yield {
            "get": MagicMock(),
            "post": MagicMock(),
            "put": MagicMock(),
            "delete": MagicMock(),
        }
        return

    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("requests.put") as mock_put,
        patch("requests.delete") as mock_delete,
    ):
        # Configure mocks to return successful responses
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {}
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {}

        yield {"get": mock_get, "post": mock_post, "put": mock_put, "delete": mock_delete}


# বাংলা: event_loop fixture সরানো হয়েছে।
# pyproject.toml-এ asyncio_mode = "auto" সেট থাকায় pytest-asyncio নিজেই
# event loop ম্যানেজ করে। manual event_loop fixture pytest-asyncio 0.21+ এ
# DeprecationWarning দেয় এবং filterwarnings="error" এর কারণে টেস্ট ফেল করে।


@pytest.fixture(scope="session")
def override_setup_test_database():
    """Session-scoped placeholder fixture for test database setup overrides."""
    yield


TEST_SECRET_KEY: str = "test_secret_key_for_jwt_auth_testing_minimum_length_required"
TEST_ALGORITHM: str = "HS256"
TEST_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


class CustomAssertions:
    """Helper assertions for unit tests."""

    @staticmethod
    def assert_valid_uuid(val: Any, version: int = 4) -> None:
        import uuid
        val_str = str(val)
        parsed = uuid.UUID(val_str, version=version)
        assert str(parsed) == val_str

    @staticmethod
    def assert_email_format(email: str) -> None:
        import re
        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        assert re.match(pattern, email) is not None, f"Invalid email format: {email}"


@pytest.fixture
def assertions() -> CustomAssertions:
    return CustomAssertions()


@pytest.fixture
def valid_password() -> str:
    return "SecurePassword123!"


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    return {
        "id": "11111111-1111-4111-a111-111111111111",
        "email": "user@example.com",
        "full_name": "Standard User",
        "role": "user",
        "is_active": True,
    }


@pytest.fixture
def sample_admin_data() -> dict[str, Any]:
    return {
        "id": "22222222-2222-4222-a222-222222222222",
        "email": "admin@example.com",
        "full_name": "Admin User",
        "role": "admin",
        "is_active": True,
    }


@pytest.fixture
def sample_operator_data() -> dict[str, Any]:
    return {
        "id": "33333333-3333-4333-a333-333333333333",
        "email": "operator@example.com",
        "full_name": "Operator User",
        "role": "operator",
        "is_active": True,
    }


@pytest.fixture
def sample_agent_data(sample_user_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "44444444-4444-4444-a444-444444444444",
        "name": "Sample Agent",
        "system_prompt": "You are a helpful assistant.",
        "model": "gpt-4o",
        "owner_id": sample_user_data["id"],
        "status": "active",
    }


@pytest.fixture
def sample_agent_create_request(sample_user_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "New Agent",
        "system_prompt": "You are an AI.",
        "model": "gpt-4o",
        "owner_id": sample_user_data["id"],
    }

