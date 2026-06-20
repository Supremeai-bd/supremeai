from __future__ import annotations

import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.app import app as base_app


@pytest.fixture()
def stream_app() -> FastAPI:
    os.environ["SUPREMEAI_API_TOKEN"] = "test-token"
    return base_app


def test_stream_endpoint_requires_auth(stream_app: FastAPI):
    client = TestClient(stream_app)
    resp = client.post("/api/stream/chat", json={"prompt": "hi", "task_type": "general"})
    assert resp.status_code == 401
    os.environ.pop("SUPREMEAI_API_TOKEN", None)


def test_stream_endpoint_with_token(stream_app: FastAPI):
    client = TestClient(stream_app)
    resp = client.post(
        "/api/stream/chat",
        json={"prompt": "hi", "task_type": "general"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    os.environ.pop("SUPREMEAI_API_TOKEN", None)

