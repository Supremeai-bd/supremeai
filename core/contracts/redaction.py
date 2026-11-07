"""Secret-safe evidence serialization and PII log redaction (#3157)."""

from __future__ import annotations

import re
from typing import Any

_SECRET_KEY = re.compile(
    r"(token|secret|password|api[_-]?key|authorization|private[_-]?key|credential|cookie)",
    re.I,
)

_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    (
        "bearer",
        re.compile(r"\bBearer\s+[A-Za-z0-9_.\-~+/=]{8,}\b", re.I),
    ),
    (
        "api_key",
        re.compile(r"\b(?:sk|ghp|gho|ghu|ghs|ghr|glpat|xoxb|xoxp)-[A-Za-z0-9_\-]{12,}\b"),
    ),
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "credit_card",
        re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    ),
    (
        "phone",
        re.compile(r"(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"),
    ),
)


def redact_log_message(message: str) -> str:
    """Redact inline PII patterns (JWT, Bearer, API key, email, card, phone) from strings."""
    if not isinstance(message, str) or len(message) < 6:
        return message
    out = message
    for label, pattern in _PII_PATTERNS:
        out = pattern.sub(f"[REDACTED:{label}]", out)
    return out


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _SECRET_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_log_message(value)
    return value


__all__ = ["redact", "redact_log_message"]
