# -*- coding: utf-8 -*-
"""Backward-compatible proxy pointing to canonical browser.runtime.content_pruner."""

from browser.runtime.content_pruner import (  # noqa: F401
    ContentPruner,
    PrunedContent,
    link_density,
)

__all__ = ["ContentPruner", "PrunedContent", "link_density"]
