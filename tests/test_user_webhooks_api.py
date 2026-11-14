"""Tests for user outbound webhooks API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.webhooks_outbound import router, _WEBHOOKS


@pytest.fixture(autouse=True)
def _reset():
    _WEBHOOKS.clear()
    yield
    _WEBHOOKS.clear()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_list_empty(client):
    resp = client.get("/api/user/webhooks")
    assert resp.status_code == 200
    assert resp.json()["webhooks"] == []


def test_create_and_list(client):
    resp = client.post("/api/user/webhooks", json={"url": "https://example.com/hook", "events": ["push"]})
    assert resp.status_code == 201
    data = resp.json()
    assert "webhook" in data
    wh = data["webhook"]
    assert wh["url"] == "https://example.com/hook"
    assert wh["events"] == ["push"]
    wid = wh["id"]

    lst = client.get("/api/user/webhooks").json()["webhooks"]
    assert any(w["id"] == wid for w in lst)


def test_create_defaults(client):
    resp = client.post("/api/user/webhooks", json={"url": "https://example.com/x"})
    assert resp.status_code == 201
    wh = resp.json()["webhook"]
    assert wh["events"] == ["*"]


def test_delete(client):
    wid = client.post("/api/user/webhooks", json={"url": "https://example.com/hook"}).json()["webhook"]["id"]
    resp = client.delete(f"/api/user/webhooks/{wid}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert client.get("/api/user/webhooks").json()["webhooks"] == []


def test_delete_not_found(client):
    resp = client.delete("/api/user/webhooks/wh_doesnotexist")
    assert resp.status_code == 404


def test_test_ping_success(client, monkeypatch):
    import api.routes.webhooks_outbound as mod

    async def fake(url):
        return {"success": True, "status_code": 200}

    monkeypatch.setattr(mod, "_test_webhook", fake)
    wid = client.post("/api/user/webhooks", json={"url": "https://example.com/hook"}).json()["webhook"]["id"]
    resp = client.post(f"/api/user/webhooks/{wid}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["status_code"] == 200


def test_test_ping_not_found(client):
    resp = client.post("/api/user/webhooks/wh_nope/test")
    assert resp.status_code == 404
