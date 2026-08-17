# tests/test_adversarial_security.py
import pytest
from backend.agents.ephemeral_executor import EphemeralExecutor
from backend.agents.skill_ingestor import SkillIngestor


def test_path_traversal_injection_aborts_immediately():
    executor = EphemeralExecutor()
    # হ্যাকার যদি '../' দিয়ে সিস্টেমে ফাইল মোছার বা বাইরে যাওয়ার চেষ্টা করে
    result = executor.execute_use_and_throw("../etc/malicious", "print('hack')", "{}")
    assert result.exit_code == -1
    assert "Blocked" in result.stderr


def test_static_ast_safety_catches_dangerous_calls():
    ingestor = SkillIngestor()
    dangerous_payload = "import subprocess; subprocess.Popen('sh')"
    is_safe, msg = ingestor.static_ast_safety_check(dangerous_payload)
    assert is_safe is False
    assert "Forbidden import found" in msg
