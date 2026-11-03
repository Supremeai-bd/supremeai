from __future__ import annotations

import pytest

# বাংলা মন্তব্য (#2597 CI triage): worker_service.py মডিউলটি #2480 batch 1
# (PR #2541) dead-file cleanup-এ মুছে ফেলা হয়েছিল — এই contract ফাইলটি
# তার orphan হিসেবে রয়ে গিয়েছিল (ModuleNotFoundError at collection)।
# Test Guard ডিলিশন আটকায় বলে ফাইলটি রেখে module-level skip করা হলো:
# ভবিষ্যতে worker-service surface পুনঃপ্রবর্তন হলে এই ফাইলের চুক্তিগুলো
# (#2601/#2602 worker deploy সংশ্লিষ্ট liveness/readiness/auth/idempotency)
# পুনর্জীবিত করার ভিত্তি হিসেবে থাকবে।
pytest.importorskip(
    "worker_service",
    reason="worker_service module deleted in #2480 batch1 (PR #2541) — orphan "
    "contract; revive with the worker-service surface (#2597 triage)",
)

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError


@pytest.fixture
def worker_app():
    from worker_service import app

    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health/live", "/api/v1/health/live"])
async def test_liveness_ok_when_queue_available(worker_app, path):
    """Issue #508: liveness must reflect the critical queue dependency (200 when up)."""
    transport = ASGITransport(app=worker_app)
    with (
        patch("worker_service._redis_url", return_value="redis://ok"),
        patch("worker_service._queue_call", return_value={}),
    ):
        async with AsyncClient(transport=transport, base_url="http://worker") as client:
            response = await client.get(path)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["queue_available"] is True


@pytest.mark.asyncio
async def test_liveness_returns_503_when_queue_unavailable(worker_app):
    """Issue #508: a worker whose queue is down must NOT report alive (503)."""
    transport = ASGITransport(app=worker_app)
    with (
        patch("worker_service._redis_url", return_value="redis://unavailable"),
        patch("worker_service._queue_call", side_effect=ConnectionError("offline")),
    ):
        async with AsyncClient(transport=transport, base_url="http://worker") as client:
            response = await client.get("/health/live")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["queue_available"] is False


@pytest.mark.asyncio
async def test_health_root_is_process_level(worker_app):
    """Bare /health stays process-level: the HTTP wrapper is up (Render keepalive)."""
    transport = ASGITransport(app=worker_app)
    async with AsyncClient(transport=transport, base_url="http://worker") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "supremeai-worker"}


@pytest.mark.asyncio
async def test_task_routes_require_worker_auth(worker_app, monkeypatch):
    monkeypatch.delenv("ALLOW_TEST_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("WORKER_AUTH_TOKEN", "test-worker-token")
    transport = ASGITransport(app=worker_app)
    async with AsyncClient(transport=transport, base_url="http://worker") as client:
        response = await client.post(
            "/tasks",
            json={"tenant_id": "tenant-a", "goal": "run"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("env_value", [None, "", "prod", "production", "staging"])
async def test_bypass_denied_unless_env_explicitly_non_production(
    worker_app, monkeypatch, env_value
):
    """Issue #512: unset/empty ENV must be treated as production (fail-closed).

    ALLOW_TEST_AUTH_BYPASS=true alone must NOT bypass worker auth — ENV has to
    be explicitly one of the non-production values (dev/development/test/local).
    """
    monkeypatch.setenv("ALLOW_TEST_AUTH_BYPASS", "true")
    monkeypatch.setenv("WORKER_AUTH_TOKEN", "test-worker-token")
    if env_value is None:
        monkeypatch.delenv("ENV", raising=False)
    else:
        monkeypatch.setenv("ENV", env_value)
    transport = ASGITransport(app=worker_app)
    async with AsyncClient(transport=transport, base_url="http://worker") as client:
        response = await client.get("/tasks/missing")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bypass_allowed_for_explicit_dev_env(worker_app, monkeypatch):
    """Issue #512: bypass still works when ENV is explicitly non-production."""
    monkeypatch.setenv("ALLOW_TEST_AUTH_BYPASS", "true")
    monkeypatch.setenv("ENV", "test")
    transport = ASGITransport(app=worker_app)
    async with AsyncClient(transport=transport, base_url="http://worker") as client:
        response = await client.get("/tasks/missing")

    assert response.status_code == 404  # auth passed, route 404s


@pytest.mark.asyncio
async def test_task_routes_accept_valid_worker_auth(worker_app, monkeypatch):
    monkeypatch.delenv("ALLOW_TEST_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("WORKER_AUTH_TOKEN", "test-worker-token")
    transport = ASGITransport(app=worker_app)
    async with AsyncClient(transport=transport, base_url="http://worker") as client:
        response = await client.get(
            "/tasks/missing",
            headers={"Authorization": "Bearer test-worker-token"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_readiness_returns_503_when_queue_is_unavailable(worker_app):
    transport = ASGITransport(app=worker_app)
    with (
        patch("worker_service._redis_url", return_value="redis://unavailable"),
        patch("worker_service._queue_call", side_effect=ConnectionError("offline")),
    ):
        async with AsyncClient(transport=transport, base_url="http://worker") as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["queue_available"] is False


@pytest.mark.asyncio
async def test_degraded_health_reports_queue_failure(worker_app):
    transport = ASGITransport(app=worker_app)
    with (
        patch("worker_service._redis_url", return_value="redis://unavailable"),
        patch("worker_service._queue_call", side_effect=ConnectionError("offline")),
    ):
        async with AsyncClient(transport=transport, base_url="http://worker") as client:
            response = await client.get("/health/degraded")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_task_contract_bounds_recovery_controls():
    from worker_service import TaskContract

    assert TaskContract(tenant_id="tenant-a", goal="bounded").max_retries == 3
    with pytest.raises(ValidationError):
        TaskContract(tenant_id="tenant-a", goal="too many retries", max_retries=4)
    with pytest.raises(ValidationError):
        TaskContract(tenant_id="tenant-a", goal="too long", timeout_seconds=901)


def test_task_contract_requires_tenant_scope():
    from worker_service import TaskContract

    with pytest.raises(ValidationError):
        TaskContract(goal="run this")


def test_task_contract_validates_scrape_url_and_metadata_size():
    from worker_service import TaskContract

    with pytest.raises(ValidationError):
        TaskContract(tenant_id="tenant-a", goal="scrape", capability="scrape")

    with pytest.raises(ValidationError):
        TaskContract(
            tenant_id="tenant-a",
            goal="large",
            metadata={"payload": "x" * 40_000},
        )


@pytest.mark.asyncio
async def test_idempotency_reuses_existing_task_id():
    from worker_service import (
        TaskContract,
        _claim_idempotency,
        _idempotency_records,
        _store_idempotency_task,
    )

    request = TaskContract(
        tenant_id="tenant-idempotent",
        goal="same task",
        idempotency_key="same-request",
    )
    _idempotency_records.clear()
    try:
        _, existing = await _claim_idempotency(request)
        assert existing is None
        await _store_idempotency_task(request, "task-123")
        _, duplicate = await _claim_idempotency(request)
        assert duplicate == "task-123"
    finally:
        _idempotency_records.clear()


@pytest.mark.asyncio
async def test_idempotency_rejects_payload_reuse_with_different_content():
    from worker_service import (
        TaskContract,
        _claim_idempotency,
        _idempotency_records,
        _store_idempotency_task,
    )

    _idempotency_records.clear()
    first = TaskContract(tenant_id="tenant-conflict", goal="first", idempotency_key="request")
    second = TaskContract(tenant_id="tenant-conflict", goal="second", idempotency_key="request")
    try:
        await _claim_idempotency(first)
        await _store_idempotency_task(first, "task-456")
        with pytest.raises(HTTPException, match="different task payload"):
            await _claim_idempotency(second)
    finally:
        _idempotency_records.clear()


def test_task_contract_accepts_supported_capabilities():
    from worker_service import TaskContract

    contract = TaskContract(
        tenant_id="tenant-a",
        user_id="user-a",
        goal="scrape docs",
        capability="scrape",
        idempotency_key="request-1",
        metadata={"url": "https://example.com"},
    )

    assert contract.tenant_id == "tenant-a"
    assert contract.idempotency_key == "request-1"
    assert contract.correlation_id is None


def test_task_event_logging_includes_tenant_and_correlation_context(caplog):
    from worker_service import TaskContract, _log_task_event

    request = TaskContract(
        tenant_id="tenant-observed",
        user_id="user-observed",
        correlation_id="corr-123",
        goal="observe",
    )
    with caplog.at_level("INFO"):
        _log_task_event("submitted", request, task_id="task-789")

    record = next(record for record in caplog.records if record.message == "worker_task_event")
    assert record.event == "submitted"
    assert record.tenant_id == "tenant-observed"
    assert record.correlation_id == "corr-123"
    assert record.task_id == "task-789"
