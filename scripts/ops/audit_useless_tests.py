"""Audit: find test files whose internal imports cannot resolve (tests dead code).

Zero-dependency stdlib. One cheap signal only (no over-engineering): a test
importing a first-party module that no longer exists is guaranteed dead weight.
NOTE: find_spec needs the repo root on sys.path because tests import first-party
packages by top-level name (core/, gateway/, scripts/ live at repo root).
"""
import ast
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOTS = [Path("tests"), Path("gateway/tests"), Path("core/tests")]

dead_imports = []
for root in ROOTS:
    if not root.exists():
        continue
    for py in root.rglob("test_*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        seen = set()
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods = [node.module]
            for m in mods:
                if not m.split(".")[0] in ("core", "gateway", "scripts", "browser"):
                    continue
                try:
                    missing = importlib.util.find_spec(m) is None
                except ModuleNotFoundError:
                    missing = True
                if missing and m not in seen:
                    seen.add(m)
                    dead_imports.append((str(py), m))

print(f"== test files importing first-party modules that DO NOT EXIST ({len(dead_imports)}) ==")
for p, m in dead_imports:
    print(f"  {p} -> {m}")
