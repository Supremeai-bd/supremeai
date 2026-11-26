#!/usr/bin/env python3
"""Read-only memory backend census (B5): lists core/memory/ modules and their callers."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    mem_dir = ROOT / "core" / "memory"
    if not mem_dir.exists():
        print(json.dumps({"total_backends": 0, "backends": []}))
        return 0
    backends = [
        str(p.relative_to(ROOT)).replace("\\", "/")
        for p in sorted(mem_dir.rglob("*.py"))
        if "__pycache__" not in p.parts and p.name != "__init__.py"
    ]
    callers: dict[str, list[str]] = {b: [] for b in backends}
    for d in ("core", "gateway", "browser", "scripts"):
        if not (ROOT / d).exists():
            continue
        for p in (ROOT / d).rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            for b in callers:
                mod = b[:-3].replace("/", ".")
                if any(mod in imp for imp in imported) and rel != b:
                    callers[b].append(rel)

    report = [{"file": k, "caller_count": len(v), "callers": sorted(v)[:10]} for k, v in callers.items()]
    print(json.dumps({"total_backends": len(report), "backends": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
