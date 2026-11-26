"""Health-probe log-skip contract (evolution_logs bloat root-cause fix).

বাংলা: প্রোড ডেটায় (২০২৬-১১-২৬) evolution_logs-এর ৪৭,১৬১ সারির ৯৬.৭%-ই ছিল
"GET /health/live - 200" প্রোব। এই টেস্ট লক করে যে —
  ১. সফল হেলথ-প্রোব evolution_logs / PostHog-এ লেখা হবে না (শুধু Prometheus),
  ২. ব্যর্থ প্রোব (>=400) ও সাধারণ API রিকোয়েস্ট আগের মতোই লগ হবে,
  ৩. HEAD /health/live এখন 200 দেয় (আগে 405)।
"""

from __future__ import annotations

import pytest
from core.observability import observability_middleware as om
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("path", "status", "expected"),
    [
        ("/health/live", 200, False),
        ("/health/live/", 200, False),
        ("/health/live?probe=render", 200, False),
        ("/health", 200, False),
        ("/healthz", 204, False),
        ("/health/ready", 200, False),
        ("/api/v1/health/live", 200, False),
        ("/api/v1/health/ready", 200, False),
        # বাংলা মন্তব্য: ব্যর্থ প্রোব = আউটেজ সিগন্যাল, তাই অবশ্যই লগ হবে
        ("/health/live", 503, True),
        ("/health/ready", 500, True),
        ("/health/live", 405, True),
        # বাংলা মন্তব্য: সাধারণ রুট ও কাছাকাছি নামের রুট স্কিপ হবে না
        ("/api/v1/models", 200, True),
        ("/health/release", 200, True),
        ("/healthcheck-report", 200, True),
        ("/", 200, True),
        ("", 200, True),
    ],
)
def test_should_persist_request_log(path: str, status: int, expected: bool) -> None:
    assert om.should_persist_request_log(path, status) is expected


class _FakeDb:
    def __init__(self) -> None:
        self.client = object()
        self.entries: list[dict] = []

    def append_evolution_log(self, entry: dict) -> None:
        self.entries.append(entry)


class _FakePosthog:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def capture(self, **kwargs) -> None:
        self.events.append(kwargs)


@pytest.fixture
def wired(monkeypatch):
    import sys
    import types

    import core.database.supabase_client as supabase_client

    fake_db = _FakeDb()
    fake_ph = _FakePosthog()
    monkeypatch.setattr(supabase_client, "db", fake_db)
    # বাংলা মন্তব্য: posthog SDK ঐচ্ছিক ডিপেন্ডেন্সি — আসল মডিউল import না করে ফেক মডিউল বসানো
    fake_posthog_module = types.ModuleType("core.observability.posthog_client")
    fake_posthog_module.posthog_client = fake_ph
    monkeypatch.setitem(sys.modules, "core.observability.posthog_client", fake_posthog_module)
    # বাংলা মন্তব্য: Redis স্যাম্পলিং বন্ধ — টেস্টে নেটওয়ার্ক কল নয়
    monkeypatch.setenv("REDIS_TRAFFIC_METRICS_SAMPLING_RATE", "0")

    app = FastAPI()

    @app.get("/health/live")
    async def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready():
        return JSONResponse({"status": "down"}, status_code=503)

    @app.get("/api/v1/models")
    async def models():
        return {"models": []}

    app.add_middleware(om.ObservabilityMiddleware)
    return TestClient(app), fake_db, fake_ph


def test_successful_probe_is_metrics_only(wired) -> None:
    client, fake_db, fake_ph = wired
    for _ in range(5):
        assert client.get("/health/live").status_code == 200
    assert fake_db.entries == []
    assert fake_ph.events == []


def test_failed_probe_and_api_requests_are_still_logged(wired) -> None:
    client, fake_db, fake_ph = wired
    assert client.get("/health/ready").status_code == 503
    assert client.get("/api/v1/models").status_code == 200
    descriptions = [e["description"] for e in fake_db.entries]
    assert descriptions == ["GET /health/ready - 503", "GET /api/v1/models - 200"]
    assert len(fake_ph.events) == 2


def test_liveness_accepts_head() -> None:
    from core.health_routes import router as health_router

    app = FastAPI()
    app.include_router(health_router, prefix="/health")
    client = TestClient(app)
    assert client.head("/health/live").status_code == 200
    assert client.get("/health/live").status_code == 200
