"""Contract tests for Feature Parity Sentinel — #2868 false-positive classes.

Four detection bugs proven against nightly run 36846145557 (7 new findings,
5 false positives + 2 real dead-code drift):

Bug A — include_router mount keyed as ``module.router`` (imported-attr suffix)
        leaks into mounted_prefixes → real routers reported as unmounted
        (web_ai_proxy false positive).
Bug B — RE_API_CALL cannot see through nested TS generics (``Record<string,
        unknown>[]`` closes the ``[^>(]*`` scan early) and misses verbs
        ``stream``/``postForm`` → live frontend calls invisible → false
        orphan-endpoints (/api/browser/ai-action, /api/browser/screenshot).
Bug C — ghost-ui import_blob is built from per-line RE_IMPORT matches, so a
        multi-line import (``} from './sessionStore';``) never contributes its
        specifier → imported files reported as ghost-ui.
Bug D — router_prefixes is keyed by module only; a module declaring TWO
        routers (tenant_admin: /admin-api/tenant-limits + /admin-api/tenants)
        loses the first prefix to last-wins overwrite → wrong effective paths
        → false missing-backend-route.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SENTINEL = REPO_ROOT / "scripts" / "feature_parity_sentinel.py"

import importlib.util

_spec = importlib.util.spec_from_file_location("fps_2868", SENTINEL)
fps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fps)


# ---------------------------------------------------------------------------
# Fixtures: minimal backend/frontend trees exercising each bug class
# ---------------------------------------------------------------------------


def _make_repo(tmp_path: Path) -> Path:
    """Synthetic repo root with backend/ + scripts/ (registry) layout."""
    root = tmp_path / "repo"
    (root / "backend" / "api" / "routes").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / "frontend" / "src" / "components" / "dash").mkdir(parents=True)
    (root / "frontend" / "src" / "components" / "infra").mkdir(parents=True)
    return root


def _patch_globals(monkeypatch: pytest.MonkeyPatch, root: Path, registry_src: str = "ALL_ROUTERS = []\n") -> None:
    monkeypatch.setattr(fps, "ROOT", root)
    monkeypatch.setattr(fps, "BACKEND_DIR", root / "backend")
    monkeypatch.setattr(fps, "FRONTEND_DIR", root / "frontend")
    monkeypatch.setattr(fps, "FE_SRC", root / "frontend" / "src")
    registry_file = root / "backend" / "api" / "routers.py"
    registry_file.write_text(registry_src, encoding="utf-8")
    monkeypatch.setattr(fps, "ROUTERS_REGISTRY", registry_file)


def _scan(root: Path):
    return fps.scan_backend(fps.py_files())


# ---------------------------------------------------------------------------
# Bug A: aliased include_router must mount the module (no ".router" suffix)
# ---------------------------------------------------------------------------


def test_bug_a_aliased_include_router_mounts_module(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    _patch_globals(monkeypatch, root)

    (root / "backend" / "api" / "routes" / "gadget.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter(prefix='/v1', tags=['gadget'])\n"
        "@router.post('/chat/completions')\n"
        "async def chat_completions():\n"
        "    return {}\n",
        encoding="utf-8",
    )
    (root / "backend" / "core").mkdir(parents=True, exist_ok=True)
    (root / "backend" / "core" / "app_builder.py").write_text(
        "from fastapi import FastAPI\n"
        "from api.routes.gadget import router as gadget_router\n"
        "app = FastAPI()\n"
        "app.include_router(gadget_router)\n"
        "app.include_router(gadget_router, prefix='/api')\n",
        encoding="utf-8",
    )

    routes_by_module, router_prefixes, mount_calls, parse_errors = _scan(root)
    findings, mounted_routes = fps.build_findings(
        routes_by_module, router_prefixes, mount_calls, parse_errors,
        [], [], [], [],
    )
    unmounted = [f for f in findings if f["category"] == "unmounted-router"]
    assert not unmounted, f"aliased include_router must mount the module, got: {unmounted}"
    assert mounted_routes, "gadget route must appear in the mounted table"


def test_bug_a_join_strips_attr_suffix_only_when_head_is_module(tmp_path, monkeypatch):
    """Join-time suffix strip: 'x.y.router' → 'x.y' when x.y is a scanned
    module, but a legitimately-named 'x.router' module key is never stripped."""
    root = _make_repo(tmp_path)
    _patch_globals(monkeypatch, root)

    (root / "backend" / "x").mkdir(parents=True)
    (root / "backend" / "x" / "y.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter(prefix='/y')\n"
        "@router.post('/go')\n"
        "async def go():\n"
        "    return {}\n",
        encoding="utf-8",
    )
    (root / "backend" / "x" / "router.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter(prefix='/r')\n"
        "@router.get('/hi')\n"
        "async def hi():\n"
        "    return {}\n",
        encoding="utf-8",
    )
    routes_by_module, router_prefixes, _mounts, parse_errors = _scan(root)
    assert "x.y" in routes_by_module and "x.router" in routes_by_module

    mount_calls = [
        {"file": "backend/core/app_builder.py", "line": 1, "module": "x.y.router", "prefix": ""},
        {"file": "backend/core/app_builder.py", "line": 2, "module": "x.router", "prefix": ""},
    ]
    findings, mounted_routes = fps.build_findings(
        routes_by_module, router_prefixes, mount_calls, parse_errors,
        [], [], [], [],
    )
    norms = {mr["norm"] for mr in mounted_routes}
    assert "/y/go" in norms, "stripped join must mount x.y routes"
    assert "/r/hi" in norms, "legitimately-named x.router module must mount untouched"
    unmounted = [f for f in findings if f["category"] == "unmounted-router"]
    assert not unmounted, f"both modules mounted; got: {unmounted}"


# ---------------------------------------------------------------------------
# Bug B: RE_API_CALL — nested generics + stream/postForm verbs
# ---------------------------------------------------------------------------


def test_bug_b_nested_generic_call_captured():
    call = (
        "const data = await apiClient.post<{ response?: string; links?: "
        "Record<string, unknown>[]; issues?: string[] }>(\n"
        "  '/api/browser/ai-action',\n"
        "  { action: 'scan' },\n"
        ")"
    )
    m = fps.RE_API_CALL.search(call)
    assert m, "nested-generic apiClient.post must match"
    raw = next(g for g in m.groups() if g)
    assert raw == "/api/browser/ai-action"


def test_bug_b_stream_verb_captured():
    call = "const response = await apiClient.stream('/api/browser/screenshot', { url });"
    m = fps.RE_API_CALL.search(call)
    assert m, "apiClient.stream must match"
    raw = next(g for g in m.groups() if g)
    assert raw == "/api/browser/screenshot"


def test_bug_b_postform_verb_captured():
    call = "await apiClient.postForm('/api/upload/media', form);"
    m = fps.RE_API_CALL.search(call)
    assert m, "apiClient.postForm must match"
    raw = next(g for g in m.groups() if g)
    assert raw == "/api/upload/media"


def test_bug_b_flat_generic_still_captured():
    call = "apiClient.post<{ score?: number }>('/api/x', {})"
    m = fps.RE_API_CALL.search(call)
    assert m
    raw = next(g for g in m.groups() if g)
    assert raw == "/api/x"


# ---------------------------------------------------------------------------
# Bug C: multi-line import must exonerate ghost-ui candidates
# ---------------------------------------------------------------------------


def test_bug_c_multiline_import_exonerates(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    _patch_globals(monkeypatch, root)

    store = root / "frontend" / "src" / "components" / "dash" / "sessionStore.ts"
    store.write_text("export const loadSessions = () => [];\n", encoding="utf-8")
    lonely = root / "frontend" / "src" / "components" / "infra" / "Lonely.tsx"
    lonely.write_text("export default function Lonely() { return null; }\n", encoding="utf-8")

    page_lines = [
        "// comment line",
        "import { useState } from 'react';",
        "import {",
        "  type DashboardSession,",
        "  loadSessions,",
        "  createSession,",
        "} from './sessionStore';",
        "export function Page() { return null; }",
    ]
    import_lines = {store: ["export const loadSessions = () => [];"], lonely: [], Path(root / "frontend" / "src" / "components" / "dash" / "SessionsPage.tsx"): page_lines}

    ghosts = fps.detect_ghost_ui([store, lonely], import_lines)
    ghost_files = [g["file"] for g in ghosts]
    assert any("sessionStore.ts" in f for f in ghost_files) is False, (
        "multi-line imported file must NOT be reported as ghost-ui"
    )
    assert any("Lonely.tsx" in f for f in ghost_files), (
        "control: never-referenced file must still be reported as ghost-ui"
    )


def test_bug_c_single_line_import_still_exonerates(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    _patch_globals(monkeypatch, root)
    comp = root / "frontend" / "src" / "components" / "dash" / "Plain.tsx"
    comp.write_text("export default function Plain() { return null; }\n", encoding="utf-8")
    importer = root / "frontend" / "src" / "components" / "dash" / "Page.tsx"
    importer.write_text("import Plain from './Plain';\n", encoding="utf-8")
    import_lines = {comp: ["export default function Plain() { return null; }"], importer: ["import Plain from './Plain';"]}
    ghosts = fps.detect_ghost_ui([comp], import_lines)
    assert not ghosts, "single-line import exoneration must keep working"


# ---------------------------------------------------------------------------
# Bug D: two routers in one module keep their distinct prefixes
# ---------------------------------------------------------------------------


def test_bug_d_dual_router_prefixes_preserved(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    _patch_globals(
        monkeypatch,
        root,
        registry_src=(
            "ALL_ROUTERS = [\n"
            "    {'path': 'api.routes.tenant_admin', 'prefix': '', 'is_admin': True, 'is_critical': False},\n"
            "]\n"
        ),
    )
    (root / "backend" / "api" / "routes" / "tenant_admin.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter(prefix='/admin-api/tenant-limits')\n"
        "@router.put('/{tenant_id}')\n"
        "async def update_limit(tenant_id: str):\n"
        "    return {}\n"
        "tenants_router = APIRouter(prefix='/admin-api/tenants')\n"
        "@tenants_router.get('')\n"
        "async def list_tenants():\n"
        "    return []\n"
        "router.include_router(tenants_router)\n",
        encoding="utf-8",
    )
    routes_by_module, router_prefixes, mount_calls, parse_errors = _scan(root)
    _findings, mounted_routes = fps.build_findings(
        routes_by_module, router_prefixes, mount_calls, parse_errors,
        [], [], [], [],
    )
    norms = {mr["norm"] for mr in mounted_routes}
    assert "/admin-api/tenant-limits/{}" in norms, (
        f"routes on primary router must keep /admin-api/tenant-limits prefix; got {sorted(norms)}"
    )
    assert "/admin-api/tenants" in norms, (
        f"routes on tenants_router must keep /admin-api/tenants prefix; got {sorted(norms)}"
    )


# ---------------------------------------------------------------------------
# Full-repo regression: the 7 nightly findings must not re-appear
# ---------------------------------------------------------------------------

FORBIDDEN_NEW_KEYS = [
    "unmounted-router|api.routes.web_ai_proxy",
    "missing-backend-route|/admin-api/tenant-limits/{}",
    "missing-backend-route|/api/chat",
    "missing-backend-route|/api/v1/agent/action",
    "ghost-ui|frontend/src/components/admin/infra/DeploymentModal.tsx",
    "ghost-ui|frontend/src/components/dashboard/sessionStore.ts",
    "orphan-endpoint|POST /api/browser/ai-action",
    "orphan-endpoint|POST /api/browser/screenshot",
]


def test_full_repo_no_known_false_positives():
    subprocess.run(
        [sys.executable, str(SENTINEL), "--json", str(REPO_ROOT / ".parity_2868_check.json")],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=300,
        check=False,
    )
    report = json.loads((REPO_ROOT / ".parity_2868_check.json").read_text(encoding="utf-8"))
    new_keys = [f["key"] for f in report["new_findings"]]
    leaked = [k for k in FORBIDDEN_NEW_KEYS if k in new_keys]
    assert not leaked, (
        "known false positives / resolved drift re-appeared as NEW findings: "
        + ", ".join(leaked)
    )
    (REPO_ROOT / ".parity_2868_check.json").unlink(missing_ok=True)
