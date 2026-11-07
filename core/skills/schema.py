"""core/skills/schema.py — Re-export SSOT for skills.schema.

Canonical SSOT: skills/schema
Provides backward-compatibility for callers while eliminating duplicate logic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT_SCHEMA = Path(__file__).resolve().parents[2] / "skills" / "schema.py"
_spec = importlib.util.spec_from_file_location("skills._root_schema", _ROOT_SCHEMA)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "skills"
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

for _k, _v in vars(_mod).items():
    if not _k.startswith("__"):
        globals()[_k] = _v

