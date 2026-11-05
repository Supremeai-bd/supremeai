"""Centralized resolver for numbered API key variants (failover/rotation).

When a base key (e.g. GEMINI_API_KEY) is unset, tries numbered variants
(GEMINI_API_KEY_2, GEMINI_API_KEY_3, ...) and returns the first non-empty value.
"""
import os
from typing import Optional


def resolve_numbered_key(base: str, max_n: int = 10) -> Optional[str]:
    """Return the first non-empty value among base and base_2..base_max_n."""
    val = os.environ.get(base, "").strip()
    if val:
        return val
    for i in range(2, max_n + 1):
        val = os.environ.get(f"{base}_{i}", "").strip()
        if val:
            return val
    return None


def resolve_key_with_aliases(base: str, aliases: list[str], max_n: int = 10) -> Optional[str]:
    """Try base, its numbered variants, then explicit aliases (and their numbered variants)."""
    for name in [base] + aliases:
        val = resolve_numbered_key(name, max_n)
        if val:
            return val
    return None
