"""FastAPI route introspection helper — version-tolerant (CI triage #2597).

FastAPI ≥0.141 changed ``include_router`` to lazy mounting: instead of
expanding the included router's routes into ``app.routes`` immediately, it
appends a single ``_IncludedRouter`` container (``path=None``) whose real
routes are exposed via ``effective_candidates()``. Any contract test that
walks ``app.routes`` looking for expanded ``APIRoute`` objects silently sees
an empty surface under the new behavior (evidence: PR #2598 Test & Build —
10 route-contract tests failed with "no route registered" although the app
booted with mounted=157/157).

বাংলা মন্তব্য: এই helper পুরোনো (expanded) ও নতুন (lazy) দুই FastAPI
আচরণেই অভিন্নভাবে "কার্যকর route-তালিকা" দেয় —
  ১. সরাসরি ``APIRoute`` থাকলে তা যোগ হয়;
  ২. lazy container থাকলে ``effective_candidates()`` recursively ভেদ করে
     ``_EffectiveRouteContext`` (prefix-সহ path/methods/endpoint) বের করে;
  ৩. ভবিষ্যৎ FastAPI আবার আচরণ বদলালে এখানেই এক জায়গায় ফিক্স হবে —
     প্রতিটি contract-test-এ নয় (SSoT)।
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi.routing import APIRoute


def _iter_effective(routes: list[Any]) -> Iterator[Any]:
    """Yield APIRoute-or-equivalent entries from app.routes, lazily."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
            continue
        # fastapi>=0.141 lazy include container (_IncludedRouter) — its
        # effective_candidates() returns _EffectiveRouteContext entries with
        # the fully-prefixed path/methods/endpoint, possibly nesting further
        # containers for routers included inside routers.
        effective_candidates = getattr(route, "effective_candidates", None)
        if callable(effective_candidates):
            yield from _iter_effective(list(effective_candidates()))
            continue
        # Leaf candidates (_EffectiveRouteContext or any path-bearing route
        # object): expose as-is — route_path/route_methods/route_endpoint
        # duck-type over both APIRoute and _EffectiveRouteContext.
        if getattr(route, "path", None) is not None:
            yield route


def app_effective_routes(app: Any) -> list[Any]:
    """Flat, order-stable list of effective routes (APIRoute-or-equivalent)."""
    return list(_iter_effective(list(app.routes)))


def route_path(route: Any) -> str:
    """Mount-time path (prefix included) — '' when not resolvable."""
    return getattr(route, "path", "") or ""


def route_methods(route: Any) -> set[str]:
    return getattr(route, "methods", None) or set()


def route_endpoint(route: Any) -> Any:
    return getattr(route, "endpoint", None)


def route_module_name(route: Any) -> str:
    """Endpoint module, normalized across repo-root vs backend-CWD imports
    (``backend.api.routes.X`` ও ``api.routes.X`` একই ফাইলের alias)।"""
    endpoint = route_endpoint(route)
    module = getattr(endpoint, "__module__", "")
    return module[8:] if module.startswith("backend.") else module
