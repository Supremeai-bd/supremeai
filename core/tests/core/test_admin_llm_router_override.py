"""Model-router override: status must not consume the budget, clear works, input is validated."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _reset_override():
    import core.llm.llm_gateway.routing as routing

    routing.clear_runtime_override()
    yield
    routing.clear_runtime_override()


def _router():
    from core.llm.llm_gateway.routing import RoutingMixin

    class _Router(RoutingMixin):
        pass

    router = _Router()
    router.routing_policy = {"complexity_rules": {"easy": ["groq/g-easy"]}, "fallback_chain": []}
    return router


def test_preview_chain_does_not_consume_override_budget():
    import core.llm.llm_gateway.routing as routing

    routing.set_runtime_override("groq", "groq/g-fast", remaining_requests=2, set_by="ops@x.com")
    router = _router()

    for _ in range(5):
        assert router._build_call_chain(None, None, "chat", consume=False)[0] == "groq/g-fast"
    state = routing.get_runtime_override()
    assert state["remaining_requests"] == 2
    assert state["set_by"] == "ops@x.com" and state["set_at"]

    router._build_call_chain(None, None, "chat")
    assert routing.get_runtime_override()["remaining_requests"] == 1


def test_clear_resets_every_field():
    import core.llm.llm_gateway.routing as routing

    routing.set_runtime_override("groq", "groq/g-fast", set_by="ops@x.com")
    routing.clear_runtime_override()
    assert routing.get_runtime_override() == {
        "provider": None,
        "model": None,
        "remaining_requests": 0,
        "set_by": None,
        "set_at": None,
    }


@pytest.fixture
def client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import core.llm.llm_gateway as gateway_pkg
    import core.llm.provider_router as provider_router
    from api.dependencies import get_current_admin
    from api.routes.admin_llm import router

    monkeypatch.setattr(gateway_pkg, "get_llm_gateway", lambda: _router())
    monkeypatch.setattr(
        provider_router,
        "router_instance",
        SimpleNamespace(stats={"groq": object(), "gemini": object()}),
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_admin] = lambda: {
        "sub": "uid-1",
        "email": "ops@x.com",
        "role": "admin",
    }
    with TestClient(app) as c:
        yield c


def test_status_endpoint_is_read_only(client):
    import core.llm.llm_gateway.routing as routing

    routing.set_runtime_override("groq", "groq/g-fast", remaining_requests=3)
    for _ in range(3):
        body = client.get("/api/admin/llm/router").json()
    assert body["current_override"]["provider"] == "groq"
    assert body["override_remaining_requests"] == 3


def test_set_validates_provider_and_model_and_records_actor(client):
    import core.llm.llm_gateway.routing as routing

    assert (
        client.post("/api/admin/llm/router/override", json={"provider": "nope"}).status_code == 400
    )
    assert (
        client.post(
            "/api/admin/llm/router/override", json={"provider": "groq", "model": "gemini/x"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/admin/llm/router/override", json={"provider": "groq", "remaining_requests": -1}
        ).status_code
        == 422
    )

    ok = client.post(
        "/api/admin/llm/router/override",
        json={"provider": "groq", "model": "groq/g-fast", "remaining_requests": 10},
    )
    assert ok.status_code == 200
    state = routing.get_runtime_override()
    assert state["provider"] == "groq" and state["set_by"] == "ops@x.com"


def test_delete_turns_override_off(client):
    import core.llm.llm_gateway.routing as routing

    routing.set_runtime_override("groq", "groq/g-fast")
    res = client.delete("/api/admin/llm/router/override")
    assert res.status_code == 200 and res.json()["cleared"] is True
    assert routing.get_runtime_override()["provider"] is None
    assert client.delete("/api/admin/llm/router/override").json()["cleared"] is False
