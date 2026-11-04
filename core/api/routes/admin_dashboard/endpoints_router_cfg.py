"""Model-router status + override endpoints
(GET /admin-api/model-router, POST /admin-api/model-router/override)."""

from api.routes.admin_dashboard import router
from api.routes.admin_dashboard._models import RouterOverrideRequest
from core.monitoring.logging_config import logger


@router.get("/model-router")
def get_model_router():
    current_override = None
    remaining = 0
    provider_order = ["openrouter", "gemini", "groq", "deepseek"]

    try:
        from core.llm.llm_gateway.routing import get_runtime_override
        override = get_runtime_override()
        if override and override.get("provider"):
            current_override = {
                "provider": override["provider"],
                "model": override.get("model") or "",
            }
            remaining = override.get("remaining_requests", 0)
    except Exception as exc:
        logger.debug(f"Unable to read live runtime override: {exc}")

    try:
        from core.llm.llm_gateway import get_llm_gateway
        gateway = get_llm_gateway()
        chain = gateway._build_call_chain(None, None, "chat")
        order: list[str] = []
        for entry in chain:
            prov = entry.split("/", 1)[0]
            if prov and prov not in order:
                order.append(prov)
        if order:
            provider_order = order
    except Exception as exc:
        logger.debug(f"Unable to resolve live call chain: {exc}")

    return {
        "current_override": current_override,
        "override_remaining_requests": remaining,
        "ab_test_active": False,
        "ab_test_split": 50,
        "provider_order": provider_order,
        "cost_quality_preference": 0.7,
    }


@router.post("/model-router/override")
def set_router_override(payload: RouterOverrideRequest):
    logger.info(
        f"Router override set: {payload.provider}/{payload.model} for {payload.remaining_requests} requests"
    )
    try:
        from core.llm.llm_gateway.routing import set_runtime_override
        set_runtime_override(
            provider=payload.provider,
            model=payload.model,
            remaining_requests=payload.remaining_requests,
        )
    except Exception as exc:
        logger.warning(f"Unable to set runtime override: {exc}")

    return {
        "status": "success",
        "override": {
            "provider": payload.provider,
            "model": payload.model,
            "remaining": payload.remaining_requests,
        },
    }
