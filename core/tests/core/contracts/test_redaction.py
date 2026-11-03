from core.contracts.redaction import redact


def test_nested_secret_fields_are_redacted():
    value = {
        "token": "secret-value",
        "nested": {"api_key": "key", "safe": "ok"},
        "items": [{"password": "pw"}],
    }
    result = redact(value)
    assert result == {
        "token": "[REDACTED]",
        "nested": {"api_key": "[REDACTED]", "safe": "ok"},
        "items": [{"password": "[REDACTED]"}],
    }
