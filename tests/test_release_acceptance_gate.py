import unittest
from scripts.ci.release_acceptance_gate import validate

class TestReleaseAcceptance(unittest.TestCase):
    def test_local_evidence_passes_with_database_pending(self):
        payload = {"schema_version": "1.0", "database": {"status": "manual_pending"}}
        for key in ("merge_policy", "route_inventory", "route_graph", "preflight_evidence", "security_tests"):
            payload[key] = {"status": "passed"}
        self.assertEqual(validate(payload), [])

    def test_live_database_cannot_be_claimed_locally(self):
        payload = {"schema_version": "1.0", "database": {"status": "passed"}}
        for key in ("merge_policy", "route_inventory", "route_graph", "preflight_evidence", "security_tests"):
            payload[key] = {"status": "passed"}
        self.assertIn("manual_pending", " ".join(validate(payload)))

if __name__ == "__main__":
    unittest.main()
