# বাংলা মন্তব্য: skills-কে একটি স্ট্যান্ডার্ড পাইথন প্যাকেজ হিসেবে চিহ্নিত করতে এই ফাইলটি তৈরি করা হলো
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_ROOT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
if str(_ROOT_SKILLS_DIR) not in __path__:
    __path__.append(str(_ROOT_SKILLS_DIR))


def _load_root_skill_module(rel_path: str, pkg: str = "skills") -> ModuleType:
    target = _ROOT_SKILLS_DIR / rel_path
    mod_name = f"skills._root_{rel_path.replace('/', '_').removesuffix('.py')}"
    spec = importlib.util.spec_from_file_location(mod_name, target)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = pkg
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


