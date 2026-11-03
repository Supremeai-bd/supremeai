"""AST contract test: no silent exception swallows in production code.

বাংলা: `except Exception:` ব্লকের বডি যদি কেবল pass/continue/return হয়
(কোনো logging/রিরেইজ ছাড়া), তাহলে ব্যতিক্রমটি নীরবে গিলে যায় — ডিবাগিং ও
ইনসিডেন্ট রেসপন্স অসম্ভব হয়ে যায়। Issue #1743 (slice-1): ৬৩টি এমন সাইটে
observability (logger.debug + exc_info) যোগ করা হয়েছে; এই কনট্র্যাক্ট টেস্ট
নিশ্চিত করে ক্লাসটি আর ফিরে আসবে না।

English: an except-handler catching Exception whose body is ONLY
pass/continue/return(-constant) — with no logging, no re-raise, no side
effect — is a "silent swallow". This contract fails if any such handler
appears in non-test production code (tests/, _archive/, alembic_migrations/
excluded).

House precedent: same AST-contract pattern as
backend/tests/api/routes/test_external_agents_admin.py.
"""

from __future__ import annotations

import ast
import os
from collections.abc import Iterator
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
EXCLUDE_PARTS = ("_archive", "alembic_migrations")
CONTROL_STATEMENTS = (ast.Pass, ast.Continue, ast.Return)

# Directory-level prune set: virtualenvs, caches, vendored trees. CI's poetry
# venv lives at backend/.venv INSIDE the repo — without pruning, the scan
# parses ~50k site-packages files and trips the per-test pytest timeout
# (merge-train batch CI failure on rollup PR #2179). Hidden dirs (.git,
# .venv, .tox, …) are pruned wholesale via the startswith(".") check.
PRUNE_DIRS = frozenset(
    {"_archive", "alembic_migrations", "__pycache__", "node_modules", "htmlcov", "venv"}
)


def _iter_python_files(root: Path) -> Iterator[Path]:
    """Yield .py paths under root, pruning vendored/virtualenv/cache trees.

    os.walk with in-place dirnames pruning never DESCENDS into excluded
    trees (rglob cannot prune and would enumerate every site-packages
    file). Sorted traversal keeps output deterministic.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in PRUNE_DIRS)
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield Path(dirpath) / name


def _is_exception_handler(handler: ast.ExceptHandler) -> bool:
    """True for `except:` (bare) or except Exception/BaseException (incl. tuples)."""
    if handler.type is None:
        return True
    t = handler.type
    if isinstance(t, ast.Name):
        return t.id in ("Exception", "BaseException")
    if isinstance(t, ast.Tuple):
        return any(
            isinstance(e, ast.Name) and e.id in ("Exception", "BaseException") for e in t.elts
        )
    return False


def _is_const_return(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.Return) and (
        stmt.value is None or isinstance(stmt.value, ast.Constant)
    )


def _is_silent_body(handler: ast.ExceptHandler) -> bool:
    return all(
        isinstance(s, CONTROL_STATEMENTS) and (not isinstance(s, ast.Return) or _is_const_return(s))
        for s in handler.body
    )


def scan_silent_swallows(root: Path) -> list[tuple[str, int, str]]:
    """Return (path, lineno, action) for every silent swallow under root."""
    hits: list[tuple[str, int, str]] = []
    for path in _iter_python_files(root):
        rel = path.as_posix()
        if (
            "/tests/" in rel
            or path.name.startswith("test_")
            or any(x in rel for x in EXCLUDE_PARTS)
        ):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _is_exception_handler(node):
                if _is_silent_body(node):
                    hits.append((rel, node.lineno, type(node.body[0]).__name__.lower()))
    return hits


def test_zero_silent_exception_swallows_in_production_code() -> None:
    hits = scan_silent_swallows(BACKEND_ROOT)
    assert not hits, (
        "Silent exception swallows detected (issue #1743 class) — add logging "
        "(logger.debug/execption with exc_info=True) or narrow the exception type:\n"
        + "\n".join(f"  {rel}:{ln} -> {action}" for rel, ln, action in hits)
    )


def test_scanner_detects_synthetic_silent_swallow() -> None:
    """Self-test: the scanner must NOT rot into a permanent no-op."""
    import tempfile

    source = (
        "def broken():\n    try:\n        risky()\n    except Exception:\n        return None\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "synthetic_module.py").write_text(source, encoding="utf-8")
        hits = scan_silent_swallows(root)
    assert len(hits) == 1, "scanner failed to detect a synthetic silent swallow"
    assert hits[0][2] == "return"


def test_scanner_ignores_instrumented_and_narrow_handlers() -> None:
    """Handlers with logging, re-raise, or narrow exception types are not 'silent'."""
    import tempfile

    source = (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "def ok_logged():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:\n"
        "        logger.debug('handled', exc_info=True)\n"
        "        return None\n"
        "def ok_reraise():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:\n"
        "        raise\n"
        "def ok_narrow():\n"
        "    try:\n"
        "        risky()\n"
        "    except ValueError:\n"
        "        return None\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "synthetic_ok.py").write_text(source, encoding="utf-8")
        assert scan_silent_swallows(root) == []
