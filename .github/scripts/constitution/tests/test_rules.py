"""Unit tests for deterministic Constitution rules."""

from pathlib import Path
import tempfile
import unittest

from constitution.rules.arch001_no_local_machine import NoLocalMachineRule
from constitution.rules.rel001_no_silent_failure import NoSilentFailureRule
from constitution.rules.sec002_no_secret_hardcoding import NoSecretHardcodingRule


class ConstitutionRuleTests(unittest.TestCase):
    def audit_text(self, filename: str, content: str, rule):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / filename
            path.write_text(content, encoding="utf-8")
            return rule.audit([path])

    def test_localhost_is_allowed_in_test_files(self):
        findings = self.audit_text(
            "test_service.py",
            "BASE_URL = 'http://localhost:8000'\n",
            NoLocalMachineRule(),
        )
        self.assertEqual(findings, [])

    def test_localhost_is_blocked_in_production_code(self):
        findings = self.audit_text(
            "service.py",
            "BASE_URL = 'http://localhost:8000'\n",
            NoLocalMachineRule(),
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "ARCH-001")

    def test_silent_python_exception_is_blocked(self):
        findings = self.audit_text(
            "service.py",
            "try:\n    run()\nexcept Exception:\n    pass\n",
            NoSilentFailureRule(),
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "REL-001")

    def test_logging_exception_is_allowed(self):
        findings = self.audit_text(
            "service.py",
            "try:\n    run()\nexcept Exception:\n    logger.exception('failed')\n",
            NoSilentFailureRule(),
        )
        self.assertEqual(findings, [])

    def test_hardcoded_secret_is_blocked(self):
        findings = self.audit_text(
            "service.py",
            "api_key = 'sk_live_123456789012345678901234'\n",
            NoSecretHardcodingRule(),
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "SEC-002")

    def test_test_secret_is_allowed(self):
        findings = self.audit_text(
            "service.py",
            "api_key = 'sk_test_mock_123456789012345678901234'\n",
            NoSecretHardcodingRule(),
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
