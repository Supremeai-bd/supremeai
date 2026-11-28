"""উৎস নির্বাচন ও execution নিরাপদ কি না: সম্পূর্ণ অফলাইন boundary tests।"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from core.services import source_discovery as sd
from scout.models import CrawlPolicy


@pytest.mark.parametrize(("query", "kind"), [
    ("ajker bangladesher khobor", "news"),
    ("ডেঙ্গু নিয়ে গবেষণাপত্র", "research"),
    ("Bangladesh history", "reference"),
    ("github repository fastapi", "technical"),
])
def test_plans_distinct_source_types(query, kind):
    plan = sd.plan_source(query)
    assert plan["kind"] == kind and plan["status"] == "ready"


@pytest.mark.parametrize("query", ["what is the weather today?", "price of rice", "research about the latest news", "google theke khuje dao"])
def test_unclear_or_current_queries_do_not_choose_stale_reference(query):
    assert sd.plan_source(query)["status"] == "needs_clarification"


@pytest.mark.asyncio
async def test_no_network_or_policy_read_without_explicit_consent(monkeypatch):
    policy = AsyncMock(side_effect=AssertionError("no policy read"))
    monkeypatch.setattr(sd, "_load_authoritative_policy", policy)
    outcome = await sd.discover("alice", "Bangladesh history")
    assert outcome["status"] == "consent_required" and not outcome["executed"]
    policy.assert_not_awaited()
    unknown = await sd.discover("alice", "google theke khuje dao", consent=True)
    assert unknown["status"] == "needs_clarification" and not unknown["executed"]
    policy.assert_not_awaited()


@pytest.mark.asyncio
async def test_disabled_and_missing_owner_fail_closed(monkeypatch):
    monkeypatch.delenv("SUPREMEAI_SOURCE_DISCOVERY", raising=False)
    with pytest.raises(sd.DiscoveryError, match="source_discovery_disabled"):
        await sd.discover("alice", "latest news", consent=True)
    with pytest.raises(sd.DiscoveryError, match="identity_required"):
        await sd.discover("*", "latest news", consent=True)


def _fake_client(monkeypatch, callback):
    original = httpx.AsyncClient
    monkeypatch.setattr(sd.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(callback), **kwargs))


@pytest.mark.asyncio
@pytest.mark.parametrize(("query", "kind", "host", "payload"), [
    ("Bangladesh history", "reference", "en.wikipedia.org", {"query": {"search": [{"title": "Bangladesh", "pageid": 1}]}}),
    ("research paper vaccines", "research", "api.crossref.org", {"message": {"items": [{"title": ["Study"], "URL": "https://doi.org/10.1000/test", "publisher": "Fixture"}]}}),
    ("github repository python", "technical", "api.github.com", {"items": [{"full_name": "org/repo", "html_url": "https://github.com/org/repo", "updated_at": "2026-01-01"}]}),
    ("Bangladesh news", "news", "www.bing.com", '<rss><channel><item><title>Headline</title><link>https://example.com/news</link><pubDate>Mon</pubDate><source>Fixture</source></item></channel></rss>'),
])
async def test_real_http_boundary_is_bounded_and_only_requested_query(monkeypatch, query, kind, host, payload):
    from scout import policy as scout_policy
    monkeypatch.setenv("SUPREMEAI_SOURCE_DISCOVERY", "true")
    policy = CrawlPolicy(tenant_id="alice", allowed_domains=[host], max_results=2)
    get_policy = AsyncMock(return_value=policy)
    limit = AsyncMock()
    monkeypatch.setattr(sd, "_load_authoritative_policy", get_policy)
    monkeypatch.setattr(sd, "_claim_rate_slot", limit)
    monkeypatch.setattr(scout_policy, "is_safe_url", lambda _: True)
    seen = []
    def respond(req):
        seen.append(req)
        return httpx.Response(200, content=payload if isinstance(payload, str) else json.dumps(payload))
    _fake_client(monkeypatch, respond)
    result = await sd.discover("alice", query, consent=True)
    assert result["kind"] == kind and result["executed"] and result["status"] == "ok"
    assert len(result["results"]) == 1 and "untrusted" in result["notice"]
    assert seen[0].url.host == host and seen[0].method == "GET"
    assert query in list(seen[0].url.params.values())
    assert "alice" not in str(seen[0].url)
    get_policy.assert_awaited_once_with("alice")
    limit.assert_awaited_once()


@pytest.mark.asyncio
async def test_blocked_domain_and_missing_quota_cannot_call_provider(monkeypatch):
    from scout import policy as scout_policy
    monkeypatch.setenv("SUPREMEAI_SOURCE_DISCOVERY", "true")
    monkeypatch.setattr(sd, "_load_authoritative_policy", AsyncMock(return_value=CrawlPolicy(tenant_id="alice", allowed_domains=["other.example"])))
    monkeypatch.setattr(scout_policy, "is_safe_url", lambda _: True)
    quota = AsyncMock()
    monkeypatch.setattr(sd, "_claim_rate_slot", quota)
    with pytest.raises(sd.DiscoveryError, match="source_not_allowed"):
        await sd.discover("alice", "Bangladesh news", consent=True)
    quota.assert_not_awaited()
    monkeypatch.setattr(sd, "_load_authoritative_policy", AsyncMock(return_value=CrawlPolicy(tenant_id="alice", allowed_domains=["www.bing.com"])))
    quota.side_effect = sd.DiscoveryError("rate_limit_unavailable", 503)
    _fake_client(monkeypatch, lambda _: pytest.fail("no external request"))
    with pytest.raises(sd.DiscoveryError, match="rate_limit_unavailable"):
        await sd.discover("alice", "Bangladesh news", consent=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["redirect", "bad_json", "oversized"])
async def test_bad_provider_responses_never_become_success(monkeypatch, mode):
    from scout import policy as scout_policy
    monkeypatch.setenv("SUPREMEAI_SOURCE_DISCOVERY", "true")
    monkeypatch.setattr(sd, "_load_authoritative_policy", AsyncMock(return_value=CrawlPolicy(tenant_id="alice", allowed_domains=["api.crossref.org"])))
    monkeypatch.setattr(sd, "_claim_rate_slot", AsyncMock())
    monkeypatch.setattr(scout_policy, "is_safe_url", lambda _: True)
    def respond(_):
        if mode == "redirect":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/"})
        return httpx.Response(200, content=b"x" * (sd.MAX_RESPONSE_BYTES + 1) if mode == "oversized" else b"not-json")
    _fake_client(monkeypatch, respond)
    with pytest.raises(sd.DiscoveryError):
        await sd.discover("alice", "research paper fixture", consent=True)


def test_unsafe_result_urls_never_become_citations():
    for url in ["http://example.com/", "https://user:pass@example.com/", "https://127.0.0.1/", "https://localhost/", "javascript:alert(1)"]:
        assert sd._safe_result_url(url) == ""
    assert sd._safe_result_url("https://doi.org/10.1/fixture")


def test_malformed_xml_and_entity_references_fail_closed():
    with pytest.raises(sd.DiscoveryError):
        sd._parse_results("news", b'<!DOCTYPE x [<!ENTITY x "fixture">]><rss>&x;</rss>', 3)


@pytest.mark.asyncio
async def test_query_redacted_from_httpx_request_log(monkeypatch, caplog):
    from scout import policy as scout_policy
    monkeypatch.setenv("SUPREMEAI_SOURCE_DISCOVERY", "true")
    monkeypatch.setattr(sd, "_load_authoritative_policy", AsyncMock(return_value=CrawlPolicy(tenant_id="alice", allowed_domains=["api.crossref.org"])))
    monkeypatch.setattr(sd, "_claim_rate_slot", AsyncMock())
    monkeypatch.setattr(scout_policy, "is_safe_url", lambda _: True)
    _fake_client(monkeypatch, lambda _: httpx.Response(200, json={"message": {"items": []}}))
    with caplog.at_level("INFO", logger="httpx"):
        out = await sd.discover("alice", "research paper UNIQUE_PRIVATE_QUERY", consent=True)
    assert out["status"] == "no_results"
    assert "UNIQUE_PRIVATE_QUERY" not in caplog.text
    assert "request details redacted" in caplog.text


@pytest.mark.asyncio
async def test_authoritative_policy_does_not_use_stale_memory(monkeypatch):
    from scout import persistence
    monkeypatch.setattr(persistence, "_client", lambda: None)
    monkeypatch.setitem(persistence._MEMORY_POLICIES, "alice", [{"tenant_id": "alice", "is_active": True, "allowed_domains": ["*"]}])
    with pytest.raises(sd.DiscoveryError, match="policy_store_unavailable"):
        await sd._load_authoritative_policy("alice")


@pytest.mark.asyncio
async def test_rate_quota_is_atomic_and_closed_on_unavailability(monkeypatch):
    from core.cache.redis_manager import redis_manager
    fake = SimpleNamespace(eval=AsyncMock(return_value=[1, 1]))
    monkeypatch.setattr(redis_manager, "get_client_async", AsyncMock(return_value=fake))
    await sd._claim_rate_slot("api.crossref.org", 5)
    assert fake.eval.await_args.args[1:3] == (1, "source-discovery:api.crossref.org")
    fake.eval.return_value = [0, 5]
    with pytest.raises(sd.DiscoveryError, match="source_rate_limited"):
        await sd._claim_rate_slot("api.crossref.org", 5)
    fake.eval.side_effect = RuntimeError("quota unavailable")
    with pytest.raises(sd.DiscoveryError, match="rate_limit_unavailable"):
        await sd._claim_rate_slot("api.crossref.org", 5)


@pytest.mark.asyncio
async def test_core_api_uses_authenticated_tenant_and_strict_consent(monkeypatch):
    from fastapi import FastAPI
    from api.deps import get_current_user_token
    from api.routes.deep_research import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_token] = lambda: {"sub": "alice", "tenant_id": "tenant-a"}
    discover = AsyncMock(return_value={"status": "ok", "results": [], "executed": True})
    monkeypatch.setattr(sd, "discover", discover)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/research/source-search", json={"query": "research paper", "kind": "research", "consent": True})
        assert response.status_code == 200
        discover.assert_awaited_once_with("tenant-a", "research paper", "research", True)
        assert (await client.post("/api/research/source-search", json={"query": "news", "consent": "true"})).status_code == 422
        assert (await client.post("/api/research/source-search", json={"query": "news", "consent": True, "tenant_id": "other"})).status_code == 422
    assert discover.await_count == 1
    app.dependency_overrides[get_current_user_token] = lambda: {"sub": "alice"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # This confirms the route forwards only the authenticated tenant; the
        # real service rejects an empty tenant (tested separately).
        await client.post("/api/research/source-search", json={"query": "news", "consent": False})
    assert discover.await_args.args[0] == ""


def test_excerpt_is_plain_text_and_drops_embedded_scripts():
    body = json.dumps({"query": {"search": [{"title": "fixture", "pageid": 12,
                "snippet": 'hello <b>world</b><script>private-instruction</script>'}]}}).encode()
    result = sd._parse_results("reference", body, 5)
    assert result[0]["snippet"] == "hello world"
    assert "private-instruction" not in result[0]["snippet"]


@pytest.mark.asyncio
async def test_authoritative_policy_query_scopes_tenant_and_checks_returned_row(monkeypatch):
    from scout import persistence
    from unittest.mock import MagicMock
    table = MagicMock()
    for name in ("select", "eq", "order", "limit"):
        getattr(table, name).return_value = table
    db = MagicMock()
    db.table.return_value = table
    monkeypatch.setattr(persistence, "_client", lambda: db)
    table.execute.return_value = SimpleNamespace(data=[{"tenant_id": "tenant-a", "is_active": True, "allowed_domains": ["api.crossref.org"]}])
    assert (await sd._load_authoritative_policy("tenant-a")).tenant_id == "tenant-a"
    db.table.assert_called_with("crawl_policies")
    assert table.eq.call_args_list[0].args == ("tenant_id", "tenant-a")
    assert table.eq.call_args_list[1].args == ("is_active", True)
    for row in [{"tenant_id": "tenant-b", "is_active": True},
                {"tenant_id": "tenant-a", "is_active": False},
                {"tenant_id": "tenant-a"},
                {"tenant_id": "tenant-a", "is_active": "true"}]:
        table.execute.return_value = SimpleNamespace(data=[row])
        with pytest.raises(sd.DiscoveryError, match="policy_not_configured"):
            await sd._load_authoritative_policy("tenant-a")
    table.execute.return_value = SimpleNamespace(data=None)
    with pytest.raises(sd.DiscoveryError, match="policy_store_unavailable"):
        await sd._load_authoritative_policy("tenant-a")
