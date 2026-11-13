"""Regression coverage for root imports, router accounting, JWTs, and CI scope."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest
import yaml
from core.app_builder import router_health_check
from fastapi import APIRouter, Depends, FastAPI, HTTPException

REPO = Path(__file__).resolve().parents[2]


def test_factory_boots_from_repo_root_without_pytest_path_injection():
    env = {**os.environ, "CI": "true", "TESTING": "true", "RATE_LIMIT_ENABLED": "false"}
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from core.app_builder import create_app; "
                "app = create_app(); "
                "assert app.state.router_registration['mounted'] > 0"
            ),
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        timeout=90,
    )
    # Do not echo a subprocess's logs: imported modules may log configuration.
    assert result.returncode == 0


def _registry(monkeypatch, *, critical=False, role="monolith"):
    from core.api import routers

    import api

    monkeypatch.setattr(api, "_registration_report", [])
    monkeypatch.setattr(
        routers,
        "settings",
        SimpleNamespace(
            supremeai_service_role=role,
            encryption_key=None,
        ),
    )
    monkeypatch.setattr(
        routers,
        "ALL_ROUTERS",
        [
            {
                "path": "audit_test_routes",
                "prefix": "",
                "is_admin": False,
                "is_critical": critical,
            }
        ],
    )
    return api, routers


def test_critical_router_import_failure_aborts_registration(monkeypatch):
    _, routers = _registry(monkeypatch, critical=True)
    with pytest.raises(ModuleNotFoundError):
        routers.register_all_routers(FastAPI())


def test_optional_failure_is_degraded_and_does_not_bleed_between_apps(monkeypatch):
    _, routers = _registry(monkeypatch)
    first = FastAPI()
    routers.register_all_routers(first)
    report = router_health_check(first)
    assert report["status"] == "degraded"
    assert (report["expected"], report["mounted"]) == (1, 0)
    assert report["failures"] == [
        {
            "module": "audit_test_routes",
            "error_type": "ModuleNotFoundError",
        }
    ]

    module = SimpleNamespace(router=APIRouter())
    monkeypatch.setitem(sys.modules, "audit_test_routes", module)
    second = FastAPI()
    routers.register_all_routers(second)
    report = router_health_check(second)
    assert report["status"] == "healthy"
    assert report["expected"] == report["mounted"] == 1
    assert report["failures"] == []


def test_router_health_does_not_hide_supplemental_failures():
    app = FastAPI()
    app.state.router_registration = {
        "expected": 1,
        "mounted": 1,
        "skipped": 0,
        "failures": [{"module": "api.routes.byoc_api", "error_type": "ImportError"}],
    }
    assert router_health_check(app)["status"] == "degraded"


def test_role_filtered_registry_entries_are_not_missing(monkeypatch):
    _, routers = _registry(monkeypatch, role="worker", critical=True)
    app = FastAPI()
    routers.register_all_routers(app)
    assert app.state.router_registration == {
        "role": "worker",
        "expected": 0,
        "mounted": 0,
        "skipped": 1,
        "failures": [],
    }


def test_router_mount_is_idempotent_per_app_and_prefix(monkeypatch):
    from gateway.tests.api._route_introspection import app_effective_routes, route_path

    import api

    router = APIRouter()

    @router.get("/probe")
    def probe():
        return {"ok": True}

    monkeypatch.setitem(sys.modules, "audit_test_routes", SimpleNamespace(router=router))
    for app in (FastAPI(), FastAPI()):
        for prefix in ("/api", "/api", "/api/v1"):
            api.register_router(app, "audit_test_routes", prefix=prefix, optional=False)
        paths = [route_path(r) for r in app_effective_routes(app)]
        assert paths.count("/api/probe") == paths.count("/api/v1/probe") == 1
        with pytest.raises(ValueError, match="authentication dependencies"):
            api.register_router(
                app, "audit_test_routes", prefix="/api", dependencies=[Depends(probe)]
            )


@pytest.fixture
def jwt_contract(monkeypatch):
    from core import security
    from core.security.authentication import auth_middleware

    from api.routes import auth

    secret = "audit-regression-fixture-signing-key-not-a-production-secret"
    monkeypatch.setattr(security, "_get_jwt_secret", lambda: secret)
    monkeypatch.setattr(auth, "_get_secret_key", lambda: secret)
    monkeypatch.setattr(auth_middleware, "settings", SimpleNamespace(jwt_secret=secret))
    monkeypatch.setattr(security, "is_token_revoked", AsyncMock(return_value=False))
    monkeypatch.setattr(auth, "is_token_revoked", AsyncMock(return_value=False))
    monkeypatch.setattr(type(auth.redis_manager), "client", property(lambda _: None))
    return security, auth, auth_middleware, secret


@pytest.mark.asyncio
@pytest.mark.parametrize("issuer", ["security", "auth"])
async def test_both_access_token_issuers_work_with_every_verifier(jwt_contract, issuer):
    security, auth, middleware, _ = jwt_contract
    token = {"security": security, "auth": auth}[issuer].create_access_token(
        {
            "sub": "audit-user",
            "role": "user",
            "type": "access",
        }
    )
    assert security.verify_token(token)["sub"] == "audit-user"
    assert (await security.verify_token_async(token))["sub"] == "audit-user"
    assert middleware._decode_jwt(token)["sub"] == "audit-user"
    assert (await auth.optional_current_user(token)).user_id == "audit-user"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claim,value",
    [
        ("iss", "foreign-issuer"),
        ("aud", "foreign-audience"),
        ("iss", None),
        ("aud", None),
        ("exp", None),
        ("jti", None),
    ],
)
async def test_invalid_claims_are_rejected_by_all_verifiers(jwt_contract, claim, value):
    security, auth, middleware, secret = jwt_contract
    token = auth.create_access_token({"sub": "audit-user", "role": "user"})
    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=security.JWT_AUDIENCE,
        issuer=security.JWT_ISSUER,
    )
    if value is None:
        payload.pop(claim)
    else:
        payload[claim] = value
    invalid = jwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(HTTPException):
        security.verify_token(invalid)
    with pytest.raises(HTTPException):
        await security.verify_token_async(invalid)
    assert middleware._decode_jwt(invalid) is None
    assert await auth.optional_current_user(invalid) is None


@pytest.mark.parametrize("route", ["branch_conversations.py", "chat_search.py", "keys.py"])
def test_thread_offload_callbacks_bind_loop_variables(route):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            str(REPO / "core/api/routes" / route),
            "--select",
            "B023",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout


def test_heavy_ci_jobs_discover_all_domains_and_enforce_coverage():
    pipeline = yaml.safe_load(
        (REPO / ".github/workflows/unified-pipeline.yml").read_text(encoding="utf-8")
    )
    for job in ("render-heavy-gate", "render-heavy-gate-fallback", "render-heavy-gate-emergency"):
        scripts = [step.get("run", "") for step in pipeline["jobs"][job]["steps"]]
        full = next(script for script in scripts if "test_audit_regressions.py" in script)
        assert any('"mcp>=1.28.1,<2"' in script for script in scripts)
        for test_name in ("test_audit_regressions.py", "test_no_auth_stubs.py", "test_agents_unified.py"):
            assert test_name in full
        if job == "render-heavy-gate":
            assert "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in full


def test_local_ci_propagates_each_native_command_failure():
    pipeline = yaml.safe_load(
        (REPO / ".github/workflows/unified-pipeline.yml").read_text(encoding="utf-8")
    )
    for step in pipeline["jobs"]["render-heavy-gate"]["steps"]:
        lines = [line.strip() for line in step.get("run", "").splitlines() if line.strip()]
        native = [
            i
            for i, line in enumerate(lines)
            if line.startswith(("python ", "pytest ", "git ", "ruff "))
        ]
        if len(native) < 2:
            continue
        for i in native:
            assert (
                i + 1 < len(lines)
                and lines[i + 1] == "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
            ), step["name"]
