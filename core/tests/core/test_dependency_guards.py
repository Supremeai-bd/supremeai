"""CI guardrail (DEP-AUDIT P0): heavy optional dependencies must never be
imported at module level without an ImportError guard.

"Heavy" = playwright, torch, sentence_transformers. They live in optional
poetry groups (`browser`, `ml`) and are ABSENT from the production core image
(`poetry install --only main`, see backend/Dockerfile). Any new unguarded
module-level import of these packages would crash the API at startup in
production — the very failure mode this file exists to prevent.

Accepted patterns per import site:
  lazy     — the import executes inside a function body (deferred to call time)
  guarded  — module-level import wrapped in try/except catching ImportError
             (ModuleNotFoundError/Exception/bare also accepted), with fallback

Standalone usage:  python tests/core/test_dependency_guards.py
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
HEAVY_PACKAGES = {"playwright", "torch", "sentence_transformers"}
_COVERING_EXC = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}
_SKIP_DIRS = {
    ".venv",
    ".venv_probe",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    ".git",
    "site-packages",
}


def _handler_covers(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:  # bare `except:`
        return True
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(t, ast.Name) and t.id in _COVERING_EXC for t in types)


def _classify(node: ast.AST, ancestor_chain: list[ast.AST]) -> str:
    for anc in ancestor_chain:  # nearest ancestor first
        if isinstance(anc, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return "lazy"
        if isinstance(anc, ast.Try) and any(_handler_covers(h) for h in anc.handlers):
            return "guarded"
    return "UNGUARDED"


def _unguarded_heavy_imports() -> list[tuple[Path, int, str]]:
    """Return (relpath, line, packages) for every unguarded heavy import site."""
    offenders: list[tuple[Path, int, str]] = []
    for path in sorted(BACKEND_ROOT.rglob("*.py")):
        if _SKIP_DIRS.intersection(path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue  # unparseable files are not this test's concern

        parents: dict[int, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[id(child)] = parent

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots = {node.module.split(".")[0]}
            else:
                continue
            heavy = roots & HEAVY_PACKAGES
            if not heavy:
                continue
            chain, cur = [], parents.get(id(node))
            while cur is not None:
                chain.append(cur)
                cur = parents.get(id(cur))
            if _classify(node, chain) == "UNGUARDED":
                offenders.append(
                    (path.relative_to(BACKEND_ROOT), node.lineno, ",".join(sorted(heavy)))
                )
    return offenders


def test_no_unguarded_heavy_imports():
    offenders = _unguarded_heavy_imports()
    assert not offenders, (
        "Unguarded module-level imports of optional heavy packages found.\n"
        "playwright/torch/sentence_transformers are NOT installed in the core\n"
        "production image (poetry install --only main), so these would crash\n"
        "startup. Wrap in try/except ImportError or move into a function:\n"
        + "\n".join(f"  {rel}:{line} [{pkg}]" for rel, line, pkg in offenders)
    )


def test_session_takeover_imports_without_playwright():
    """Dynamic proof: with playwright unimportable, the guard falls back to Any."""
    saved = {
        k: v for k, v in sys.modules.items() if k == "playwright" or k.startswith("playwright.")
    }
    for key in saved:
        del sys.modules[key]

    class PlaywrightBlocker:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "playwright" or fullname.startswith("playwright."):
                raise ImportError(f"playwright blocked for test: {fullname}")
            return None

    sys.meta_path.insert(0, PlaywrightBlocker())
    try:
        spec = importlib.util.spec_from_file_location(
            "session_takeover_isolated_guard_test",
            str(BACKEND_ROOT / "api" / "routes" / "session_takeover.py"),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.Page is Any, f"expected Any fallback, got {module.Page!r}"
    finally:
        sys.meta_path.pop(0)
        sys.modules.update(saved)  # restore for any other test in the session


if __name__ == "__main__":
    bad = _unguarded_heavy_imports()
    if bad:
        print("FAIL: unguarded heavy imports:")
        for rel, line, pkg in bad:
            print(f"  {rel}:{line} [{pkg}]")
        sys.exit(1)
    print(f"PASS: no unguarded {sorted(HEAVY_PACKAGES)} imports in backend")
    sys.exit(0)
