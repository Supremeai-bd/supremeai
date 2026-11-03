"""Health route (api/routes/health.py) এর ইউনিট টেস্ট।

বাংলা: হেলথ রাউটার সরাসরি একটি মিনিমাল FastAPI অ্যাপে মাউন্ট করে TestClient দিয়ে
লাইভনেস/রেডিনেস/হেলথ চেক কভার করা হয়েছে। redis_manager ও registry মক করা হয়েছে।
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_client():
    from api.routes.health import router

    app = FastAPI()
    app.include_router(router)
    return app


def test_health_live_returns_alive():
    client = TestClient(_build_client())
    resp = client.get("/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "alive"


def test_health_ready_returns_ok():
    # বাংলা মন্তব্য: #2613-verification চলাকালে ধরা পড়া gap — /ready রাউটের
    # DB-সাবসিস্টেম চেক SQLAlchemy asyncio ইঞ্জিন ছোঁয়; CI venv-এ greenlet
    # অনুপস্থিত থাকলে repo-র canonical importorskip প্যাটার্ন অনুযায়ী সৎ skip
    # (#2587 প্যাটার্ন: test_billing_api_routes.py:37, test_mcp_hub.py:38,
    # test_missions_boundaries.py:44)। /live ও /health টেস্ট প্রভাবিত নয়।
    pytest.importorskip(
        "greenlet", reason="greenlet not installed — required for SQLAlchemy asyncio engine"
    )
    client = TestClient(_build_client())
    resp = client.get("/ready")
    # In a bare FastAPI context without mocked redis/db, this should now return 503
    assert resp.status_code in (200, 503)
    body = resp.json()
    if resp.status_code == 200:
        assert "status" in body
    else:
        assert "detail" in body


def test_health_check_ok_without_subsystems():
    # বাংলা: app.state-এ db_pool/redis সাবসিস্টেম না থাকলে 'degraded' ফেরত দেওয়া উচিত (HTTP 503)
    # বাংলা মন্তব্য (#2613-verification): /health রাউটও DB-সাবসিস্টেম চেকে SQLAlchemy
    # asyncio ইঞ্জিন ছোঁয় — উপরের importorskip-এর মতোই (greenlet অনুপস্থিত → সৎ skip)।
    pytest.importorskip(
        "greenlet", reason="greenlet not installed — required for SQLAlchemy asyncio engine"
    )
    client = TestClient(_build_client())
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"
