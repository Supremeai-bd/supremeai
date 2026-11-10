# -*- coding: utf-8 -*-
"""Backward-compatible proxy pointing to canonical browser.runtime.session_manager."""

from browser.runtime.session_manager import (  # noqa: F401
    BrowserSessionManager,
    RuntimeCapabilityError,
    playwright_available,
)

__all__ = ["BrowserSessionManager", "RuntimeCapabilityError", "playwright_available"]
