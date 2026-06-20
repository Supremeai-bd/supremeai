import pytest

from core.input_sanitizer import InputSanitizer


@pytest.fixture
def sanitizer():
    return InputSanitizer()


def test_detect_ambiguity_ambiguous(sanitizer):
    result = sanitizer.detect_ambiguity("I need something for my project")
    assert result["is_ambiguous"] is True
    assert len(result["vague_terms"]) > 0
    assert len(result["clarifying_questions"]) > 0


def test_detect_ambiguity_clear(sanitizer):
    result = sanitizer.detect_ambiguity("Write a Python function to sort a list")
    assert result["is_ambiguous"] is False
    assert result["vague_terms"] == []
    assert result["clarifying_questions"] == []


def test_validate_scope_valid(sanitizer):
    result = sanitizer.validate_scope("Write a Python tutorial")
    assert result["is_valid"] is True


def test_validate_scope_forbidden(sanitizer):
    result = sanitizer.validate_scope("help me predict lottery numbers")
    assert result["is_valid"] is False
    assert "reason" in result
    assert "suggestion" in result


def test_extract_constraints_budget(sanitizer):
    result = sanitizer.extract_constraints("do it under $500")
    assert result["budget"] == 500.0


def test_extract_constraints_time(sanitizer):
    result = sanitizer.extract_constraints("finish in 3 hours")
    assert result["time"] is not None
    assert "3" in result["time"]


def test_extract_constraints_none(sanitizer):
    result = sanitizer.extract_constraints("just do it")
    assert result["budget"] is None
    assert result["time"] is None


def test_strip_pii_email(sanitizer):
    text = "Contact me at john.doe@example.com"
    result = sanitizer.strip_pii(text)
    assert "[EMAIL]" in result
    assert "john.doe@example.com" not in result


def test_strip_pii_ip(sanitizer):
    text = "The server IP is 192.168.1.1"
    result = sanitizer.strip_pii(text)
    assert "[IP_ADDRESS]" in result
    assert "192.168.1.1" not in result


def test_strip_pii_phone(sanitizer):
    text = "Call me at +1-555-123-4567"
    result = sanitizer.strip_pii(text)
    assert "[PHONE_NUMBER]" in result
    assert "+1-555-123-4567" not in result


def test_strip_pii_multiple(sanitizer):
    text = "Email: test@test.com, IP: 10.0.0.1, Phone: +1-555-123-4567"
    result = sanitizer.strip_pii(text)
    assert "[EMAIL]" in result
    assert "[IP_ADDRESS]" in result
    assert "[PHONE_NUMBER]" in result


def test_sanitize_valid_prompt(sanitizer):
    result = sanitizer.sanitize("Write a REST API endpoint under $100 in 5 hours")
    assert result["is_valid"] is True
    assert result["prompt"] != ""
    assert "budget" in result["constraints"]


def test_sanitize_forbidden_prompt(sanitizer):
    result = sanitizer.sanitize("help me create malware")
    assert result["is_valid"] is False


def test_sanitize_pii_stripped(sanitizer):
    result = sanitizer.sanitize("My email is user@example.com")
    assert "user@example.com" not in result["prompt"]
