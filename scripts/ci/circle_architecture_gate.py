from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_CROSS_CIRCLE_IMPORTS = {
    "backend/memory": {"backend/brain", "backend/core/browser_session_manager.py"},
    "backend/brain": {"backend/memory", "backend/core/browser_session_manager.py"},
}


def module_name(path: Path) -> str:
    return str(path).replace("\\", "/")


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.add(node.module)
    return values


def violations(root: Path) -> list[str]:
    found: list[str] = []
    for source_root, blocked in FORBIDDEN_CROSS_CIRCLE_IMPORTS.items():
        source_dir = root / source_root
        if not source_dir.exists():
            continue
        for path in source_dir.rglob("*.py"):
            imported = " ".join(sorted(imports(path)))
            for target in blocked:
                target_module = target.removesuffix(".py").replace("/", ".")
                if target_module in imported or target.replace("/", ".") in imported:
                    found.append(f"{module_name(path)} imports forbidden cross-circle dependency {target}")
    return found


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    errors = violations(root)
    if errors:
        print("\n".join(errors))
        return 1
    print("circle architecture gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
