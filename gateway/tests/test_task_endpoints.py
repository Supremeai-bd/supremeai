from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

from core.app import app

client = TestClient(app)


@pytest.fixture
def mock_dependencies():
    import core.services as services_mod
    from core import services

    previous_admin = services.admin_god
    previous_router = services_mod.model_router
    previous_intent = services.intent_clf

    fake_admin = MagicMock()
    fake_admin.enforce.return_value = None
    fake_router = MagicMock()
    fake_router.async_route_and_generate = AsyncMock(
        return_value={
            "success": True,
            "text": "def hello():\n    pass",
            "provider": "test",
            "cost": 0.001,
        }
    )
    fake_intent = MagicMock()
    fake_intent.classify.return_value = MagicMock(task_type="general", confidence=1.0)

    services.admin_god = fake_admin
    services_mod.model_router = fake_router
    services.intent_clf = fake_intent

    def resolve():
        services.admin_god = previous_admin
        services_mod.model_router = previous_router
        services.intent_clf = previous_intent

    return resolve


@pytest.fixture
def valid_auth_headers(monkeypatch):
    """Exercise JWT verification without real revocation-service I/O."""
    import core.security
    from core.config import settings
    from core.security import JWT_AUDIENCE, JWT_ISSUER

    monkeypatch.setenv("SUPREMEAI_JWT_SECRET", "local-task-contract-test-secret-" * 3)
    monkeypatch.setattr(core.security, "is_token_revoked", AsyncMock(return_value=False))
    token = jwt.encode(
        {"sub": "task-test-user", "role": "viewer", "tenant_id": "task-test-tenant",
         "jti": "task-contract-jti", "iss": JWT_ISSUER, "aud": JWT_AUDIENCE,
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.jwt_secret, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_session():
    import core.services as services_mod
    from core import services

    previous_admin = services.admin_god
    previous_router = services_mod.model_router
    previous_intent = services.intent_clf

    fake_admin = MagicMock()
    fake_admin.enforce.return_value = None
    fake_router = MagicMock()
    fake_router.async_route_and_generate = AsyncMock(
        return_value={
            "success": True,
            "text": "def hello():\n    pass",
            "provider": "test",
            "cost": 0.001,
        }
    )
    fake_intent = MagicMock()
    fake_intent.classify.return_value = MagicMock(task_type="general", confidence=1.0)

    services.admin_god = fake_admin
    services_mod.model_router = fake_router
    services.intent_clf = fake_intent

    try:
        yield
    finally:
        services.admin_god = previous_admin
        services_mod.model_router = previous_router
        services.intent_clf = previous_intent


def test_task_execute_returns_200(mock_session, valid_auth_headers):
    response = client.post(
        "/task/execute",
        json={"task": "write hello world", "task_type": "general"},
        headers=valid_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "provider" in data


def test_task_execute_with_messages(mock_session, valid_auth_headers):
    payload = {
        "task": "continue the code",
        "task_type": "general",
        "messages": [
            {"role": "user", "content": "start"},
            {"role": "assistant", "content": "here is code"},
        ],
    }
    response = client.post(
        "/task/execute",
        json=payload,
        headers=valid_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_task_execute_with_session_id(mock_session, valid_auth_headers):
    response = client.post(
        "/task/execute",
        json={"task": "test", "task_type": "general", "session_id": "sess-123"},
        headers=valid_auth_headers,
    )
    assert response.status_code == 200


def test_task_execute_upstream_failure(mock_session, valid_auth_headers):
    import core.services as services_mod

    previous_router = services_mod.model_router
    fake_router = MagicMock()
    fake_router.async_route_and_generate = AsyncMock(
        return_value={
            "success": False,
            "error": "upstream timeout",
            "provider": "test",
            "cost": 0.0,
        }
    )
    services_mod.model_router = fake_router

    try:
        response = client.post(
            "/task/execute",
            json={"task": "test", "task_type": "general"},
            headers=valid_auth_headers,
        )
        assert response.status_code == 502
    finally:
        services_mod.model_router = previous_router


def test_chat_completion_streaming(valid_auth_headers):
    import core.services as services_mod

    previous_router = services_mod.model_router
    fake_router = MagicMock()

    async def fake_stream(*args, **kwargs):
        for token in ["def", " hello()", ":", "\n", "    pass"]:
            yield token.encode()

    fake_router.async_route_and_stream = fake_stream
    services_mod.model_router = fake_router

    try:
        response = client.post(
            "/api/chat/stream",
            json={"message": "write hello", "sessionId": "s-1"},
            headers=valid_auth_headers,
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
    finally:
        services_mod.model_router = previous_router
