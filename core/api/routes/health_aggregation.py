"""
Admin Health Aggregation Endpoint
Aggregates health status from all microservices and external dependencies.
"""

import asyncio
import hashlib
import os
import time
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from api.dependencies import get_current_admin
from brain.model_registry import ModelRegistry
from core.deployment_fallback_defaults import ADMIN_URL_DEFAULT, SCRAPER_URL_DEFAULT
from core.health.uptime_tracker import (
    get_history,
    get_uptime_summary,
    record_check,
)
from core.messaging.event_bus import ErrorEvent, error_event_bus

router = APIRouter(prefix="/admin-api", tags=["health"], dependencies=[Depends(get_current_admin)])

# ══════════════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════════════


class SchemaDriftStatus(BaseModel):
    status: str = "skipped"  # ok, drift, error, skipped
    fingerprint: str | None = None
    baseline_fingerprint: str | None = None
    tables: int = 0
    columns: int = 0
    detail: str = ""
    probed_at: float = 0.0


class ServiceHealth(BaseModel):
    name: str
    display_name: str
    status: str  # healthy, degraded, unhealthy, unknown
    response_time_ms: float | None = None
    status_code: int | None = None
    error: str | None = None
    last_check: datetime
    url: str
    critical: bool = False
    uptime_24h: float | None = None
    uptime_7d: float | None = None
    uptime_30d: float | None = None


class HealthAggregationResponse(BaseModel):
    timestamp: datetime
    overall_status: str
    services: list[ServiceHealth]
    summary: dict[str, int]
    uptime_percentage: float
    alerts: list[str]
    schema_drift: SchemaDriftStatus | None = None


_SCHEMA_PROBE_TTL_SECONDS = 30.0
_schema_state: dict[str, Any] = {
    "baseline": None,
    "fingerprint": None,
    "status": "skipped",
    "tables": 0,
    "columns": 0,
    "detail": "",
    "probed_at": 0.0,
    "alert_key": None,
}


def _fingerprint_rows(rows: list[tuple[str, str, str]]) -> str:
    canonical = "\n".join(
        f"{t}|{c}|{dt}" for t, c, dt in sorted((str(a), str(b), str(d)) for a, b, d in rows)
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


async def _collect_schema_rows(session: Any) -> list[tuple[str, str, str]] | None:
    bind = getattr(session, "bind", None)
    dialect = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect == "postgresql":
        query = (
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
            "ORDER BY table_name, column_name"
        )
        res = await session.execute(text(query))
        return [(str(r[0]), str(r[1]), str(r[2])) for r in res.fetchall()]
    if dialect == "sqlite":
        tbl_query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        tbl_res = await session.execute(text(tbl_query))
        rows: list[tuple[str, str, str]] = []
        for (tbl_name,) in tbl_res.fetchall():
            pragma_res = await session.execute(text(f'PRAGMA table_info("{tbl_name}")'))
            for col in pragma_res.fetchall():
                rows.append((str(tbl_name), str(col[1]), str(col[2])))
        return rows
    return None


def _current_schema_status() -> SchemaDriftStatus:
    return SchemaDriftStatus(
        status=_schema_state["status"],
        fingerprint=_schema_state["fingerprint"],
        baseline_fingerprint=_schema_state["baseline"],
        tables=_schema_state["tables"],
        columns=_schema_state["columns"],
        detail=_schema_state["detail"],
        probed_at=_schema_state["probed_at"],
    )


async def probe_schema_drift(
    *,
    force: bool = False,
    session_factory: Any = None,
) -> SchemaDriftStatus:
    now = time.monotonic()
    if (
        not force
        and _schema_state["probed_at"] > 0.0
        and (now - _schema_state["probed_at"]) < _SCHEMA_PROBE_TTL_SECONDS
    ):
        return _current_schema_status()

    if session_factory is None:
        from core.database import AsyncSessionLocal

        session_factory = AsyncSessionLocal

    try:
        async with session_factory() as session:
            bind = getattr(session, "bind", None)
            dialect = getattr(getattr(bind, "dialect", None), "name", "unknown")
            rows = await _collect_schema_rows(session)
            if rows is None:
                _schema_state.update(
                    status="skipped",
                    detail=f"unsupported dialect: {dialect}",
                    probed_at=now,
                )
                return _current_schema_status()

            fp = _fingerprint_rows(rows)
            tables_count = len({r[0] for r in rows})
            cols_count = len(rows)
            baseline = _schema_state["baseline"]

            if baseline is None:
                baseline = fp
                _schema_state["baseline"] = fp

            if fp == baseline:
                was_drift = _schema_state["alert_key"] is not None
                _schema_state.update(
                    status="ok",
                    fingerprint=fp,
                    tables=tables_count,
                    columns=cols_count,
                    detail="schema matches baseline",
                    probed_at=now,
                    alert_key=None,
                )
                if was_drift:
                    error_event_bus.emit(
                        ErrorEvent(
                            module="health_aggregation",
                            error_type="SCHEMA_DRIFT_RESOLVED",
                            message=f"Schema drift resolved; matches baseline {baseline}",
                            severity="INFO",
                            resolved=True,
                            context={"fingerprint": fp, "baseline": baseline},
                        )
                    )
            else:
                alert_key = f"drift:{baseline}->{fp}"
                should_emit = _schema_state["alert_key"] != alert_key
                _schema_state.update(
                    status="drift",
                    fingerprint=fp,
                    tables=tables_count,
                    columns=cols_count,
                    detail=f"fingerprint {fp} != baseline {baseline}",
                    probed_at=now,
                    alert_key=alert_key,
                )
                if should_emit:
                    error_event_bus.emit(
                        ErrorEvent(
                            module="health_aggregation",
                            error_type="SCHEMA_DRIFT",
                            message=f"Database schema drift detected: {fp} != {baseline}",
                            severity="ERROR",
                            resolved=False,
                            context={
                                "fingerprint": fp,
                                "baseline": baseline,
                                "remediation": "trigger connection-pool recycle and verify migrations",
                            },
                        )
                    )
    except Exception as exc:
        err_msg = str(exc)
        alert_key = f"error:{err_msg}"
        should_emit = _schema_state["alert_key"] != alert_key
        _schema_state.update(
            status="error",
            detail=err_msg,
            probed_at=now,
            alert_key=alert_key,
        )
        if should_emit:
            error_event_bus.emit(
                ErrorEvent(
                    module="health_aggregation",
                    error_type="SCHEMA_PROBE_FAILED",
                    message=f"Schema drift probe failed: {err_msg}",
                    severity="WARNING",
                    resolved=False,
                    context={"error": err_msg},
                )
            )

    return _current_schema_status()


class DependencyHealth(BaseModel):
    database: ServiceHealth
    redis: ServiceHealth
    supabase: ServiceHealth
    llm_providers: dict[str, ServiceHealth]


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

SERVICE_REGISTRY = [
    {
        "name": "main_backend",
        "display_name": "Main Backend",
        "url": (
            os.environ.get("BACKEND_URL")
            or os.environ.get("SUPREMEAI_BACKEND_URL")
            or "http://localhost:8080"  # is_local()
        )
        + "/api/v1/health",
        "critical": True,
        "timeout": 5.0,
    },
    {
        "name": "admin_backend",
        "display_name": "Admin Backend",
        "url": os.environ.get("ADMIN_URL", ADMIN_URL_DEFAULT) + "/api/v1/health",
        "critical": True,
        "timeout": 8.0,
    },
    {
        "name": "scraper_service",
        "display_name": "Scraper Microservice",
        "url": os.environ.get("SCRAPER_URL", SCRAPER_URL_DEFAULT) + "/health",
        "critical": False,
        "timeout": 8.0,
    },
    {
        "name": "cloudflare_worker",
        "display_name": "Edge Worker",
        "url": "https://supremeai-edge.your-subdomain.workers.dev/health",
        "critical": True,
        "timeout": 5.0,
    },
]

LLM_PROVIDERS = {
    "openrouter": {"url": "https://openrouter.ai/api/v1/models", "critical": False},
    "openai": {"url": "https://api.openai.com/v1/models", "critical": False},
    "gemini": {"url": "https://generativelanguage.googleapis.com/v1beta/models", "critical": False},
}

# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════


async def check_single_service(config: dict) -> ServiceHealth:
    """Perform async health check on a single service."""
    start_time = datetime.now()

    try:
        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            response = await client.get(
                config["url"],
                headers={"User-Agent": "SupremeAI-HealthChecker/2.0"},
            )

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                # Try to parse health details from response
                try:
                    data = response.json()
                    status = data.get("status", "healthy")
                    if status == "degraded":
                        status = "degraded"
                    else:
                        status = "healthy"
                except Exception:
                    status = "healthy"
            elif response.status_code >= 500:
                status = "unhealthy"
            else:
                status = "degraded"

            return ServiceHealth(
                name=config["name"],
                display_name=config["display_name"],
                status=status,
                response_time_ms=round(response_time, 2),
                status_code=response.status_code,
                last_check=datetime.utcnow(),
                url=config["url"],
                critical=config.get("critical", False),
            )

    except httpx.TimeoutException:
        return ServiceHealth(
            name=config["name"],
            display_name=config["display_name"],
            status="unhealthy",
            response_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            error=f"Timeout after {config['timeout']}s",
            last_check=datetime.utcnow(),
            url=config["url"],
            critical=config.get("critical", False),
        )
    except Exception as e:
        return ServiceHealth(
            name=config["name"],
            display_name=config["display_name"],
            status="unhealthy",
            response_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            error=str(e)[:200],
            last_check=datetime.utcnow(),
            url=config["url"],
            critical=config.get("critical", False),
        )


async def check_all_services() -> list[ServiceHealth]:
    """Check all registered services concurrently."""
    tasks = [check_single_service(svc) for svc in SERVICE_REGISTRY]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to unhealthy status
    services = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            services.append(
                ServiceHealth(
                    name=SERVICE_REGISTRY[i]["name"],
                    display_name=SERVICE_REGISTRY[i]["display_name"],
                    status="unknown",
                    error=str(result),
                    last_check=datetime.utcnow(),
                    url=SERVICE_REGISTRY[i]["url"],
                    critical=SERVICE_REGISTRY[i].get("critical", False),
                )
            )
        else:
            services.append(result)

    # Persist each check + attach rolling uptime percentages (best-effort).
    for svc in services:
        record_check(svc.name, svc.status, svc.response_time_ms)
        summary = get_uptime_summary(svc.name)
        svc.uptime_24h = summary["uptime_24h"]
        svc.uptime_7d = summary["uptime_7d"]
        svc.uptime_30d = summary["uptime_30d"]

    return services


def calculate_overall_status(services: list[ServiceHealth]) -> tuple:
    """Calculate overall system status."""
    counts = {"healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0}

    for svc in services:
        counts[svc.status] = counts.get(svc.status, 0) + 1

    # Critical services down = overall unhealthy
    critical_unhealthy = any(
        svc.critical and svc.status in ("unhealthy", "unknown") for svc in services
    )

    if critical_unhealthy or counts["unhealthy"] > 0:
        overall = "unhealthy"
    elif counts["degraded"] > 0:
        overall = "degraded"
    else:
        overall = "healthy"

    return overall, counts


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/health-aggregation", response_model=HealthAggregationResponse)
async def get_health_aggregation():
    """
    Comprehensive health check of all SupremeAI services.
    Returns aggregated status with detailed per-service information.
    """
    # Check all services concurrently
    services = await check_all_services()

    # Calculate overall status
    overall_status, summary = calculate_overall_status(services)

    # Generate alerts for unhealthy critical services
    alerts = []
    for svc in services:
        if svc.critical and svc.status in ("unhealthy", "unknown"):
            alerts.append(f"🚨 CRITICAL: {svc.display_name} is {svc.status.upper()}")
        elif svc.status == "degraded":
            alerts.append(f"⚠️ WARNING: {svc.display_name} is degraded")

    return HealthAggregationResponse(
        timestamp=datetime.utcnow(),
        overall_status=overall_status,
        services=services,
        summary=summary,
        uptime_percentage=round((summary.get("healthy", 0) / len(services)) * 100, 1)
        if services
        else 0,
        alerts=alerts,
    )


@router.get("/service-uptime")
async def get_service_uptime(service: str = Query(...), hours: int = Query(24, ge=1, le=720)):
    """
    Historical up/down timeline + rolling uptime % for one service.
    Powers the uptime bar / sparkline in the admin dashboard.
    """
    return {
        "service": service,
        "hours": hours,
        "summary": get_uptime_summary(service),
        "history": get_history(service, hours=hours),
    }


@router.get("/service-health-map")
async def get_health_map():
    """
    Service-level health map (per-provider service status).

    Distinct from ``/admin-api/health-map`` (admin_dashboard.endpoints_health)
    which returns infrastructure-component status (DB/Redis/CF/Render).
    This endpoint returns service-level status grouped by provider
    (render/cloudflare/railway/other) — used by the HealthBanner component.

    #2114: previously registered at ``/health-map``, silently shadowing
    the established admin_dashboard.endpoints_health handler (Resolves #778).
    Moved to ``/service-health-map`` so both surfaces are reachable.
    """
    services = await check_all_services()
    overall_status, _ = calculate_overall_status(services)

    # Group by provider/type
    health_map = {}
    for svc in services:
        # Extract provider from name
        if "backend" in svc.name:
            provider = "render"
        elif "worker" in svc.name:
            provider = "cloudflare"
        elif "scraper" in svc.name:
            provider = "railway"
        else:
            provider = "other"

        if provider not in health_map or health_map[provider]["status"] == "healthy":
            health_map[provider] = {
                "status": svc.status if svc.status != "healthy" else "healthy",
                "service": svc.display_name,
            }

    return health_map


@router.get("/provider-readiness")
async def get_provider_readiness():
    """Return safe model diagnostics; readiness is never inferred from key presence."""
    return {
        "status": "ready" if not ModelRegistry.validate() else "degraded",
        "registry_issues": ModelRegistry.validate(),
        "models": ModelRegistry.readiness_snapshot(),
    }


@router.get("/dependencies")
async def check_dependencies():
    """
    Check external dependencies (database, Redis, LLM providers).
    """
    return {
        "database": {"status": "unknown"},
        "redis": {"status": "unknown"},
        "supabase": {"status": "unknown"},
        "llm_providers": {
            provider: {"status": "unvalidated"}
            for provider in sorted(
                {entry["provider"] for entry in ModelRegistry.readiness_snapshot().values()}
            )
        },
    }


@router.post("/test-service")
async def test_specific_service(service_url: str = Query(...)):
    """
    Test a specific service URL for connectivity.
    Useful for ad-hoc debugging from admin panel.
    """
    start_time = datetime.now()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                service_url,
                headers={"User-Agent": "SupremeAI-Admin-Test/1.0"},
            )

            return {
                "success": True,
                "url": service_url,
                "status_code": response.status_code,
                "response_time_ms": round((datetime.now() - start_time).total_seconds() * 1000, 2),
                "headers": dict(response.headers),
                "body_preview": response.text[:500] if response.text else None,
            }
    except Exception as e:
        return {
            "success": False,
            "url": service_url,
            "error": str(e),
            "response_time_ms": round((datetime.now() - start_time).total_seconds() * 1000, 2),
        }
