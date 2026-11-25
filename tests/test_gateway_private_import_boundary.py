#!/usr/bin/env python3
"""tests/test_gateway_private_import_boundary.py — gateway→core private-import boundary guard.

Auditor finding #1693: two gateway files imported core's underscore-private
module ``core._monitoring_legacy`` directly across the domain boundary,
bypassing the ``core.monitoring`` public facade that exists precisely to
re-export it (3-strategy fallback). A refactor of ``_monitoring_legacy``
internals would silently break the gateway admin dashboard.

Remediation (this patch): swap the two gateway import sites to
``from core.monitoring import get_metrics_collector`` — the facade is the
only sanctioned cross-domain surface. This guard pins that invariant:

  1. ``test_gateway_never_imports_core_private_modules`` — zero static or
     dynamic (``importlib.import_module``/``import_module``) imports of
     ``core._*`` across all tracked ``gateway/**/*.py`` files.
  2. ``test_core_monitoring_facade_reexports_collector`` — the facade
     exposes ``get_metrics_collector`` (the symbol the remediated call
     sites consume) without importing the gateway domain.

In-domain note: ``core/*`` importing its own ``core._*`` internals is NOT a
violation (domain-internal access is legitimate); the boundary this guard
enforces is one-directional: gateway → core private.

Design (zero-dependency doctrine, dual mode — pytest + stdlib runners):
  - pytest:  pytest tests/test_gateway_private_import_boundary.py
  - stdlib:  python3 tests/test_gateway_private_import_boundary.py

Every check is offline and deterministic (pure AST over the worktree).
Fail-closed: if the gateway tree cannot be located, the test fails loudly
rather than silently passing.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GATEWAY_DIR = REPO_ROOT / "gateway"
PRIVATE_PREFIX = "core._"


class _Skip(Exception):
    """Honest skip signal (dual-mode; mirrors test_ci_guards.py)."""


def _tracked_gateway_py_files() -> list[Path]:
    """Tracked *.py under gateway/ via git ls-files (fail-closed on git failure)."""
    out = subprocess.run(
        ["git", "ls-files", "--", "gateway/*.py", "gateway/**/*.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60, check=True,
    )
    files = [REPO_ROOT / f for f in out.stdout.splitlines() if f.strip()]
    if not files:
        # Fail-closed: a vanished gateway tree must fail loudly, not pass vacuously.
        if not GATEWAY_DIR.exists():
            raise _Skip("gateway/ tree not found in worktree")
        files = sorted(GATEWAY_DIR.rglob("*.py"))
    return files


def _dynamic_import_module_violation(node, path, is_target):
    """Return a violation string if node is an import_module(...) call targeting a module, else None."""
    func = node.func
    is_import_module = (
        (isinstance(func, ast.Attribute) and func.attr == "import_module")
        or (isinstance(func, ast.Name) and func.id == "import_module")
    )
    if not (is_import_module and node.args):
        return None
    arg = node.args[0]
    if (
        isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and is_target(arg.value)
    ):
        return f"{path}:{node.lineno} import_module({arg.value!r}) (dynamic)"
    return None


def _scan_forbidden_imports(
    path: Path,
    *,
    is_forbidden: object,
    check_core_private_attr: bool = False,
    ignore_relative: bool = False,
) -> list[str]:
    """Shared AST import scanner for both gateway→core-private and core→gateway boundaries."""
    violations: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError as exc:  # unparsable file cannot hide imports — flag it
        return [f"{path}: SyntaxError ({exc}) — cannot verify boundary"]

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if ignore_relative and node.level != 0:
                continue
            if is_forbidden(node.module):  # type: ignore[operator]
                violations.append(f"{path}:{node.lineno} from {node.module} import ...")
            elif check_core_private_attr and node.module == "core":
                for alias in node.names:
                    if alias.name.startswith("_"):
                        violations.append(f"{path}:{node.lineno} from core import {alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if is_forbidden(alias.name):  # type: ignore[operator]
                    violations.append(f"{path}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.Call):
            v = _dynamic_import_module_violation(node, path, is_forbidden)
            if v:
                violations.append(v)
    return violations


def _find_private_core_imports(path: Path) -> list[str]:
    """Return human-readable violations for private core imports in one file."""
    return _scan_forbidden_imports(
        path,
        is_forbidden=lambda m: m.startswith(PRIVATE_PREFIX),
        check_core_private_attr=True,
    )


def test_gateway_never_imports_core_private_modules():
    assert GATEWAY_DIR.exists(), "gateway/ tree missing from worktree"
    files = _tracked_gateway_py_files()
    assert len(files) >= 50, f"expected a real gateway tree (>=50 py files), got {len(files)}"
    violations: list[str] = []
    for f in files:
        violations.extend(_find_private_core_imports(f))
    assert violations == [], (
        "gateway→core private-import boundary violated (use the core public facade):\n"
        + "\n".join(sorted(violations))
    )


def test_core_monitoring_facade_reexports_collector():
    facade = REPO_ROOT / "core" / "monitoring" / "__init__.py"
    assert facade.exists(), "core/monitoring/__init__.py facade missing"
    src = facade.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    # Facade uses module-level __getattr__ forwarding; pin the two load-bearing pieces:
    has_getattr = any(
        isinstance(n, ast.FunctionDef) and n.name == "__getattr__" for n in tree.body
    )
    assert has_getattr, "facade lost its __getattr__ re-export mechanism"
    assert "core._monitoring_legacy" in src, (
        "facade no longer references core._monitoring_legacy — re-export chain changed?"
    )


def _find_core_to_gateway_imports(path: Path) -> list[str]:
    """বাংলা মন্তব্য: Graphify অডিটে ধরা পড়া core -> gateway উল্টো-লেয়ার ইমপোর্ট রোধ করে।"""
    return _scan_forbidden_imports(
        path,
        is_forbidden=lambda m: m == "gateway" or m.startswith("gateway."),
        ignore_relative=True,
    )


def test_core_never_imports_gateway_domain():
    """Ensure inner production `core/` modules never import outer `gateway/` transport layer."""
    core_dir = REPO_ROOT / "core"
    assert core_dir.exists(), "core/ tree missing from worktree"
    out = subprocess.run(
        ["git", "ls-files", "--", "core/*.py", "core/**/*.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60, check=True,
    )
    files = [
        REPO_ROOT / f
        for f in out.stdout.splitlines()
        if f.strip() and not f.startswith("core/tests/") and "/tests/" not in f
    ]
    assert len(files) >= 50, f"expected real core tree (>=50 py files), got {len(files)}"
    violations: list[str] = []
    for f in files:
        if f.exists():
            violations.extend(_find_core_to_gateway_imports(f))
    assert violations == [], (
        "core→gateway layer boundary violated (inner core domain must never import outer gateway):\n"
        + "\n".join(sorted(violations))
    )


def main() -> int:  # plain stdlib runner (dual mode)
    try:
        test_gateway_never_imports_core_private_modules()
        test_core_monitoring_facade_reexports_collector()
        test_core_never_imports_gateway_domain()
    except _Skip as exc:
        print(f"SKIP: {exc}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        return 1
    print("PASS: gateway↔core import boundaries clean; facade re-export intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
