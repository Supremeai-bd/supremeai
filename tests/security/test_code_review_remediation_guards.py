"""Mechanical regression guards for the 2026-11-05 Read-Only Security & Code Review findings."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security.origin_validator import TrustedOriginMiddleware

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_vscode_release_workflow_has_no_hardcoded_signing_password_or_self_signed_cert() -> None:
    workflow = (REPO_ROOT / "vscode" / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "SupremeAI2026!" not in workflow, "Hardcoded signing password must never appear in release.yml"
    assert "New-SelfSignedCertificate" not in workflow, "Self-signed certificate generation must not be used in release.yml"
    assert "http://timestamp.digicert.com" not in workflow, "Insecure HTTP timestamp URL must not be used"
    assert "https://timestamp.digicert.com" in workflow


def test_cors_wildcards_and_manual_sse_wildcard_headers_removed() -> None:
    sse_route = (REPO_ROOT / "core" / "api" / "routes" / "stream_chat_sse.py").read_text(encoding="utf-8")
    assert '"Access-Control-Allow-Origin": "*"' not in sse_route

    origin_validator = (REPO_ROOT / "core" / "security" / "origin_validator.py").read_text(encoding="utf-8")
    assert 'origin or "*"' not in origin_validator

    standalone_app = (REPO_ROOT / "core" / "ecosystem" / "standalone_app.py").read_text(encoding="utf-8")
    assert 'allow_origins=["*"]' not in standalone_app
    assert 'expose_headers=["*"]' not in standalone_app

    browser_server = (REPO_ROOT / "browser" / "server.py").read_text(encoding="utf-8")
    assert 'allow_origins=["*"]' not in browser_server

    gateway_app = (REPO_ROOT / "gateway" / "service" / "app.py").read_text(encoding="utf-8")
    assert r".*\.vercel\.app" not in gateway_app
    assert r".*\.workers\.dev" not in gateway_app


def test_hostile_origin_and_credentialed_preflight_negative_cases(monkeypatch) -> None:
    from core.config import settings

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://supremeai.live,https://app.supremeai.live")
    monkeypatch.setattr(settings, "env", "production", raising=False)
    app = FastAPI()
    app.add_middleware(TrustedOriginMiddleware)

    @app.get("/api/private/data")
    async def private_data():
        return {"ok": True}

    client = TestClient(app)

    # 1. Hostile origin preflight must NOT receive Access-Control-Allow-Origin or Credentials
    preflight_hostile = client.options(
        "/api/private/data",
        headers={"Origin": "https://evil-attacker.example.com"},
    )
    assert "access-control-allow-origin" not in preflight_hostile.headers
    assert "access-control-allow-credentials" not in preflight_hostile.headers

    # 2. Hostile origin GET on non-public path in production must be blocked with 403
    get_hostile = client.get(
        "/api/private/data",
        headers={"Origin": "https://evil-attacker.example.com"},
    )
    assert get_hostile.status_code == 403

    # 3. Missing Origin preflight must NOT emit wildcard '*' with credentials
    preflight_no_origin = client.options("/api/private/data")
    assert preflight_no_origin.headers.get("access-control-allow-origin") != "*"
    assert "access-control-allow-credentials" not in preflight_no_origin.headers

    # 4. Trusted origin preflight receives exact origin + credentials
    preflight_trusted = client.options(
        "/api/private/data",
        headers={"Origin": "https://supremeai.live"},
    )
    assert preflight_trusted.headers.get("access-control-allow-origin") == "https://supremeai.live"
    assert preflight_trusted.headers.get("access-control-allow-credentials") == "true"


def test_ci_workflows_do_not_swallow_dependency_or_test_failures() -> None:
    browser_ci = (REPO_ROOT / "browser" / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements.txt || true" not in browser_ci

    gateway_ci = (REPO_ROOT / "gateway" / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pip install -r service/requirements.txt || true" not in gateway_ci
    assert "pip install -r gateway/requirements.txt || true" not in gateway_ci
    assert "pytest gateway/tests/ -v || true" not in gateway_ci
    assert "pytest tests/ -v || true" not in gateway_ci

    vscode_ci = (REPO_ROOT / "vscode" / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "npm ci --ignore-scripts || npm install || true" not in vscode_ci
    assert "continue-on-error: true" not in vscode_ci


def test_previously_broken_python_files_parse_cleanly_without_bom() -> None:
    targets = [
        "gateway/gateway/main.py",
        "gateway/tests/api/_route_introspection.py",
        "backend/__init__.py",
        "browser/tests/conftest.py",
        "core/api/__init__.py",
        "gateway/service/router.py",
        "scripts/agents/agent_solution_memory.py",
        "tests/conftest.py",
    ]
    for rel in targets:
        raw = (REPO_ROOT / rel).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM found in {rel}"
        ast.parse(raw.decode("utf-8"), filename=rel)


def test_root_gitignore_does_not_ignore_lockfiles() -> None:
    gitignore_lines = {
        line.strip()
        for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert "package-lock.json" not in gitignore_lines
    assert "yarn.lock" not in gitignore_lines
    assert "src-tauri/Cargo.lock" not in gitignore_lines


def test_phase0_canonical_service_registry_and_ssot_alignment() -> None:
    """Verify Phase 0 SSOT convergence across service_registry.yaml, plan_render_deploys.py,
    service_topology.yaml, canonical_name_registry.json, and MCP env.ts."""
    registry_path = REPO_ROOT / "config" / "service_registry.yaml"
    assert registry_path.exists(), "Canonical config/service_registry.yaml must exist"
    reg = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    services = reg.get("services") or {}

    # 1. Verify all 7 Render services + edge/frontend/firebase exist in canonical registry
    for required_svc in ("api", "scraper", "mcp", "core", "worker", "brain", "ci-runner", "cloudflare", "frontend", "firebase"):
        assert required_svc in services, f"Missing service {required_svc} in config/service_registry.yaml"

    # 2. Verify plan_render_deploys.py rules match canonical_service_id_env and canonical_api_key_env
    from scripts.ci.plan_render_deploys import SERVICE_ID_ALIASES, SERVICE_RULES

    for svc_name, (env_id, api_key_env, _prefixes) in SERVICE_RULES.items():
        assert svc_name in services, f"Planner service {svc_name} missing from service_registry.yaml"
        reg_svc = services[svc_name]
        assert reg_svc["canonical_service_id_env"] == env_id
        assert reg_svc["canonical_api_key_env"] == api_key_env
        assert env_id.endswith("_SERVICE_ID"), f"Canonical ID {env_id} must end with _SERVICE_ID (not _SVC_ID)"
        assert env_id in SERVICE_ID_ALIASES

    # 3. Verify core/config/service_topology.yaml watches active monorepo directories (core/**, studio/**, gateway/**)
    topo = yaml.safe_load((REPO_ROOT / "core" / "config" / "service_topology.yaml").read_text(encoding="utf-8"))
    topo_services = topo.get("services") or {}
    assert "core/**" in topo_services["core"]["watch_paths"]
    assert "core/**" in topo_services["worker"]["watch_paths"]
    assert "studio/**" in topo_services["frontend"]["watch_paths"]
    assert "gateway/**" in topo_services["api"]["watch_paths"]

    # 4. Verify MCP env.ts prefers canonical RENDER_*_SERVICE_ID over legacy *_SVC_ID
    mcp_env_ts = (REPO_ROOT / "infrastructure" / "mcp-control-plane" / "src" / "lib" / "env.ts").read_text(encoding="utf-8")
    for canonical_id in (
        "RENDER_CORE_SERVICE_ID",
        "RENDER_WORKER_SERVICE_ID",
        "RENDER_SCRAPER_SERVICE_ID",
        "RENDER_MCP_SERVICE_ID",
        "RENDER_API_SERVICE_ID",
        "RENDER_BRAIN_SERVICE_ID",
        "RENDER_CI_RUNNER_SERVICE_ID",
    ):
        assert f'optional("{canonical_id}"' in mcp_env_ts, f"MCP env.ts must prefer canonical {canonical_id} first"

    # 5. Verify canonical_name_registry.json maps all legacy *_SVC_ID aliases
    canon_reg = json.loads((REPO_ROOT / "scripts" / "ci" / "canonical_name_registry.json").read_text(encoding="utf-8"))
    render_canon = canon_reg["families"]["RENDER"]["canonical"]
    assert "RENDER_PRIMARY_SVC_ID" in render_canon["RENDER_CORE_SERVICE_ID"]
    assert "RENDER_BROWSER_SERVICE_ID" in render_canon["RENDER_SCRAPER_SERVICE_ID"]
