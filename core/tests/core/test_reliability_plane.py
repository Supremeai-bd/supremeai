from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.failure_fingerprint import make_fingerprint
from core.reliability_controller import ReliabilityController
from core.request_context import RequestContextMiddleware, get_correlation_id
from core.retry_budget import RetryBudget
from core.startup_validator import StartupValidator


def test_failure_fingerprint():
    # বাংলা মন্তব্য: একই ধরনের এক্সেপশনের জন্য ফিঙ্গারপ্রিন্ট যেন একই আসে তা নিশ্চিত করা।
    exc1 = ValueError("test error message")
    exc2 = ValueError("test error message")
    try:
        raise exc1
    except ValueError as e1:
        fp1 = make_fingerprint(e1)

    try:
        raise exc2
    except ValueError as e2:
        fp2 = make_fingerprint(e2)

    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex digest length


@pytest.mark.anyio
async def test_retry_budget():
    # বাংলা মন্তব্য: রিট্রাই বাজেটের কনসাম্পশন লিমিট চেক।
    budget = RetryBudget(max_tokens=3, refill_rate_per_sec=0.1)
    assert await budget.consume() is True
    assert await budget.consume() is True
    assert await budget.consume() is True
    # ফোর্থ বার রিট্রাই ব্লক হওয়া উচিত
    assert await budget.consume() is False


@pytest.mark.anyio
async def test_startup_validator():
    await StartupValidator.validate()
    status = StartupValidator.last_status()
    assert status["validated"] is True
    assert status["success"] is True


def test_request_context_middleware():
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test-context")
    def read_context():
        # বাংলা মন্তব্য: রিকোয়েস্ট ফ্লোর ভেতরে কোরিলেশন আইডি জেনারেট হওয়ার প্রমাণ।
        corr_id = get_correlation_id()
        assert corr_id != ""
        return {"correlation_id": corr_id}

    client = TestClient(app)
    response = client.get("/test-context")
    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers
    assert response.json()["correlation_id"] == response.headers["X-Correlation-ID"]


@pytest.mark.anyio
async def test_reliability_controller():
    # বাংলা মন্তব্য: রিকভারি কন্ট্রোলারের এরর কাউন্ট ট্র্যাকিং।
    ReliabilityController._failures.clear()
    ReliabilityController._health_score = 100.0

    exc = RuntimeError("unexpected database timeout")
    failure = await ReliabilityController.register_failure(None, exc)

    assert failure.correlation_id != ""
    assert failure.fingerprint != ""

    health = ReliabilityController.health()
    assert health["failures_tracked"] == 1
    assert health["health_score"] == 99.0
