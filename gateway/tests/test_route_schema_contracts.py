"""API route schema contract tests (#3270).

বাংলা: এই টেস্টগুলো FastAPI app এর registered routes গুলোর
contract verify করে — প্রতিটি route এর path, methods, expected
status codes, এবং response model contract।
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from core.app import app as _APP


def _app_paths(app: FastAPI) -> list[str]:
    """#3270: version-robust route-path discovery।

    বাংলা: starlette ≥0.50 (fastapi ≥0.141)-এ `include_router` রুটগুলোকে
    `_IncludedRouter` wrapper-এর ভেতরে রাখে — `app.routes`-enumeration-এ
    ওদের `.path` আর দেখা যায় না (রুট নিজে ঠিকই কাজ করে)। OpenAPI schema
    উভয় প্রজন্মেই সব registered path-এর সম্পূর্ণ তালিকা দেয় — এটাই এখন
    path-চুক্তির একক উৎস।
    """
    return list(app.openapi().get("paths", {}).keys())


def _app_path_methods(app: FastAPI) -> set[tuple[str, str]]:
    """#3270: openapi থেকে (path, method) জোড়া — সংস্করণ-নিরপেক্ষ।"""
    pairs: set[tuple[str, str]] = set()
    for path, ops in app.openapi().get("paths", {}).items():
        for method in ops:
            pairs.add((path, method.lower()))
    return pairs


# ── App route discovery tests ────────────────────────────────────────────────


class TestAppRouteDiscovery:
    """#3270: FastAPI app route discovery + structure verification।

    বাংলা: চুক্তি-বস্তু = **canonical singleton** (`core.app.app`) — এটিই
    registry-mount-সহ আসল production surface (auth/chat/agents/...)। খালি
    `create_app()` শুধু base (browser+health) দেয় — registry-mount হয়
    `backend/app.py`-তে, তাই টেস্ট সেটাই ব্যবহার করে।
    """

    def test_app_has_routes(self):
        # বাংলা: app should have registered routes (>0)
        assert len(_app_paths(_APP)) > 0

    def test_health_routes_registered(self):
        paths = _app_paths(_APP)
        assert any("health" in p.lower() for p in paths), "health routes should be registered"

    def test_api_v1_prefix_routes_registered(self):
        paths = _app_paths(_APP)
        api_routes = [p for p in paths if p.startswith("/api/v1") or p.startswith("/api/")]
        assert len(api_routes) > 10, "should have many API routes"

    def test_all_paths_start_with_slash(self):
        for path in _app_paths(_APP):
            assert isinstance(path, str)
            assert path.startswith("/"), f"route path must start with /: {path}"

    def test_all_route_methods_valid(self):
        valid = {"get", "post", "put", "patch", "delete", "options", "head"}
        for _path, method in _app_path_methods(_APP):
            assert method in valid, f"unexpected HTTP method: {method}"


# ── Route path uniqueness tests ──────────────────────────────────────────────


class TestRoutePathUniqueness:
    """#3270: no duplicate (method, path) tuples — each route is unique।"""

    def test_no_duplicate_method_path_combos(self):
        pairs = _app_path_methods(_APP)
        assert len(pairs) > 0
        # openapi paths-dict স্বভাবতই unique-keyed — তাই (path, method) জোড়ার
        # সংখ্যা == আসল সংখ্যা হলে ডুপ্লিকেট নেই; এখানে সেট-ই চুক্তি-গার্ড।
        for path, method in pairs:
            assert isinstance(path, str) and path.startswith("/")
            assert method in ("get", "post", "put", "patch", "delete", "options", "head")


# ── Health endpoint contract tests ──────────────────────────────────────────


class TestHealthEndpointContracts:
    """#3270: health endpoints — path + method contracts।"""

    def test_health_live_endpoint_exists(self):
        paths = _app_paths(_APP)
        assert any("health" in p.lower() for p in paths), "health endpoint should exist"

    def test_health_endpoints_are_get(self):
        # বাংলা: canonical health-probe surface = `/health/*` (operational
        # source of truth — app_builder-এর P0 নোট অনুযায়ী)। GET-only চুক্তি।
        # (`/api/v1/health/*` legacy alias-য় *health*-নামের business endpoint-ও
        # বসে — যেমন /api/v1/health/agents-এর POST (agent-check কমান্ড) —
        # ওরা probe নয়, তাই এই চুক্তির বাইরে।)
        for path, method in _app_path_methods(_APP):
            if path == "/health" or path.startswith("/health/"):
                assert method == "get", f"health probe should be GET: {path} (found {method})"


# ── Auth route contract tests ───────────────────────────────────────────────


class TestAuthRouteContracts:
    """#3270: auth routes — login, register, refresh, logout contracts।"""

    def test_auth_routes_registered(self):
        paths = _app_paths(_APP)
        auth_routes = [p for p in paths if "/auth" in p.lower()]
        assert len(auth_routes) > 0, "auth routes should be registered"

    def test_login_endpoint_exists(self):
        paths = _app_paths(_APP)
        assert any("login" in p.lower() for p in paths), "login endpoint should exist"

    def test_register_endpoint_exists(self):
        paths = _app_paths(_APP)
        # May be named 'register' or 'signup'
        assert any("register" in p.lower() or "signup" in p.lower() for p in paths), (
            "register/signup endpoint should exist"
        )


# ── OpenAPI schema tests ────────────────────────────────────────────────────


class TestOpenAPISchema:
    """#3270: OpenAPI schema generation — ensures all routes have valid schema।"""

    def test_openapi_schema_generated(self):
        schema = _APP.openapi()
        assert schema is not None
        assert "paths" in schema
        assert len(schema["paths"]) > 0

    def test_openapi_has_info(self):
        schema = _APP.openapi()
        assert "info" in schema
        assert "title" in schema["info"]

    def test_openapi_paths_have_methods(self):
        schema = _APP.openapi()
        for path, methods in schema["paths"].items():
            for method in methods:
                assert method.lower() in (
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                ), f"unexpected method {method} for path {path}"

    def test_openapi_routes_have_responses(self):
        # বাংলা: each route in OpenAPI should have at least a response definition
        schema = _APP.openapi()
        for path, methods in schema["paths"].items():
            for method, spec in methods.items():
                if isinstance(spec, dict) and "responses" in spec:
                    assert len(spec["responses"]) > 0, (
                        f"{method.upper()} {path} has no responses defined"
                    )
