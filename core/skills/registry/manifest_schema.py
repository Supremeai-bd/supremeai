"""core/skills/registry/manifest_schema.py — Re-export SSOT for skills.registry.manifest_schema.

Canonical SSOT: skills/registry/manifest_schema
Provides backward-compatibility for callers while eliminating duplicate logic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT_MANIFEST = Path(__file__).resolve().parents[3] / "skills" / "registry" / "manifest_schema.py"
_spec = importlib.util.spec_from_file_location("_root_skills_manifest_schema", _ROOT_MANIFEST)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

CapabilityDescriptor = _mod.CapabilityDescriptor
ManifestError = _mod.ManifestError
parse_cursor_plugin = _mod.parse_cursor_plugin
parse_skill_md = _mod.parse_skill_md

__all__ = [
    "CapabilityDescriptor",
    "ManifestError",
    "parse_cursor_plugin",
    "parse_skill_md",
]

