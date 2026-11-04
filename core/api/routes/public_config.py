from fastapi import APIRouter
from pydantic import BaseModel

from core.config import settings
from core.services.config_registry import safe_defaults
from utils.branding import MODEL_DISPLAY, PROVIDER_DISPLAY

router = APIRouter(
    prefix="/config/public",
    tags=["public_config"],
)


class PublicConfigResponse(BaseModel):
    maxConcurrency: int  # -- camelCase required to match frontend JSON API contract
    features: dict[str, bool]
    version: str
    models: dict[str, str]
    adminEmail: str = ""  # -- empty to prevent administrative email disclosure
    branding: dict = {}
    navigation: list = []
    maintenanceMode: bool = False
    degradedMessage: str = ""
    limits: dict = {}


@router.get("", response_model=PublicConfigResponse)
async def get_public_config():
    defaults = safe_defaults(public_only=True)
    features = {
        "selfHealing": bool(defaults.get("feature.self_healing", False)),
        "costGuard": bool(defaults.get("feature.cost_guard", True)),
        "chat": bool(defaults.get("feature.chat", True)),
        "research": bool(defaults.get("feature.research", True)),
        "scheduledTasks": bool(defaults.get("feature.scheduled_tasks", True)),
        "browser": bool(defaults.get("feature.browser", False)),
        "billing": bool(defaults.get("feature.billing", True)),
    }
    return PublicConfigResponse(
        adminEmail="",
        maxConcurrency=int(defaults.get("runtime.max_concurrency", 5)),
        features=features,
        version="2.0.0",
        models={
            "chat": settings.model_chat,
            "general": settings.model_general,
            "multilingual": settings.model_multilingual,
        },
        branding={
            "productName": defaults.get("branding.product_name", "SupremeAI"),
            "supportUrl": defaults.get("branding.support_url", ""),
            "statusPageUrl": defaults.get("branding.status_page_url", ""),
        },
        navigation=list(defaults.get("navigation.user", [])),
        maintenanceMode=bool(defaults.get("system.maintenance_mode", False)),
        degradedMessage=str(defaults.get("system.degraded_message", "")),
        limits={
            "dailyUsage": defaults.get("limits.daily_usage", 1000),
            "monthlyUsage": defaults.get("limits.monthly_usage", 10000),
            "maxPromptChars": defaults.get("runtime.max_prompt_chars", 20000),
        },
    )


@router.get("/branding")
async def get_public_branding():
    """Return the canonical SupremeAI model/provider branding maps.

    Public (no auth) so the customer dashboard can brand model names without
    an admin token. The frontend uses this as the single source of truth,
    falling back to its local copy when offline.
    """
    return {
        "models": {k: v["label"] for k, v in MODEL_DISPLAY.items()},
        "providers": PROVIDER_DISPLAY,
    }
