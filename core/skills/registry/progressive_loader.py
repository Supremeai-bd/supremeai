"""core/skills/registry/progressive_loader.py — Re-export SSOT for skills.registry.progressive_loader.

Canonical SSOT: skills/registry/progressive_loader
Provides backward-compatibility for callers while eliminating duplicate logic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT_LOADER = Path(__file__).resolve().parents[3] / "skills" / "registry" / "progressive_loader.py"
_spec = importlib.util.spec_from_file_location(
    "skills.registry._root_progressive_loader",
    _ROOT_LOADER,
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "skills.registry"
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

CURSOR_MANIFEST = _mod.CURSOR_MANIFEST
SKILL_MD = _mod.SKILL_MD
ProgressiveLoader = _mod.ProgressiveLoader

__all__ = ["CURSOR_MANIFEST", "SKILL_MD", "ProgressiveLoader"]

