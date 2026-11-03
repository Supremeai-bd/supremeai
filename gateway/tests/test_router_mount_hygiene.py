"""Router mount hygiene — every registry router mounts EXACTLY once.

Background (2026-09-15 mount-dedup repair): PR #304/#305 shipped direct
``include_router`` blocks in ``core/app.py`` while PR #307 additionally
registered the same routers in the canonical ``ALL_ROUTERS`` registry — the app
ended up with 22 mission + 14 mcp-hub routes (each endpoint registered twice).
First-match wins at runtime so requests still worked, but OpenAPI listed
duplicates and the registry's mounted=N/N accounting no longer described the
app. This sentinel pins the invariant:

    1. the missions router contributes exactly 11 route registrations (one
       per @router decorator in the module — POST/GET on the same path are
       separate registrations, but a double-mount would make it 22);
    2. the mcp-hub router contributes exactly 7;
    3. NO (route path, method, endpoint) triple appears more than once on the
       app — any future double-mount of ANY router fails this test.

The duplicate-detection arc is the durable half: it does not hardcode counts,
so it keeps guarding every future router without maintenance.
"""

from __future__ import annotations

from collections import Counter

from fastapi.routing import APIRoute

from tests.api._route_introspection import (
    app_effective_routes,
    route_endpoint,
    route_methods,
    route_module_name,
    route_path,
)


def _app_routes():
    """Effective (mount-time) routes — FastAPI ≥0.141 lazy-include tolerant.

    বাংলা মন্তব্য: fastapi 0.141+ এ include_router lazy (_IncludedRouter) —
    app.routes-এ expanded APIRoute থাকে না; helper দুই আচরণকেই একরূপ করে
    (CI triage #2597)।"""
    from core.app import app

    return app_effective_routes(app)


def test_missions_router_mounted_exactly_once() -> None:
    import api.routes.missions as missions_module

    routes = [r for r in _app_routes() if route_module_name(r) == missions_module.__name__]
    # 11 endpoint registrations in api/routes/missions.py (create, list, get,
    # approve, start, advance, fail, repair, cancel, trace, trace/stream).
    # Counting registrations (not unique paths): POST+GET share "" — a second
    # full mount would double this to 22.
    assert len(routes) == 11, (
        f"missions router should contribute 11 route registrations, got "
        f"{len(routes)}: {sorted((route_path(r), tuple(route_methods(r))) for r in routes)}"
    )


def test_mcp_hub_router_mounted_exactly_once() -> None:
    import api.routes.mcp_hub as hub_module

    routes = [r for r in _app_routes() if route_module_name(r) == hub_module.__name__]
    # 7 endpoint registrations: gateway, slug/claim, clients list+create (same
    # path, two methods), patch, rotate, delete. A second full mount → 14.
    assert len(routes) == 7, (
        f"mcp_hub router should contribute 7 route registrations, got "
        f"{len(routes)}: {sorted((route_path(r), tuple(route_methods(r))) for r in routes)}"
    )


def test_no_route_registered_more_than_once() -> None:
    """Global double-mount guard: (path, method, endpoint-qualified-name) must
    be unique across the whole app.

    KNOWN EXCEPTIONS (both documented, both raised for owner decision):
    1. the ``api.routes.browser`` family: core/app_builder.py mounts it
       unconditionally ("route discovery must not depend on the optional
       safe-import registry") while ALL_ROUTERS also lists it — but with the
       scraper-route role filter skipping it on the ``core`` service role.
       Removing either mount today would change which service roles expose
       the browser surface.
    2. ``backend.*``-aliased module copies: the legacy import path can import
       the SAME files under the ``backend.`` namespace (order-dependent under
       import-mode=importlib), re-executing registration onto the singleton
       app with ``backend.api.routes...`` module names. The durable fix is
       conftest-level alias unification (sys.modules redirect), tracked as a
       next-round item with the full-suite verification it deserves.
    Every OTHER module is guarded — this guard already caught and fixed the
    api.routes.admin_routes, missions/mcp_hub, codeflow and vulnerability_prophet
    double mounts.
    """
    seen = Counter()
    for r in _app_routes():
        endpoint_module = getattr(route_endpoint(r), "__module__", "")
        if endpoint_module.startswith("api.routes.browser"):
            continue  # documented owner-decision exception, see docstring
        if endpoint_module.startswith("backend."):
            continue  # legacy-alias copy pollution, see docstring item 2
        for method in route_methods(r):
            key = (
                route_path(r),
                method,
                f"{getattr(route_endpoint(r), '__module__', '')}.{getattr(route_endpoint(r), '__qualname__', '')}",
            )
            seen[key] += 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    assert not dupes, f"duplicate route registrations found: {sorted(dupes)[:10]}"


def test_registry_paths_all_reachable_on_app() -> None:
    """Every non-conditional registry path must be present on the booted app
    (guards against a future regression to 'defined but never mounted')."""
    from api.routers import ALL_ROUTERS

    app_paths = {route_path(r) for r in _app_routes()}
    missing = []
    for router_def in ALL_ROUTERS:
        path = router_def["path"]
        # Registry paths are module paths; derive the expected prefix from the
        # same module the registry would import (mirrors register_all_routers).
        import importlib

        try:
            module = importlib.import_module(path)
        except Exception:  # noqa: BLE001 — optional routers may be absent in
            continue  # minimal service roles (scraper/worker); not a mount bug
        router = getattr(module, "router", None)
        if router is None:
            continue
        # Mirror register_router(): include_router(prefix=<registry prefix>).
        # The router's own prefix is already baked into route.path — do NOT
        # append it again.
        prefix = router_def.get("prefix") or ""
        for route in router.routes:
            if isinstance(route, APIRoute):
                expected = prefix + route.path
                if expected not in app_paths:
                    missing.append(f"{path} -> {expected}")
    assert not missing, f"registry routers with unmounted routes: {missing[:10]}"
