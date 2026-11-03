import unittest
from fastapi.testclient import TestClient
from service.app import app
from service.pool import squad, KeySlot
from service.keygen import generate_key, verify_key

class GatewayEndpointsTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_healthz(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service_name"], "supremeai-api")
        self.assertIn("total_keys", data)

    def test_models_endpoint(self):
        resp = self.client.get("/v1/models")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["object"], "list")
        model_ids = [m["id"] for m in data["data"]]
        self.assertIn("auto", model_ids)
        self.assertIn("supremeai/gemini", model_ids)
        self.assertIn("supremeai/groq", model_ids)

    def test_keygen_and_verification(self):
        # 1. Generate client key
        client_key = generate_key(client_name="test-agent", quota="tier-unlimited")
        self.assertTrue(client_key.startswith("sk-supreme-test-agent."))

        # 2. Verify key statelessly
        meta = verify_key(client_key)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["client"], "test-agent")
        self.assertEqual(meta["quota"], "tier-unlimited")

        # 3. Forged key verification
        bad_key = client_key[:-4] + "zzzz"
        self.assertIsNone(verify_key(bad_key))

    def test_pool_cooldown_mechanism(self):
        pool = squad.pools["gemini"]
        slot = KeySlot(name="TEST_KEY", key="test-key-123", provider="gemini")
        pool.slots = [slot]
        self.assertTrue(slot.is_healthy)

        # Report 429 error
        pool.report_injury(slot, 429)
        self.assertFalse(slot.is_healthy)
        self.assertGreater(slot.cooldown_until, 0)
        self.assertEqual(slot.total_errors, 1)

if __name__ == "__main__":
    unittest.main()
