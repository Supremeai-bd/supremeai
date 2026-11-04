"""Capability status endpoint — single source of truth for feature availability.

Returns a versioned capability profile used by frontend banners, navigation,
admin health dashboard, smoke tests, and release checks. Each capability has a
state of: live | degraded | unavailable | planned | deprecated.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from core.services.config_registry import safe_defaults

router = APIRouter(
    prefix="/capabilities",
    tags=["capabilities"],
)


class CapabilityStatus(BaseModel):
    state: str  # live | degraded | unavailable | planned | deprecated
    requires_auth: bool = False
    reason_code: str | None = None


class CapabilitiesResponse(BaseModel):
    config_version: int = 1
    capabilities: dict[str, CapabilityStatus]


def _browser_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


@router.get("", response_model=CapabilitiesResponse)
async def get_capabilities():
    defaults = safe_defaults(public_only=True)
    features = {
        "chat": bool(defaults.get("feature.chat", True)),
        "research": bool(defaults.get("feature.research", True)),
        "scheduled_tasks": bool(defaults.get("feature.scheduled_tasks", True)),
        "browser": bool(defaults.get("feature.browser", False)),
        "billing": bool(defaults.get("feature.billing", True)),
    }
    maintenance = bool(defaults.get("system.maintenance_mode", False))

    caps: dict[str, CapabilityStatus] = {}

    # Chat
    if maintenance:
        caps["chat"] = CapabilityStatus(state="degraded", requires_auth=False, reason_code="MAINTENANCE_MODE")
    elif features["chat"]:
        caps["chat"] = CapabilityStatus(state="live", requires_auth=False)
    else:
        caps["chat"] = CapabilityStatus(state="unavailable", reason_code="FEATURE_DISABLED")

    # Research
    if maintenance:
        caps["research"] = CapabilityStatus(state="degraded", requires_auth=True, reason_code="MAINTENANCE_MODE")
    elif features["research"]:
        caps["research"] = CapabilityStatus(state="live", requires_auth=True)
    else:
        caps["research"] = CapabilityStatus(state="unavailable", reason_code="FEATURE_DISABLED")

    # Scheduled tasks
    if maintenance:
        caps["scheduled_tasks"] = CapabilityStatus(state="degraded", requires_auth=True, reason_code="MAINTENANCE_MODE")
    elif features["scheduled_tasks"]:
        caps["scheduled_tasks"] = CapabilityStatus(state="live", requires_auth=True)
    else:
        caps["scheduled_tasks"] = CapabilityStatus(state="unavailable", reason_code="FEATURE_DISABLED")

    # Browser
    if not features["browser"]:
        caps["browser"] = CapabilityStatus(state="planned", reason_code="FEATURE_DISABLED")
    elif not _browser_available():
        caps["browser"] = CapabilityStatus(state="unavailable", requires_auth=True, reason_code="BROWSER_RUNTIME_MISSING")
    elif maintenance:
        caps["browser"] = CapabilityStatus(state="degraded", requires_auth=True, reason_code="MAINTENANCE_MODE")
    else:
        caps["browser"] = CapabilityStatus(state="live", requires_auth=True)

    # Billing
    if features["billing"]:
        caps["billing"] = CapabilityStatus(state="live", requires_auth=True)
    else:
        caps["billing"] = CapabilityStatus(state="unavailable", reason_code="FEATURE_DISABLED")

    return CapabilitiesResponse(capabilities=caps)
PYEOF