"""skill_plane_parity_guard.py — keep .agents/skills and skills planes in sync.

Compares SKILL.md frontmatter (name, version) and body hash for skills
present in both planes. A skill may declare `parity: divergent` to opt out.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / ".agents" / "skills"
RUNTIME = ROOT / "skills"

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    data: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.split("#", 1)[0].rstrip()
        if not line.strip() or ":" not in line:
            continue
        key, _, val = line.partition(":")
        data[key.strip()] = val.strip().strip("'\"")
    return data


def body_of(text: str) -> str:
    m = FRONTMATTER_RE.match(text)
    return text[m.end():].strip() if m else text.strip()


def body_hash(text: str) -> str:
    return hashlib.sha256(body_of(text).encode("utf-8")).hexdigest()


def check() -> list[str]:
    errors: list[str] = []
    agent_skills = {p.parent.name: p for p in AGENTS.glob("*/SKILL.md")} if AGENTS.is_dir() else {}
    runtime_skills = {p.parent.name: p for p in RUNTIME.glob("*/SKILL.md")} if RUNTIME.is_dir() else {}
    common = sorted(set(agent_skills) & set(runtime_skills))
    for name in common:
        a_text = agent_skills[name].read_text(encoding="utf-8")
        r_text = runtime_skills[name].read_text(encoding="utf-8")
        a_fm = parse_frontmatter(a_text)
        r_fm = parse_frontmatter(r_text)
        if a_fm.get("parity") == "divergent" or r_fm.get("parity") == "divergent":
            continue
        if a_fm.get("name") != r_fm.get("name"):
            errors.append(f"{name}: name drift ({a_fm.get('name')} vs {r_fm.get('name')})")
        if a_fm.get("version") != r_fm.get("version"):
            errors.append(f"{name}: version drift ({a_fm.get('version')} vs {r_fm.get('version')})")
        if body_hash(a_text) != body_hash(r_text):
            errors.append(f"{name}: body hash drift")
    return errors


def main() -> int:
    errors = check()
    if errors:
        print("skill-plane-parity-guard: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    shared = sorted(set(p.parent.name for p in AGENTS.glob("*/SKILL.md")) & set(p.parent.name for p in RUNTIME.glob("*/SKILL.md")))
    print(f"skill-plane-parity-guard: OK ({len(shared)} shared skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

