from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from core.auth_middleware import AuthMiddleware
from core.rate_limiter import RateLimiter


def test_rate_limiter_functional():
    limiter = RateLimiter(requests_per_minute=2, burst=2)
    assert limiter.is_allowed("client1") is True
    assert limiter.is_allowed("client1") is True
    assert limiter.is_allowed("client1") is False
    assert limiter.remaining("client1") == 0


def test_auth_middleware_allows_health_without_token():
    app = FastAPI()

    @app.get("/health")
    def health():
        return PlainTextResponse("ok")

    app.add_middleware(AuthMiddleware)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_auth_middleware_blocks_protected_route_without_token():
    os.environ["SUPREMEAI_API_TOKEN"] = "test-token"
    app = FastAPI()

    @app.get("/api/task/execute")
    def task():
        return PlainTextResponse("ok")

    app.add_middleware(AuthMiddleware)
    client = TestClient(app)
    resp = client.get("/api/task/execute")
    assert resp.status_code == 401
    del os.environ["SUPREMEAI_API_TOKEN"]


def test_auth_middleware_allows_with_valid_token():
    import os
    os.environ["SUPREMEAI_API_TOKEN"] = "test-token"
    app = FastAPI()

    @app.get("/api/task/execute")
    def task():
        return PlainTextResponse("ok")

    app.add_middleware(AuthMiddleware)
    client = TestClient(app)
    resp = client.get("/api/task/execute", headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 200
    del os.environ["SUPREMEAI_API_TOKEN"]
