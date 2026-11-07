"""core/skills/registry/package_manager.py — Re-export SSOT for skills.registry.package_manager.

Canonical SSOT: skills/registry/package_manager
Provides backward-compatibility for callers while eliminating duplicate logic.
"""

from skills.registry.package_manager import *  # noqa: F401, F403
