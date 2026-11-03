"""MESH-7 (issue #962) — GitHub webhook endpoint tests (HMAC fail-closed + MESH-6 hooks).

বাংলা সারসংক্ষেপ:
------------------
1. Ping event → 200 active
2. Secret কনফিগার না থাকলে → 503 (fail-closed ingest)
3. Signature অনুপস্থিত/ভুল → 401
4. pull_request opened/synchronize → MESH-6 verification task জমা হয় (tester role)
5. pull_request closed(merged) → ওই PR-এর stale pending task cancel
6. ভুল JSON body → 400
7. push event → 200 handled=False (CI নিজেই হ্যান্ডল করে)

আসল TaskRouter (in-memory) ব্যবহার হয় — কোনো fake task store নেই।
"""

from __future__ import annotations

import hashlib
import hmac
import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.task_router import TaskRouter, get_task_router, reset_task_router_for_tests
from integrations.github_webhook import router as webhook_router

SECRET = "webhook-test-secret"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _pr_event(action: str, pr_number: int = 101, merged: bool = False) -> bytes:
    return json.dumps(
        {
            "action": action,
            "pull_request": {
                "number": pr_number,
                "title": f"Fix thing {pr_number}",
                "html_url": f"https://github.com/SaifulHaqueNiloy/supremeai/pull/{pr_number}",
                "state": "closed" if merged else "open",
                "merged": merged,
                "head": {"ref": f"mesh/task-{pr_number}", "sha": "deadbeef"},
            },
        }
    ).encode("utf-8")


class _SettingsStub:
    """settings.github_webhook_secret-এর নিয়ন্ত্রিত স্টাব।"""

    def __init__(self, secret: str | None):
        if secret is not None:
            self.github_webhook_secret = secret


class GithubWebhookEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        import integrations.github_webhook as wh

        self.wh = wh
        self._orig_settings = wh.settings
        wh.settings = _SettingsStub(SECRET)  # type: ignore[assignment]

        self.task_router = TaskRouter(lease_seconds=600, max_active_per_node=3)
        app = FastAPI()
        app.include_router(webhook_router)
        app.dependency_overrides[get_task_router] = lambda: self.task_router
        self.app = app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.wh.settings = self._orig_settings
        self.app.dependency_overrides.clear()
        reset_task_router_for_tests()

    def _post(self, event: str, body: bytes, signature: str | None = "auto") -> TestClient.response:
        headers = {"X-GitHub-Event": event}
        if signature == "auto":
            headers["X-Hub-Signature-256"] = _sign(body)
        elif signature is not None:
            headers["X-Hub-Signature-256"] = signature
        return self.client.post(
            "/api/v1/integrations/github/webhook", content=body, headers=headers
        )

    # ── fail-closed gates ────────────────────────────────────────────────
    def test_ping_ok(self):
        response = self._post("ping", b"{}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_missing_secret_fails_closed_503(self):
        self.wh.settings = _SettingsStub(None)
        response = self._post("ping", b"{}")
        self.assertEqual(response.status_code, 503)

    def test_missing_signature_401(self):
        response = self._post("ping", b"{}", signature=None)
        self.assertEqual(response.status_code, 401)

    def test_bad_signature_401(self):
        response = self._post("ping", b"{}", signature="sha256=" + "0" * 64)
        self.assertEqual(response.status_code, 401)

    def test_invalid_json_400(self):
        response = self._post("pull_request", b"not-json{")
        self.assertEqual(response.status_code, 400)

    # ── MESH-6 hooks ─────────────────────────────────────────────────────
    def test_pr_opened_submits_verification_task(self):
        response = self._post("pull_request", _pr_event("opened"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        task_id = data["task_id"]
        record = self.task_router._tasks[task_id]
        self.assertEqual(record.task_type, "pytest")
        self.assertEqual(record.target_role, "tester")
        self.assertEqual(record.payload["pr_number"], 101)
        self.assertEqual(record.payload["source"], "github_webhook")
        self.assertEqual(record.payload["branch"], "mesh/task-101")

    def test_pr_synchronize_submits_another_task(self):
        self._post("pull_request", _pr_event("opened"))
        response = self._post("pull_request", _pr_event("synchronize"))
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertNotEqual(data["task_id"], "")
        self.assertEqual(len(self.task_router._tasks), 2)

    def test_pr_merged_cancels_stale_verification_tasks(self):
        self._post("pull_request", _pr_event("opened", pr_number=101))
        self._post("pull_request", _pr_event("synchronize", pr_number=101))
        # অন্য PR-এর task — merge-এর পরেও থাকা উচিত
        self._post("pull_request", _pr_event("opened", pr_number=202))

        response = self._post("pull_request", _pr_event("closed", pr_number=101, merged=True))
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["cancelled_tasks"]), 2)

        statuses = [t.status for t in self.task_router._tasks.values()]
        self.assertEqual(statuses.count("cancelled"), 2)
        self.assertEqual(statuses.count("pending"), 1)

    def test_pr_closed_without_matching_tasks_returns_empty(self):
        response = self._post("pull_request", _pr_event("closed", pr_number=999, merged=True))
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["cancelled_tasks"], [])

    def test_push_event_log_only(self):
        response = self._post("push", json.dumps({"ref": "refs/heads/main"}).encode("utf-8"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data.get("handled", True))

    def test_pr_other_action_passthrough(self):
        response = self._post("pull_request", _pr_event("labeled"))
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data.get("handled", True))
        self.assertEqual(len(self.task_router._tasks), 0)


if __name__ == "__main__":
    unittest.main()
