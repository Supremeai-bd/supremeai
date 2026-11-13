"""Regression guard: Core API route modules must never ship fail-open auth stubs.

Context (audit finding N1)
--------------------------
Several route modules used to guard the auth-dependency import like this::

    try:
        from core.api.deps import get_current_user_token
    except ImportError:
        try:
            from api.deps import get_current_user_token
        except ImportError:  # pragma: no cover -- CI bootstrap only
            async def get_current_user_token() -> str:
                return "mock-token"

That innermost ``except ImportError`` branch is a FAIL-OPEN security hole. If
the auth module cannot be imported -- a bad deploy, a missing dependency, a
renamed package -- every endpoint that depends on ``get_current_user_token``
silently resolves to a permissive stub that always succeeds, so anonymous
callers reach routes that were supposed to be token-guarded.

The correct shape is FAIL-CLOSED::

    except ImportError:
        raise

so importing the app fails loudly at startup instead of quietly serving
unauthenticated traffic.

What this test enforces
-----------------------
It parses every ``.py`` file under ``core/api/routes/`` with the AST and fails
when any ``except ImportError`` handler *defines a function whose body returns
a string literal* -- the structural signature of a permissive auth stub.

The detector is deliberately narrow (only ``except ImportError`` handlers, only
function definitions, only constant ``str`` returns) so it does not flag
legitimate optional-dependency fallbacks -- for example the "reportlab not
installed, fall back to markdown" handlers in ``chat_export.py`` -- which are
not authentication dependencies and are allowed to degrade gracefully.

The companion tests at the bottom prove the detector is not a silent no-op:
one feeds it the known-bad N1 snippet (must be flagged) and one feeds it the
fail-closed replacement (must pass).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# core/tests/test_no_auth_stubs.py -> core/ -> core/api/routes
ROUTES_DIR = Path(__file__).resolve().parents[1] / "api" / "routes"

_ROUTE_MODULES: tuple[Path, ...] = tuple(
    sorted(path for path in ROUTES_DIR.rglob("*.py") if path.is_file())
)


def _catches_import_error(node: ast.expr | None) -> bool:
    """True when an ``except`` clause names ImportError (bare, qualified or in a tuple)."""
    if node is None:
        return False
    if isinstance(node, ast.Tuple):
        return any(_catches_import_error(element) for element in node.elts)
    if isinstance(node, ast.Name):
        return node.id == "ImportError"
    if isinstance(node, ast.Attribute):
        return node.attr == "ImportError"
    return False


def _returned_string_literal(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str | None:
    """Return the first constant string this function returns, else None.

    A permissive stub is exactly ``def f() -> str: return "something"``, so the
    presence of a literal (non-computed) string return is the signal we look for.
    """
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant):
            value = node.value.value
            if isinstance(value, str):
                return value
    return None


def _fail_open_stubs(source: str, filename: str = "<memory>") -> list[tuple[str, int, str, str]]:
    """Find permissive stubs defined inside ``except ImportError`` handlers.

    Returns a list of ``(filename, lineno, function_name, returned_literal)``.
    ``ast.walk`` visits nested handlers on its own, so only the statements that
    sit directly in each handler body need to be inspected.
    """
    tree = ast.parse(source, filename=filename)
    offenders: list[tuple[str, int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or not _catches_import_error(node.type):
            continue
        for statement in node.body:
            if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            literal = _returned_string_literal(statement)
            if literal is not None:
                offenders.append((filename, statement.lineno, statement.name, literal))
    return offenders


def _describe(offenders: list[tuple[str, int, str, str]]) -> str:
    return "\n".join(
        f"  {filename}:{lineno}: def {name}() returns {literal!r}"
        for filename, lineno, name, literal in offenders
    )


def test_route_modules_are_discovered() -> None:
    """Guard against a silently vacuous scan (wrong cwd, renamed directory)."""
    assert ROUTES_DIR.is_dir(), f"routes directory not found: {ROUTES_DIR}"
    assert _ROUTE_MODULES, f"no Python modules discovered under {ROUTES_DIR}"


@pytest.mark.parametrize("module_path", _ROUTE_MODULES, ids=lambda path: path.name)
def test_route_module_has_no_fail_open_auth_stub(module_path: Path) -> None:
    offenders = _fail_open_stubs(
        module_path.read_text(encoding="utf-8"),
        str(module_path),
    )
    assert not offenders, (
        "Fail-open authentication stub detected in a Core API route module.\n"
        "An `except ImportError` handler defines a function returning a string "
        "literal, so a missing auth dependency silently degrades into an "
        "allow-all dependency instead of refusing to start.\n"
        "Fix by making the handler fail closed:\n"
        "    except ImportError:\n"
        "        raise\n"
        "Offenders:\n" + _describe(offenders)
    )


def test_detector_flags_the_known_bad_pattern() -> None:
    """The guard must not be a no-op: it has to catch the original N1 snippet."""
    bad_source = '''
try:
    from core.api.deps import get_current_user_token
except ImportError:
    try:
        from api.deps import get_current_user_token
    except ImportError:  # pragma: no cover - CI bootstrap only
        async def get_current_user_token() -> str:
            return "mock-token"
'''
    offenders = _fail_open_stubs(bad_source, "<known-bad>")
    assert len(offenders) == 1, f"expected exactly one stub, got {offenders}"
    _, _, name, literal = offenders[0]
    assert name == "get_current_user_token"
    assert literal == "mock-token"


def test_detector_accepts_the_fail_closed_fix() -> None:
    """The sanctioned replacement (`except ImportError: raise`) must pass."""
    fixed_source = '''
try:
    from core.api.deps import get_current_user_token
except ImportError:
    try:
        from api.deps import get_current_user_token
    except ImportError:
        raise
'''
    assert _fail_open_stubs(fixed_source, "<fixed>") == []


def test_detector_ignores_non_auth_optional_dependency_fallbacks() -> None:
    """Graceful degradation for a non-auth dependency must stay allowed.

    Covers the two tolerated shapes already present in ``core/api/routes/``:

    * ``chat_export.py`` -- the handler logs and returns a value directly,
      without defining a replacement dependency function.
    * ``payments.py`` -- the handler defines a vendor-SDK mock *class*, not a
      bare auth-dependency function.
    """
    direct_return_source = '''
try:
    from reportlab.pdfgen import canvas
except ImportError:
    logger.warning("reportlab not installed; falling back to markdown-as-PDF.")
    return _build_markdown(conversation, messages).encode("utf-8")
'''
    assert _fail_open_stubs(direct_return_source, "<direct-return>") == []

    mock_class_source = '''
try:
    import stripe
except ImportError:
    class _MockStripe:
        class Webhook:
            @staticmethod
            def construct_event(*args, **kwargs):
                raise RuntimeError("Stripe webhook not configured")

    stripe = _MockStripe
'''
    assert _fail_open_stubs(mock_class_source, "<mock-class>") == []
