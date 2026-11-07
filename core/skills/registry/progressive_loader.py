"""core/skills/registry/progressive_loader.py — Re-export SSOT for skills.registry.progressive_loader."""

from .. import _load_root_skill_module

_pl = _load_root_skill_module("registry/progressive_loader.py", pkg="skills.registry")
CURSOR_MANIFEST = _pl.CURSOR_MANIFEST
SKILL_MD = _pl.SKILL_MD
ProgressiveLoader = _pl.ProgressiveLoader
__all__ = ["CURSOR_MANIFEST", "SKILL_MD", "ProgressiveLoader"]


