"""MESH-1 (issue #939) — Tower presence endpoint tests.

বাংলা সারসংক্ষেপ:
------------------
এই test suite নিশ্চিত করে যে `/api/v1/nodes/heartbeat` এবং সংশ্লিষ্ট endpoints
ঠিকমতো কাজ করছে — আসল `PresenceRegistry` (in-memory mode, কোনো Redis নেই)
দিয়ে। কোনো fake/mock/stub নেই; tests গুলো আসল behavior যাচাই করে।

Coverage:
1. POST /heartbeat → 200 + lease info block (status, lease_active, lease_expires_at)
2. GET /nodes → 200 + list of active nodes
3. Stale node (last_seen > 10 min) not in active list
4. PATCH /nodes/{id} → role updates registry
5. GET /nodes/{id} → 200 with full record
6. GET /nodes/{unknown} → 404
7. PATCH /nodes/{unknown} → 404
8. POST invalid node_type → 422
9. POST invalid role → 422
10. PATCH invalid role → 422
11. Stale lease release (release_stale_leases) → lease_active=False
12. POST preserves existing assigned_tasks (lease continuation)
"""

from __future__ import annotations

import time
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.mesh import router as mesh_router
from core.presence_registry import (
    PresenceRegistry,
    get_presence_registry,
    reset_presence_registry_for_tests,
)


def _make_app(registry: PresenceRegistry) -> tuple[FastAPI, TestClient]:
    """নতুন FastAPI app তৈরি করো যেটি নির্দিষ্ট registry instance ব্যবহার করবে।

    বাংলা: প্রতিটি test fresh registry পায় — কোনো cross-test contamination নেই।
    """
    app = FastAPI()
    app.include_router(mesh_router)
    # FastAPI dependency override — registry instance test-isolated।
    app.dependency_overrides[get_presence_registry] = lambda: registry
    return app, TestClient(app)


def _sample_heartbeat_body(node_id: str = "pc-1-dev-rig") -> dict:
    """issue #939 spec-এর সাথে মিল রেখে একটি valid heartbeat payload।"""
    return {
        "node_id": node_id,
        "node_type": "local_pc",
        "role": "planner",
        "capabilities": ["file_edit", "pytest", "ollama", "git_push"],
        "timestamp": "2026-09-21T01:00:00Z",
        "load": {"cpu": 45, "mem": 60, "active_tasks": 1},
    }


class TestMeshHeartbeatEndpoint(unittest.TestCase):
    """POST /api/v1/nodes/heartbeat ও সহযোগী endpoints-এর ব্যাপক contract যাচাই।"""

    def setUp(self) -> None:
        # প্রতিটি test fresh in-memory registry পায় — কোনো Redis backing নেই।
        self.registry = PresenceRegistry()
        self.app, self.client = _make_app(self.registry)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        reset_presence_registry_for_tests()

    # ── Test 1: happy-path heartbeat ─────────────────────────────────────────
    def test_heartbeat_returns_200_with_lease_info(self) -> None:
        body = _sample_heartbeat_body()
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)

        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        # issue spec-এর response block-এর সাথে ১:১ মিল
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["lease_active"])
        self.assertIn("lease_expires_at", data)
        self.assertNotEqual(data["lease_expires_at"], "")
        self.assertEqual(data["node_id"], body["node_id"])
        # assigned_tasks একটি list হতে হবে (খালি হলেও চলবে)
        self.assertIsInstance(data["assigned_tasks"], list)
        # last_seen অবশ্যই ISO 8601 timestamp হবে
        self.assertIn("T", data["last_seen"])

    # ── Test 2: GET /nodes returns the registered node ───────────────────────
    def test_list_active_nodes_returns_registered_node(self) -> None:
        body = _sample_heartbeat_body(node_id="pc-2-coder")
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        self.assertEqual(res.status_code, 200, res.text)

        res = self.client.get("/api/v1/nodes")
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(len(data["nodes"]), 1)
        node = data["nodes"][0]
        self.assertEqual(node["node_id"], "pc-2-coder")
        self.assertEqual(node["role"], "planner")
        self.assertEqual(node["node_type"], "local_pc")
        self.assertIn("pytest", node["capabilities"])
        self.assertTrue(node["lease_active"])
        # last_seen থাকতেই হবে
        self.assertIn("last_seen", node)
        # stale_after_seconds echo হয়ে আসবে (default 600)
        self.assertEqual(data["stale_after_seconds"], 600)

    # ── Test 3: stale node excluded from active list ───────────────────────────
    def test_stale_node_excluded_from_active_list(self) -> None:
        # Step 1: একটি node register করো
        body = _sample_heartbeat_body(node_id="pc-stale")
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        self.assertEqual(res.status_code, 200, res.text)

        # Step 2: record সরাসরি registry-তে manipulate করে last_seen পুরোনো করো
        # (আসল production code-এ এটা time পার হওয়ার সাথে সাথে ঘটবে)
        record = self.registry._nodes["pc-stale"]
        stale_epoch = record.last_seen_epoch - 700  # 11 মিনিট আগে
        from datetime import UTC, datetime, timedelta

        stale_iso = datetime.fromtimestamp(stale_epoch, tz=UTC).isoformat()
        self.registry._nodes["pc-stale"] = record.model_copy(
            update={
                "last_seen_epoch": stale_epoch,
                "last_seen": stale_iso,
            }
        )

        # Step 3: GET /nodes — এইবার stale node তালিকায় থাকবে না
        res = self.client.get("/api/v1/nodes")
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["count"], 0, "stale node must NOT appear in active list")
        self.assertEqual(len(data["nodes"]), 0)

        # Step 4: কিন্তু get_node দিয়ে এখনো record দেখা যায় (audit contract)
        import asyncio

        record_still_present = asyncio.run(self.registry.get_node("pc-stale"))
        self.assertIsNotNone(record_still_present)

    # ── Test 4: PATCH role updates registry ──────────────────────────────────
    def test_patch_role_updates_registry(self) -> None:
        body = _sample_heartbeat_body(node_id="bolt-agent")
        body["role"] = "planner"
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        self.assertEqual(res.status_code, 200, res.text)

        # Now change role via PATCH
        res = self.client.patch("/api/v1/nodes/bolt-agent", json={"role": "coder"})
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["node"]["node_id"], "bolt-agent")
        self.assertEqual(data["node"]["role"], "coder")

        # Verify the change persisted in registry
        import asyncio

        record = asyncio.run(self.registry.get_node("bolt-agent"))
        self.assertIsNotNone(record)
        self.assertEqual(record.role, "coder")

    # ── Test 5: GET /nodes/{id} returns 200 with full record ─────────────────
    def test_get_single_node_returns_detail(self) -> None:
        body = _sample_heartbeat_body(node_id="lovable-web")
        body["capabilities"] = ["design", "frontend"]
        body["load"] = {"cpu": 12.5, "mem": 40, "active_tasks": 2}
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        self.assertEqual(res.status_code, 200, res.text)

        res = self.client.get("/api/v1/nodes/lovable-web")
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        node = data["node"]
        self.assertEqual(node["node_id"], "lovable-web")
        self.assertEqual(node["role"], "planner")
        self.assertEqual(node["node_type"], "local_pc")
        self.assertIn("design", node["capabilities"])
        self.assertEqual(node["load"]["cpu"], 12.5)
        self.assertEqual(node["load"]["active_tasks"], 2)

    # ── Test 6: GET /nodes/{unknown} returns 404 ─────────────────────────────
    def test_get_unknown_node_returns_404(self) -> None:
        res = self.client.get("/api/v1/nodes/does-not-exist")
        self.assertEqual(res.status_code, 404)
        self.assertIn("not registered", res.json()["detail"])

    # ── Test 7: PATCH /nodes/{unknown} returns 404 ────────────────────────────
    def test_patch_unknown_node_returns_404(self) -> None:
        res = self.client.patch("/api/v1/nodes/ghost-node", json={"role": "tester"})
        self.assertEqual(res.status_code, 404)

    # ── Test 8: invalid node_type → 422 ───────────────────────────────────────
    def test_invalid_node_type_returns_422(self) -> None:
        body = _sample_heartbeat_body()
        body["node_type"] = "magic_oracle"  # not in VALID_NODE_TYPES
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        self.assertEqual(res.status_code, 422)

    # ── Test 9: invalid role → 422 ────────────────────────────────────────────
    def test_invalid_role_returns_422(self) -> None:
        body = _sample_heartbeat_body()
        body["role"] = "wizard"  # not in VALID_ROLES
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        self.assertEqual(res.status_code, 422)

    # ── Test 10: PATCH with invalid role → 422 ───────────────────────────────
    def test_patch_invalid_role_returns_422(self) -> None:
        body = _sample_heartbeat_body(node_id="gemini-web")
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        self.assertEqual(res.status_code, 200, res.text)

        res = self.client.patch("/api/v1/nodes/gemini-web", json={"role": "sorcerer"})
        self.assertEqual(res.status_code, 422)

    # ── Test 11: stale lease release → lease_active=False ─────────────────────
    def test_release_stale_leases(self) -> None:
        import asyncio

        body = _sample_heartbeat_body(node_id="stale-leaser")
        body["assigned_tasks"] = ["task-A", "task-B"]
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["assigned_tasks"], ["task-A", "task-B"])

        # Manipulate last_seen to make it stale
        record = self.registry._nodes["stale-leaser"]
        stale_epoch = record.last_seen_epoch - 700
        self.registry._nodes["stale-leaser"] = record.model_copy(
            update={"last_seen_epoch": stale_epoch}
        )

        # Now release stale leases
        released = asyncio.run(self.registry.release_stale_leases())
        self.assertEqual(released, ["stale-leaser"])

        # Verify lease_active=False and assigned_tasks cleared
        record_after = asyncio.run(self.registry.get_node("stale-leaser"))
        self.assertIsNotNone(record_after)
        self.assertFalse(record_after.lease_active)
        self.assertEqual(record_after.assigned_tasks, [])

    # ── Test 12: heartbeat preserves existing assigned_tasks ──────────────────
    def test_heartbeat_preserves_existing_assigned_tasks(self) -> None:
        """Lease continuation contract — দ্বিতীয় heartbeat যদি assigned_tasks
        field সম্পূর্ণ omit করে, প্রথমের tasks হারিয়ে যাবে না।
        বাংলা: caller স্পষ্টভাবে খালি list পাঠালে সেটাই override হবে (clears tasks);
        কিন্তু field omit করলে (None) পূর্বের tasks preserved থাকে।"""
        # First heartbeat with explicit assigned_tasks
        body1 = _sample_heartbeat_body(node_id="lease-continuation-test")
        body1["assigned_tasks"] = ["task-X", "task-Y"]
        res = self.client.post("/api/v1/nodes/heartbeat", json=body1)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["assigned_tasks"], ["task-X", "task-Y"])

        # Second heartbeat — omit assigned_tasks field entirely
        body2 = _sample_heartbeat_body(node_id="lease-continuation-test")
        body2.pop("assigned_tasks", None)
        res = self.client.post("/api/v1/nodes/heartbeat", json=body2)
        self.assertEqual(res.status_code, 200, res.text)
        # Tasks preserved (lease continuation)
        self.assertEqual(
            res.json()["assigned_tasks"],
            ["task-X", "task-Y"],
            "omitting assigned_tasks field must preserve previous tasks",
        )

        # Third heartbeat — explicitly empty list clears the tasks
        body3 = _sample_heartbeat_body(node_id="lease-continuation-test")
        body3["assigned_tasks"] = []
        res = self.client.post("/api/v1/nodes/heartbeat", json=body3)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(
            res.json()["assigned_tasks"],
            [],
            "explicit empty list must clear assigned_tasks",
        )

    # ── Test 13: capabilities + load round-trip via GET /nodes ─────────────────
    def test_capabilities_and_load_roundtrip(self) -> None:
        body = _sample_heartbeat_body(node_id="cap-test")
        body["capabilities"] = ["file_edit", "pytest", "ollama"]
        body["load"] = {"cpu": 78.3, "mem": 55.0, "active_tasks": 3}
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        self.assertEqual(res.status_code, 200, res.text)

        res = self.client.get("/api/v1/nodes/cap-test")
        self.assertEqual(res.status_code, 200, res.text)
        node = res.json()["node"]
        self.assertEqual(node["capabilities"], ["file_edit", "pytest", "ollama"])
        self.assertEqual(node["load"]["cpu"], 78.3)
        self.assertEqual(node["load"]["mem"], 55.0)
        self.assertEqual(node["load"]["active_tasks"], 3)

    # ── Test 14: stale_after_seconds query param is honored ───────────────────
    def test_stale_after_seconds_param(self) -> None:
        body = _sample_heartbeat_body(node_id="threshold-test")
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        self.assertEqual(res.status_code, 200, res.text)

        # Set last_seen to 5 seconds ago
        record = self.registry._nodes["threshold-test"]
        self.registry._nodes["threshold-test"] = record.model_copy(
            update={"last_seen_epoch": record.last_seen_epoch - 5}
        )

        # threshold = 10s → node still active (5 < 10)
        res = self.client.get("/api/v1/nodes?stale_after_seconds=10")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)

        # threshold = 1s → node stale (5 > 1)
        res = self.client.get("/api/v1/nodes?stale_after_seconds=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 0)

    # ── Test 15: empty node_id rejected ────────────────────────────────────────
    def test_empty_node_id_rejected(self) -> None:
        body = _sample_heartbeat_body()
        body["node_id"] = ""
        res = self.client.post("/api/v1/nodes/heartbeat", json=body)
        # Pydantic min_length=1 → 422
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()
