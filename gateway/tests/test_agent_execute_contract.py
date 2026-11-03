"""ERR-H07/H08 contract tests — dual agent routers + sync-execution offload.

Pins the two-surface agent contract declared in ``api/routers.py``:

- ``/api/agents``     (``api.routes.agents``)  — USER token, read-only
  catalog/status/research surface.
- ``/api/v1/agents``  (``api.routes.agent``)   — INTEGRATION JWT,
  canonical execution surface.

And the ERR-H08 execution semantics of ``POST /api/v1/agents/execute``:

- ``auto_execute=false`` → plan-only response, NOTHING is executed.
- ``auto_execute=true``  → full execution, offloaded off the event loop
  (``AutonomousAgent.execute`` is synchronous).
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from unittest.mock import patch

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import agent as agent_route
from core.config import settings

PROMPT = "fix the failing login test and verify the build"


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(agent_route.router)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    token = pyjwt.encode({"sub": "integration-test"}, settings.jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


# --- ERR-H07: mount-site drift guard ---------------------------------------


class TestTwoSurfaceContract:
    def test_execution_router_prefix_is_versioned_plural(self):
        assert agent_route.router.prefix == "/api/v1/agents"

    def test_read_surface_router_prefix(self):
        from api.routes import agents as agents_route

        assert agents_route.router.prefix == "/api/agents"

    def test_routers_registry_mounts_exactly_two_agent_surfaces(self):
        import api.routers as routers

        paths = [entry["path"] for entry in routers.ALL_ROUTERS]
        agent_paths = [p for p in paths if p in ("api.routes.agent", "api.routes.agents")]
        assert agent_paths == ["api.routes.agents", "api.routes.agent"], (
            "The two-surface agent contract drifted: expected exactly "
            "api.routes.agents (read) + api.routes.agent (execute) in ALL_ROUTERS"
        )

    def test_no_execution_endpoint_on_read_surface(self):
        from api.routes import agents as agents_route

        route_paths = {getattr(r, "path", "") for r in agents_route.router.routes}
        assert all("execute" not in p for p in route_paths), (
            "ERR-H07 violation: execution endpoint added to the user read surface"
        )

    def test_exactly_one_post_execute_registration_across_all_routers(self):
        """Issue #1822 drift guard: agent_tasks.py used to register a second
        POST /api/v1/agents/execute with a different request contract and
        auth — FastAPI serves first-registered, so it was permanently
        unreachable while looking live to clients. This walks EVERY module
        in ALL_ROUTERS (not just the two surfaces above) and fails if more
        than one POST registration of the canonical execution path exists.
        """
        from api.routers import ALL_ROUTERS

        METHOD = "POST"
        FULL_PATH = "/api/v1/agents/execute"
        registrations = []
        for entry in ALL_ROUTERS:
            module = importlib.import_module(entry["path"])
            router = getattr(module, "router", None)
            if router is None:
                continue
            for route in getattr(router, "routes", []):
                route_path = getattr(route, "path", "")
                methods = {m.upper() for m in getattr(route, "methods", set()) or set()}
                if route_path.rstrip("/") == FULL_PATH and METHOD in methods:
                    registrations.append((entry["path"], route_path, METHOD))
        assert len(registrations) == 1, (
            f"POST {FULL_PATH} is registered {len(registrations)} times "
            f"({registrations}) — first-registration wins, so every extra "
            "registration is an unreachable shadow endpoint with possibly "
            "divergent contracts/auth (issue #1822)"
        )
        assert registrations and registrations[0][0] == "api.routes.agent", (
            "The canonical execution surface must be api.routes.agent"
        )


# --- ERR-H08: execution semantics ------------------------------------------


class TestExecuteContract:
    def test_auto_execute_false_returns_plan_without_executing(self, client, auth_headers):
        executed = []

        def _boom(*args, **kwargs):
            executed.append("called")
            raise AssertionError("execute() must not run when auto_execute=false")

        with patch("core.agents.framework.task_runner_agent.AutonomousAgent.execute", _boom):
            res = client.post(
                "/api/v1/agents/execute",
                json={"task_id": "t-plan-1", "prompt": PROMPT, "auto_execute": False},
                headers=auth_headers,
            )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "planned"
        # plan text derived verbatim from the planner (fix prompt → fix plan)
        assert "Investigate issue" in body["result"]
        assert "1. investigate" in body["result"]
        assert executed == []

    def test_auto_execute_true_runs_offloaded(self, client, auth_headers):
        with patch(
            "core.agents.framework.task_runner_agent.AutonomousAgent.execute",
            return_value={"success": True, "output": "all steps finished"},
        ) as mock_exec:
            res = client.post(
                "/api/v1/agents/execute",
                json={"task_id": "t-run-1", "prompt": PROMPT, "auto_execute": True},
                headers=auth_headers,
            )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "success"
        assert body["result"] == "all steps finished"
        mock_exec.assert_called_once_with(PROMPT)

    def test_auto_execute_true_failed_step_maps_to_failed_status(self, client, auth_headers):
        with patch(
            "core.agents.framework.task_runner_agent.AutonomousAgent.execute",
            return_value={"success": False, "output": None},
        ):
            res = client.post(
                "/api/v1/agents/execute",
                json={"task_id": "t-run-2", "prompt": PROMPT, "auto_execute": True},
                headers=auth_headers,
            )
        body = res.json()
        assert body["status"] == "failed"
        assert "completed successfully" in body["result"]  # task-id fallback text

    def test_execute_exception_maps_to_500_with_error_bus(self, client, auth_headers):
        with patch(
            "core.agents.framework.task_runner_agent.AutonomousAgent.execute",
            side_effect=RuntimeError("provider socket died"),
        ):
            res = client.post(
                "/api/v1/agents/execute",
                json={"task_id": "t-run-3", "prompt": PROMPT, "auto_execute": True},
                headers=auth_headers,
            )
        assert res.status_code == 500
        assert "self-healing" in res.json()["detail"]


# --- auth: integration JWT is mandatory ------------------------------------


class TestAuthContract:
    def test_missing_token_rejected(self, client):
        res = client.post(
            "/api/v1/agents/execute",
            json={"task_id": "t-1", "prompt": PROMPT, "auto_execute": False},
        )
        assert res.status_code in (401, 403)  # missing credentials → unauthorized

    def test_invalid_token_rejected(self, client):
        res = client.post(
            "/api/v1/agents/execute",
            json={"task_id": "t-1", "prompt": PROMPT, "auto_execute": False},
            headers={"Authorization": "Bearer not-a-jwt"},
        )
        assert res.status_code == 401
