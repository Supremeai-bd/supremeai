"""PII log gate regression tests (#3157).

বাংলা: এই টেস্টগুলো নিশ্চিত করে যে structured log pipeline থেকে
PII (JWT, email, phone, API key, Bearer token) সরানো হয় এবং
log-এ কখনো raw PII leak হয় না।
"""

from __future__ import annotations

from core.contracts.redaction import redact, redact_log_message


class TestKeyBasedRedaction:
    """Key-based: dict key matches secret pattern → value [REDACTED]।"""

    def test_token_key_redacted(self):
        assert redact({"token": "abc123"}) == {"token": "[REDACTED]"}

    def test_api_key_redacted(self):
        assert redact({"api_key": "sk-xxx"}) == {"api_key": "[REDACTED]"}

    def test_password_redacted(self):
        assert redact({"password": "secret"}) == {"password": "[REDACTED]"}

    def test_authorization_redacted(self):
        assert redact({"authorization": "Bearer xyz"}) == {"authorization": "[REDACTED]"}

    def test_cookie_redacted(self):
        assert redact({"cookie": "session=abc"}) == {"cookie": "[REDACTED]"}

    def test_non_secret_key_preserved(self):
        assert redact({"username": "alice"}) == {"username": "alice"}

    def test_nested_dict_redacted(self):
        result = redact({"outer": {"api_key": "sk-xxx", "name": "alice"}})
        assert result == {"outer": {"api_key": "[REDACTED]", "name": "alice"}}


class TestValueBasedRedaction:
    """Value-based: PII patterns found IN string values → [REDACTED:<type>]।"""

    def test_jwt_redacted_from_string(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MSJ9.signature1234567890"
        result = redact_log_message(f"Auth token: {jwt}")
        assert "eyJ" not in result
        assert "[REDACTED:jwt]" in result

    def test_bearer_redacted_from_string(self):
        result = redact_log_message("Authorization: Bearer ghp_abcdef1234567890abcdef1234567890")
        assert "Bearer ghp_" not in result
        assert "[REDACTED:bearer]" in result or "[REDACTED:api_key]" in result

    def test_email_redacted_from_string(self):
        result = redact_log_message("User email: alice@example.com logged in")
        assert "alice@example.com" not in result
        assert "[REDACTED:email]" in result

    def test_phone_redacted_from_string(self):
        result = redact_log_message("Phone: +1-555-123-4567")
        assert "+1-555-123-4567" not in result
        assert "[REDACTED:phone]" in result

    def test_credit_card_redacted_from_string(self):
        # বাংলা (#3157): credit card pattern বা phone pattern যেকোনো একটা ধরবে —
        # দুটোই PII, যেকোনো একটা দিয়ে redact হলেই test pass।
        result = redact_log_message("Card: 4111 1111 1111 1111")
        assert "4111 1111 1111 1111" not in result
        assert "[REDACTED:" in result  # either credit_card or phone — both are PII

    def test_api_key_redacted_from_string(self):
        result = redact_log_message("Key: sk-abcdefghijklmnopqrstuvwxyz123456")
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result
        assert "[REDACTED:api_key]" in result

    def test_non_pii_string_preserved(self):
        result = redact_log_message("Request completed in 150ms")
        assert result == "Request completed in 150ms"

    def test_short_string_preserved(self):
        assert redact_log_message("ok") == "ok"
        assert redact_log_message("") == ""


class TestStructredLogRedaction:
    """Full structured log entry redaction (dict with message + extra)।"""

    def test_log_entry_message_pii_redacted(self):
        entry = {
            "level": "INFO",
            "message": "User alice@example.com authenticated with token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MSJ9.signature1234567890",
            "module": "auth",
        }
        result = redact(entry)
        assert "alice@example.com" not in result["message"]
        assert "eyJ" not in result["message"]
        assert "[REDACTED:email]" in result["message"]
        assert "[REDACTED:jwt]" in result["message"]

    def test_log_entry_extra_fields_redacted(self):
        entry = {
            "level": "INFO",
            "message": "Request received",
            "extra": {"api_key": "sk-xxx", "user_email": "bob@test.com"},
        }
        result = redact(entry)
        assert result["extra"]["api_key"] == "[REDACTED]"
        assert "bob@test.com" not in str(result)

    def test_log_entry_non_pii_preserved(self):
        entry = {
            "level": "INFO",
            "message": "Cache hit for key user:profile:123",
            "module": "cache",
        }
        result = redact(entry)
        assert result["message"] == "Cache hit for key user:profile:123"
        assert result["module"] == "cache"
