# -*- coding: utf-8 -*-
"""Backward-compatible proxy pointing to canonical browser.runtime.config."""

from browser.runtime.config import (  # noqa: F401
    PRESETS,
    BrowserProfile,
    get_profile,
    profile_names,
)

__all__ = ["PRESETS", "BrowserProfile", "get_profile", "profile_names"]
