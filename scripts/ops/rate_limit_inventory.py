#!/usr/bin/env python3
"""Read-only rate-limiter inventory (B4): lists rate-limiter files and their import callers."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("core", "gateway", "browser", "scripts")


def main() -> int:
    py_files = [
        p
        for d in SCAN_DIRS
        if (ROOT / d).exists()
        for p in (ROOT / d).rglob("*.py")
        if "__pycache__" not in p.parts
    ]
    limiters = [
        p
        for p in py_files
        if "rate_limit" in p.name.lower() or "ratelimit" in p.name.lower()
    ]
    callers: dict[str, list[str]] = {
        str(p.relative_to(ROOT)).replace("\\", "/"): [] for p in limiters
    }

    for p in py_files:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(text)
        except SyntaxError:
            continue
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for lim in callers:
            mod = lim[:-3].replace("/", ".")
            stem = Path(lim).stem
            if any(mod in imp or imp.endswith(stem) for imp in imported) and rel != lim:
                callers[lim].append(rel)

    report = [
        {"file": k, "caller_count": len(v), "callers": sorted(v)[:10]}
        for k, v in sorted(callers.items())
    ]
    print(json.dumps({"total_limiters": len(report), "limiters": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
