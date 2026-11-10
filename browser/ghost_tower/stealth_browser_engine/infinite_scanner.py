# -*- coding: utf-8 -*-
"""Backward-compatible proxy pointing to canonical browser.runtime.infinite_scanner."""

from browser.runtime.infinite_scanner import (  # noqa: F401
    SCROLL_AND_EXPAND_JS,
    FeedExpander,
    ScrollPlan,
    ScrollStep,
)

__all__ = ["SCROLL_AND_EXPAND_JS", "FeedExpander", "ScrollPlan", "ScrollStep"]
