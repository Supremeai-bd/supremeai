"""Issue #1497 — admin route consolidation contract tests.

Locks the deprecation contract introduced to resolve the duplicate/conflicting
admin routes:

  Rules engine (feature switches):
    - CANONICAL:  GET/POST /admin-api/rules   (admin_dashboard/endpoints_command.py)
    - DEPRECATED: GET/POST /admin/rules       (admin_routes.py — legacy shape alias,
                  same services.rules_engine backend, cannot drift)

  Constitutional rules (GodLayer — a DIFFERENT concept, intentionally not merged):
    - GET/POST /api/admin/rules               (admin.py)

  System alert ingestion:
    - CANONICAL:  POST /api/v1/admin/alerts   (internal.py — AI Log Analyzer)
    - DEPRECATED: POST /api/admin/alerts      (admin.py — legacy DB-persist alias)

The deprecated paths must stay advertised with ``deprecated: true`` in the
OpenAPI schema so tooling can flag new usages while legacy consumers keep
working.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routes.admin as admin_core_routes
import api.routes.admin_routes as admin_surface_routes
import api.routes.internal as internal_routes
from api.routes.admin_dashboard.endpoints_command import router as commandcenter_router


def _build() -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    app.include_router(admin_surface_routes.router)
    app.include_router(admin_core_routes.router)
    app.include_router(commandcenter_router)
    app.include_router(internal_routes.router)
    # Auth-free contract probing: the deprecation contract is about the OpenAPI
    # surface, not the auth layer (locked elsewhere).
    app.dependency_overrides[admin_surface_routes.get_current_admin] = lambda: {
        "sub": "contract-test",
        "role": "admin",
    }
    app.dependency_overrides[admin_core_routes.get_current_admin] = lambda: {
        "sub": "contract-test",
        "role": "admin",
    }
    return app, TestClient(app)


def _schema() -> dict:
    app, _ = _build()
    return app.openapi()


def test_rules_engine_canonical_surface_is_advertised():
    paths = _schema()["paths"]
    assert "/admin-api/rules" in paths
    assert "get" in paths["/admin-api/rules"]
    assert "post" in paths["/admin-api/rules"]
    # Canonical endpoints must NOT be flagged deprecated.
    assert not paths["/admin-api/rules"]["get"].get("deprecated", False)


def test_legacy_admin_rules_marked_deprecated():
    paths = _schema()["paths"]
    assert "/admin/rules" in paths
    assert paths["/admin/rules"]["get"].get("deprecated") is True
    assert paths["/admin/rules"]["post"].get("deprecated") is True


def test_constitutional_rules_surface_is_distinct_and_not_deprecated():
    # /api/admin/rules is the GodLayer constitutional surface — intentionally a
    # separate concept from the rules-engine switches (#1497 disambiguation).
    paths = _schema()["paths"]
    assert "/api/admin/rules" in paths
    assert not paths["/api/admin/rules"]["get"].get("deprecated", False)
    assert not paths["/api/admin/rules"]["post"].get("deprecated", False)


def test_alert_ingestion_contract():
    paths = _schema()["paths"]
    # Canonical ingestion endpoint.
    assert "/api/v1/admin/alerts" in paths
    assert "post" in paths["/api/v1/admin/alerts"]
    assert not paths["/api/v1/admin/alerts"]["post"].get("deprecated", False)
    # Legacy DB-persist alias stays advertised but flagged.
    assert "/api/admin/alerts" in paths
    assert paths["/api/admin/alerts"]["post"].get("deprecated") is True
    # Admin read surface is distinct and not deprecated.
    assert not paths["/api/admin/alerts"]["get"].get("deprecated", False)


def test_deprecated_aliases_still_serve_the_legacy_contract():
    """The aliases must keep working (contract compatibility) — same backend."""
    _, client = _build()
    # Legacy GET alias → same rules_engine payload shape (raw engine rules).
    resp = client.get("/admin/rules")
    assert resp.status_code == 200
    # Legacy POST alias → same engine persist contract.
    resp = client.post("/admin/rules", json={"rules": {"probe": 1}})
    assert resp.status_code == 200
    assert resp.json()["status"] in ("success", "error")  # engine-backed, not a 404/redirect
