import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure test signing secret is present before keygen runs
os.environ.setdefault("SUPREMEAI_MASTER_KEY", "test-master-key-for-stealth-webhook-suite")

from service.app import app
from service.keygen import generate_key
import service.app as app_module


class StealthWebhookPriorityTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.auth_key = generate_key("test", "standard")
        self.auth_headers = {"Authorization": f"Bearer {self.auth_key}"}

    def test_healthz_contains_stealth_and_web_flags(self):
        with patch.object(app_module, "STEALTH_WEBHOOK_URL", "https://stealth-runner.internal/v1/generate"):
            resp = self.client.get("/healthz")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data.get("status"), "healthy")
            self.assertTrue(data.get("chat_ready"))

    @patch("service.app.forward_stealth_webhook")
    def test_priority1_stealth_webhook_success(self, mock_forward):
        with patch.object(app_module, "STEALTH_WEBHOOK_URL", "https://stealth-runner.internal/v1/generate"):
            mock_forward.return_value = (
                200,
                {
                    "id": "chatcmpl-mock-123",
                    "object": "chat.completion",
                    "created": 123456789,
                    "model": "stealth-priority1",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Stealth response success"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

            resp = self.client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "Hello"}]},
                headers=self.auth_headers,
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get("x-supremeai-provider"), "stealth-webhook")
            self.assertEqual(resp.headers.get("x-supremeai-slot"), "priority-1")
            data = resp.json()
            self.assertEqual(data["choices"][0]["message"]["content"], "Stealth response success")
            mock_forward.assert_called_once()

    @patch("service.app.forward_stealth_webhook")
    def test_priority1_stealth_timeout_fails_closed_without_api_fallback(self, mock_stealth):
        """Per admin mandate, API-key fallback is disabled so a webhook timeout returns 502 honestly."""
        with patch.object(app_module, "STEALTH_WEBHOOK_URL", "https://stealth-runner.internal/v1/generate"):
            mock_stealth.return_value = (504, {"error": "Stealth webhook timed out"})

            resp = self.client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "Hello"}]},
                headers=self.auth_headers,
            )
            self.assertEqual(resp.status_code, 502)
            self.assertIn("Stealth webhook timed out", resp.json().get("detail", ""))
            mock_stealth.assert_called_once()

    def test_unconfigured_stealth_webhook_returns_503(self):
        with patch.object(app_module, "STEALTH_WEBHOOK_URL", ""):
            resp = self.client.post(
                "/v1/chat/completions",
                json={"model": "supremeai/ghost_gemini", "messages": [{"role": "user", "content": "Test prompt"}]},
                headers=self.auth_headers,
            )
            self.assertEqual(resp.status_code, 503)
            self.assertIn("Stealth Webhook relay is currently unconfigured", resp.json().get("detail", ""))

    @patch("service.app.forward_stealth_webhook")
    def test_stealth_webhook_raw_reply_wrapping(self, mock_stealth):
        """Verify raw {'reply': '...'} payloads from /api/chat style webhooks are auto-wrapped to OpenAI format."""
        with patch.object(app_module, "STEALTH_WEBHOOK_URL", "https://stealth-runner.internal/v1/generate"):
            mock_stealth.return_value = (200, {"reply": "Wrapped stealth reply"})

            resp = self.client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "Test raw wrap"}]},
                headers=self.auth_headers,
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["choices"][0]["message"]["content"], "Wrapped stealth reply")


if __name__ == "__main__":
    unittest.main()
