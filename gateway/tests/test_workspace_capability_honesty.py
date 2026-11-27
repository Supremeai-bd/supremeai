"""Workspace capability payload must not promise agentic chat (audit ⑥ / ⑳ / ②₄).

``GET /api/v1/connections/my-workspace`` is the contract a dashboard renders as
"what SupremeAI can do for me". The gateway used to answer with three identical
``status: "ready"`` cards whose purposes claimed autonomous research, sandboxed
code execution and browser automation — while the gateway chat path has **no**
tool-calling loop, so a chat turn could invoke none of them. The payload now
states that explicitly:

* ``chatToolCalling: false`` at the top level;
* every capability carries ``invocableFromChat: false`` and the real
  ``invocationSurface``;
* the browser card names the surface a user actually has (the automation UI/API).

If tool-calling lands, flip these flags in ``gateway/service/app.py`` and update
this test in the same commit — that is the point of pinning them.
"""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.abspath(__file__))
SAT = os.path.abspath(os.path.join(BASE, ".."))
if SAT not in sys.path:
    sys.path.insert(0, SAT)

try:
    from service.app import app
except ImportError:  # pragma: no cover - package layout fallback
    from gateway.service.app import app

from starlette.testclient import TestClient


class TestWorkspaceCapabilityHonesty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["ENV"] = "test"
        os.environ["SUPREMEAI_MASTER_KEY"] = "test-master-key-32-bytes-supersecret-token"
        from gateway.service import app as app_module
        token = app_module._issue_signed_token("workspace-honesty-test", "standard")
        cls.client = TestClient(app)
        cls.payload = cls.client.get(
            "/api/v1/connections/my-workspace",
            headers={"Authorization": f"Bearer {token}"},
        ).json()

    def test_workspace_declares_no_chat_tool_calling(self):
        self.assertIs(self.payload["chatToolCalling"], False)

    def test_no_capability_is_claimed_as_chat_invocable(self):
        capabilities = self.payload["capabilities"]
        self.assertGreaterEqual(len(capabilities), 1)
        for cap in capabilities:
            self.assertIs(
                cap["invocableFromChat"],
                False,
                f"{cap['capabilityId']} claims chat invocation that does not exist",
            )
            self.assertIn(
                cap["invocationSurface"],
                {"api", "browser_ui", "chat_text_only"},
                f"{cap['capabilityId']} has an undocumented surface",
            )

    def test_browser_capability_points_at_the_real_surface(self):
        browser = next(
            c for c in self.payload["capabilities"] if c["capabilityId"] == "cap-browser"
        )
        self.assertEqual(browser["invocationSurface"], "browser_ui")
        self.assertIn("/api/browser/automation", browser["purpose"])
        # The old copy advertised cookie capture + bot-protection bypass as if a
        # chat turn could do it.
        self.assertNotIn("bypass bot protections", browser["purpose"])

    def test_code_capability_does_not_promise_a_sandbox(self):
        code = next(c for c in self.payload["capabilities"] if c["capabilityId"] == "cap-code")
        self.assertEqual(code["invocationSurface"], "chat_text_only")
        self.assertIn("No sandbox", code["unavailableReason"])
