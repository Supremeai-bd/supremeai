"""Secret-safe evidence serialization + PII redaction (#3157).

বাংলা: এই মডিউল দুই স্তরে redaction করে:
  ১. Key-based: dict key-এ token/secret/password/api_key থাকলে value [REDACTED]
  ২. Value-based: string value-তে email/phone/JWT/bearer/API-key প্যাটার্ন
     থাকলে সেগুলো [REDACTED:<type>] দিয়ে replace হয়।

এটি logging pipeline + evidence serialization উভয় জায়গায় ব্যবহার হয়।
"""

from __future__ import annotations

import re
from typing import Any

# ── Key-based: dict key matches → value fully redacted ──
_SECRET_KEY = re.compile(
    r"(token|secret|password|api[_-]?key|authorization|private[_-]?key|credential|cookie|session)",
    re.I,
)

# ── Value-based: PII patterns found IN string values → redacted in-place ──
# বাংলা (#3157): প্রতিটি pattern একটি named group; replace করে [REDACTED:<type>]
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # JWT tokens (three base64 segments separated by dots)
    ("jwt", re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b")),
    # Bearer tokens
    ("bearer", re.compile(r"\bBearer\s+[a-zA-Z0-9_.\-]{20,}", re.I)),
    # API keys (common formats: sk-..., ghp_..., ghs_..., etc.)
    ("api_key", re.compile(r"\b(sk-[a-zA-Z0-9]{20,}|gh[pst]_[a-zA-Z0-9]{20,}|gho_[a-zA-Z0-9]{20,}|AKIA[A-Z0-9]{12,})\b")),
    # Email addresses
    ("email", re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")),
    # Phone numbers (international + local formats)
    ("phone", re.compile(r"\b\+?\d{1,3}?[-.\s]?\(?\d{1,4}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")),
    # Credit card numbers (13-19 digit groups)
    ("credit_card", re.compile(r"\b(?:\d{4}[-\s]?){3}\d{1,4}\b")),
    # Authorization headers in serialized strings
    ("auth_header", re.compile(r"(authorization|auth)\s*[:=]\s*[\"']?[a-zA-Z0-9_.\-]{20,}[\"']?", re.I)),
    # Cookie values
    ("cookie", re.compile(r"\b(cookie|set-cookie)\s*[:=]\s*[\"']?[a-zA-Z0-9_+/=.\-]{20,}[\"']?", re.I)),
]


def _redact_string(text: str) -> str:
    """Apply all PII value patterns to a string, replacing matches with [REDACTED:<type>]."""
    if not text or len(text) < 5:
        return text
    for pii_type, pattern in _PII_PATTERNS:
        text = pattern.sub(f"[REDACTED:{pii_type}]", text)
    return text


def redact(value: Any) -> Any:
    """Recursively redact secrets + PII from any data structure.

    বাংলা: dict key এ secret-marker থাকলে value [REDACTED] হয়।
    string value-তে PII pattern (JWT, email, phone, API key) থাকলে
    in-place replace হয় [REDACTED:<type>] দিয়ে।
    """
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
        return _redact_string(value)
    return value


def redact_log_message(msg: str) -> str:
    """Redact PII from a log message string (#3157).

    বাংলা: এটি loguru/stdlib logging filter থেকে call হয়। প্রতিটি
    log message থেকে JWT/email/phone/API-key/Bearer সরানো হয়।
    """
    return _redact_string(msg)


__all__ = ["redact", "redact_log_message"]
