# SupremeAI 2.0 — Route RBAC Security Matrix Regression Suite
# বাংলা মন্তব্য: কনসোলিডেটেড রাউটগুলোর জন্য RBAC সিকিউরিটি ম্যাট্রিক্স। প্রতিটি
# অ্যাডমিন রাউটে require_admin_token ডিপেন্ডেন্সি থাকতে হবে, আর পাবলিক রাউটে
# কোনো অ্যাডমিন গার্ড থাকবে না — এটাই ফেইজ-৩ এর fail-closed নীতি।

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

# Import guard: route modules may transitively import optional google.genai.
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.genai", MagicMock())

from fastapi import APIRouter  # noqa: E402
from fastapi.security import HTTPAuthorizationCredentials  # noqa: E402


def _collect_auth_dependency_names(route) -> set[str]:
    """Collect every auth-related dependency callable name guarding a route.

    Covers router-level dependencies (e.g. APIRouter(dependencies=[...])),
    endpoint parameter-level Depends(...), and one level of nested sub-dependencies.
    FastAPI stores these either as ``Dependant`` objects (via ``.call``) or wrapped
    ``Depends`` objects (via ``.dependency``), so both are checked.
    """

    def _name_of(dep) -> str:
        fn = getattr(dep, "call", None) or getattr(dep, "dependency", None)
        return getattr(fn, "__name__", "")

    names: set[str] = set()
    for d in getattr(route, "dependencies", []) or []:
        names.add(_name_of(d))
    dependant = getattr(route, "dependant", None)
    if dependant is not None:
        for d in dependant.dependencies:
            names.add(_name_of(d))
            sub = getattr(d, "dependant", None)
            if sub is not None:
                for sd in sub.dependencies:
                    names.add(_name_of(sd))
    return names


def _routes_of(module_path: str) -> APIRouter:
    module = __import__(module_path, fromlist=["router"])
    return module.router


def _find_route(router: APIRouter, path: str):
    for route in router.routes:
        if getattr(route, "path", None) == path:
            return route
    raise AssertionError(f"Route {path} not found in {router}")


# ── Wholly-admin routers: router-level guard must cover every route ─────────
ADMIN_ROUTER_MODULES = [
    "api.routes.admin_dashboard",
    "api.routes.admin_v1",
]


@pytest.mark.parametrize("module_path", ADMIN_ROUTER_MODULES)
def test_admin_router_modules_enforce_admin_token(module_path):
    """Fail-closed matrix: all admin router routes carry require_admin_token."""
    router = _routes_of(module_path)
    unguarded = []
    for route in router.routes:
        methods = getattr(route, "methods", None) or set()
        if methods and methods == {"OPTIONS"}:
            continue
        deps = _collect_auth_dependency_names(route)
        if "require_admin_token" not in deps:
            unguarded.append((getattr(route, "path", "?"), sorted(methods)))
    assert unguarded == [], f"Unguarded admin routes in {module_path}: {unguarded}"


# ── Curated positive matrix: sensitive paths MUST be admin-guarded ──────────
# (module, path) -> expected to require an admin token
ADMIN_GUARDED_PATHS = [
    ("api.routes.browser", "/api/browser/credentials"),
    ("api.routes.browser", "/api/browser/credentials/{id}"),
    ("api.routes.browser", "/api/browser/scrape"),
    ("api.routes.browser", "/api/browser/browse"),
    ("api.routes.browser", "/api/browser/extract"),
    ("api.routes.browser", "/api/browser/urls/allowAll"),
    ("api.routes.config_routes", "/config/{key}"),
    ("api.routes.evolution", "/evolution/logs"),
    ("api.routes.evolution", "/evolution/quarantine"),
    ("api.routes.evolution", "/evolution/proposals"),
    ("api.routes.evolution", "/evolution/breed"),
    ("api.routes.evolution", "/evolution/evaluate-performance"),
]


@pytest.mark.parametrize("module_path,path", ADMIN_GUARDED_PATHS)
def test_sensitive_paths_require_admin_token(module_path, path):
    router = _routes_of(module_path)
    route = _find_route(router, path)
    deps = _collect_auth_dependency_names(route)
    assert "require_admin_token" in deps, f"{path} in {module_path} missing admin guard"


# ── Public paths must NOT carry an admin guard (fail-open prevention) ───────
PUBLIC_PATHS = [
    ("api.routes.config_routes", "/config/public"),
]


@pytest.mark.parametrize("module_path,path", PUBLIC_PATHS)
def test_public_paths_not_admin_guarded(module_path, path):
    router = _routes_of(module_path)
    route = _find_route(router, path)
    deps = _collect_auth_dependency_names(route)
    assert "require_admin_token" not in deps, f"Public route {path} is admin-gated"


def test_public_auth_login_not_admin_guarded():
    """The login endpoint must be publicly reachable, never admin-only."""
    from api.routes import auth as auth_routes

    router = auth_routes.router
    login_routes = [r for r in router.routes if "login" in getattr(r, "path", "")]
    assert login_routes, "Expected at least one login route"
    for route in login_routes:
        deps = _collect_auth_dependency_names(route)
        assert "require_admin_token" not in deps, (
            f"Login route {route.path} is admin-gated (should be public)"
        )


def test_health_endpoint_not_admin_guarded():
    """Health checks are public and must not require an admin token."""
    try:
        from api.routes import health as health_routes
    except Exception:
        pytest.skip("health routes module not importable in this environment")
    router = health_routes.router
    for route in router.routes:
        deps = _collect_auth_dependency_names(route)
        assert "require_admin_token" not in deps, f"Health route {route.path} is admin-gated"


# ── Building blocks: admin token dependency must fail-closed ────────────────
def test_require_admin_token_rejects_invalid_token():
    """A non-admin / malformed token must be rejected (fail-closed)."""
    from unittest.mock import MagicMock

    from fastapi import HTTPException, Request

    from api.routes.admin_auth import require_admin_token

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-valid-jwt")
    request_mock = MagicMock(spec=Request)
    request_mock.cookies = {}

    with pytest.raises(HTTPException) as exc_info:
        # require_admin_token is async; exercised via asyncio.run
        asyncio.run(require_admin_token(request=request_mock, credentials=creds))
    assert exc_info.value.status_code in (401, 403)
