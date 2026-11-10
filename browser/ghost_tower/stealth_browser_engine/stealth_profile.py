# -*- coding: utf-8 -*-
"""Backward-compatible proxy pointing to canonical browser.runtime.stealth_profile."""

from browser.runtime.stealth_profile import (  # noqa: F401
    StealthProfile,
    bezier_path,
    generate,
    webgl_pairs,
)

__all__ = ["StealthProfile", "bezier_path", "generate", "webgl_pairs"]
