"""
Utility and Helper Functions Test Suite
==========================================

Tests for common utility functions, helpers, and shared logic
used throughout the SupremeAI application.

Test Coverage:
- String validation and sanitization
- Date/time utilities
- ID generation and validation
- Data transformation helpers
- Security utilities
- Formatting functions

Run with: pytest tests/test_utils.py -v --cov=utils
"""

import asyncio
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Optional, Union
from unittest.mock import AsyncMock, MagicMock

import pytest

# ============================================================================
# MOCK UTILITIES MODULE (for testing)
# ============================================================================


class MockStringUtils:
    """String utility functions."""

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email format."""
        if not email:
            return False

        import re

        # ROOT-CAUSE FIX: আগের প্যাটার্নে (a) TLD-তে অন্তত ২টা letter লাগত, তাই
        # সংখ্যাসূচক/১-অক্ষরের TLD ("123@456.789", "a@b.c") reject হতো যদিও
        # test এগুলোকে valid ধরে; (b) consecutive dots ("user..name@...")
        # block করার কোনো লজিক ছিল না, তাই সেটা ভুলভাবে accept হতো। নতুন
        # প্যাটার্নে negative lookahead দিয়ে ডাবল-ডট আটকানো হলো এবং TLD-তে
        # alphanumeric (সংখ্যাসহ) অনুমোদন করা হলো।
        pattern = (
            r"^(?!.*\.\.)[a-zA-Z0-9][a-zA-Z0-9._%+-]*"
            r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?"
            r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*"
            r"\.[a-zA-Z0-9]+$"
        )
        return bool(re.match(pattern, email))

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Validate URL format."""
        if not url:
            return False

        import re

        pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        return bool(re.match(pattern, url))

    @staticmethod
    def is_valid_uuid(value: str, version: int = 4) -> bool:
        """Validate UUID format."""
        if not value:
            return False

        try:
            import uuid

            parsed = uuid.UUID(value, version=version)
            return str(parsed) == value.lower()
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def sanitize_string(
        text: str,
        max_length: int | None = None,
        strip_html: bool = True,
        normalize_whitespace: bool = True,
    ) -> str:
        """Sanitize string input."""
        if not text:
            return ""

        result = text

        # Strip HTML tags
        if strip_html:
            import re

            result = re.sub(r"<[^>]+>", "", result)

        # Normalize whitespace
        if normalize_whitespace:
            import re

            result = re.sub(r"\s+", " ", result).strip()

        # Truncate to max length
        if max_length and len(result) > max_length:
            result = result[: max_length - 3] + "..."

        return result

    @staticmethod
    def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """Truncate text to specified length with suffix."""
        if not text or len(text) <= max_length:
            return text or ""

        return text[: max_length - len(suffix)] + suffix

    @staticmethod
    def slugify(text: str, max_length: int = 50) -> str:
        """Convert text to URL-safe slug."""
        if not text:
            return ""

        import re

        # Convert to lowercase
        slug = text.lower()
        # Replace non-alphanumeric with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        # Truncate
        if len(slug) > max_length:
            slug = slug[:max_length].rstrip("-")

        return slug or "untitled"

    @staticmethod
    def mask_sensitive_value(value: str, visible_chars: int = 4, mask_char: str = "*") -> str:
        """Mask sensitive value showing only first/last chars."""
        if not value or len(value) <= visible_chars * 2:
            return value or ""

        prefix = value[:visible_chars]
        suffix = value[-visible_chars:]
        masked_length = len(value) - visible_chars * 2

        return f"{prefix}{mask_char * masked_length}{suffix}"


class MockDateUtils:
    """Date and time utility functions."""

    @staticmethod
    def is_iso_datetime(value: str) -> bool:
        """Check if string is valid ISO datetime."""
        if not value:
            return False

        try:
            # Handle both with and without timezone
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"

            datetime.fromisoformat(value)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def format_datetime(
        dt: datetime | str, format_str: str = "%Y-%m-%d %H:%M:%S", timezone_aware: bool = True
    ) -> str:
        """Format datetime object or ISO string."""
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))

        if timezone_aware and dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        return dt.strftime(format_str)

    @staticmethod
    def format_relative_time(past_dt: datetime | str) -> str:
        """Format datetime as relative time (e.g., '2 hours ago')."""
        if isinstance(past_dt, str):
            past_dt = datetime.fromisoformat(past_dt.replace("Z", "+00:00"))

        now = datetime.now(UTC)
        if past_dt.tzinfo is None:
            past_dt = past_dt.replace(tzinfo=UTC)

        delta = now - past_dt

        seconds = delta.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif seconds < 31536000:
            months = int(seconds / 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(seconds / 31536000)
            return f"{years} year{'s' if years != 1 else ''} ago"

    @staticmethod
    def get_time_range(period: str) -> tuple:
        """Get start/end datetime tuple for a period string."""
        now = datetime.now(UTC)

        ranges = {
            "hour": (now - timedelta(hours=1), now),
            "day": (now - timedelta(days=1), now),
            "week": (now - timedelta(weeks=1), now),
            "month": (now - timedelta(days=30), now),
            "year": (now - timedelta(days=365), now),
            "all": (now - timedelta(days=365 * 10), now),  # 10 years
        }

        if period not in ranges:
            raise ValueError(f"Invalid period: {period}. Must be one of {list(ranges.keys())}")

        return ranges[period]


class MockSecurityUtils:
    """Security-related utility functions."""

    @staticmethod
    def generate_random_token(length: int = 32) -> str:
        """Generate cryptographically secure random token."""
        import secrets

        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def generate_api_key(prefix: str = "sk-", length: int = 32) -> str:
        """Generate API key with prefix."""
        token = MockSecurityUtils.generate_random_token(length)
        return f"{prefix}{token}"

    @staticmethod
    def hash_value(value: str, salt: str | None = None) -> str:
        """Hash a value using SHA-256."""
        import hashlib

        salt = salt or "default-salt"
        return hashlib.sha256(f"{salt}{value}".encode()).hexdigest()

    @staticmethod
    def detect_pii(text: str) -> dict[str, list[str]]:
        """Detect potential PII in text."""
        import re

        findings = {
            "emails": [],
            "phones": [],
            "ssn": [],
            "credit_cards": [],
            "ip_addresses": [],
        }

        # Email patterns
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        findings["emails"] = re.findall(email_pattern, text)

        # Phone patterns (US format)
        phone_pattern = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        findings["phones"] = re.findall(phone_pattern, text)

        # SSN pattern
        ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
        findings["ssn"] = re.findall(ssn_pattern, text)

        # Credit card pattern
        cc_pattern = r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"
        findings["credit_cards"] = re.findall(cc_pattern, text)

        # IP address pattern
        ip_pattern = r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
        findings["ip_addresses"] = re.findall(ip_pattern, text)

        return findings

    @staticmethod
    def redact_pii(text: str, replacement: str = "[REDACTED]") -> str:
        """Redact detected PII from text."""
        pii = MockSecurityUtils.detect_pii(text)
        result = text

        for pii_type, matches in pii.items():
            for match in matches:
                result = result.replace(match, replacement)

        return result


class MockDataUtils:
    """Data transformation and validation utilities."""

    @staticmethod
    def deep_get(data: dict[str, Any], keys: list[str], default: Any = None) -> Any:
        """Safely get nested dictionary value."""
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    @staticmethod
    def safe_int(
        value: Any, default: int = 0, min_val: int | None = None, max_val: int | None = None
    ) -> int:
        """Safely convert to integer with bounds checking."""
        try:
            result = int(value)

            if min_val is not None and result < min_val:
                return min_val

            if max_val is not None and result > max_val:
                return max_val

            return result
        except (TypeError, ValueError):
            return default

    @staticmethod
    def safe_float(
        value: Any,
        default: float = 0.0,
        min_val: float | None = None,
        max_val: float | None = None,
    ) -> float:
        """Safely convert to float with bounds checking."""
        try:
            result = float(value)

            if min_val is not None and result < min_val:
                return min_val

            if max_val is not None and result > max_val:
                return max_val

            return round(result, 6)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def safe_bool(value: Any, default: bool = False) -> bool:
        """Safely convert to boolean."""
        if value is None:
            return default

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")

        if isinstance(value, (int, float)):
            return value > 0

        return default

    @staticmethod
    def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
        """Split list into chunks of specified size."""
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")

        return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]

    @staticmethod
    def flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = ".") -> dict[str, Any]:
        """Flatten nested dictionary with dot notation."""
        items = []

        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k

            if isinstance(v, dict):
                items.extend(MockDataUtils.flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))

        return dict(items)


# ============================================================================
# TEST CLASS: String Utilities
# ============================================================================


class TestStringUtils:
    """Tests for string utility functions."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_is_valid_email_valid(self):
        """Should accept valid email formats."""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "123@456.789",
            "a@b.c",
        ]

        for email in valid_emails:
            assert MockStringUtils.is_valid_email(email), f"Should accept: {email}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_is_valid_email_invalid(self):
        """Should reject invalid email formats."""
        invalid_emails = [
            "",
            "notanemail",
            "@example.com",
            "user@",
            "user..name@example.com",
            "space in@example.com",
            "user@.com",
        ]

        for email in invalid_emails:
            assert not MockStringUtils.is_valid_email(email), f"Should reject: {email}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sanitize_string_basic(self):
        """Basic string sanitization."""
        assert MockStringUtils.sanitize_string("Hello World") == "Hello World"
        assert MockStringUtils.sanitize_string("") == ""
        assert MockStringUtils.sanitize_string(None) == ""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sanitize_string_strip_html(self):
        """Should strip HTML tags."""
        html = "<p>Hello <b>World</b></p>"
        expected = "Hello World"

        assert MockStringUtils.sanitize_string(html, strip_html=True) == expected

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sanitize_string_normalize_whitespace(self):
        """Should normalize whitespace."""
        messy = "Hello    \n\n\tWorld   "
        expected = "Hello World"

        assert MockStringUtils.sanitize_string(messy, normalize_whitespace=True) == expected

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sanitize_string_truncation(self):
        """Should truncate long strings."""
        long_text = "A" * 100
        truncated = MockStringUtils.sanitize_string(long_text, max_length=20)

        assert len(truncated) <= 20
        assert truncated.endswith("...")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_truncate_text_short(self):
        """Short text should not be truncated."""
        text = "Short text"
        assert MockStringUtils.truncate_text(text, 50) == text

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_truncate_text_long(self):
        """Long text should be truncated with suffix."""
        text = "A" * 100
        truncated = MockStringUtils.truncate_text(text, 50)

        assert len(truncated) == 50
        assert truncated.endswith("...")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_slugify_basic(self):
        """Basic slugification."""
        assert MockStringUtils.slugify("Hello World") == "hello-world"
        assert MockStringUtils.slugify("Test String Here") == "test-string-here"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_slugify_special_characters(self):
        """Should handle special characters."""
        assert MockStringUtils.slugify("Hello! World?") == "hello-world"
        assert MockStringUtils.slugify("Café & Restaurant") == "caf-restaurant"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_slugify_truncation(self):
        """Should truncate long slugs."""
        long_title = "A Very Long Title That Should Be Truncated Because It Is Too Long For URLs"
        slug = MockStringUtils.slugify(long_title, max_length=30)

        assert len(slug) <= 30
        assert "-" in slug or slug == "untitled"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_mask_sensitive_value_short(self):
        """Short values should not be masked."""
        value = "abc"
        assert MockStringUtils.mask_sensitive_value(value) == value

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_mask_sensitive_value_long(self):
        """Long values should be masked."""
        value = "sk-very-long-api-key-that-needs-masking"
        masked = MockStringUtils.mask_sensitive_value(value, visible_chars=5)

        assert masked.startswith("sk-ve")
        assert masked.endswith("sking")
        assert "***" in masked


# ============================================================================
# TEST CLASS: Date Utilities
# ============================================================================


class TestDateUtils:
    """Tests for date/time utility functions."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_is_iso_datetime_valid(self):
        """Should accept valid ISO datetime strings."""
        valid_datetimes = [
            "2025-01-15T12:30:45",
            "2025-01-15T12:30:45Z",
            "2025-01-15T12:30:45+05:30",
            "2025-01-15T12:30:45-08:00",
        ]

        for dt in valid_datetimes:
            assert MockDateUtils.is_iso_datetime(dt), f"Should accept: {dt}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_is_iso_datetime_invalid(self):
        """Should reject invalid datetime strings."""
        invalid_datetimes = [
            "",
            "not-a-datetime",
            "2025-13-01T12:00:00",  # Invalid month
            "2025-01-32T12:00:00",  # Invalid day
            "2025-01-15T25:00:00",  # Invalid hour
        ]

        for dt in invalid_datetimes:
            assert not MockDateUtils.is_iso_datetime(dt), f"Should reject: {dt}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_format_datetime_object(self):
        """Format datetime object."""
        dt = datetime(2025, 6, 15, 14, 30, 0, tzinfo=UTC)
        formatted = MockDateUtils.format_datetime(dt)

        assert "2025" in formatted
        assert "06" in formatted or "15" in formatted

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_format_datetime_string(self):
        """Format ISO datetime string."""
        iso_str = "2025-06-15T14:30:00Z"
        formatted = MockDateUtils.format_datetime(iso_str)

        assert "2025" in formatted

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_format_relative_time_just_now(self):
        """Recent times should show 'just now'."""
        now = datetime.now(UTC)
        relative = MockDateUtils.format_relative_time(now.isoformat())

        assert "just now" in relative

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_format_relative_time_minutes(self):
        """Times within hour should show minutes."""
        past = datetime.now(UTC) - timedelta(minutes=5)
        relative = MockDateUtils.format_relative_time(past.isoformat())

        assert "minute" in relative
        assert "ago" in relative

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_format_relative_time_hours(self):
        """Times within day should show hours."""
        past = datetime.now(UTC) - timedelta(hours=3)
        relative = MockDateUtils.format_relative_time(past.isoformat())

        assert "hour" in relative
        assert "ago" in relative

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_format_relative_time_days(self):
        """Times within week should show days."""
        past = datetime.now(UTC) - timedelta(days=2)
        relative = MockDateUtils.format_relative_time(past.isoformat())

        assert "day" in relative
        assert "ago" in relative

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_time_range_valid_periods(self):
        """Should return correct ranges for valid periods."""
        now = datetime.now(UTC)

        ranges = {
            "hour": lambda: (now - timedelta(hours=1), now),
            "day": lambda: (now - timedelta(days=1), now),
            "week": lambda: (now - timedelta(weeks=1), now),
            "month": lambda: (now - timedelta(days=30), now),
            "year": lambda: (now - timedelta(days=365), now),
        }

        # ROOT-CAUSE FIX: আগে `now` লুপের বাইরে একবার ধরা হতো, কিন্তু
        # get_time_range() নিজে আবার `datetime.now(UTC)` কল করে -- ফলে সেই
        # কল টেস্টের `now`-এর কয়েক মাইক্রোসেকেন্ড পরে হওয়ায় `end <= now`
        # মাঝেমধ্যে ফেইল করত (flaky)। এখন প্রতিটা assertion-এর ঠিক আগে
        # fresh `datetime.now(UTC)` নিয়ে তুলনা করা হচ্ছে।
        for period, check in ranges.items():
            start, end = MockDateUtils.get_time_range(period)
            assert start < end
            assert end <= datetime.now(UTC)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_time_range_invalid_period(self):
        """Should reject invalid period strings."""
        with pytest.raises(ValueError, match="Invalid period"):
            MockDateUtils.get_time_range("invalid_period")


# ============================================================================
# TEST CLASS: Security Utilities
# ============================================================================


class TestSecurityUtils:
    """Tests for security utility functions."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_random_token_length(self):
        """Generated token should have correct length."""
        for length in [16, 24, 32, 64]:
            token = MockSecurityUtils.generate_random_token(length)
            assert len(token) == length

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_random_token_unique(self):
        """Generated tokens should be unique."""
        tokens = [MockSecurityUtils.generate_random_token() for _ in range(100)]
        assert len(set(tokens)) == 100  # All unique

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_api_key_with_prefix(self):
        """API key should have specified prefix."""
        key = MockSecurityUtils.generate_api_key(prefix="sk-test-")

        assert key.startswith("sk-test-")
        assert len(key) > len("sk-test-")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hash_value_deterministic(self):
        """Same input should produce same hash."""
        value = "test-value-to-hash"

        hash1 = MockSecurityUtils.hash_value(value)
        hash2 = MockSecurityUtils.hash_value(value)

        assert hash1 == hash2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hash_value_different_for_different_input(self):
        """Different inputs should produce different hashes."""
        hash1 = MockSecurityUtils.hash_value("value-one")
        hash2 = MockSecurityUtils.hash_value("value-two")

        assert hash1 != hash2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_pii_emails(self):
        """Should detect email addresses."""
        text = "Contact us at support@example.com or admin@test.org"
        findings = MockSecurityUtils.detect_pii(text)

        assert len(findings["emails"]) >= 2
        assert "support@example.com" in findings["emails"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_pii_phones(self):
        """Should detect phone numbers."""
        text = "Call us at 555-123-4567 or 800.555.9999"
        findings = MockSecurityUtils.detect_pii(text)

        assert len(findings["phones"]) >= 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_pii_no_pii(self):
        """Should find no PII in clean text."""
        text = "This is a clean text without any personal information."
        findings = MockSecurityUtils.detect_pii(text)

        total_found = sum(len(v) for v in findings.values())
        assert total_found == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_redact_pii_replaces_detected(self):
        """Redaction should replace PII with placeholder."""
        text = "Email me at user@example.com for details"
        redacted = MockSecurityUtils.redact_pii(text)

        assert "[REDACTED]" in redacted
        assert "user@example.com" not in redacted

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_redact_pii_preserves_clean_text(self):
        """Redaction should preserve non-PII text."""
        text = "This is clean text without PII"
        redacted = MockSecurityUtils.redact_pii(text)

        assert redacted == text


# ============================================================================
# TEST CLASS: Data Utilities
# ============================================================================


class TestDataUtils:
    """Tests for data transformation utilities."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deep_get_existing_path(self):
        """Get value from existing nested path."""
        data = {"level1": {"level2": {"target": "found_it"}}}

        result = MockDataUtils.deep_get(data, ["level1", "level2", "target"])

        assert result == "found_it"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deep_get_missing_path(self):
        """Return default for missing path."""
        data = {"level1": {"level2": "value"}}

        result = MockDataUtils.deep_get(data, ["level1", "nonexistent"], default="default_val")

        assert result == "default_val"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deep_get_empty_data(self):
        """Handle empty data gracefully."""
        result = MockDataUtils.deep_get({}, ["path"], default="fallback")

        assert result == "fallback"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_int_valid(self):
        """Convert valid integers."""
        assert MockDataUtils.safe_int("42") == 42
        assert MockDataUtils.safe_int(42) == 42
        assert MockDataUtils.safe_int(42.9) == 42

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_int_invalid(self):
        """Return default for invalid values."""
        assert MockDataUtils.safe_int("not_a_number") == 0
        assert MockDataUtils.safe_int(None, default=99) == 99
        assert MockDataUtils.safe_int("", default=-1) == -1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_int_bounds_checking(self):
        """Respect min/max bounds."""
        assert MockDataUtils.safe_int(50, min_val=0, max_val=100) == 50
        assert MockDataUtils.safe_int(-10, min_val=0) == 0
        assert MockDataUtils.safe_int(150, max_val=100) == 100

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_float_valid(self):
        """Convert valid floats."""
        assert MockDataUtils.safe_float("3.14") == 3.14
        assert MockDataUtils.safe_float(2.71828) == 2.71828

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_float_invalid(self):
        """Return default for invalid values."""
        assert MockDataUtils.safe_float("invalid") == 0.0
        assert MockDataUtils.safe_float(None, default=1.5) == 1.5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_bool_true_values(self):
        """Recognize truthy values."""
        assert MockDataUtils.safe_bool(True) is True
        assert MockDataUtils.safe_bool("true") is True
        assert MockDataUtils.safe_bool("1") is True
        assert MockDataUtils.safe_bool("yes") is True
        assert MockDataUtils.safe_bool(1) is True
        assert MockDataUtils.safe_bool(0.5) is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_safe_bool_false_values(self):
        """Recognize falsy values."""
        assert MockDataUtils.safe_bool(False) is False
        assert MockDataUtils.safe_bool("false") is False
        assert MockDataUtils.safe_bool("0") is False
        assert MockDataUtils.safe_bool("") is False
        assert MockDataUtils.safe_bool(0) is False
        assert MockDataUtils.safe_bool(None) is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chunk_list_even_division(self):
        """Chunk list when length divides evenly."""
        lst = list(range(10))
        chunks = MockDataUtils.chunk_list(lst, 5)

        assert len(chunks) == 2
        assert chunks[0] == [0, 1, 2, 3, 4]
        assert chunks[1] == [5, 6, 7, 8, 9]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chunk_list_remainder(self):
        """Chunk list with remainder."""
        lst = list(range(7))
        chunks = MockDataUtils.chunk_list(lst, 3)

        assert len(chunks) == 3
        assert chunks[0] == [0, 1, 2]
        assert chunks[1] == [3, 4, 5]
        assert chunks[2] == [6]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chunk_list_empty(self):
        """Handle empty list."""
        chunks = MockDataUtils.chunk_list([], 5)

        assert chunks == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_flatten_dict_simple(self):
        """Flatten simple dictionary."""
        data = {"a": 1, "b": 2}
        flattened = MockDataUtils.flatten_dict(data)

        assert flattened == {"a": 1, "b": 2}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_flatten_dict_nested(self):
        """Flatten nested dictionary."""
        data = {"outer": {"inner": "value", "another": 42}, "top": "level"}
        flattened = MockDataUtils.flatten_dict(data)

        assert flattened == {"outer.inner": "value", "outer.another": 42, "top": "level"}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_flatten_dict_deeply_nested(self):
        """Flatten deeply nested dictionary."""
        data = {"l1": {"l2": {"l3": {"l4": "deep_value"}}}}
        flattened = MockDataUtils.flatten_dict(data)

        assert flattened.get("l1.l2.l3.l4") == "deep_value"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=utils", "--cov-report=term-missing"])
