"""Centralized resolver for numbered API key variants (failover/rotation).

Infisical exports every vault secret as a flat env var, so a multi-key API pool
is stored as GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3, … (plus comma
pools such as GROQ_API_KEYS). The ``iter_*`` helpers let a caller walk EVERY key
in the pool and fail over until one is valid, instead of giving up after the
base key.
"""
import os

# .env.example documents numbered pools up to _12 (GEMINI_API_KEY_12); keep
# discovery in sync so "check every key" actually reaches the last slot.
MAX_NUMBERED_KEY_INDEX = 12


def iter_numbered_keys(base: str, max_n: int = MAX_NUMBERED_KEY_INDEX) -> list[tuple[str, str]]:
    """Return (env_name, value) pairs for base and base_2..base_max_n, in order.

    Values are whitespace-stripped; duplicate values across slots are removed so
    a caller never retries the same key under a different env name.
    """
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in [base] + [f"{base}_{i}" for i in range(2, max_n + 1)]:
        val = os.environ.get(name, "").strip()
        if val and val not in seen:
            pairs.append((name, val))
            seen.add(val)
    return pairs


def resolve_numbered_key(base: str, max_n: int = MAX_NUMBERED_KEY_INDEX) -> str | None:
    """Return the first non-empty value among base and base_2..base_max_n."""
    for _, val in iter_numbered_keys(base, max_n):
        return val
    return None


def iter_key_with_aliases(
    base: str, aliases: list[str], max_n: int = MAX_NUMBERED_KEY_INDEX
) -> list[tuple[str, str]]:
    """Iterate base + numbered variants, then each alias + its numbered variants.

    Values are deduped across the whole alias chain.
    """
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in [base] + list(aliases):
        for env_name, val in iter_numbered_keys(name, max_n):
            if val not in seen:
                pairs.append((env_name, val))
                seen.add(val)
    return pairs


def resolve_key_with_aliases(base: str, aliases: list[str], max_n: int = MAX_NUMBERED_KEY_INDEX) -> str | None:
    """Try base, its numbered variants, then explicit aliases (and their numbered variants)."""
    for _, val in iter_key_with_aliases(base, aliases, max_n):
        return val
    return None
