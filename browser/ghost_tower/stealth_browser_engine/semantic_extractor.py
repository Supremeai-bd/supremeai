# -*- coding: utf-8 -*-
"""Backward-compatible proxy pointing to canonical browser.runtime.semantic_extractor."""

from browser.runtime.semantic_extractor import (  # noqa: F401
    SemanticNode,
    SemanticTree,
    estimate_tokens,
    extract_semantic_tree,
)

__all__ = ["SemanticNode", "SemanticTree", "estimate_tokens", "extract_semantic_tree"]
