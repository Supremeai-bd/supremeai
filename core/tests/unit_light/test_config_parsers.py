"""Roadmap 1.4 / issue #1173 — canonical origin-list parser contract tests.

DoD (docs/ROADMAP.md item 1.4): JSON / comma / empty / malformed — ৪-টেস্ট,
plus strip-filter semantics and the tuple/frozenset wrappers used by
``middleware/cors_policy.py`` and ``core/security/origin_validator.py``.
"""

import pytest

from core.config_parsers import parse_origin_list


class TestParseOriginList:
    def test_json_array_string(self):
        """DoD case 1: JSON-array form is parsed, stripped and filtered."""
        assert parse_origin_list('["https://a.com", "https://b.com"]') == [
            "https://a.com",
            "https://b.com",
        ]

    def test_comma_separated_string(self):
        """DoD case 2: comma-separated form is parsed identically."""
        assert parse_origin_list("https://a.com, https://b.com") == [
            "https://a.com",
            "https://b.com",
        ]

    def test_empty_string(self):
        """DoD case 3: empty/whitespace-only input yields an empty list."""
        assert parse_origin_list("") == []
        assert parse_origin_list("   ") == []

    def test_malformed_json_falls_back_to_comma_split(self):
        """DoD case 4: malformed JSON degrades to comma-split, never crash."""
        assert parse_origin_list('["https://a.com,, https://b.com') == [
            '["https://a.com',
            "https://b.com",
        ]

    def test_non_array_json_is_treated_as_literal(self):
        """A JSON scalar is not silently swallowed — kept as a literal entry."""
        assert parse_origin_list('"just-a-string"') == ['"just-a-string"']

    def test_list_passthrough_strips_and_filters(self):
        """Existing list/tuple values are stripped, cast and empty-filtered."""
        assert parse_origin_list([" https://a.com ", "", "https://b.com"]) == [
            "https://a.com",
            "https://b.com",
        ]
        assert parse_origin_list((" https://a.com ",)) == ["https://a.com"]

    def test_other_types_returned_untouched(self):
        """Non-str/list values pass through so pydantic validation stays loud."""
        sentinel = {"k": 1}
        assert parse_origin_list(sentinel) is sentinel
        assert parse_origin_list(None) is None


class TestMigratedCallers:
    """The two dependency-free wrappers built on the canonical parser."""

    def test_cors_policy_load_origins(self, monkeypatch):
        from middleware.cors_policy import _load_origins

        monkeypatch.setenv("T_ORIGINS", '[" https://x.com ", ""]')
        assert _load_origins("T_ORIGINS", ()) == ("https://x.com",)
        monkeypatch.setenv("T_ORIGINS", "https://a.com , ,https://b.com")
        assert _load_origins("T_ORIGINS", ()) == ("https://a.com", "https://b.com")
        monkeypatch.delenv("T_ORIGINS", raising=False)
        assert _load_origins("T_ORIGINS", ("default",)) == ("default",)

    def test_origin_validator_load_origins(self, monkeypatch):
        from core.security.origin_validator import _load_origins

        monkeypatch.setenv(
            "T_ORIGINS_OV", '["https://admin.example.com", "https://admin.example.com"]'
        )
        assert _load_origins("T_ORIGINS_OV", frozenset()) == frozenset(
            {"https://admin.example.com"}
        )
        monkeypatch.delenv("T_ORIGINS_OV", raising=False)
        assert _load_origins("T_ORIGINS_OV", frozenset({"d"})) == frozenset({"d"})

    def test_config_fields_reexport_identity(self):
        """Historical import path keeps returning the same function object."""
        from core.config_fields import parse_origin_list as via_config_fields

        assert via_config_fields is parse_origin_list
