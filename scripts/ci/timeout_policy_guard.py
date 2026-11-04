#!/usr/bin/env python3
"""Timeout policy guard — enforces explicit timeout on network calls.

Prevents unbounded network hangs in production services.
Scans runtime code in core/ and gateway/ (excluding tests, venvs, devops scripts, and examples).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]

NETWORK_FUNCS = {
    ("urllib", "request", "urlopen"),
    ("requests", "get"),
    ("requests", "post"),
    ("requests", "put"),
    ("requests", "delete"),
    ("requests", "patch"),
    ("requests", "request"),
    ("httpx", "get"),
    ("httpx", "post"),
    ("httpx", "put"),
    ("httpx", "delete"),
    ("httpx", "patch"),
    ("httpx", "request"),
}

EXCLUDE_PARTS = {
    "tests", "test", "mock", ".venv", "venv", "node_modules", "examples",
    ".pytest_cache", "__pycache__", "site-packages", "docs", "scripts", "github", ".github"
}


class TimeoutVisitor(ast.NodeVisitor):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.violations: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        func_name = ""
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            val = node.func.value
            mod_chain = []
            while isinstance(val, ast.Attribute):
                mod_chain.append(val.attr)
                val = val.value
            if isinstance(val, ast.Name):
                mod_chain.append(val.id)
            mod_chain.reverse()
            full_call = (*mod_chain, func_name)

            is_match = False
            if full_call in NETWORK_FUNCS:
                is_match = True
            elif mod_chain and mod_chain[-1] in ("requests", "httpx") and func_name in ("get", "post", "put", "delete", "request"):
                is_match = True
            elif func_name == "urlopen" and mod_chain and mod_chain[-1] in ("request", "urllib"):
                is_match = True

            if is_match:
                has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
                if not has_timeout and func_name == "urlopen" and len(node.args) >= 3:
                    has_timeout = True

                if not has_timeout:
                    self.violations.append(
                        f"{self.filename}:{node.lineno} -> {'.'.join(full_call)}() missing explicit timeout="
                    )

        self.generic_visit(node)


def main() -> int:
    scan_dirs = [REPO_ROOT / "core", REPO_ROOT / "gateway"]
    all_violations: list[str] = []

    for s_dir in scan_dirs:
        if not s_dir.exists():
            continue
        for py_path in s_dir.rglob("*.py"):
            parts = set(py_path.parts)
            if parts.intersection(EXCLUDE_PARTS):
                continue

            try:
                tree = ast.parse(py_path.read_text(encoding="utf-8", errors="replace"), filename=str(py_path))
                visitor = TimeoutVisitor(str(py_path.relative_to(REPO_ROOT)))
                visitor.visit(tree)
                all_violations.extend(visitor.violations)
            except Exception:
                pass

    if all_violations:
        print(f"[FAIL] timeout_policy_guard found {len(all_violations)} call(s) without timeout:")
        for v in all_violations:
            print(f"  - {v}")
        return 1

    print("[PASS] timeout_policy_guard: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
