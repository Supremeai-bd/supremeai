"""P1 — DB degradation policy wired into BOTH readiness endpoints.

core/health_policy.py is the single source of truth (used by
core/app_builder.py for the canonical /health/ready criticality and, since
this change, by api/routes/health.py /ready). Policy:

    core / unset role  → production/staging: DB failure = NOT READY (503);
                         SUPABASE_ALLOW_DB_DEGRADATION is IGNORED (fail-closed)
    core               → dev/local: flag opts into degraded-serving
    worker/scraper/mcp → role-specific degradation allowed in every env,
                         with the degraded state VISIBLE in the response

See docs/deployment/HEALTH_CONTRACT.md ("DB degradation policy").
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import Response
from fastapi.responses import JSONResponse

import api.routes.health as legacy_health
import core.health_routes as hr
from core.health_routes import HealthCheck


def _checks(*checks: HealthCheck):
    return list(checks)


def _db_check(healthy: bool, critical: bool) -> HealthCheck:
    return HealthCheck(
        name="database",
        check_fn=lambda: healthy,
        critical=critical,
    )


def _mem_check(healthy: bool) -> HealthCheck:
    return HealthCheck(name="memory", check_fn=lambda: healthy, critical=False)


# ---------------------------------------------------------------------------
# Canonical /health/ready (core/health_routes.readiness_probe)
# ---------------------------------------------------------------------------


class TestCanonicalReadinessProbe:
    async def test_core_role_db_failure_is_not_ready_503(self, monkeypatch):
        monkeypatch.setenv("SUPREMEAI_SERVICE_ROLE", "core")
        monkeypatch.setattr(hr, "_checks", _checks(_db_check(False, critical=True)))
        response = Response()
        data = await hr.readiness_probe(response)
        assert response.status_code == 503
        assert data["status"] == "not_ready"
        assert data["role"] == "core"

    async def test_worker_role_db_failure_stays_ready_and_visible(self, monkeypatch):
        monkeypatch.setenv("SUPREMEAI_SERVICE_ROLE", "worker")
        monkeypatch.setattr(
            hr, "_checks", _checks(_db_check(False, critical=False), _mem_check(True))
        )
        response = Response()
        data = await hr.readiness_probe(response)
        assert response.status_code == 200
        assert data["status"] == "degraded"
        assert data["degraded"] == ["database"]
        assert data["role"] == "worker"

    async def test_all_critical_healthy_no_degradation(self, monkeypatch):
        monkeypatch.setenv("SUPREMEAI_SERVICE_ROLE", "core")
        monkeypatch.setattr(
            hr, "_checks", _checks(_db_check(True, critical=True), _mem_check(True))
        )
        response = Response()
        data = await hr.readiness_probe(response)
        assert response.status_code == 200
        assert data["status"] == "ready"
        assert data["degraded"] == []

    async def test_scraper_and_mcp_roles_same_tolerant_semantics(self, monkeypatch):
        for role in ("scraper", "mcp"):
            monkeypatch.setenv("SUPREMEAI_SERVICE_ROLE", role)
            monkeypatch.setattr(hr, "_checks", _checks(_db_check(False, critical=False)))
            response = Response()
            data = await hr.readiness_probe(response)
            assert response.status_code == 200, role
            assert data["status"] == "degraded", role

    async def test_no_critical_checks_defaults_ready(self, monkeypatch):
        monkeypatch.setenv("SUPREMEAI_SERVICE_ROLE", "worker")
        monkeypatch.setattr(hr, "_checks", _checks())
        response = Response()
        data = await hr.readiness_probe(response)
        assert response.status_code == 200
        assert data["status"] == "ready"
        assert data["degraded"] == []

    async def test_role_unset_behaves_as_core(self, monkeypatch):
        monkeypatch.delenv("SUPREMEAI_SERVICE_ROLE", raising=False)
        monkeypatch.setattr(hr, "_checks", _checks(_db_check(False, critical=True)))
        response = Response()
        data = await hr.readiness_probe(response)
        assert response.status_code == 503
        assert data["role"] == "core"


# ---------------------------------------------------------------------------
# Legacy alias /api/v1/ready (api/routes/health.readiness_check)
# ---------------------------------------------------------------------------


async def _call_legacy(monkeypatch, *, db, redis="healthy", role=None, env=None, flag=None):
    async def fake_db():
        return db

    async def fake_redis():
        return redis

    monkeypatch.setattr(legacy_health, "_check_database", fake_db)
    monkeypatch.setattr(legacy_health, "_check_redis", fake_redis)
    if role is None:
        monkeypatch.delenv("SUPREMEAI_SERVICE_ROLE", raising=False)
    else:
        monkeypatch.setenv("SUPREMEAI_SERVICE_ROLE", role)
    # The handler prefers settings.env (loaded once at import) over the raw
    # ENV var, so patch the cached settings object directly.
    from core.config import settings as app_settings

    if env is None:
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.setattr(app_settings, "env", "", raising=False)
    else:
        monkeypatch.setenv("ENV", env)
        monkeypatch.setattr(app_settings, "env", env, raising=False)
    if flag is None:
        monkeypatch.delenv("SUPABASE_ALLOW_DB_DEGRADATION", raising=False)
    else:
        monkeypatch.setenv("SUPABASE_ALLOW_DB_DEGRADATION", flag)
    return await legacy_health.readiness_check()


class TestLegacyReadyEndpointRolePolicy:
    async def test_core_role_db_failure_503_with_reason(self, monkeypatch):
        with pytest.raises(Exception) as exc:
            await _call_legacy(monkeypatch, db="unhealthy", role="core", env="production")
        assert getattr(exc.value, "status_code", None) == 503
        assert "not ready" in str(getattr(exc.value, "detail", ""))

    async def test_worker_role_db_failure_200_degraded_visible(self, monkeypatch):
        data = await _call_legacy(monkeypatch, db="unhealthy", role="worker", env="production")
        assert data["status"] == "degraded"
        assert data["persistence_mode"] == "unavailable"
        assert data["role"] == "worker"
        assert data["readiness_policy"]["decision"] == "role-tolerated"
        assert "role-specific degradation allowed" in data["readiness_policy"]["reason"]

    async def test_core_prod_degradation_flag_is_ignored(self, monkeypatch):
        # Isolate the genuinely-UNAVAILABLE path (db_degraded() False): with
        # the flag set AND a degraded-engine boot, the pre-existing escape
        # hatch semantics (persistence_mode=degraded, 200) apply instead —
        # covered by test_db_degraded_flag_keeps_current_semantics.
        monkeypatch.setattr(legacy_health, "db_degraded", lambda: False)
        with pytest.raises(Exception) as exc:
            await _call_legacy(
                monkeypatch, db="unhealthy", role="core", env="production", flag="true"
            )
        assert getattr(exc.value, "status_code", None) == 503
        # the fail-closed reason must say the flag is ignored, not silently honoured
        assert "IGNORED" in str(getattr(exc.value, "detail", "")).upper()

    async def test_core_dev_flag_allows_degraded(self, monkeypatch):
        data = await _call_legacy(
            monkeypatch, db="unhealthy", role="core", env="development", flag="true"
        )
        assert data["status"] == "degraded"
        assert data["readiness_policy"]["decision"] == "role-tolerated"
        assert "dev degradation allowed" in data["readiness_policy"]["reason"]

    async def test_db_degraded_flag_keeps_current_semantics(self, monkeypatch):
        # db "unhealthy" + degraded-mode active (core.degraded_mode.db_degraded)
        # is the pre-existing escape hatch path: status degraded, no 503.
        # NOTE: health.py holds a from-import reference, so patch THERE.
        monkeypatch.setenv("SUPABASE_ALLOW_DB_DEGRADATION", "true")
        monkeypatch.setattr(legacy_health, "db_degraded", lambda: True)
        data = await _call_legacy(monkeypatch, db="unhealthy", role="core", env="test")
        assert data["status"] == "degraded"
        assert data["persistence_mode"] == "degraded"

    async def test_healthy_db_unchanged_shape(self, monkeypatch):
        data = await _call_legacy(monkeypatch, db="healthy", redis="healthy", role="core")
        assert data["status"] == "ok"
        assert data["persistence_mode"] == "healthy"
        assert data["cache"] == "healthy"
        assert data["role"] == "core"
        assert "readiness_policy" not in data

    async def test_scraper_role_and_mcp_role_tolerated(self, monkeypatch):
        for role in ("scraper", "mcp"):
            data = await _call_legacy(monkeypatch, db="unhealthy", role=role, env="production")
            assert data["status"] == "degraded", role
            assert data["readiness_policy"]["decision"] == "role-tolerated", role


# ---------------------------------------------------------------------------
# Policy module cross-check (the single source of truth itself)
# ---------------------------------------------------------------------------


class TestPolicyCrossCheck:
    def test_policy_matches_endpoint_expectations(self):
        from core.health_policy import db_failure_readiness, is_critical_db_check

        assert db_failure_readiness("core", "production", True)[0] is False
        assert db_failure_readiness("core", "staging", True)[0] is False
        assert db_failure_readiness("core", "development", True)[0] is True
        assert db_failure_readiness("", "production", False)[0] is False
        for role in ("worker", "scraper", "mcp"):
            assert db_failure_readiness(role, "production", False)[0] is True
            assert is_critical_db_check(role) is False
        assert is_critical_db_check("core") is True
        assert is_critical_db_check("") is True
