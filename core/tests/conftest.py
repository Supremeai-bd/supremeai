"""Shared test fixtures for core/tests."""

from __future__ import annotations

import re
import uuid
from typing import Any

import pytest

TEST_SECRET_KEY: str = "test_secret_key_for_jwt_auth_testing_minimum_length_required"
TEST_ALGORITHM: str = "HS256"
TEST_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


class CustomAssertions:
    """Helper assertions for unit tests."""

    @staticmethod
    def assert_valid_uuid(val: Any, version: int = 4) -> None:
        val_str = str(val)
        parsed = uuid.UUID(val_str, version=version)
        assert str(parsed) == val_str

    @staticmethod
    def assert_email_format(email: str) -> None:
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
