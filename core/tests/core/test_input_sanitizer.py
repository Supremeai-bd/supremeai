"""Tests for core.security.input_sanitizer — InputSanitizer standalone module."""

import pytest

from core.security.input_sanitizer import InputSanitizer


@pytest.fixture
def sanitizer():
    return InputSanitizer()


class TestAmbiguityDetection:
    """Tests for detect_ambiguity method."""

    def test_no_ambiguity(self, sanitizer):
        result = sanitizer.detect_ambiguity("write a Python function to sort a list")
        assert result["is_ambiguous"] is False
        assert result["vague_terms"] == []

    def test_vague_something(self, sanitizer):
        result = sanitizer.detect_ambiguity("do something with the data")
        assert result["is_ambiguous"] is True
        assert any("something" in term for term in result["vague_terms"])

    def test_vague_anything(self, sanitizer):
        result = sanitizer.detect_ambiguity("can you do anything about this")
        assert result["is_ambiguous"] is True

    def test_vague_etc(self, sanitizer):
        result = sanitizer.detect_ambiguity("use python, javascript, etc")
        assert result["is_ambiguous"] is True

    def test_multiple_vague_terms(self, sanitizer):
        result = sanitizer.detect_ambiguity("do something or anything with etc")
        assert len(result["vague_terms"]) >= 2

    def test_clarifying_questions_present(self, sanitizer):
        result = sanitizer.detect_ambiguity("something")
        assert len(result["clarifying_questions"]) > 0


class TestScopeValidation:
    """Tests for validate_scope method."""

    def test_valid_scope(self, sanitizer):
        result = sanitizer.validate_scope("write a Python script")
        assert result["is_valid"] is True

    def test_forbidden_lottery(self, sanitizer):
        result = sanitizer.validate_scope("predict lottery numbers")
        assert result["is_valid"] is False

    def test_forbidden_hack(self, sanitizer):
        result = sanitizer.validate_scope("hack into database")
        assert result["is_valid"] is False

    def test_forbidden_fake_news(self, sanitizer):
        result = sanitizer.validate_scope("generate fake news article")
        assert result["is_valid"] is False

    def test_forbidden_malware(self, sanitizer):
        result = sanitizer.validate_scope("create malware")
        assert result["is_valid"] is False

    def test_forbidden_impersonate(self, sanitizer):
        result = sanitizer.validate_scope("impersonate real person")
        assert result["is_valid"] is False

    def test_suggestion_present_on_block(self, sanitizer):
        result = sanitizer.validate_scope("generate fake news")
        assert "suggestion" in result


class TestConstraintsExtraction:
    """Tests for extract_constraints method."""

    def test_extract_budget(self, sanitizer):
        result = sanitizer.extract_constraints("build this under $500")
        assert result["budget"] == 500.0

    def test_extract_time_hours(self, sanitizer):
        result = sanitizer.extract_constraints("complete in 3 hours")
        assert result["time"] is not None

    def test_extract_time_days(self, sanitizer):
        result = sanitizer.extract_constraints("finish in 7 days")
        assert result["time"] is not None

    def test_extract_no_constraints(self, sanitizer):
        result = sanitizer.extract_constraints("build this project")
        assert result["budget"] is None
        assert result["time"] is None


class TestPIIStrip:
    """Tests for strip_pii method."""

    def test_strip_email(self, sanitizer):
        result = sanitizer.strip_pii("email me at test@example.com")
        assert "test@example.com" not in result
        assert "[EMAIL]" in result

    def test_strip_ip(self, sanitizer):
        result = sanitizer.strip_pii("server at 192.168.1.1")
        assert "192.168.1.1" not in result
        assert "[IP_ADDRESS]" in result

    def test_strip_phone(self, sanitizer):
        result = sanitizer.strip_pii("call me at +8801712345678")
        assert "+8801712345678" not in result

    def test_strip_multiple_pii(self, sanitizer):
        text = "email: test@test.com, ip: 10.0.0.1"
        result = sanitizer.strip_pii(text)
        assert "[EMAIL]" in result
        assert "[IP_ADDRESS]" in result

    def test_no_pii_preserved(self, sanitizer):
        text = "Hello, this is a normal message"
        result = sanitizer.strip_pii(text)
        assert result == text


class TestSanitizePipeline:
    """Tests for the full sanitize method."""

    def test_sanitize_clean_input(self, sanitizer):
        result = sanitizer.sanitize("write a Python script")
        assert result["is_valid"] is True
        assert result["is_ambiguous"] is False

    def test_sanitize_invalid_scope(self, sanitizer):
        result = sanitizer.sanitize("predict lottery numbers")
        assert result["is_valid"] is False
        assert "reason" in result

    def test_sanitize_strips_pii(self, sanitizer):
        result = sanitizer.sanitize("email test@example.com for help")
        assert result["is_valid"] is True
        assert "[EMAIL]" in result["prompt"]

    def test_sanitize_detects_ambiguity(self, sanitizer):
        result = sanitizer.sanitize("do something")
        assert result["is_ambiguous"] is True
        assert len(result["clarifying_questions"]) > 0

    def test_sanitize_extracts_constraints(self, sanitizer):
        result = sanitizer.sanitize("build this under $1000")
        assert result["constraints"]["budget"] == 1000.0
