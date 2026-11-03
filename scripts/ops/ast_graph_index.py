#!/usr/bin/env python3
"""ast_graph_index.py — zero-token local AST symbol & dependency graph (Phase C.1).

Uses tree-sitter to parse Python (and TS/JS when available) source files into
a symbol + import graph and persists a JSON snapshot for fast agent context
retrieval. No cloud calls, no tokens.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from tree_sitter import Language, Parser
    from tree_sitter_python import language as _py_language
    _TS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    _TS_AVAILABLE = False


def find_repo_root(start: Path | None = None) -> Path:
    cur = (start or Path(__file__).resolve()).parent
    for _ in range(10):
        if (cur / ".git").exists() or (cur / "AGENTS.md").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return Path.cwd()


def discover_py_files(root: Path) -> list[Path]:
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "ls-files", "*.py"],
            capture_output=True, text=True, check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return sorted(root / p for p in res.stdout.splitlines() if p.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return sorted(p for p in root.rglob("*.py") if "node_modules" not in p.parts and ".git" not in p.parts)


_PY_PARSER = None


def _get_parser() -> "Parser | None":
    global _PY_PARSER
    if not _TS_AVAILABLE:
        return None
    if _PY_PARSER is None:
        lang = Language(_py_language())
        _PY_PARSER = Parser(lang)
    return _PY_PARSER


def _node_text(src: bytes, node) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def parse_file(path: Path) -> dict[str, Any]:
    record: dict[str, Any] = {"path": str(path), "functions": [], "classes": [], "imports": []}
    try:
        src = path.read_bytes()
    except OSError:
        return record
    parser = _get_parser()
    if parser is None:
        # Fallback: regex-ish via ast
        import ast as _ast
        try:
            tree = _ast.parse(src.decode("utf-8", errors="replace"))
        except SyntaxError:
            return record
        for node in _ast.walk(tree):
            if isinstance(node, _ast.FunctionDef):
                record["functions"].append({"name": node.name, "line": node.lineno})
            elif isinstance(node, _ast.ClassDef):
                record["classes"].append({"name": node.name, "line": node.lineno})
            elif isinstance(node, _ast.Import):
                for n in node.names:
                    record["imports"].append(n.name)
            elif isinstance(node, _ast.ImportFrom):
                if node.module:
                    record["imports"].append(node.module)
        return record

    tree = parser.parse(src)
    root = tree.root_node

    def walk(node):
        t = node.type
        if t == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                record["functions"].append({"name": _node_text(src, name_node), "line": node.start_point[0] + 1})
        elif t == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                record["classes"].append({"name": _node_text(src, name_node), "line": node.start_point[0] + 1})
        elif t in ("import_statement", "import_from_statement"):
            record["imports"].append(_node_text(src, node).strip())
        for c in node.children:
            walk(c)

    walk(root)
    return record


def build_graph(root: Path, limit: int | None = None) -> dict[str, Any]:
    files = discover_py_files(root)
    if limit:
        files = files[:limit]
    records = [parse_file(p) for p in files]
    # normalize paths to relative
    for r in records:
        try:
            r["path"] = str(Path(r["path"]).relative_to(root))
        except ValueError:
            pass
    return {"root": str(root), "file_count": len(records), "files": records}


def self_test() -> int:
    fails = 0
    root = find_repo_root()
    # parse a known file
    sample = root / "scripts" / "ci" / "pr_preflight_guard.py"
    if sample.is_file():
        rec = parse_file(sample)
        if not any(f["name"] == "check_branch" for f in rec["functions"]):
            fails += 1
            print("FAIL parse-function", rec.get("functions"))
        else:
            print("PASS parse-function")
    # build small graph
    g = build_graph(root, limit=5)
    if g["file_count"] != 5:
        fails += 1
        print("FAIL graph-count", g["file_count"])
    else:
        print("PASS graph-count")
    # json serializable
    try:
        json.dumps(g)
        print("PASS json-serializable")
    except Exception as exc:
        fails += 1
        print("FAIL json", exc)
    print("self-test: %d failure(s)" % fails)
    return 0 if fails == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Local AST graph index (Phase C.1)")
    ap.add_argument("--root", default=None, help="Repository root (default: auto)")
    ap.add_argument("--output", default=None, help="Write JSON snapshot to this path")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of files")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    root = Path(args.root).resolve() if args.root else find_repo_root()
    graph = build_graph(root, limit=args.limit)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        print(f"wrote {out} ({graph['file_count']} files)")
    else:
        print(json.dumps({"file_count": graph["file_count"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
