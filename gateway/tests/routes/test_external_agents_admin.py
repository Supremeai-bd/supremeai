"""
Route-level tests for api.routes.external_agents_admin (issue #2148).

The module under test is the smallest honest wire for backend/external_agents
(EAOL Part-3 seed, PLAN-EAOL-003; registry §11). Contracts locked here:

- Flag off (default): every endpoint fails closed with a clean 503
  (billing ERR-G01 precedent — never fabricate availability).
- Flag on, no worker configured: delegate fails closed with
  ``no_worker_configured`` — no jobs are accepted into a queue nothing
  will ever drain.
- Flag on + explicit worker: delegate → get → cancel lifecycle works and
  reflects the durable state machine (QUEUED → ... → CANCELLED).

Tests build a minimal FastAPI app containing ONLY the router under test —
the admin auth dependency is applied by routers.include_admin_routers() in
production and is exercised there; these tests target the wire semantics.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import external_agents_admin as mod

MODULE_REF = f"{__name__}:stub_worker_ok"
HANGING_REF = f"{__name__}:stub_worker_hangs"


async def stub_worker_ok(task: Any, record: Any) -> dict[str, Any]:
    """Instantly-completing stub worker (deterministic lifecycle checks)."""
    return {"ok": True, "goal": task.goal}


async def stub_worker_hangs(task: Any, record: Any) -> dict[str, Any]:
    """Never-returning stub — the job stays live and cancellable."""
    await asyncio.Event().wait()
    return None  # pragma: no cover — unreachable


@pytest.fixture(autouse=True)
def _reset_singleton():
    mod.reset_job_api_singleton()
    yield
    mod.reset_job_api_singleton()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(mod.router)
    with TestClient(app) as c:  # context = portal lifecycle owns bg workers
        yield c


def _enable(monkeypatch: pytest.MonkeyPatch, worker: str | None = None) -> None:
    monkeypatch.setenv(mod.FLAG_ENABLED, "1")
    if worker is None:
        monkeypatch.delenv(mod.FLAG_WORKER, raising=False)
    else:
        monkeypatch.setenv(mod.FLAG_WORKER, worker)


# ----------------------------------------------------------------------
# Flag off (default) — honest 503, import-safe
# ----------------------------------------------------------------------


class TestFlagOff:
    def test_delegate_is_503_when_disabled(self, client: TestClient):
        r = client.post("/api/v1/external-agents/jobs", json={"goal": "x"})
        assert r.status_code == 503
        assert "external_agents_disabled" in r.json()["detail"]

    def test_get_is_503_when_disabled(self, client: TestClient):
        r = client.get("/api/v1/external-agents/jobs/job-abc")
        assert r.status_code == 503

    def test_delete_is_503_when_disabled(self, client: TestClient):
        r = client.delete("/api/v1/external-agents/jobs/job-abc")
        assert r.status_code == 503

    def test_import_is_side_effect_free(self):
        # Import-safety contract: importing the module must not create the
        # singleton nor read/require any env var.
        assert mod._job_api is None


# ----------------------------------------------------------------------
# Flag on, worker gate — fail closed, no fabricated progress
# ----------------------------------------------------------------------


class TestWorkerGate:
    def test_delegate_without_worker_is_503_no_worker_configured(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        _enable(monkeypatch, worker=None)
        r = client.post("/api/v1/external-agents/jobs", json={"goal": "do it"})
        assert r.status_code == 503
        assert "no_worker_configured" in r.json()["detail"]

    def test_delegate_with_unresolvable_worker_is_503_worker_unavailable(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        _enable(monkeypatch, worker="no.such.module:worker")
        r = client.post("/api/v1/external-agents/jobs", json={"goal": "do it"})
        assert r.status_code == 503
        assert "worker_unavailable" in r.json()["detail"]

    def test_delegate_with_non_callable_worker_is_503(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        _enable(monkeypatch, worker=f"{__name__}:MODULE_REF")  # str attr → not callable
        r = client.post("/api/v1/external-agents/jobs", json={"goal": "do it"})
        assert r.status_code == 503
        assert "worker_unavailable" in r.json()["detail"]


# ----------------------------------------------------------------------
# Flag on + worker — full lifecycle through the durable state machine
# ----------------------------------------------------------------------


class TestLifecycle:
    def test_delegate_get_cancel_lifecycle(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        _enable(monkeypatch, worker=HANGING_REF)

        r = client.post(
            "/api/v1/external-agents/jobs",
            json={
                "goal": "wire the module",
                "issue_number": 2148,
                "constraints": {"scope": "backend/external_agents"},
                "allowed_providers": ["zcode"],
                "metadata": {"lane": "coder-1"},
            },
        )
        assert r.status_code == 202
        job = r.json()
        assert job["job_id"].startswith("job-")
        assert job["task_id"].startswith("task-")
        assert job["state"] in {"QUEUED", "CLAIMED", "RUNNING"}

        g = client.get(f"/api/v1/external-agents/jobs/{job['job_id']}")
        assert g.status_code == 200
        assert g.json()["job_id"] == job["job_id"]

        d = client.delete(f"/api/v1/external-agents/jobs/{job['job_id']}")
        assert d.status_code == 200
        assert d.json() == {"job_id": job["job_id"], "cancelled": True}

        g2 = client.get(f"/api/v1/external-agents/jobs/{job['job_id']}")
        assert g2.status_code == 200
        assert g2.json()["state"] == "CANCELLED"

    def test_unknown_job_get_and_delete_are_404(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        _enable(monkeypatch, worker=HANGING_REF)
        assert client.get("/api/v1/external-agents/jobs/job-nope").status_code == 404
        assert client.delete("/api/v1/external-agents/jobs/job-nope").status_code == 404

    def test_get_delete_before_any_delegate_is_404(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        # Honest: no delegate has run in this process → no jobs exist.
        _enable(monkeypatch, worker=None)
        assert client.get("/api/v1/external-agents/jobs/job-x").status_code == 404
        assert client.delete("/api/v1/external-agents/jobs/job-x").status_code == 404

    def test_terminal_job_reports_cancelled_false(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        _enable(monkeypatch, worker=MODULE_REF)
        r = client.post("/api/v1/external-agents/jobs", json={"goal": "finish fast"})
        job = r.json()
        # Poll (bounded) until the stub worker drives the job terminal.
        state = None
        for _ in range(50):
            state = client.get(f"/api/v1/external-agents/jobs/{job['job_id']}").json()["state"]
            if state == "COMPLETED":
                break
            time.sleep(0.05)
        assert state == "COMPLETED"
        d = client.delete(f"/api/v1/external-agents/jobs/{job['job_id']}")
        assert d.status_code == 200
        assert d.json()["cancelled"] is False  # never fake a post-hoc cancel

    def test_invalid_provider_is_422(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        _enable(monkeypatch, worker=MODULE_REF)
        r = client.post(
            "/api/v1/external-agents/jobs",
            json={"goal": "x", "allowed_providers": ["not-a-provider"]},
        )
        assert r.status_code == 422
        assert "not-a-provider" in r.json()["detail"]

    def test_empty_goal_is_422(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        _enable(monkeypatch, worker=MODULE_REF)
        r = client.post("/api/v1/external-agents/jobs", json={"goal": ""})
        assert r.status_code == 422

    def test_blank_worker_env_is_treated_as_unconfigured(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        _enable(monkeypatch, worker="   ")
        r = client.post("/api/v1/external-agents/jobs", json={"goal": "x"})
        assert r.status_code == 503
        assert "no_worker_configured" in r.json()["detail"]


# ----------------------------------------------------------------------
# Registry contract (routers.py) — no heavy app import needed
# ----------------------------------------------------------------------


class TestRegistryEntry:
    def test_all_routers_contains_external_agents_admin_entry(self):
        import ast
        import os

        path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "api", "routers.py")
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        entries = []
        for node in ast.walk(tree):
            if isinstance(node, ast.List):
                for elt in node.elts:
                    if isinstance(elt, ast.Dict):
                        kv = {
                            k.value: v.value
                            for k, v in zip(elt.keys, elt.values, strict=False)
                            if isinstance(k, ast.Constant)
                        }
                        if str(kv.get("path", "")).endswith("external_agents_admin"):
                            entries.append(kv)
        assert len(entries) == 1, "exactly ONE ALL_ROUTERS entry expected"
        assert entries[0]["is_admin"] is True  # admin auth gate (double-gating)
