"""gateway/skills/installer.py — Re-export SSOT for skills.installer.

Canonical SSOT: skills/installer.py
Provides backward-compatibility for callers while eliminating duplicate logic.
"""

from skills.installer import *  # noqa: F401, F403
