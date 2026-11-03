from __future__ import annotations

import base64
import hashlib
import hmac
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from httpx import ASGITransport, AsyncClient

from api.routes.integrations import _sign_oauth_state, _verify_oauth_state, router
from core.config import settings


@pytest.mark.asyncio
async def test_oauth_state_signing_and_verification():
    """Verify that HMAC signed OAuth state correctly validates and rejects tampering/expiry."""
    user_id = "test-user-uuid-123"
    future_time = int(time.time()) + 600

    # 1. Valid state generated
    state = _sign_oauth_state(user_id, future_time)
    assert _verify_oauth_state(state, user_id) is True

    # 2. Reject state for different user (cross-tenant / CSRF planting attempt)
    assert _verify_oauth_state(state, "attacker-user-uuid-999") is False

    # 3. Reject expired state
    past_time = int(time.time()) - 10
    expired_state = _sign_oauth_state(user_id, past_time)
    assert _verify_oauth_state(expired_state, user_id) is False

    # 4. Reject tampered state payload
    tampered_raw = f"{user_id}|{future_time}|badsignature1234567890123456"
    tampered_state = base64.urlsafe_b64encode(tampered_raw.encode()).decode()
    assert _verify_oauth_state(tampered_state, user_id) is False

    # 5. Reject malformed base64
    assert _verify_oauth_state("not-a-valid-base64-string", user_id) is False


@pytest.mark.asyncio
async def test_github_oauth_callback_rejects_missing_or_invalid_state():
    """Verify that /integrations/github/callback rejects calls with invalid or missing CSRF state."""
    app = FastAPI()
    app.include_router(router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Mock user token payload
        with patch(
            "api.routes.integrations.get_current_user_token", return_value={"sub": "user-456"}
        ):
            # Attempt callback with empty state
            response = await client.get("/integrations/github/callback?code=mock_code")
            assert response.status_code == 307
            redirect_url = response.headers.get("location", "")
            assert "status=error" in redirect_url
            assert (
                "Invalid+or+expired+state" in redirect_url
                or "Invalid%20or%20expired%20state" in redirect_url
            )

            # Attempt callback with forged state
            response = await client.get(
                "/integrations/github/callback?code=mock_code&state=forged_state"
            )
            assert response.status_code == 307
            redirect_url = response.headers.get("location", "")
            assert "status=error" in redirect_url
            assert (
                "Invalid+or+expired+state" in redirect_url
                or "Invalid%20or%20expired%20state" in redirect_url
            )
