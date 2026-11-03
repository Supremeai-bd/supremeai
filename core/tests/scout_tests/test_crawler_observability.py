"""Unit tests for Crawler Observability, Telemetry, and Admin API endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routes.crawler_admin import router
from scout.models import CrawlEventType
from scout.telemetry import CrawlerTelemetry

app = FastAPI()
app.include_router(router)


def test_crawler_telemetry_emit() -> None:
    telemetry = CrawlerTelemetry(tenant_id="tenant-123", task_id="task-abc")
    # Emit info and error events - verify no exception is raised
    telemetry.emit_event(
        CrawlEventType.NAV_START, "Navigating to test site", metadata={"url": "https://example.com"}
    )
    telemetry.emit_event(
        CrawlEventType.ERROR, "Encountered 500 error", severity="ERROR", metadata={"status": 500}
    )


@pytest.mark.asyncio
async def test_crawler_admin_api_policy_crud() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Get default policies
        resp = await client.get("/api/v1/admin/crawler/policies?tenant_id=tenant-test")
        assert resp.status_code == 200
        policies = resp.json()
        assert len(policies) >= 1

        # 2. Create custom policy
        create_payload = {
            "name": "Custom Restricted Policy",
            "is_active": True,
            "max_depth": 3,
            "max_results": 15,
            "default_rate_limit_per_min": 45,
            "allowed_domains": ["example.org"],
            "domain_rules": [
                {
                    "domain": "example.org",
                    "trust_level": "trusted",
                    "rate_limit_per_min": 60,
                    "render_js": False,
                }
            ],
        }
        create_resp = await client.post(
            "/api/v1/admin/crawler/policies?tenant_id=tenant-test", json=create_payload
        )
        assert create_resp.status_code == 201
        new_pol = create_resp.json()
        assert new_pol["name"] == "Custom Restricted Policy"
        assert new_pol["max_depth"] == 3


@pytest.mark.asyncio
async def test_crawler_admin_api_history_and_events() -> None:
    """Phase 1 update: /events আর hardcoded placeholder নয় — সত্যিকারের telemetry।

    আগে এই টেস্ট স্টাবের ভুয়া আচরণ দাবি করত (ফিল্টার যা-ই হোক, ঠিক ১টা
    hardcoded item ফেরত যেত) — অর্থাৎ 'dead inside but looks alive'। এখন চুক্তি:
    রেকর্ড করা event-ই শুধু ফেরত যায়; কিছু না থাকলে খালি তালিকা (সত্য)।
    """
    from scout import persistence

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Query history (durable store; empty হলেও সেটাই সত্য)
        hist_resp = await client.get("/api/v1/admin/crawler/history?tenant_id=tenant-test")
        assert hist_resp.status_code == 200
        assert isinstance(hist_resp.json(), list)

        # বাংলা: events এখন tenant-scoped — bypass admin-এর আসল tenant policies
        # এন্ডপয়েন্ট থেকে বের করে সেই টেন্যান্টে event রেকর্ড করা হলো
        pol_resp = await client.get("/api/v1/admin/crawler/policies")
        assert pol_resp.status_code == 200
        tenant = pol_resp.json()[0]["tenant_id"] if pol_resp.json() else "tenant-test"

        # Record a real event, then query it back through the admin surface
        marker_task = "task-observability-1"
        await persistence.record_event(
            tenant,
            marker_task,
            CrawlEventType.NAV_COMPLETE,
            "test event: navigation completed",
            metadata={"url": "https://example.com"},
        )
        events_resp = await client.get(f"/api/v1/admin/crawler/events?task_id={marker_task}")
        assert events_resp.status_code == 200
        events = events_resp.json()
        assert len(events) == 1
        assert events[0]["task_id"] == marker_task
        assert events[0]["event_type"] == CrawlEventType.NAV_COMPLETE

        # event_type ফিল্টারও সত্যিকারের ডেটায় কাজ করে
        filtered = await client.get(
            f"/api/v1/admin/crawler/events?task_id={marker_task}&event_type=error"
        )
        assert filtered.status_code == 200
        assert all(e["event_type"] == "error" for e in filtered.json())
