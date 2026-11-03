import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from service.app import app
from service.pool import squad, KeySlot
from service.keygen import generate_key
from service.providers.web_session import WebSessionAccount, web_bridge
import service.app as app_module


class StealthWebhookPriorityTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.auth_key = generate_key("test", "standard")
        self.auth_headers = {"Authorization": f"Bearer {self.auth_key}"}

    def test_healthz_contains_stealth_and_web_flags(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("stealth_priority1_configured", data)
        self.assertIn("web_sessions_active", data)
        self.assertIn("web_session_status", data)

    @patch("service.app.forward_stealth_webhook")
    def test_priority1_stealth_webhook_success(self, mock_forward):
        # Configure stealth webhook URL
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
                            "finish_reason": "stop"
                        }
                    ]
                }
            )

            resp = self.client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "Hello"}]},
                headers=self.auth_headers
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get("x-supremeai-provider"), "stealth-webhook")
            self.assertEqual(resp.headers.get("x-supremeai-slot"), "priority-1")
            data = resp.json()
            self.assertEqual(data["choices"][0]["message"]["content"], "Stealth response success")
            mock_forward.assert_called_once()

    @patch("service.app.forward_chat_completion")
    @patch("service.app.forward_stealth_webhook")
    def test_priority1_stealth_fallback_to_priority2_squad(self, mock_stealth, mock_squad):
        with patch.object(app_module, "STEALTH_WEBHOOK_URL", "https://stealth-runner.internal/v1/generate"):
            mock_stealth.return_value = (504, {"error": "Stealth webhook timed out"})

            mock_squad.return_value = (
                200,
                {
                    "id": "chatcmpl-squad-456",
                    "object": "chat.completion",
                    "created": 123456789,
                    "model": "llama-3.3-70b-versatile",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Squad fallback response"},
                            "finish_reason": "stop"
                        }
                    ]
                }
            )

            gemini_pool = squad.pools["gemini"]
            test_slot = KeySlot(name="GEMINI_FALLBACK", key="test-key", provider="gemini")
            gemini_pool.slots = [test_slot]

            resp = self.client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "Hello"}]},
                headers=self.auth_headers
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get("x-supremeai-provider"), "gemini")
            self.assertEqual(resp.headers.get("x-supremeai-slot"), "GEMINI_FALLBACK")
            data = resp.json()
            self.assertEqual(data["choices"][0]["message"]["content"], "Squad fallback response")
            mock_stealth.assert_called_once()
            mock_squad.assert_called_once()

    def test_native_web_session_direct(self):
        # Register a mock active account in web_bridge
        with patch.object(app_module, "STEALTH_WEBHOOK_URL", ""):
            mock_acc = WebSessionAccount(provider="gemini", token="test-cookie", label="test_gemini")
            web_bridge.accounts = [mock_acc]

            resp = self.client.post(
                "/v1/chat/completions",
                json={"model": "supremeai/ghost_gemini", "messages": [{"role": "user", "content": "Test prompt"}]},
                headers=self.auth_headers
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("choices", data)
            self.assertIn("GEMINI Web Session Active", data["choices"][0]["message"]["content"])

    @patch("service.app.forward_chat_completion")
    @patch("service.app.forward_stealth_webhook")
    def test_multi_model_consensus_endpoint(self, mock_stealth, mock_squad):
        with patch.object(app_module, "STEALTH_WEBHOOK_URL", "https://stealth-runner.internal/v1/generate"):
            mock_stealth.return_value = (
                200,
                {"id": "c1", "object": "chat.completion", "choices": [{"message": {"content": "Web reply"}}]}
            )
            mock_squad.return_value = (
                200,
                {"id": "c2", "object": "chat.completion", "choices": [{"message": {"content": "Cloud reply"}}]}
            )

            # Ensure groq and gemini have candidate slots
            squad.pools["groq"].slots = [KeySlot(name="GROQ_TEST", key="g-key", provider="groq")]
            squad.pools["gemini"].slots = [KeySlot(name="GEMINI_TEST", key="gem-key", provider="gemini")]

            resp = self.client.post(
                "/v1/consensus",
                json={"messages": [{"role": "user", "content": "Compare roadmaps"}]},
                headers=self.auth_headers
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "success")
            self.assertGreaterEqual(data["consensus_count"], 1)
            self.assertEqual(len(data["responses"]), 3)


if __name__ == "__main__":
    unittest.main()
