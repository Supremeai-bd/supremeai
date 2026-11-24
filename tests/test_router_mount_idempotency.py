"""Regression tests for the router double-mount foot-gun (audit 2026-11-24).

``register_router`` deduplicates mounts by ``(id(router), prefix)`` via
``app.state.mounted_routers``. Without that guard, ``api.routes.browser``
would be mounted twice for every role except ``core`` (once by the optional
registry loop, once by the explicit ``app_builder`` call). These tests pin the
two properties the deployment depends on:

1. mounting the same module twice with the same prefix is a silent no-op,
2. mounting the same module with DIFFERENT dependencies is a hard error
   (a security misconfiguration must never be silently accepted).

Note: fastapi >= 0.115 no longer flattens included routers into ``app.routes``
at include time (it mounts a lazy ``_IncludedRouter``), so mount counts are
asserted on ``len(app.routes)`` and on the OpenAPI document, not on flattened
route paths.
"""

from __future__ import annotations

import sys
import types

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi is required to build an app")

from fastapi import APIRouter, FastAPI  # noqa: E402

from core.api import register_router  # noqa: E402


def _fake_router_module(module_name: str) -> types.ModuleType:
    module = types.ModuleType(module_name)
    router = APIRouter()

    @router.get("/ping")
    async def _ping():  # pragma: no cover - route body irrelevant for mounting
        return {"ok": True}

    module.router = router
    sys.modules[module_name] = module
    return module


def _new_app() -> FastAPI:
    return FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def test_register_router_mounts_exactly_once():
    name = "tests._fake_router_idempotent"
    _fake_router_module(name)
    try:
        app = _new_app()
        assert len(app.routes) == 0
        register_router(app, name, optional=False)
        register_router(app, name, optional=False)  # must no-op, not duplicate
        assert len(app.routes) == 1
        assert "/ping" in app.openapi()["paths"]
    finally:
        sys.modules.pop(name, None)


def test_register_router_same_dependencies_noop():
    name = "tests._fake_router_deps_same"
    _fake_router_module(name)
    try:
        app = _new_app()
        register_router(app, name, dependencies=["dep-a"], optional=False)
        register_router(app, name, dependencies=["dep-a"], optional=False)
        assert len(app.routes) == 1
    finally:
        sys.modules.pop(name, None)


def test_register_router_conflicting_dependencies_raise():
    name = "tests._fake_router_deps_conflict"
    _fake_router_module(name)
    try:
        app = _new_app()
        register_router(app, name, dependencies=["dep-a"], optional=False)
        with pytest.raises(ValueError, match="Conflicting authentication dependencies"):
            register_router(app, name, dependencies=["dep-b"], optional=False)
    finally:
        sys.modules.pop(name, None)


def test_register_router_optional_missing_module_records_but_does_not_raise():
    app = _new_app()
    from core.api import _registration_report

    before = len(_registration_report)
    register_router(app, "tests._module_that_does_not_exist_xyz", optional=True)
    assert len(_registration_report) == before + 1
    assert len(app.routes) == 0
