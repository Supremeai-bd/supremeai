"""Tests for Admin Swarm Workers and Task Queue endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.admin_swarm_queue import router as admin_swarm_queue_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(admin_swarm_queue_router)
    return TestClient(app)


def test_get_swarm_workers(client):
    """Test retrieving swarm workers list."""
    res = client.get("/api/admin/swarm")
    assert res.status_code == 200
    data = res.json()
    assert "workers" in data
    assert len(data["workers"]) >= 4

    worker = data["workers"][0]
    assert "id" in worker
    assert "name" in worker
    assert "type" in worker
    assert "status" in worker


def test_toggle_and_scale_swarm_worker(client):
    """Test toggling worker status and scaling compute."""
    # Toggle worker
    toggle_res = client.post("/api/admin/swarm/worker-solver-01/toggle")
    assert toggle_res.status_code == 200
    worker = toggle_res.json()["worker"]
    assert worker["status"] in ("active", "paused")

    # Scale worker
    scale_res = client.post("/api/admin/swarm/worker-solver-01/scale", json={"delta": 1})
    assert scale_res.status_code == 200
    scaled = scale_res.json()["worker"]
    assert "cpuPercent" in scaled


def test_get_and_manage_queue_jobs(client):
    """Test retrieving, retrying, and clearing queue jobs."""
    # Get jobs
    get_res = client.get("/api/admin/queue")
    assert get_res.status_code == 200
    data = get_res.json()
    assert "jobs" in data
    assert len(data["jobs"]) >= 6

    # Retry job
    retry_res = client.post("/api/admin/queue/retry/job_q_105")
    assert retry_res.status_code == 200
    assert retry_res.json()["job"]["status"] == "active"

    # Flush DLQ
    flush_res = client.post("/api/admin/queue/flush-dlq")
    assert flush_res.status_code == 200
    assert flush_res.json()["success"] is True

    # Clear completed
    clear_res = client.delete("/api/admin/queue/completed")
    assert clear_res.status_code == 200
    assert clear_res.json()["success"] is True
