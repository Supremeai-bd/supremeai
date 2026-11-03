"""
Scraper route guard tests (production-readiness plan, item 1).

নিশ্চিত করে:
- /api/v1/scrape|browse|recipe — auth ছাড়া 401
- non-admin (regular user) token দিয়ে 403
- admin token দিয়ে SSRF-সেফ URL হলে ভেতরে ঢোকে (mock scraper)
- Semaphore present — MAX_CONCURRENCY সাপোর্ট
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import scraper as scraper_routes

pytestmark = [pytest.mark.unit, pytest.mark.critical]


def _disable_test_bypass(monkeypatch):
    """বাংলা: conftest টেস্ট-এনভায়রনমেন্টে admin bypass চালু রাখে — গার্ড
    টেস্ট করতে সেই bypass বন্ধ করতে হয় (production-এ এটি hard False)।"""
    monkeypatch.setattr("api.dependencies.is_test_environment", lambda: False)


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(scraper_routes.router, prefix="/api/v1")
    return TestClient(app, raise_server_exceptions=False)


def _auth_headers(role: str = "admin", email: str = "admin@supremeai.dev") -> dict:
    from core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token({'sub': email, 'role': role})}"}


@pytest.fixture
def client() -> TestClient:
    return _make_client()


def test_scrape_without_auth_returns_401(client, monkeypatch):
    _disable_test_bypass(monkeypatch)
    resp = client.post("/api/v1/scrape", json={"url": "https://example.com"})
    assert resp.status_code == 401


def test_browse_without_auth_returns_401(client, monkeypatch):
    _disable_test_bypass(monkeypatch)
    resp = client.post("/api/v1/browse", json={"url": "https://example.com"})
    assert resp.status_code == 401


def test_recipe_without_auth_returns_401(client, monkeypatch):
    _disable_test_bypass(monkeypatch)
    resp = client.post("/api/v1/recipe", json={"steps": [], "initial_url": "https://example.com"})
    assert resp.status_code == 401


def test_health_stays_public(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_regular_user_gets_403(client):
    # বাংলা: bare app-এ AuthMiddleware নেই — তাই middleware-এর role pipeline
    # simulate করতে dependency override ব্যবহার করা হয় (get_current_admin এর
    # আসল লজিকের উপরেই চলে)।
    from api.dependencies import get_current_user_token

    client.app.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "u@x.dev",
        "role": "user",
        "tenant_id": "t",
    }
    try:
        resp = client.post("/api/v1/scrape", json={"url": "https://example.com"})
        assert resp.status_code == 403  # admin access required
    finally:
        client.app.dependency_overrides.clear()


def test_admin_can_scrape_with_mock(client):
    # বাংলা: middleware simulate — admin identity সরাসরি override
    from api.dependencies import get_current_user_token

    client.app.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "admin@supremeai.dev",
        "role": "admin",
        "tenant_id": "t",
    }
    try:
        with patch.object(
            scraper_routes._scraper, "fetch_page", return_value={"ok": True, "content": "hi"}
        ):
            resp = client.post(
                "/api/v1/scrape",
                json={"url": "https://example.com"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "content": "hi"}
    finally:
        client.app.dependency_overrides.clear()


def test_semaphore_module_present():
    # বাংলা: module-level semaphore আছে এবং MAX_CONCURRENCY মান ধারণ করে
    assert scraper_routes._scraper_semaphore is not None
    assert scraper_routes.MAX_CONCURRENCY >= 1
