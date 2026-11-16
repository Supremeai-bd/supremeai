"""
SuperAI Health Check Endpoints
===============================
Comprehensive system health monitoring.

Author: SuperAI Transformation Patch
Version: 1.0.0
"""

import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.cache.redis_manager import redis_manager
from core.db_schema_gate import check_schema_status, production_schema_incompatible
from core.degraded_mode import db_degraded
from core.monitoring.logging_config import logger

router = APIRouter()


class HealthStatus(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str
    uptime_seconds: float
    services: dict
    persistence_mode: str
    cache_stats: dict | None = None


_start_time = time.time()

# ── Health-probe TTL caches (quota guard) ───────────────────────────────────
# Render/uptime monitors probe /health and /readyz every few seconds on every
# service; an uncached live PING/SELECT per probe is needless load and, on the
# shared free-tier Upstash account, burns the 500k command budget. Cache each
# probe result for a short, env-tunable TTL so N probes within the window share
# one command. ``(expires_at_epoch, status)`` tuples.
_DB_PROBE_CACHE: tuple[float, str] | None = None
_REDIS_PROBE_CACHE: tuple[float, str] | None = None


def _db_probe_ttl() -> float:
    try:
        return max(5.0, float(os.getenv("HEALTH_DB_CACHE_TTL", "15")))
    except ValueError:
        return 15.0


def _redis_probe_ttl() -> float:
    try:
        return max(10.0, float(os.getenv("HEALTH_REDIS_CACHE_TTL", "60")))
    except ValueError:
        return 60.0


@router.get("/health")
@router.get("/deep")
async def deep_health_check(response: Response):
    """
    Comprehensive health check endpoint.
    Sets status_code to 503 if any critical dependency is degraded, so orchestrators (Render/K8s) know it's unhealthy.
    """
    db_start = time.time()
    db_status = await _check_database()
    db_latency = round((time.time() - db_start) * 1000, 2)

    redis_start = time.time()
    redis_status = await _check_redis()
    redis_latency = round((time.time() - redis_start) * 1000, 2)

    cache_status = (
        "connected"
        if redis_manager.is_connected
        else ("not_configured" if redis_status == "not_configured" else "disabled")
    )
    persistence_mode = (
        "healthy" if db_status == "healthy" else ("degraded" if db_degraded() else "unavailable")
    )

    scraper_url = (
        os.getenv("SCRAPER_URL")
        or os.getenv("SCRAPER_SERVICE_URL")
        or os.getenv("RENDER_SCRAPER_URL")
    )
    scraper_status = "configured" if scraper_url else "not_configured"

    ollama_url = os.getenv("OLLAMA_URL")
    ollama_status = "configured" if ollama_url else "not_configured"

    overall_status = "healthy"
    if persistence_mode != "healthy":
        overall_status = "degraded" if persistence_mode == "degraded" else "unavailable"
    if redis_status == "unhealthy":
        # Redis is an optional cache/broadcast dependency. Its active outage should be
        # observable in deep health, but must not prevent the API from receiving traffic.
        # An unconfigured optional service is NOT an outage.
        if overall_status == "healthy":
            overall_status = "degraded"

    # Capture subsystem status from agent_supervisor
    from core.agent_supervisor import agent_supervisor

    agents_status = agent_supervisor.get_health()
    all_agents_healthy = all(a["status"] == "running" for a in agents_status.values())
    if not all_agents_healthy:
        overall_status = "degraded"

    if overall_status in ("degraded", "unavailable"):
        response.status_code = 503

    return HealthStatus(
        status=overall_status,
        timestamp=datetime.now(UTC).isoformat(),
        version="3.0.0-superai",
        uptime_seconds=round(time.time() - _start_time, 2),
        services={
            "database": {"status": db_status, "latency_ms": db_latency},
            "persistence": {"mode": persistence_mode},
            "redis": {"status": redis_status, "latency_ms": redis_latency},
            "scraper": {"status": scraper_status},
            "ollama": {"status": ollama_status},
            "cache": {"status": cache_status},
            "agents": agents_status,
        },
        persistence_mode=persistence_mode,
        cache_stats=None,
    )


@router.get("/ready")
async def readiness_check():
    """Kubernetes-style readiness probe.

    Role-aware per the P1 DB degradation policy (``core/health_policy.py``,
    the same single source of truth ``core/app_builder.py`` uses for the
    canonical ``/health/ready``):

    * core / unset role — DB failure means NOT READY (503). In
      production/staging ``SUPABASE_ALLOW_DB_DEGRADATION`` is IGNORED
      (fail-closed); in dev it may opt into degraded mode.
    * worker / scraper / mcp — role-specific degradation allowed: the probe
      stays 200 with ``status: degraded`` + a ``readiness_policy`` block so
      the degraded state is visible instead of silently green.
    """
    db_ok = await _check_database()
    redis_ok = await _check_redis()

    # Issue #478: schema gate — report schema state; fail closed in production
    # when a required table is missing (missing-table runtime failures are
    # worse than an honest 503). Read-only REST probe, cached 60s.
    import asyncio

    try:
        schema_reason = await asyncio.to_thread(production_schema_incompatible)
        schema_status = await asyncio.to_thread(check_schema_status)
    except Exception as exc:  # noqa: BLE001 — probe must never crash readiness
        logger.warning(f"schema gate probe error (treated as unknown): {exc}")
        schema_reason = None
        schema_status = {"checked": False, "reason": "probe error", "missing": [], "present": []}
    if schema_reason:
        env_hint = os.getenv("ENV", "")
        logger.critical(f"Readiness schema gate: {schema_reason} (env={env_hint})")
        raise HTTPException(
            status_code=503,
            detail=f"Schema incompatible — not ready ({schema_reason})",
        )

    persistence_mode = (
        "healthy" if db_ok == "healthy" else ("degraded" if db_degraded() else "unavailable")
    )
    role = (os.getenv("SUPREMEAI_SERVICE_ROLE", "core") or "core").strip().lower() or "core"

    if persistence_mode == "unavailable":
        degradation_requested = (
            os.getenv("SUPABASE_ALLOW_DB_DEGRADATION", "false").strip().lower() == "true"
        )
        try:
            from core.config import settings as _settings

            env = str(getattr(_settings, "env", "") or os.getenv("ENV", ""))
        except Exception:  # circular-import safety / very early boot
            env = os.getenv("ENV", "")
        from core.health_policy import db_failure_readiness

        serve_ready, reason = db_failure_readiness(role, env, degradation_requested)
        if not serve_ready:
            raise HTTPException(
                status_code=503,
                detail=f"Database unavailable — not ready ({reason})",
            )
        return {
            "status": "degraded",
            "service": "supremeai-backend",
            "role": role,
            "persistence_mode": persistence_mode,
            "cache": "healthy" if redis_ok == "healthy" else "degraded",
            "schema": {
                k: schema_status.get(k) for k in ("checked", "missing", "present", "unknown")
            },
            "readiness_policy": {"decision": "role-tolerated", "reason": reason},
        }

    return {
        "status": "ok" if persistence_mode == "healthy" else "degraded",
        "service": "supremeai-backend",
        "role": role,
        "persistence_mode": persistence_mode,
        "cache": "healthy" if redis_ok == "healthy" else "degraded",
        "schema": {k: schema_status.get(k) for k in ("checked", "missing", "present", "unknown")},
    }


@router.get("/live")
async def liveness_check():
    """Kubernetes-style liveness probe."""
    return {"status": "alive", "alive": True, "timestamp": datetime.now(UTC).isoformat()}


class AgentHealthFilter(BaseModel):
    """Optional request body for POST /health/agents — filter by agent ids."""

    agent_ids: list[str] | None = None


@router.get("/health/agents")
@router.post("/health/agents")
async def agents_health_check(agent_filter: AgentHealthFilter | None = None):
    """
    Per-agent health heartbeat (backend/frontend parity audit fix).

    Frontend consumers that previously received 404:
      - GET  /api/v1/health/agents             (useSwarmGraph — 2s heartbeat poll)
      - POST /api/v1/health/agents {agent_ids} (MockSwarmProvider — swarm metrics)
    Returns the agent_supervisor health map keyed by agent name. Requested ids
    that have no supervisor entry are reported as ``status="unknown"`` so clients
    always receive a complete, predictable key set.
    """
    from core.agent_supervisor import agent_supervisor

    health = agent_supervisor.get_health()
    requested_ids = agent_filter.agent_ids if agent_filter else None
    if requested_ids:
        health = {aid: health.get(aid, {"status": "unknown"}) for aid in requested_ids}
    return health


async def _check_database() -> str:
    """Check database connectivity (short-TTL cached — see _DB_PROBE_CACHE).

    Render/UptimeRobot probe /health & /readyz every few seconds on every
    service. An uncached ``SELECT 1`` per probe is needless DB load; cache the
    result for ``HEALTH_DB_CACHE_TTL`` seconds (default 15) so N probes within
    the window share one check. 15s keeps readiness fail-closed honest while
    removing the probe storm.
    """
    global _DB_PROBE_CACHE
    now = time.time()
    if _DB_PROBE_CACHE is not None and _DB_PROBE_CACHE[0] > now:
        return _DB_PROBE_CACHE[1]
    try:
        from database.session import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status = "healthy"
    except (SQLAlchemyError, OSError, TimeoutError):
        logger.warning("Database health check failed", exc_info=True)
        status = "unhealthy"
    _DB_PROBE_CACHE = (now + _db_probe_ttl(), status)
    return status


async def _check_redis() -> str:
    """Check Redis connectivity via the failover-aware manager (TTL cached).

    Root-cause fix (quota + correctness):
      * Previously this called ``get_cache()._redis`` — but ``get_cache()``
        returns ``SimpleCacheProxy``, which has **no** ``_redis`` attribute, so
        every probe raised ``AttributeError`` → was caught → ALWAYS reported
        "unhealthy". That made ``/health`` return a false 503 on every service
        that uses the deep health route, and spammed an exception per probe.
      * Now we go through ``redis_manager.get_client_async()`` — the SAME
        failover-aware client every consumer uses — so health checks rotate
        across the Upstash account chain instead of hammering a dead primary.
      * The result is cached for ``HEALTH_REDIS_CACHE_TTL`` seconds (default 60)
        so frequent Render/uptime probes share ONE command instead of one per
        probe. This is the quota guard: health checks can never burn the free
        tier budget by themselves.
      * A configured-but-exhausted Redis (quota/budget breaker open) reports
        "degraded" (NOT "unhealthy") so an optional cache outage cannot trigger
        a Render restart loop; only a real connection failure is "unhealthy".
    """
    global _REDIS_PROBE_CACHE
    now = time.time()
    if _REDIS_PROBE_CACHE is not None and _REDIS_PROBE_CACHE[0] > now:
        return _REDIS_PROBE_CACHE[1]

    status = "not_configured"
    try:
        client = await redis_manager.get_client_async()
        if client is not None:
            await client.ping()
            status = "healthy"
        elif not (getattr(redis_manager, "url", "") or ""):
            status = "not_configured"
        else:
            # Configured but currently unavailable (quota/budget breaker open).
            # Optional cache outage → degraded, not a hard outage (no 503 loop).
            status = "degraded"
    except Exception:
        logger.warning("Redis health check failed", exc_info=True)
        status = "unhealthy"

    _REDIS_PROBE_CACHE = (now + _redis_probe_ttl(), status)
    return status
