from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.routes import scraper
from core.service_registry import get_service_registry


def test_registry_contains_all_runtime_capabilities():
    services = {service.id: service for service in get_service_registry()}
    assert {"core-api", "async-worker", "scraper", "mcp-control-plane"} <= services.keys()
    assert "browser.scrape" in services["scraper"].capabilities
    assert "tasks.submit" in services["async-worker"].capabilities


from fastapi import FastAPI

test_app = FastAPI()
test_app.include_router(scraper.router)


def test_scraper_rejects_private_urls():
    client = TestClient(test_app)
    response = client.post("/scrape", json={"url": "http://127.0.0.1:8080/admin"})
    assert response.status_code == 400
    assert "SSRF" in response.json()["detail"]


def test_scraper_rejects_private_browser_urls():
    client = TestClient(test_app)
    response = client.post("/browse", json={"url": "http://localhost:8080"})
    assert response.status_code == 400
    assert "SSRF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_scraper_browse_validates_before_agent_call():
    with patch.object(scraper._agent, "navigate_and_interact", new_callable=AsyncMock) as navigate:
        client = TestClient(test_app)
        response = client.post("/browse", json={"url": "http://127.0.0.1"})
        assert response.status_code == 400
        navigate.assert_not_awaited()
