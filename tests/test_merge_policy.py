import json
import unittest
from pathlib import Path

from scripts.ci.merge_policy import classify_result, load_policy, record_decision


class MergePolicyTests(unittest.TestCase):
    def test_policy_registry_is_valid_and_advisory(self):
        policy = load_policy()
        self.assertEqual(policy["mode"], "advisory")
        self.assertEqual(policy["default_fail_on"], "HIGH")
        self.assertIn("secrets", policy["checks"])

    def test_failed_check_is_classified_without_blocking_in_advisory_mode(self):
        item = classify_result("tsc", "ts", "FAIL", 3, load_policy())
        self.assertEqual(item["classification"], "failure")
        self.assertEqual(item["severity"], "HIGH")
        self.assertFalse(item["blocking"])

    def test_pass_and_warning_classification(self):
        policy = load_policy()
        self.assertEqual(classify_result("ruff", "ruff", "PASS", 0, policy)["classification"], "pass")
        self.assertEqual(classify_result("ruff", "ruff", "WARN", 2, policy)["classification"], "warning")

    def test_decision_log_is_structured_jsonl(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "decisions.jsonl"
            record_decision("PASS WITH WARNINGS", [{"check": "ruff", "blocking": False}], path=target)
            entry = json.loads(target.read_text().strip())
            self.assertEqual(entry["verdict"], "PASS WITH WARNINGS")
            self.assertEqual(entry["blocking_count"], 0)


if __name__ == "__main__":
    unittest.main()
