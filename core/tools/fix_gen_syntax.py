#!/usr/bin/env python3
"""Repair known generated knowledge-seed syntax damage before static auditing.

2026-11-17: the repair used to run at module import time against a cwd-relative
path, so importing ``core.tools.fix_gen_syntax`` raised FileNotFoundError. It is
now a real entrypoint and resolves its target relative to the repository root.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "core" / "tools" / "gen_knowledge_seed.py"

KEYWORDS = (
    "assumptions=",
    "invariants=",
    "failure_modes=",
    "counterarguments=",
    "evidence=",
)


def main() -> int:
    path = TARGET
    if not path.is_file():
        print(f"target missing: {path}")
        return 1

    content = path.read_text(encoding="utf-8")

    # A generated entry occasionally contains a malformed final string such as
    # `"...queries")]`. The intended list element is `"...queries)"`.
    content = re.sub(r'"\)\]', ')\"]', content)

    fixed: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        matched_kw = next((kw for kw in KEYWORDS if stripped.startswith(kw)), None)

        if matched_kw:
            indent_match = re.match(r"^(\s+)", line)
            indent = indent_match.group(1) if indent_match else ""
            eq_idx = stripped.index("=")
            value_part = stripped[eq_idx + 1 :]
            target = '"]'
            last_close = value_part.rfind(target)
            if last_close >= 0:
                list_value = value_part[: last_close + len(target)]
                fixed.append(f"{indent}{matched_kw}{list_value},")
                continue

        fixed.append(line)

    path.write_text("\n".join(fixed) + "\n", encoding="utf-8")

    print(f"Syntax repair applied to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
