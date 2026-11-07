"""core/skills/schema.py — Re-export SSOT for skills.schema.

Canonical SSOT: skills/schema
Provides backward-compatibility for callers while eliminating duplicate logic.
"""

from skills.schema import *  # noqa: F401, F403
