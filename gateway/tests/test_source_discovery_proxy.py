"""Gateway research proxy — real auth path stays in force, no fabricated result."""
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from gateway.service import app as edge


def test_source_discovery_proxy_preserves_request_and_core_error(monkeypatch):
    monkeypatch.setattr(edge, "_verify_client_auth", lambda *_: True)
    forward = AsyncMock(return_value={"status": "consent_required", "results": [], "executed": False})
    monkeypatch.setattr(edge, "_forward_agent_request", forward)
    payload = {"query": "dengue research", "kind": "research", "consent": False}
    response = TestClient(edge.app).post("/v1/research/source-search", json=payload, headers={"Authorization": "Bearer fixture"})
    assert response.status_code == 200 and response.json()["executed"] is False
    assert forward.await_args.args[0:2] == ("POST", "/api/research/source-search")
    assert forward.await_args.args[2].headers["authorization"] == "Bearer fixture"
    assert forward.await_args.args[3] == payload


def test_source_discovery_proxy_does_not_forward_unauthorized(monkeypatch):
    monkeypatch.setattr(edge, "_verify_client_auth", lambda *_: False)
    forward = AsyncMock()
    monkeypatch.setattr(edge, "_forward_agent_request", forward)
    response = TestClient(edge.app).post("/v1/research/source-search", json={"query": "fixture"})
    assert response.status_code == 401
    forward.assert_not_awaited()


def test_untrusted_source_links_and_markdown_are_not_promoted_to_commands():
    from gateway.service.source_discovery_chat import render_discovery
    result = {"status": "ok", "executed": True, "source": "Fixture", "results": [
        {"title": "[click](javascript:alert(1)) <script>", "url": "https://example.com/a)b"},
        {"title": "private", "url": "https://127.0.0.1/private"},
    ]}
    text = render_discovery(result, bengali=False)
    assert "<script>" not in text and "\\[click\\]" in text
    assert "https://127.0.0.1" not in text and "https://example.com/a%29b" in text
    assert "not read the full pages" in text


def test_chat_to_core_to_source_is_real_path_with_mock_network(monkeypatch):
    """Gateway→core auth boundary→tenant policy/quota→source; কেবল network mock।"""
    import httpx
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from api.deps import get_current_user_token
    from api.routes.deep_research import router
    from core.services import source_discovery as sd
    from scout.models import CrawlPolicy
    from scout import policy as scout_policy

    core = FastAPI()
    core.include_router(router)
    core.dependency_overrides[get_current_user_token] = lambda: {"sub": "alice", "tenant_id": "tenant-a"}
    observed = []

    @core.middleware("http")
    async def ensure_forwarded_bearer(request: Request, call_next):
        observed.append(request.headers.get("authorization"))
        if observed[-1] != "Bearer fixture":
            return JSONResponse(status_code=401, content={"detail": "missing bearer"})
        return await call_next(request)

    monkeypatch.setenv("CORE_API_URL", "https://core.fixture")
    monkeypatch.setenv("SUPREMEAI_SOURCE_DISCOVERY", "true")
    monkeypatch.setenv("SUPREMEAI_TRIVIAL_FASTPATH", "0")
    monkeypatch.setattr(edge, "_verify_client_auth", lambda *_: True)
    monkeypatch.setattr(edge, "_extract_user_id", lambda *_: "alice")
    monkeypatch.setattr(edge, "_extract_registered_user_id", lambda *_: None)
    monkeypatch.setattr(edge, "compile_chat_context", lambda **kwargs: kwargs["messages"])
    monkeypatch.setattr(sd, "_load_authoritative_policy", AsyncMock(return_value=CrawlPolicy(tenant_id="tenant-a", allowed_domains=["api.crossref.org"])))
    quota = AsyncMock()
    monkeypatch.setattr(sd, "_claim_rate_slot", quota)
    monkeypatch.setattr(scout_policy, "is_safe_url", lambda _: True)
    received = []
    def external(req):
        received.append(req)
        return httpx.Response(200, json={"message": {"items": [{"title": ["Vaccine paper"],
            "URL": "https://doi.org/10.1234/fixture", "abstract": "Real source excerpt fixture"}]}})
    original = httpx.AsyncClient
    def clients(**kwargs):
        if kwargs.get("timeout") == 12.0:
            return original(transport=httpx.ASGITransport(app=core), **kwargs)
        return original(transport=httpx.MockTransport(external), **kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", clients)
    response = TestClient(edge.app).post("/v1/chat/completions", headers={"Authorization": "Bearer fixture"},
        json={"model": "supreme-spark", "messages": [{"role": "user", "content": "ডেঙ্গু গবেষণা"}],
              "source_search": {"query": "dengue vaccine", "kind": "research", "consent": True}})
    assert response.status_code == 200, response.text
    content = response.json()["choices"][0]["message"]["content"]
    assert "Vaccine paper" in content and "Real source excerpt fixture" in content
    assert "https://doi.org/10.1234/fixture" in content and "স্বাধীনভাবে যাচাই করিনি" in content
    assert observed == ["Bearer fixture"]
    assert received[0].url.host == "api.crossref.org" and received[0].url.params["query.bibliographic"] == "dengue vaccine"
    assert "alice" not in str(received[0].url)
    quota.assert_awaited_once()
    before = len(received)
    consent_body = {"model": "supreme-spark", "messages": [{"role": "user", "content": "ডেঙ্গু গবেষণা"}],
                    "source_search": {"query": "dengue vaccine", "kind": "research", "consent": False}}
    planned = TestClient(edge.app).post("/v1/chat/completions", headers={"Authorization": "Bearer fixture"}, json=consent_body)
    assert planned.status_code == 200 and planned.json()["source_search"]["executed"] is False
    assert "সংরক্ষণ" in planned.json()["choices"][0]["message"]["content"]
    assert len(received) == before and quota.await_count == 1
