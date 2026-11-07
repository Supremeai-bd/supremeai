"""core/skills/schema.py — Re-export SSOT for skills.schema."""

from . import _load_root_skill_module

_sc = _load_root_skill_module("schema.py")
globals().update({k: v for k, v in vars(_sc).items() if not k.startswith("__")})


