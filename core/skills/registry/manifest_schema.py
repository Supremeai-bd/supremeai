"""core/skills/registry/manifest_schema.py — Re-export SSOT for skills.registry.manifest_schema."""

from .. import _load_root_skill_module

_ms = _load_root_skill_module("registry/manifest_schema.py", pkg="skills.registry")
CapabilityDescriptor = _ms.CapabilityDescriptor
ManifestError = _ms.ManifestError
parse_cursor_plugin = _ms.parse_cursor_plugin
parse_skill_md = _ms.parse_skill_md
__all__ = ["CapabilityDescriptor", "ManifestError", "parse_cursor_plugin", "parse_skill_md"]


