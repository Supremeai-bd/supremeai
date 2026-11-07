"""Canonical re-export from skills.installer (SSOT)."""

from . import _load_root_skill_module

_mod = _load_root_skill_module("installer.py")
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})


