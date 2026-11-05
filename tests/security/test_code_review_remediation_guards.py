"""Mechanical regression guards for the 2026-11-05 Read-Only Security & Code Review findings."""

from __future__ import annotations

import ast
from pathlib import Path

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
