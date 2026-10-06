"""Centralized feature-flag checker for SupremeAI 2.0.

বাংলা মন্তব্য: এই মডিউলটি backend/integrations/ এবং সাধারণ ব্যবহারকারীর জন্য
একটি একীকৃত ফিচার-ফ্ল্যাগ চেকার সরবরাহ করে। এটি দুটি স্তরে কাজ করে:

1. **Env-var first (Zero-cost, no DB)** — SUPREMEAI_MEM0_ENABLED ইত্যাদি
   env ভ্যারিয়েবলের মান চেক করে। কোনো ডাটাবেস সংযোগ ছাড়াই কাজ করে।
   Explicit মান (true/false) চূড়ান্ত — unset হলেই কেবল DB স্তরে যাওয়া হয়।

2. **DB fallback (Supabase)** — যদি env-var সেট না থাকে, তবে
   SupabaseClient.is_feature_enabled() ক্যাল করে। per-user rollout ও
   allowed_users চেক করে।

নকশা-ইতিহাস (#4097 reconciliation): এই ফ্ল্যাগগুলো একসময় premium
integrations (mem0, Graphiti, browser-use, E2B) নিয়ন্ত্রণ করত — সেই সব
adapter অবসর নিয়েছে (browser_use/openhands: #4044/#4045 → execution
#4068; mem0/e2b/graphiti: #4057 → execution PR #4103; বিস্তারিত
docs/architecture/retired_adapters.md)। ফ্ল্যাগ-কনস্ট্যান্ট ও DB-টিয়ার
ম্যাপিং (admin-UI feature_names চুক্তি, #1818) compatibility-র জন্য বহাল
আছে — কোনো live adapter-path এখন এগুলোর উপর নির্ভর করে না।
"""

from __future__ import annotations

import os
from typing import Any

from core.logging_config import logger

# ── Flag name constants ──────────────────────────────────────────────────────
MEM0_FLAG = "SUPREMEAI_MEM0_ENABLED"
GRAPHITI_FLAG = "SUPREMEAI_GRAPHITI_ENABLED"
E2B_FLAG = "SUPREMEAI_E2B_ENABLED"

# Supabase DB feature_flags টেবিলের feature_name কলামের জন্য ম্যাপিং
_DB_FLAG_NAMES: dict[str, str] = {
    MEM0_FLAG: "mem0_enabled",
    GRAPHITI_FLAG: "graphiti_enabled",
    E2B_FLAG: "e2b_enabled",
}

_TRUTHY: frozenset[str] = frozenset({"1", "true", "yes", "on"})

# Canonical runtime feature_name keys (feature_flags DB table) — the single
# naming source the admin UI and the runtime must share (issue #1818 bug 3).
RUNTIME_FLAG_NAMES: frozenset[str] = frozenset(_DB_FLAG_NAMES.values())


def _env_flag(name: str) -> bool | None:
    """Tri-state env read (issue #1818 bug-2 fix).

    True/False when the variable is explicitly set (even to a falsy value),
    None when unset or blank — the caller can then distinguish
    "explicit kill-switch" from "not configured" and only consult the DB
    tier in the latter case. Previously unset and explicit-false were
    indistinguishable, so ``SUPREMEAI_MEM0_ENABLED=false`` was still
    overridden by a true DB row (the documented env-first contract was
    inverted).
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    return raw.strip().lower() in _TRUTHY


def _db_flag(name: str, user_id: str | None = None) -> bool | None:
    """Query the Supabase feature_flags table.

    Returns True/False, or None when DB is unreachable / flag row missing.
    """
    try:
        from database.supabase_client import db

        if not db:
            return None
        # Issue #1818 bug-1 fix: is_feature_enabled lives on the SupabaseDB
        # WRAPPER, not on the raw supabase-py client — the old db.client...
        # call raised AttributeError, swallowed at DEBUG level, so DB flags
        # could never enable anything.
        return db.is_feature_enabled(_DB_FLAG_NAMES.get(name, name), user_id)
    except Exception as exc:
        logger.debug(f"feature_flags: DB lookup for '{name}' failed (non-fatal): {exc}")
        return None


class FeatureFlags:
    """Singleton-style feature flag accessor.

    Usage::

        from core.feature_flags import feature_flags

        if feature_flags.mem0_enabled():
            ...  # premium path
        else:
            ...  # zero-cost free fallback

    Never raises — when DB unreachable and no env-var, default is False (free path).
    """

    _cache: dict[str, bool] = {}

    def mem0_enabled(self, user_id: str | None = None) -> bool:
        """True when the premium Mem0 memory layer should be used."""
        return self._check(MEM0_FLAG, user_id)

    def graphiti_enabled(self, user_id: str | None = None) -> bool:
        """True when the premium Graphiti knowledge-graph memory should be used."""
        return self._check(GRAPHITI_FLAG, user_id)

    def e2b_enabled(self, user_id: str | None = None) -> bool:
        """True when the premium E2B sandbox should be used."""
        return self._check(E2B_FLAG, user_id)

    def _check(self, flag_name: str, user_id: str | None = None) -> bool:
        """Two-tier check: env-var → DB, cache result."""
        if flag_name in self._cache:
            return self._cache[flag_name]
        # Issue #1818 bug-2 fix — documented "env-var first" contract, now
        # actually honored: an EXPLICIT env value (true or false) is final;
        # the DB tier is consulted only when the env var is unset/blank.
        env_result = _env_flag(flag_name)
        if env_result is not None:
            result = env_result
        else:
            result = _db_flag(flag_name, user_id) is True
        self._cache[flag_name] = result
        return result

    def reset_cache(self) -> None:
        """Clear the cache — useful for testing or runtime reconfiguration."""
        self._cache.clear()

    # Advanced-upgrade rollout flags (Phase 1-7)
    ADV_FLAGS: dict[str, dict[str, Any]] = {
        "adv.i18n_ai_translate": {"enabled": True, "pct": 100},  # Phase 1a
        "adv.preferences_adaptive": {"enabled": True, "pct": 100},  # Phase 1b
        "adv.health_predictive": {"enabled": True, "pct": 100},  # Phase 2a
        "adv.email_smart": {"enabled": True, "pct": 100},  # Phase 2b
        "adv.theme_server_tokens": {"enabled": True, "pct": 100},  # Phase 3a
        "adv.docs_living": {"enabled": True, "pct": 100},  # Phase 3b (CI living docs)
        "adv.search_semantic": {"enabled": True, "pct": 100},  # Phase 5a
        "adv.onboarding_adaptive": {"enabled": True, "pct": 100},  # Phase 5b
    }

    @classmethod
    def is_enabled(cls, flag: str, user_id: str | None = None) -> bool:
        """Deterministic percentage-based rollout checker for advanced features."""
        cfg = cls.ADV_FLAGS.get(flag)
        if not cfg or not cfg.get("enabled"):
            return False
        pct = cfg.get("pct", 0)
        if pct >= 100:
            return True
        if pct <= 0:
            return False
        bucket = abs(hash(user_id or flag)) % 100
        return bucket < pct

    def is_advanced_enabled(self, flag: str, user_id: str | None = None) -> bool:
        return self.is_enabled(flag, user_id)

    def status(self) -> dict[str, Any]:
        """Return current state of all integration flags and advanced rollout flags."""
        return {
            "mem0": self.mem0_enabled(),
            "graphiti": self.graphiti_enabled(),
            "e2b": self.e2b_enabled(),
            "advanced_rollout": {k: v["pct"] for k, v in self.ADV_FLAGS.items() if v["enabled"]},
        }


# Module-level singleton
feature_flags = FeatureFlags()

__all__ = [
    "RUNTIME_FLAG_NAMES",
    "E2B_FLAG",
    "GRAPHITI_FLAG",
    "MEM0_FLAG",
    "FeatureFlags",
    "feature_flags",
]
