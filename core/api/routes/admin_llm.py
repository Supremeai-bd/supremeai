"""Admin LLM Gateway control endpoints.

FIX(phantom-api): the CommandCenter LlmGatewayPage has always called
``/api/admin/llm/*`` — endpoints that never existed in the backend, so the
page rendered a permanent error state in every deployment. This module makes
that contract REAL by exposing actual routing state and control:

- ``GET  /providers``        — live provider stats from the latency-aware
                               weighted router (readiness, measured latency,
                               models derived from the routing policy).
- ``GET  /router``           — the real chat fallback chain, the active
                               runtime override (if any) and the live
                               cost/quality preference knob if configured.
- ``POST /router/override``  — activates a real routing override consumed by
                               the gateway's actual request path.
- ``DELETE /router/override`` — turns the override off again.
- ``GET  /rules``            — constitutional rules (God layer) as an object.
- ``POST /rules``            — bulk-persist rule key/values.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_admin
from api.routes.admin import god_layer  # shared God-layer instance (single SQLite handle)
from core.monitoring.logging_config import logger
from core.request_context import get_correlation_id

router = APIRouter(prefix="/api/admin/llm", tags=["Admin LLM Gateway"])


class RouterOverridePayload(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    model: str | None = Field(default=None, max_length=200)
    # None/0 = until turned off; otherwise the next N requests.
    remaining_requests: int | None = Field(default=None, ge=0, le=100_000)


def _known_providers() -> set[str]:
    """Providers the live router knows about (empty set = unknown, skip the check)."""
    try:
        from core.llm.provider_router import router_instance

        return {str(name) for name in router_instance.stats}
    except Exception:  # pragma: no cover — router import must never break the endpoint
        return set()


def _override_view(override: dict) -> dict | None:
    if not override.get("provider"):
        return None
    return {
        "provider": override["provider"],
        "model": override.get("model") or "",
        "set_by": override.get("set_by"),
        "set_at": override.get("set_at"),
    }


class BulkRulesPayload(BaseModel):
    rules: dict[str, str]


@router.get("/providers")
async def get_llm_providers(admin_user: dict = Depends(get_current_admin)):
    """Live provider readiness, measured latency and routing-policy models."""
    from core.llm.llm_gateway import get_llm_gateway
    from core.llm.provider_router import router_instance

    try:
        gateway = get_llm_gateway()
        policy = getattr(gateway, "routing_policy", {}) or {}
        known_models: list[str] = []

        fallbacks = policy.get("fallback_chain", [])
        if isinstance(fallbacks, list):
            known_models.extend(str(m) for m in fallbacks)
        for candidates in (policy.get("complexity_rules", {}) or {}).values():
            if isinstance(candidates, list):
                known_models.extend(str(m) for m in candidates)

        providers = []
        for name, stats in router_instance.stats.items():
            models = sorted({m.split("/", 1)[1] for m in known_models if m.startswith(f"{name}/")})
            is_healthy = stats.ready and not stats.is_circuit_open()
            providers.append(
                {
                    "id": name,
                    "name": name,
                    "status": "healthy" if is_healthy else stats.readiness_status or "unavailable",
                    # Measured rolling average; 0 = no samples yet.
                    "latency_ms": round(stats.avg_latency_ms, 1),
                    "models": [
                        # Full "provider/model" ids — the switcher posts them back.
                        f"{name}/{m}" if "/" not in m else m
                        for m in models
                    ],
                    "mode": "latency-weighted",
                }
            )
        return providers
    except Exception as exc:
        correlation_id = get_correlation_id() or uuid.uuid4().hex[:12]
        logger.exception(f"llm providers listing failed correlation_id={correlation_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error (correlation_id: {correlation_id})",
        ) from exc


@router.get("/router")
async def get_llm_router(admin_user: dict = Depends(get_current_admin)):
    """Real fallback chain + active runtime override state."""
    from core.llm.llm_gateway import get_llm_gateway
    from core.llm.llm_gateway.routing import get_runtime_override

    try:
        gateway = get_llm_gateway()
        # consume=False: viewing the status must not eat the override's request budget.
        chain = gateway._build_call_chain(None, None, "chat", consume=False)
        provider_order: list[str] = []
        for entry in chain:
            provider = entry.split("/", 1)[0]
            if provider and provider not in provider_order:
                provider_order.append(provider)

        override = get_runtime_override()
        current_override = _override_view(override)

        return {
            "current_override": current_override,
            "provider_order": provider_order,
            "cost_quality_preference": None,
            "fallback_chain": chain,
            "override_remaining_requests": override["remaining_requests"],
        }
    except Exception as exc:
        correlation_id = get_correlation_id() or uuid.uuid4().hex[:12]
        logger.exception(f"llm router state failed correlation_id={correlation_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error (correlation_id: {correlation_id})",
        ) from exc


@router.post("/router/override")
async def set_llm_router_override(
    payload: RouterOverridePayload, admin_user: dict = Depends(get_current_admin)
):
    """Activate a real routing override (consumed by the gateway request path)."""
    from core.llm.llm_gateway.routing import set_runtime_override

    provider = payload.provider.strip()
    model = (payload.model or "").strip() or None
    known = _known_providers()
    if known and provider not in known:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    if model and not model.startswith(f"{provider}/"):
        raise HTTPException(
            status_code=400, detail=f"Model must belong to the provider ({provider}/...)"
        )

    try:
        set_runtime_override(
            provider=provider,
            model=model,
            remaining_requests=payload.remaining_requests,
            set_by=str(admin_user.get("email") or admin_user.get("sub") or "admin"),
        )
        logger.critical(
            f"🔒 LLM routing override set to {payload.provider}/{payload.model or '(chain default)'}"
            f" by {admin_user.get('sub')}"
        )
        return {
            "status": "success",
            "provider": provider,
            "model": model,
            "remaining_requests": payload.remaining_requests,
        }
    except Exception as exc:
        correlation_id = get_correlation_id() or uuid.uuid4().hex[:12]
        logger.exception(f"llm router override failed correlation_id={correlation_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error (correlation_id: {correlation_id})",
        ) from exc


@router.delete("/router/override")
async def clear_llm_router_override(admin_user: dict = Depends(get_current_admin)):
    """Turn the runtime routing override off (normal automatic routing resumes)."""
    from core.llm.llm_gateway.routing import clear_runtime_override, get_runtime_override

    was_active = bool(get_runtime_override().get("provider"))
    clear_runtime_override()
    logger.critical(f"🔓 LLM routing override cleared by {admin_user.get('sub')}")
    return {"status": "success", "cleared": was_active}


@router.get("/finops")
async def get_finops(admin_user: dict = Depends(get_current_admin)):
    """FinOps: live limits (Supabase finops_settings) + today's estimated usage (Redis)."""
    from core.finops import guard

    settings = await guard.load_settings(force=True)
    try:
        usage = await guard.usage_snapshot()
    except Exception as exc:  # noqa: BLE001 — usage is informative; limits still shown
        logger.warning(f"finops usage snapshot failed: {type(exc).__name__}")
        usage = {"available": False, "globalTokens": 0, "topUsers": []}
    return {"settings": settings, "source": guard._cache.get("source", "default"), "usage": usage}


@router.put("/finops")
async def update_finops(payload: dict, admin_user: dict = Depends(get_current_admin)):
    """Update FinOps limits. Enforced by core within ~60s (settings cache)."""
    from core.finops import guard

    try:
        changes = guard.validate_settings(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    who = str(payload.get("updated_by") or admin_user.get("email") or admin_user.get("sub") or "admin")
    try:
        settings = await guard.save_settings(changes, who)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    logger.warning(f"💸 FinOps limits updated by {who}: {changes}")
    return {"status": "success", "settings": settings}


@router.get("/rules")
async def get_llm_rules(admin_user: dict = Depends(get_current_admin)):
    """Constitutional rules as a plain key/value object for the editor."""
    try:
        rules = god_layer.list_rules()
        as_object: dict[str, str] = {}
        for entry in rules or []:
            if isinstance(entry, dict) and "key" in entry:
                as_object[str(entry["key"])] = str(entry.get("value", ""))
        return as_object
    except Exception as exc:
        correlation_id = get_correlation_id() or uuid.uuid4().hex[:12]
        logger.exception(f"llm rules read failed correlation_id={correlation_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error (correlation_id: {correlation_id})",
        ) from exc


@router.post("/rules")
async def update_llm_rules(
    payload: BulkRulesPayload, admin_user: dict = Depends(get_current_admin)
):
    """Bulk-persist rule key/values through the God layer."""
    try:
        for key, value in payload.rules.items():
            god_layer.set_rule(key, value)
        logger.critical(
            f"🔒 {len(payload.rules)} constitutional rule(s) updated via LLM gateway by {admin_user.get('sub')}"
        )
        return {"status": "success", "updated": len(payload.rules)}
    except Exception as exc:
        correlation_id = get_correlation_id() or uuid.uuid4().hex[:12]
        logger.exception(f"llm rules write failed correlation_id={correlation_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error (correlation_id: {correlation_id})",
        ) from exc
