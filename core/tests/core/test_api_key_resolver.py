"""Tests for api_key_resolver (numbered key failover)."""
import os
from unittest.mock import patch

import pytest

from core.utils.api_key_resolver import resolve_numbered_key, resolve_key_with_aliases


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
