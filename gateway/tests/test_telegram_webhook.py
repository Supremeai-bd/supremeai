import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from service.app import app

class TelegramWebhookTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_telegram_status_endpoint(self):
        resp = self.client.get("/webhook/telegram/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "active")
        self.assertIn("triggers", data)
        self.assertIn("/spark", data["triggers"])

    def test_non_text_or_empty_update(self):
        resp = self.client.post("/webhook/telegram", json={})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ignored_non_text"})

    def test_non_triggered_message_passthrough(self):
        update = {
            "message": {
                "message_id": 100,
                "chat": {"id": 12345, "type": "group"},
                "text": "Regular user chat without any trigger tags"
            }
        }
        resp = self.client.post("/webhook/telegram", json=update)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "passthrough"})

    @patch("service.telegram_webhook._process_and_reply", new_callable=AsyncMock)
    def test_spark_triggered_message_accepted(self, mock_process):
        update = {
            "message": {
                "message_id": 101,
                "chat": {"id": 12345},
                "text": "/spark latency optimization roadmap"
            }
        }
        resp = self.client.post("/webhook/telegram", json=update)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "accepted"})
        mock_process.assert_called_once_with(12345, "/spark latency optimization roadmap", 101)

if __name__ == "__main__":
    unittest.main()
