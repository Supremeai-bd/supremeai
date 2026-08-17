"""backend arch refactor — নিরাপদ মডিউল মুভ হেল্পার।

প্রতিটি মুভ করে:
  1) git mv backend/core/X.py -> backend/<pkg>/X.py
  2) সরানো ফাইলের ভিতরের relative import (from .Y) -> absolute (from backend.core.Y)
     (যাতে সহ-মুভ করা অন্য ফাইলের shim থাকলেও ভাঙ্গে না)
  3) backend/core/X.py এ DeprecationWarning shim রাখে (বাইরের importer অক্ষত থাকে)

ব্যবহার:
  python scripts/refactor/move_core_modules.py --moves '[["backend/core/billing_plans.py","backend/services/billing/billing_plans.py"], ...]'
"""
import ast
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r"F:\supremeai backup")


def fix_relative_imports(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        print(f"  ! SKIP import-fix (syntax error): {path}")
        return False
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level and node.level >= 1:
            if node.level == 1:
                base = "backend.core"
            else:
                base = "backend"
            new_mod = base + (("." + node.module) if node.module else "")
            edits.append((node, new_mod))
    if not edits:
        return False
    lines = src.splitlines(keepends=True)
    for node, new_mod in sorted(edits, key=lambda e: e[0].lineno, reverse=True):
        start = node.lineno - 1
        end = node.end_lineno if node.end_lineno else node.lineno
        names = [
            a.name + (f" as {a.asname}" if a.asname else "") for a in node.names
        ]
        indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
        newline = f"{indent}from {new_mod} import {', '.join(names)}\n"
        lines[start:end] = [newline]
    path.write_text("".join(lines), encoding="utf-8")
    print(f"  ~ fixed {len(edits)} relative import(s): {path.name}")
    return True


def ensure_init(pkg_dir: Path) -> None:
    init = pkg_dir / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
        print(f"  + created {init.relative_to(REPO)}")


def dotted_from_path(p: Path) -> str:
    rel = p.relative_to(REPO).with_suffix("")
    return ".".join(rel.parts)


def write_shim(old_path: Path, new_dotted: str) -> None:
    name = old_path.stem
    content = (
        f"# DEPRECATED: backend.core.{name} -> {new_dotted}\n"
        "# নোট: backend architecture refactor plan অনুযায়ী সরানো হয়েছে।\n"
        "# ভবিষ্যতে সব importer নতুন path-এ সরিয়ে এই shim মুছে ফেলতে হবে।\n"
        "import warnings\n"
        "warnings.warn(\n"
        f"    \"backend.core.{name} is deprecated; import from {new_dotted}\",\n"
        "    DeprecationWarning, stacklevel=2,\n"
        ")\n"
        f"from {new_dotted} import *  # noqa: F401,F403\n"
    )
    old_path.write_text(content, encoding="utf-8")
    print(f"  + shim written: {old_path.relative_to(REPO)}")


def move_one(old_rel: str, new_rel: str) -> None:
    old = REPO / old_rel
    new = REPO / new_rel
    print(f"[move] {old_rel} -> {new_rel}")
    new.parent.mkdir(parents=True, exist_ok=True)
    ensure_init(new.parent)
    subprocess.run(["git", "mv", str(old), str(new)], cwd=REPO, check=True)
    fix_relative_imports(new)
    write_shim(old, dotted_from_path(new))


def main() -> None:
    if "--moves-file" in sys.argv:
        idx = sys.argv.index("--moves-file")
        moves = json.loads(Path(sys.argv[idx + 1]).read_text(encoding="utf-8"))
    elif "--moves" in sys.argv:
        idx = sys.argv.index("--moves")
        moves = json.loads(sys.argv[idx + 1])
    else:
        print("Usage: --moves-file <path.json>   (file contains [[\"old\",\"new\"], ...])")
        sys.exit(1)
    for old_rel, new_rel in moves:
        move_one(old_rel, new_rel)
    print("DONE")


if __name__ == "__main__":
    main()
