"""supremeai-skills registry: manifest schemas and descriptors."""

from .manifest_schema import (
    CapabilityDescriptor,
    ManifestError,
    parse_cursor_plugin,
    parse_skill_md,
)
from .progressive_loader import ProgressiveLoader

try:
    from ..skill_registry import SkillRegistry
except Exception:
    try:
        from ..registry import SkillRegistry  # type: ignore
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
