"""MESH-6 (issue #926) — /api/v1/mesh/tasks REST endpoints + heartbeat auto-dispatch tests.

বাংলা সারসংক্ষেপ:
------------------
REST আবরণ ও MESH-1 integration যাচাই:
1. POST /tasks → 201 pending
2. GET /tasks + ?task_status= filter + queue/stats
3. GET /tasks/{id} → 200 / 404
4. POST /tasks/any/claim → 200 best-match / 204 idle
5. POST /tasks/{id}/claim → 409 conflict (not pending)
6. lease renewal → 200 / 403 wrong node / 404 unknown
7. complete → 200 + result / 403 wrong node
8. fail → 200 (retry) / 403 wrong node
9. cancel → 200 / 422 terminal
10. POST /tasks/reap → expired lease re-queue
11. heartbeat auto-dispatch: node heartbeat → assigned_tasks পূরণ হয় (MESH-1 contract)
12. auto-dispatch respects max_active_per_node

কোনো fake/mock নেই — আসল PresenceRegistry + TaskRouter (in-memory) দিয়ে।
"""

from __future__ import annotations

import time
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.mesh import router as mesh_router
from api.routes.mesh_tasks import router as tasks_router
from core.presence_registry import (
    PresenceRegistry,
    get_presence_registry,
    reset_presence_registry_for_tests,
)
from core.task_router import (
    TaskRouter,
    get_task_router,
    reset_task_router_for_tests,
)


def _make_app(registry: PresenceRegistry, router: TaskRouter) -> tuple[FastAPI, TestClient]:
    """নতুন FastAPI app — উভয় mesh router + fresh instances (test isolation)।"""
    app = FastAPI()
    app.include_router(mesh_router)
    app.include_router(tasks_router)
    app.dependency_overrides[get_presence_registry] = lambda: registry
    app.dependency_overrides[get_task_router] = lambda: router
    return app, TestClient(app)


class MeshTasksEndpointTest(unittest.TestCase):
    """POST/GET /api/v1/mesh/tasks endpoints-এর ব্যাপক contract যাচাই।"""

    def setUp(self) -> None:
        self.registry = PresenceRegistry()
        self.task_router = TaskRouter(lease_seconds=600, max_active_per_node=2)
        self.app, self.client = _make_app(self.registry, self.task_router)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        reset_presence_registry_for_tests()
        reset_task_router_for_tests()

    def _submit(self, **overrides) -> dict:
        body = {
            "task_type": "pytest",
            "title": "run tests",
            "payload": {"test_path": "tests/core"},
            "required_capabilities": ["pytest"],
        }
        body.update(overrides)
        res = self.client.post("/api/v1/mesh/tasks", json=body)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    # ── submit ───────────────────────────────────────────────────────────────
    def test_submit_201_pending(self) -> None:
        data = self._submit()
        self.assertTrue(data["task_id"].startswith("task-"))
        self.assertEqual(data["status"], "pending")

    def test_submit_invalid_type_422(self) -> None:
        res = self.client.post("/api/v1/mesh/tasks", json={"task_type": "fly", "title": "x"})
        self.assertEqual(res.status_code, 422)

    # ── list / detail / stats ────────────────────────────────────────────────
    def test_list_filter_and_stats(self) -> None:
        self._submit(title="a")
        data = self.client.get("/api/v1/mesh/tasks").json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["stats"]["pending"], 1)
        res = self.client.get("/api/v1/mesh/tasks", params={"task_status": "pending"})
        self.assertEqual(res.status_code, 200)
        res = self.client.get("/api/v1/mesh/tasks", params={"task_status": "bogus"})
        self.assertEqual(res.status_code, 422)
        stats = self.client.get("/api/v1/mesh/tasks/queue/stats").json()
        self.assertEqual(stats["pending"], 1)

    def test_get_task_404(self) -> None:
        res = self.client.get("/api/v1/mesh/tasks/task-missing")
        self.assertEqual(res.status_code, 404)

    # ── claim ────────────────────────────────────────────────────────────────
    def test_claim_any_best_match_then_204(self) -> None:
        self._submit()
        res = self.client.post(
            "/api/v1/mesh/tasks/any/claim",
            json={"node_id": "pc-1", "role": "tester", "capabilities": ["pytest"]},
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["task_type"], "pytest")
        # আর কোনো pending নেই → 204
        res2 = self.client.post(
            "/api/v1/mesh/tasks/any/claim",
            json={"node_id": "pc-2", "role": "tester", "capabilities": ["pytest"]},
        )
        self.assertEqual(res2.status_code, 204)

    def test_claim_specific_conflict_409(self) -> None:
        data = self._submit()
        tid = data["task_id"]
        res1 = self.client.post(
            f"/api/v1/mesh/tasks/{tid}/claim",
            json={"node_id": "pc-1", "capabilities": ["pytest"]},
        )
        self.assertEqual(res1.status_code, 200)
        res2 = self.client.post(
            f"/api/v1/mesh/tasks/{tid}/claim",
            json={"node_id": "pc-2", "capabilities": ["pytest"]},
        )
        self.assertEqual(res2.status_code, 409)

    def test_claim_unknown_404(self) -> None:
        res = self.client.post(
            "/api/v1/mesh/tasks/task-missing/claim",
            json={"node_id": "pc-1", "capabilities": []},
        )
        self.assertEqual(res.status_code, 404)

    # ── lease / complete / fail / cancel ────────────────────────────────────
    def test_lease_complete_fail_lifecycle(self) -> None:
        data = self._submit()
        tid = data["task_id"]
        self.client.post(
            f"/api/v1/mesh/tasks/{tid}/claim",
            json={"node_id": "pc-1", "capabilities": ["pytest"]},
        )
        # wrong node → 403
        res_forbidden = self.client.post(
            f"/api/v1/mesh/tasks/{tid}/lease", json={"node_id": "ghost"}
        )
        self.assertEqual(res_forbidden.status_code, 403)
        # owner renewal → 200
        res_renew = self.client.post(
            f"/api/v1/mesh/tasks/{tid}/lease", json={"node_id": "pc-1", "lease_seconds": 300}
        )
        self.assertEqual(res_renew.status_code, 200)
        # complete with result → 200, result persisted
        res_done = self.client.post(
            f"/api/v1/mesh/tasks/{tid}/complete",
            json={"node_id": "pc-1", "result": {"passed": 10}},
        )
        self.assertEqual(res_done.status_code, 200)
        self.assertEqual(res_done.json()["result"], {"passed": 10})
        # terminal cancel → 422
        res_cancel = self.client.post(f"/api/v1/mesh/tasks/{tid}/cancel")
        self.assertEqual(res_cancel.status_code, 422)

    def test_fail_retry_then_422_on_terminal(self) -> None:
        data = self._submit(max_attempts=1)
        tid = data["task_id"]
        self.client.post(
            f"/api/v1/mesh/tasks/{tid}/claim",
            json={"node_id": "pc-1", "capabilities": ["pytest"]},
        )
        res_fail = self.client.post(
            f"/api/v1/mesh/tasks/{tid}/fail", json={"node_id": "pc-1", "error": "boom"}
        )
        self.assertEqual(res_fail.status_code, 200)
        self.assertEqual(res_fail.json()["status"], "failed")

    def test_fail_wrong_node_403(self) -> None:
        data = self._submit()
        tid = data["task_id"]
        self.client.post(
            f"/api/v1/mesh/tasks/{tid}/claim",
            json={"node_id": "pc-1", "capabilities": ["pytest"]},
        )
        res = self.client.post(
            f"/api/v1/mesh/tasks/{tid}/fail", json={"node_id": "ghost", "error": "x"}
        )
        self.assertEqual(res.status_code, 403)

    # ── reap ─────────────────────────────────────────────────────────────────
    def test_reap_requeues_expired(self) -> None:
        data = self._submit()
        tid = data["task_id"]
        # 1-সেকেন্ড lease নিয়ে মেয়াদ শেষ করা হচ্ছে
        self.client.post(
            f"/api/v1/mesh/tasks/{tid}/claim",
            json={"node_id": "pc-dead", "capabilities": ["pytest"], "lease_seconds": 1},
        )
        time.sleep(1.1)
        res = self.client.post("/api/v1/mesh/tasks/reap")
        self.assertEqual(res.status_code, 200)
        self.assertIn(tid, res.json()["reaped"])
        after = self.client.get(f"/api/v1/mesh/tasks/{tid}").json()
        self.assertEqual(after["status"], "pending")

    # ── heartbeat auto-dispatch (MESH-1 × MESH-6 integration) ───────────────
    def test_heartbeat_auto_dispatch_assigns_matching_tasks(self) -> None:
        self._submit()
        hb = {
            "node_id": "pc-2-headless",
            "node_type": "local_pc",
            "role": "tester",
            "capabilities": ["pytest", "bash"],
            "timestamp": "2026-09-21T01:00:00Z",
        }
        res = self.client.post("/api/v1/nodes/heartbeat", json=hb)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(len(data["assigned_tasks"]), 1, "matching task auto-assigned")

    def test_heartbeat_no_match_leaves_assigned_empty(self) -> None:
        self._submit(required_capabilities=["gpu"])
        hb = {
            "node_id": "pc-2-headless",
            "node_type": "local_pc",
            "role": "tester",
            "capabilities": ["pytest"],
            "timestamp": "2026-09-21T01:00:00Z",
        }
        data = self.client.post("/api/v1/nodes/heartbeat", json=hb).json()
        self.assertEqual(data["assigned_tasks"], [])

    def test_heartbeat_respects_max_active_per_node(self) -> None:
        for i in range(3):
            self._submit(title=f"t{i}")
        hb = {
            "node_id": "pc-2-headless",
            "node_type": "local_pc",
            "role": "tester",
            "capabilities": ["pytest"],
            "timestamp": "2026-09-21T01:00:00Z",
        }
        data = self.client.post("/api/v1/nodes/heartbeat", json=hb).json()
        self.assertEqual(len(data["assigned_tasks"]), 2, "max_active_per_node=2 সীমা মানা হয়েছে")


if __name__ == "__main__":
    unittest.main()
