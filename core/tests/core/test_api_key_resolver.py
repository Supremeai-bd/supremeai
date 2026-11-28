"""Tests for api_key_resolver (numbered key failover)."""
import os
from unittest.mock import patch

from core.utils.api_key_resolver import (
    iter_key_with_aliases,
    iter_numbered_keys,
    resolve_key_with_aliases,
    resolve_numbered_key,
)


def test_resolve_numbered_key_base():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "base-val"}, clear=True):
        assert resolve_numbered_key("GEMINI_API_KEY") == "base-val"


def test_resolve_numbered_key_fallback_to_numbered():
    with patch.dict(os.environ, {"GEMINI_API_KEY_2": "v2"}, clear=True):
        assert resolve_numbered_key("GEMINI_API_KEY") == "v2"


def test_resolve_numbered_key_prefers_base():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "base", "GEMINI_API_KEY_2": "v2"}, clear=True):
        assert resolve_numbered_key("GEMINI_API_KEY") == "base"


def test_resolve_numbered_key_none_when_empty():
    with patch.dict(os.environ, {}, clear=True):
        assert resolve_numbered_key("GEMINI_API_KEY") is None


def test_resolve_numbered_key_strips_whitespace():
    with patch.dict(os.environ, {"GEMINI_API_KEY_2": "  spaced  "}, clear=True):
        assert resolve_numbered_key("GEMINI_API_KEY") == "spaced"


def test_resolve_key_with_aliases():
    with patch.dict(os.environ, {"OPENROUTER_API_KEY_2": "v2"}, clear=True):
        assert resolve_key_with_aliases("OPENROUTER_API_KEY", ["OPENROUTER_KEY"]) == "v2"


def test_resolve_key_with_aliases_none():
    with patch.dict(os.environ, {}, clear=True):
        assert resolve_key_with_aliases("OPENROUTER_API_KEY", ["OPENROUTER_KEY"]) is None


def test_iter_numbered_keys_returns_slots_in_order():
    env = {"GEMINI_API_KEY": "v-base", "GEMINI_API_KEY_2": "v2", "GEMINI_API_KEY_12": "v12"}
    with patch.dict(os.environ, env, clear=True):
        pairs = iter_numbered_keys("GEMINI_API_KEY")
    assert pairs == [
        ("GEMINI_API_KEY", "v-base"),
        ("GEMINI_API_KEY_2", "v2"),
        ("GEMINI_API_KEY_12", "v12"),
    ]


def test_iter_numbered_keys_dedupes_identical_values():
    with patch.dict(os.environ, {"GROQ_API_KEY": "same", "GROQ_API_KEY_2": "same"}, clear=True):
        assert iter_numbered_keys("GROQ_API_KEY") == [("GROQ_API_KEY", "same")]


def test_iter_key_with_aliases_skips_dupes_across_chain():
    env = {"GEMINI_API_KEY": "v2", "GEMINI_API_KEY_2": "v2", "GOOGLE_API_KEY": "g-base"}
    with patch.dict(os.environ, env, clear=True):
        pairs = iter_key_with_aliases("GEMINI_API_KEY", ["GOOGLE_API_KEY"])
    assert pairs == [("GEMINI_API_KEY", "v2"), ("GOOGLE_API_KEY", "g-base")]


def test_iter_key_with_aliases_walks_alias_numbered_slots():
    with patch.dict(os.environ, {"GOOGLE_API_KEY_3": "g3"}, clear=True):
        pairs = iter_key_with_aliases("GEMINI_API_KEY", ["GOOGLE_API_KEY"])
    assert pairs == [("GOOGLE_API_KEY_3", "g3")]
