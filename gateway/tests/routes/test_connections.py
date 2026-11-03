"""Universal Zero-Complexity Interface — connections + access API tests.

বাংলা: Phase 1 acid-test subset। backend/tests/api/routes/ পথে থাকায়
conftest tier system এগুলোকে 'Important' tier-এ ক্লাসিফাই করে (PR checks-এ চলবে)।
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


def _make_client():
    from fastapi import FastAPI

    from api.routes.access import router as access_router
    from api.routes.connections import router as connections_router

    app = FastAPI()
    app.include_router(connections_router)
    app.include_router(access_router)
    from fastapi.testclient import TestClient

    return TestClient(app), app


FAKE_USER = {"sub": "user-123", "tenant_id": "t-1"}


def _auth_headers():
    # বাংলা: test env-এ conftest auth bypass চালু থাকে; শুধু formality হিসেবে header
    return {}


class TestConnectionsAPI(unittest.TestCase):
    def setUp(self):
        # FIX (final-test ci-fixes): app রেফারেন্সও রাখা হলো যেন per-test
        # dependency_overrides দেওয়া যায় (register endpoint-এর tenant contract-এর জন্য)।
        self.client, self.app = _make_client()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_detect_github_oauth(self):
        res = self.client.post(
            "/api/v1/connections/detect", json={"url": "https://github.com/acme/repo"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["detected"])
        self.assertEqual(data["protocol"], "oauth")
        # বাংলা: wire format frontend/types/contracts (camelCase) মেনে চলে —
        # snake_case গেলে AddNewWizard-এ providerLabel undefined হতো
        self.assertEqual(data["providerLabel"], "GitHub")

    def test_detect_mcp_transport(self):
        res = self.client.post(
            "/api/v1/connections/detect", json={"url": "https://tools.example.com/mcp"}
        )
        data = res.json()
        self.assertEqual(data["protocol"], "mcp")

    def test_detect_empty_is_custom(self):
        res = self.client.post("/api/v1/connections/detect", json={"url": " "})
        data = res.json()
        self.assertFalse(data["detected"])
        self.assertEqual(data["protocol"], "custom")

    def test_my_workspace_requires_scoped_shape(self):
        with patch("api.routes.connections.get_capability_registry") as getter:
            registry = getter.return_value
            registry.list.return_value = []
            res = self.client.get("/api/v1/connections/my-workspace")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # বাংলা: test env-এ conftest auth bypass test-admin user inject করে —
        # userId backend থেকেই আসছে (client-supplied নয়), শুধু non-empty যাচাই করা হলো
        self.assertTrue(data["userId"])
        # বাংলা: camelCase contract — authorizedContexts (authorized_contexts নয়)
        self.assertEqual([c["id"] for c in data["authorizedContexts"]], ["personal"])
        self.assertIn(data["executionMode"], {"read_only", "ask_before_acting", "autonomous"})
        # বাংলা: Zero-Friction unification — connections এখন ConnectionRegistry থেকেও আসে
        self.assertIsInstance(data["connections"], list)

    def test_register_creates_capability(self):
        # FIX (final-test ci-fixes): register endpoint এখন tenant-scoped fail-closed —
        # pytest RBAC fallback user-এ tenant_id থাকে না, তাই সত্যিকারের production
        # contract পরীক্ষা করতে tenant-সহ FAKE_USER দিয়ে dependency override করা হলো।
        from core.security.authentication.rbac import get_current_user_token

        self.app.dependency_overrides[get_current_user_token] = lambda: FAKE_USER
        with patch("api.routes.connections.get_capability_registry") as getter:
            registry = getter.return_value
            registry.register.return_value.capability_id = "cap-abc"
            res = self.client.post(
                "/api/v1/connections/register",
                json={"name": "My Tool", "url": "https://tools.example.com/mcp"},
            )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # বাংলা: camelCase contract — UserDashboard capabilityId পড়ে
        self.assertEqual(data["capabilityId"], "cap-abc")
        self.assertEqual(data["health"], "pending")

    def test_register_rejects_blank_url(self):
        res = self.client.post("/api/v1/connections/register", json={"name": "x", "url": "  "})
        self.assertEqual(res.status_code, 400)

    def test_set_mode_valid_enum(self):
        res = self.client.post("/api/v1/access/set-mode", json={"mode": "read_only"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["mode"], "read_only")

    def test_set_mode_rejects_invalid_enum(self):
        res = self.client.post("/api/v1/access/set-mode", json={"mode": "admin"})
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()
