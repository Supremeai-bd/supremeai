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

    # G5.1 (reaudit 2026-11-26): write-path census — which functions write
    # into which backend/table (save/insert/add/update/upsert semantics).
    write_names = ("save", "insert", "add_", "append", "update", "upsert", "store", "put_")
    write_paths: list[dict] = []
    for d in ("core", "gateway", "browser", "scripts"):
        if not (ROOT / d).exists():
            continue
        for path in (ROOT / d).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                lname = node.name.lower()
                if not any(w in lname for w in write_names):
                    continue
                # crude table/backend hint from literals in the function body
                literals = [
                    n.value
                    for n in ast.walk(node)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                ]
                tables = sorted(
                    {
                        lit
                        for lit in literals
                        if lit
                        in {
                            "ai_memory",
                            "learned_facts",
                            "memories",
                            "knowledge_base",
                            "memory_entries",
                            "conversation_memory",
                        }
                        or lit.endswith("_memory")
                        or lit.endswith("_facts")
                    }
                )
                write_paths.append(
                    {
                        "file": rel,
                        "function": node.name,
                        "line": node.lineno,
                        "tables": tables,
                    }
                )

    print(
        json.dumps(
            {
                "total_backends": len(report),
                "backends": report,
                "write_paths": write_paths,
                "write_path_count": len(write_paths),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
