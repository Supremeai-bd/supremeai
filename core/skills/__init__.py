# বাংলা মন্তব্য: skills-কে একটি স্ট্যান্ডার্ড পাইথন প্যাকেজ হিসেবে চিহ্নিত করতে এই ফাইলটি তৈরি করা হলো
from __future__ import annotations

from pathlib import Path

_ROOT_SKILLS_DIR = str(Path(__file__).resolve().parents[2] / "skills")
if _ROOT_SKILLS_DIR not in __path__:
    __path__.append(_ROOT_SKILLS_DIR)

