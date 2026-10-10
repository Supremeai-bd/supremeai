"""
Admin Health Aggregation Endpoint
Aggregates health status from all microservices and external dependencies.
"""

import asyncio
import hashlib
import os
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.dependencies import get_current_admin
from brain.model_registry import ModelRegistry
from core.deployment_fallback_defaults import ADMIN_URL_DEFAULT, SCRAPER_URL_DEFAULT
from core.health.uptime_tracker import (
    get_history,
    get_uptime_summary,
    record_check,
)
from core.http_client import get_shared_async_client
from core.logging_config import logger

router = APIRouter(prefix="/admin-api", tags=["health"], dependencies=[Depends(get_current_admin)])

# ══════════════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════════════


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


class SchemaDriftStatus(BaseModel):
    """#2681 Finding 2: DB schema-fingerprint প্রোবের ফলাফল।

    status: ok (baseline-এর সাথে মিল) · drift (live schema বদলেছে) ·
            error (প্রোব ব্যর্থ) · skipped (dialect সাপোর্টেড নয়)
    """

    status: str
    fingerprint: str | None = None
    baseline_fingerprint: str | None = None
    tables: int = 0
    columns: int = 0
    detail: str = ""


class HealthAggregationResponse(BaseModel):
    timestamp: datetime
    overall_status: str
    services: list[ServiceHealth]
    summary: dict[str, int]
    uptime_percentage: float
    alerts: list[str]
    # বাংলা মন্তব্য (#2681 Finding 2): runtime schema-drift প্রোবের ফলাফল —
    # None = প্রোব এখনো চলেনি/স্কিপড; backward-compat-এর জন্য optional।
    schema_drift: SchemaDriftStatus | None = None


class DependencyHealth(BaseModel):
    database: ServiceHealth
    redis: ServiceHealth
    supabase: ServiceHealth
    llm_providers: dict[str, ServiceHealth]


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

# বাংলা মন্তব্য (#3079): edge-worker URL এখন env-চালিত — প্লেসহোল্ডার host
# (supremeai-edge.your-subdomain.workers.dev) সরানো হয়েছে (লাইভ প্রোব → 404)।
# workers.dev সাবডোমেইন অ্যাকাউন্ট-স্পেসিফিক, রিপোর বাইরে — EDGE_WORKER_URL আনসেট হলে
# প্রোব স্কিপ (Rule 7: গ্রেসফুল ডিগ্রেডেশন, ফেক হেলথ-স্ট্যাটাস নয়)।
_EDGE_WORKER_URL = os.environ.get("EDGE_WORKER_URL", "").rstrip("/")

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
        "url": (_EDGE_WORKER_URL + "/health") if _EDGE_WORKER_URL else "",
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
        client = get_shared_async_client()
        response = await client.get(
            config["url"],
            headers={"User-Agent": "SupremeAI-HealthChecker/2.0"},
            timeout=config["timeout"],
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


# ══════════════════════════════════════════════════════════════════════════════
# #2681 Finding 2 — SCHEMA-DRIFT PROBE (deep health diagnostic)
# বাংলা মন্তব্য: আগের হেলথ-চেক presence-only ছিল (HTTP status/DB connectivity)।
# এখন cheap information_schema fingerprint দিয়ে runtime schema drift ধরা হয় —
# প্রথম সফল প্রোব = baseline; পরের প্রোবে fingerprint বদলালে = DRIFT + error_event_bus-এ
# remediation ইভেন্ট (#2527-এর issue-filer ব্রিজের একই পরিবার)।
# ══════════════════════════════════════════════════════════════════════════════

# বাংলা মন্তব্য: /health-aggregation কল-প্রতি DB প্রোব এড়াতে ৬০s TTL ক্যাশ।
_SCHEMA_PROBE_TTL_S = 60.0

_schema_state: dict = {
    "baseline": None,  # প্রথম সফল fingerprint — known-good হিসেবে
    "fingerprint": None,
    "status": "skipped",
    "tables": 0,
    "columns": 0,
    "detail": "",
    "probed_at": 0.0,
    "alert_key": None,  # শেষ emit-করা ইভেন্টের key — ডুপ্লিকেট স্প্যাম আটকায়
}
_schema_probe_lock = asyncio.Lock()


def _fingerprint_rows(rows: list[tuple[str, str, str]]) -> str:
    """#2681: (table, column, type) সারিগুলোর স্থিতিশীল sha256 ফিঙ্গারপ্রিন্ট।"""
    # বাংলা মন্তব্য: sort করে hash — কলাম-অর্ডার/কেস যেকোনো পরিবর্তন নির্ণয়যোগ্য, কিন্তু
    # একই স্কিমার জন্য ফিঙ্গারপ্রিন্ট অপরিবর্তিত থাকে (deterministic)।
    canonical = "\n".join(f"{t}.{c}:{y}" for t, c, y in sorted(rows))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


async def _collect_schema_rows(session) -> list[tuple[str, str, str]]:
    """#2681: dialect-aware সস্তা স্কিমা সারি সংগ্রহ।

    postgresql → information_schema.columns (public ছাড়া সিস্টেম স্কিমা বাদ)
    sqlite → sqlite_master + PRAGMA table_info (রেফারেন্স ফাইলের স্কিমা পাওয়া যায় না)
    অন্য dialect → ValueError (স্কিপড হবে)
    """
    dialect = getattr(getattr(session, "bind", None), "dialect", None)
    dialect_name = getattr(dialect, "name", "") or ""

    if dialect_name == "postgresql":
        # বাংলা মন্তব্য: এক কুয়েরিতে পুরো পাবলিক স্কিমা — সস্তা ও নিরাপদ (read-only)।
        from sqlalchemy import text

        result = await session.execute(
            text(
                "SELECT table_name, column_name, data_type FROM information_schema.columns "
                "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
                "ORDER BY table_name, column_name"
            )
        )
        return [(str(r[0]), str(r[1]), str(r[2])) for r in result.fetchall()]

    if dialect_name == "sqlite":
        from sqlalchemy import text

        tables_result = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        )
        rows: list[tuple[str, str, str]] = []
        for (table_name,) in tables_result.fetchall():
            info_result = await session.execute(text(f'PRAGMA table_info("{table_name}")'))
            for col in info_result.fetchall():
                # বাংলা মন্তব্য: PRAGMA → (cid, name, type, notnull, dflt_value, pk)।
                rows.append((str(table_name), str(col[1]), str(col[2])))
        return rows

    raise ValueError(f"unsupported dialect for schema probe: {dialect_name!r}")


def _emit_drift_event(status: dict) -> None:
    """#2681: drift/error ট্রানজিশনে একবারই remediation ইভেন্ট — spam-guard সহ।

    error_event_bus (#2527 issue-filer ব্রিজ) একই পরিবারের পাইপলাইন —
    severity ERROR হলে GitHub issue পর্যন্ত পৌঁছাতে পারে।
    """
    from core.messaging.event_bus import ErrorEvent, error_event_bus

    if status["status"] == "drift":
        alert_key = f"drift:{status['baseline']}->{status['fingerprint']}"
        event = ErrorEvent(
            module="health_aggregation",
            error_type="SCHEMA_DRIFT",
            message=(
                f"Live DB schema drifted from baseline "
                f"({status['baseline']} -> {status['fingerprint']}); "
                f"tables={status['tables']} columns={status['columns']}"
            ),
            severity="ERROR",
            context={
                "remediation": "connection-pool recycle + migration reconciliation advised",
                **{k: status[k] for k in ("baseline", "fingerprint", "tables", "columns")},
            },
        )
    elif status["status"] == "error":
        alert_key = f"error:{status['detail'][:80]}"
        event = ErrorEvent(
            module="health_aggregation",
            error_type="SCHEMA_PROBE_FAILED",
            message=f"Schema drift probe failed: {status['detail'][:200]}",
            severity="WARNING",
            context={"remediation": "check DB connectivity + privileges for information_schema"},
        )
    elif status["status"] == "ok" and str(_schema_state.get("alert_key") or "").startswith(
        ("drift:", "error:")
    ):
        # বাংলা মন্তব্য: drift/error থেকে সুস্থতায় ফেরা — resolved ইভেন্ট (নীরব স্কিপ নয়)।
        alert_key = "recovered"
        event = ErrorEvent(
            module="health_aggregation",
            error_type="SCHEMA_DRIFT",
            message="Schema drift resolved — live fingerprint matches baseline again",
            severity="INFO",
            resolved=True,
            context={"fingerprint": status["fingerprint"]},
        )
    else:
        return

    if alert_key == _schema_state.get("alert_key"):
        return  # বাংলা মন্তব্য: একই অবস্থা পুনরায় emit হবে না — ডুপ্লিকেট স্প্যাম আটকাও।
    _schema_state["alert_key"] = alert_key
    try:
        error_event_bus.emit(event)
    except Exception:
        # বাংলা মন্তব্য: ইভেন্ট-বাস নিজেই listener-isolated, তবুও হেলথ-এন্ডপয়েন্ট কখনো
        # emit-ফেইলুরে ভাঙবে না — তবে নীরবে গিলবে না (#1743): observability বাধ্যতামূলক।
        logger.debug("schema-drift remediation event emit failed (non-fatal)", exc_info=True)


async def probe_schema_drift(force: bool = False, session_factory=None) -> SchemaDriftStatus:
    """#2681 Finding 2: TTL-ক্যাশড schema-drift প্রোব (injectable factory — টেস্টবিল)।"""
    import time as _time

    async with _schema_probe_lock:
        now = _time.monotonic()
        if (
            not force
            and _schema_state["probed_at"]
            and (now - _schema_state["probed_at"]) < _SCHEMA_PROBE_TTL_S
        ):
            return SchemaDriftStatus(
                status=_schema_state["status"],
                fingerprint=_schema_state["fingerprint"],
                baseline_fingerprint=_schema_state["baseline"],
                tables=_schema_state["tables"],
                columns=_schema_state["columns"],
                detail=_schema_state["detail"],
            )

        _schema_state["probed_at"] = now
        try:
            if session_factory is None:
                # বাংলা মন্তব্য: lazy resolve — app-boot ছাড়া ইমপোর্ট-টাইমে DB টানবে না।
                from core.db import get_session_factory

                session_factory = get_session_factory()
            async with session_factory() as session:
                rows = await _collect_schema_rows(session)
        except ValueError as err:
            _schema_state.update(status="skipped", detail=str(err)[:200])
        except Exception as err:
            _schema_state.update(status="error", detail=str(err)[:200], fingerprint=None)
        else:
            fingerprint = _fingerprint_rows(rows)
            tables = len({t for t, _, _ in rows})
            # বাংলা মন্তব্য: প্রথম সফল প্রোবই baseline — known-good স্ন্যাপশট।
            baseline = _schema_state["baseline"] or fingerprint
            drift_status = "ok" if fingerprint == baseline else "drift"
            _schema_state.update(
                status=drift_status,
                fingerprint=fingerprint,
                baseline=baseline,
                tables=tables,
                columns=len(rows),
                detail="",
            )

        _emit_drift_event(dict(_schema_state))
        return SchemaDriftStatus(
            status=_schema_state["status"],
            fingerprint=_schema_state["fingerprint"],
            baseline_fingerprint=_schema_state["baseline"],
            tables=_schema_state["tables"],
            columns=_schema_state["columns"],
            detail=_schema_state["detail"],
        )


async def check_all_services() -> list[ServiceHealth]:
    """Check all registered services concurrently."""
    # বাংলা মন্তব্য (#3079): কনফিগার-অনুপস্থিত (খালি URL) সার্ভিস স্কিপ — কৃত্রিম লাল অ্যালার্ম নয়।
    probed = [svc for svc in SERVICE_REGISTRY if svc["url"]]
    tasks = [check_single_service(svc) for svc in probed]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to unhealthy status
    services = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            services.append(
                ServiceHealth(
                    name=probed[i]["name"],
                    display_name=probed[i]["display_name"],
                    status="unknown",
                    error=str(result),
                    last_check=datetime.utcnow(),
                    url=probed[i]["url"],
                    critical=probed[i].get("critical", False),
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
        # বাংলা মন্তব্য (#2681 Finding 2): প্রতি কলে deep-diagnostic স্কিমা-ড্রিফট
        # প্রোব — ভেতরে ৬০s TTL ক্যাশ, তাই এন্ডপয়েন্ট সস্তাই থাকে। প্রোব নিজে
        # fail-safe: DB নেমা থাকলে status=error ফেরায়, এন্ডপয়েন্ট ভাঙে না।
        schema_drift=await probe_schema_drift(),
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
        client = get_shared_async_client()
        response = await client.get(
            service_url, headers={"User-Agent": "SupremeAI-Admin-Test/1.0"}, timeout=10.0
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
