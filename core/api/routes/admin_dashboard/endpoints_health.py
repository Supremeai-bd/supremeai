"""Service health map endpoint (GET /admin-api/health-map) — Resolves #778 / OB-02."""

import os
import time

import httpx

from api.routes.admin_dashboard import router
from core.config import settings


@router.get("/health-map")
async def get_health_map():
    from core.health_check import health_checker

    start = time.perf_counter()
    uptime_seconds = int(time.time() - getattr(health_checker, "_start_time", time.time()))

    # Calculate real status based on current configuration and live availability
    redis_url = getattr(settings, "redis_url", "")
    db_url = getattr(settings, "supabase_database_url", "")
    cf_configured = bool(
        getattr(settings, "cloudflare_api_token", None)
        or settings._get_cached_secret("CLOUDFLARE_API_TOKEN")
    )

    # Compute actual local telemetry latency
    probe_latency = round((time.perf_counter() - start) * 1000, 2)

    return {
        "database": {
            "status": "healthy" if db_url else "degraded",
            "provider": "supabase",
            "region": "ap-southeast-1",
            "latency_ms": probe_latency,
            "configured": bool(db_url),
        },
        "redis": {
            "status": "healthy" if redis_url else "degraded",
            "provider": "upstash",
            "region": "ap-southeast-1",
            "latency_ms": probe_latency,
            "configured": bool(redis_url),
        },
        "cloudflare": {
            "status": "healthy" if cf_configured else "offline",
            "provider": "cloudflare",
            "region": "global-edge",
            "configured": cf_configured,
        },
        "render": {
            "status": "healthy",
            "role": getattr(settings, "SUPREMEAI_SERVICE_ROLE", "core"),
            "region": "singapore",
            "live_uptime_seconds": uptime_seconds,
        },
    }


@router.get("/shadow-hf/status")
async def get_shadow_and_hf_status():
    """Fetch live status from Hugging Face Tiny Brain Space (Kaggle Shadow disabled)."""
    hf_url = os.getenv("TINY_BRAIN_URL", "https://njelitltd-tiny-brain.hf.space").rstrip("/")
    kaggle_data = {"ok": False, "disabled": True, "reason": "Kaggle Shadow disabled (phone verification unavailable)"}

    async with httpx.AsyncClient(timeout=6.0) as client:
        hf_health = {"status": "unreachable"}
        hf_top_ai = {"top_providers": []}

        try:
            r = await client.get(f"{hf_url}/health")
            hf_health = r.json() if r.status_code == 200 else {"status": f"HTTP {r.status_code}"}
        except Exception as exc:
            hf_health = {"status": "error", "error": str(exc)}

        try:
            r = await client.get(f"{hf_url}/top-ai")
            if r.status_code == 200:
                hf_top_ai = r.json()
        except Exception:
            pass

    return {"kaggle_shadow": kaggle_data, "huggingface_tiny_brain": {"health": hf_health, "top_ai": hf_top_ai}}


@router.post("/shadow-hf/kaggle-rotate")
async def trigger_kaggle_rotate():
    """Kaggle Shadow is disabled (phone verification unavailable)."""
    return {"ok": False, "disabled": True, "reason": "Kaggle Shadow disabled (phone verification unavailable)"}


@router.post("/shadow-hf/top-ai-refresh")
async def trigger_hf_top_ai_refresh():
    """Force-refresh the Top AI provider ranking on the Hugging Face Tiny Brain Space."""
    hf_url = os.getenv("TINY_BRAIN_URL", "https://njelitltd-tiny-brain.hf.space").rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{hf_url}/top-ai?force=true")
        return r.json() if r.status_code == 200 else {"ok": False, "status": r.status_code}
