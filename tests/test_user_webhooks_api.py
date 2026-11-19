"""The retired Core webhook surface neither advertises nor performs delivery."""

from unittest.mock import Mock

import httpx
import pytest
from api.routes.webhooks_outbound import get_current_user_token, router
from fastapi import FastAPI
from fastapi.testclient import TestClient

API = "/api/user/webhooks"


@pytest.fixture
def app():
    api = FastAPI()
    api.include_router(router)
    return api


def test_outbound_webhooks_require_auth(app):
    assert TestClient(app).get(API).status_code == 401


@pytest.mark.parametrize(
    "method,suffix", [("GET", ""), ("POST", ""), ("DELETE", "/wh_fixture"), ("POST", "/wh_fixture/test")]
)
def test_outbound_management_and_test_fail_closed(app, monkeypatch, method, suffix):
    outbound = Mock(side_effect=AssertionError("no webhook egress is supported"))
    monkeypatch.setattr(httpx, "AsyncClient", outbound)
    app.dependency_overrides[get_current_user_token] = lambda: {"sub": "fixture-user"}
    response = TestClient(app).request(method, API + suffix, json={"url": "https://example.invalid/fixture"})
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]
    outbound.assert_not_called()


def test_outbound_webhooks_are_not_advertised_in_openapi(app):
    assert all(not path.startswith(API) for path in app.openapi()["paths"])
