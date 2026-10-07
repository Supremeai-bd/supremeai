"""Unit tests for DynamicCredentialBroker (scripts/agents/dynamic_credential_broker.py)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.agents.dynamic_credential_broker import (  # noqa: E402
    FORBIDDEN_KEYS,
    DynamicCredentialBroker,
)


class TestDynamicCredentialBroker(unittest.TestCase):
    def setUp(self):
        self.broker = DynamicCredentialBroker()

    def test_fetch_vault_keys_from_env(self):
        with mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "cf-token-123"}, clear=True):
            keys = self.broker._fetch_vault_keys({"CLOUDFLARE_API_TOKEN"})
            self.assertEqual(keys, {"CLOUDFLARE_API_TOKEN": "cf-token-123"})

    def test_fetch_vault_keys_subprocess_fallback(self):
        mock_proc = mock.MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = (
            "CLOUDFLARE_API_TOKEN=cf-secret-token\n"
            "INFISICAL_CLIENT_SECRET=forbidden-secret\n"
            "# Comment line\n"
            "OTHER_KEY=ignore-me\n"
        )

        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("subprocess.run", return_value=mock_proc) as mock_run:
            keys = self.broker._fetch_vault_keys({"CLOUDFLARE_API_TOKEN"})
            self.assertEqual(keys, {"CLOUDFLARE_API_TOKEN": "cf-secret-token"})
            self.assertNotIn("INFISICAL_CLIENT_SECRET", keys)
            self.assertTrue(mock_run.called)

    def test_activate_watcher_role(self):
        with mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "cf-123"}, clear=True), \
             mock.patch.object(self.broker, "_call_mcp_tower", return_value={"status": "ok"}):
            scoped = self.broker.activate("supremeai-platform-agent[bot]", "watcher")
            self.assertEqual(scoped.get("AGENT_ROLE"), "watcher")
            self.assertEqual(scoped.get("AGENT_NAME"), "supremeai-platform-agent[bot]")
            self.assertEqual(scoped.get("CLOUDFLARE_API_TOKEN"), "cf-123")
            for forbidden in FORBIDDEN_KEYS:
                self.assertNotIn(forbidden, scoped)

    def test_deactivate_agent(self):
        with mock.patch.object(self.broker, "_call_mcp_tower", return_value={"status": "ok"}):
            self.broker.deactivate("supremeai-platform-agent[bot]")


if __name__ == "__main__":
    unittest.main()
