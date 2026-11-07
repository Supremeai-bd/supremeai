"""supremeai-skills registry: manifest schemas and descriptors."""

from pathlib import Path

_ROOT_REGISTRY_DIR = str(Path(__file__).resolve().parents[3] / "skills" / "registry")
if _ROOT_REGISTRY_DIR not in __path__:
    __path__.append(_ROOT_REGISTRY_DIR)

from .manifest_schema import (
    CapabilityDescriptor,
    ManifestError,
    parse_cursor_plugin,
    parse_skill_md,
)
from .progressive_loader import ProgressiveLoader

try:
    import importlib.util as _ilu
    import sys as _sys

    _reg_file = Path(__file__).resolve().parents[1] / "registry.py"
    _spec = _ilu.spec_from_file_location("skills._db_registry", _reg_file)
    assert _spec is not None and _spec.loader is not None
    _reg_mod = _ilu.module_from_spec(_spec)
    _sys.modules[_spec.name] = _reg_mod
    _spec.loader.exec_module(_reg_mod)
    SkillRegistry = _reg_mod.SkillRegistry
except Exception:
    try:
        from ..skill_registry import SkillRegistry  # type: ignore
    except Exception:
        SkillRegistry = None  # type: ignore

__all__ = [
    "CapabilityDescriptor",
    "ManifestError",
    "ProgressiveLoader",
    "SkillRegistry",
    "parse_cursor_plugin",
    "parse_skill_md",
]
