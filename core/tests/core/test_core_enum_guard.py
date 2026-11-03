# tests/test_core_enum_guard.py
"""Tests for the core EnumGuard safe enum parsing utility."""

import enum

import pytest

from core.enum_guard import EnumGuard, EnumGuardError


class Color(enum.Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


def test_parse_enum_member_returns_same():
    assert EnumGuard.validate_and_parse(Color, Color.RED) is Color.RED


def test_parse_by_name_case_insensitive():
    assert EnumGuard.validate_and_parse(Color, "red") is Color.RED
    assert EnumGuard.validate_and_parse(Color, "GREEN") is Color.GREEN


def test_parse_by_value():
    assert EnumGuard.validate_and_parse(Color, "green") is Color.GREEN


def test_invalid_value_raises_enum_guard_error():
    with pytest.raises(EnumGuardError):
        EnumGuard.validate_and_parse(Color, "purple")


def test_enum_guard_error_is_value_error():
    with pytest.raises(ValueError):
        EnumGuard.validate_and_parse(Color, "bad")


def test_safe_fallback_with_valid_value():
    assert EnumGuard.safe_fallback(Color, "red", Color.GREEN) is Color.RED


def test_safe_fallback_with_invalid_value():
    assert EnumGuard.safe_fallback(Color, "bad", Color.GREEN) is Color.GREEN


def test_whitespace_is_stripped():
    assert EnumGuard.validate_and_parse(Color, "  blue  ") is Color.BLUE
