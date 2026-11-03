# tests/test_adversarial_security.py
from backend.agents.skill_ingestor import SkillIngestor


def test_static_ast_safety_catches_dangerous_calls():
    ingestor = SkillIngestor()
    dangerous_payload = "import subprocess; subprocess.Popen('sh')"
    is_safe, msg = ingestor.static_ast_safety_check(dangerous_payload)
    assert is_safe is False
    assert "Forbidden import found" in msg
