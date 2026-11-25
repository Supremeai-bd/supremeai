"""Admin API route for 3-Tier Routing governance (#4050).

বাংলা: admin endpoint-গুলো routing decisions + approvals manage করার জন্য।
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_admin
from governance.policy_engine import enforce_routing, evaluate_routing
from governance.routing_tiers import (
    RoutingDecision,
    RoutingTier,
    classify_tier,
    is_blocked,
)

router = APIRouter(prefix="/admin-api/routing", tags=["routing-governance"])


class RoutingRequest(BaseModel):
    """Request body for evaluating a routing decision."""

    action: str = Field(
        ...,
        description="Routing action (e.g., latency_weight_adjustment, provider_preference, constitutional_change)",
    )
    provider: str = Field(..., description="Provider name (e.g., groq, openai, cerebras)")
    task_type: str = Field("default", description="Task type")
    agent_id: str = Field(..., description="Agent requesting the routing")
    reason: str = Field("", description="Human-readable reason")
    approval_id: str | None = Field(None, description="Admin approval ID (for Tier-3)")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")


@router.post("/evaluate")
async def evaluate_routing_endpoint(
    request: RoutingRequest,
    _admin: Any = Depends(get_current_admin),
) -> dict[str, Any]:
    """Evaluate a routing request through the 3-Tier boundary.

    বাংলা: একটি routing request evaluate করে। Tier-3 without approval → PENDING_APPROVAL।
    """
    try:
        decision: RoutingDecision = evaluate_routing(
            action=request.action,
            provider=request.provider,
            task_type=request.task_type,
            agent_id=request.agent_id,
            reason=request.reason,
            approval_id=request.approval_id,
            details=request.details,
        )
        return {
            "status": "ok",
            "decision": decision.to_dict(),
            "allowed": not is_blocked(decision),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing evaluation failed: {e}") from e


@router.post("/enforce")
async def enforce_routing_endpoint(
    request: RoutingRequest,
    _admin: Any = Depends(get_current_admin),
) -> dict[str, Any]:
    """Evaluate + enforce a routing decision. Returns allowed=true/false.

    বাংলা: routing decision enforce করে। blocked হলে allowed=false।
    """
    try:
        decision = evaluate_routing(
            action=request.action,
            provider=request.provider,
            task_type=request.task_type,
            agent_id=request.agent_id,
            reason=request.reason,
            approval_id=request.approval_id,
            details=request.details,
        )
        allowed = enforce_routing(decision)
        return {
            "status": "ok",
            "decision": decision.to_dict(),
            "allowed": allowed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing enforcement failed: {e}") from e


@router.get("/tiers")
async def list_tiers_endpoint(
    _admin: Any = Depends(get_current_admin),
) -> dict[str, Any]:
    """List all 3 routing tiers with their actions.

    বাংলা: ৩টি routing tier-এর তালিকা + প্রতিটি tier-এর actions।
    """
    from governance.routing_tiers import TIER1_ACTIONS, TIER2_ACTIONS, TIER3_ACTIONS

    return {
        "tiers": [
            {
                "name": RoutingTier.AUTOMATIC.value,
                "description": "System (no human) — zero-latency, zero-human, logged on anomaly",
                "actions": sorted(TIER1_ACTIONS),
            },
            {
                "name": RoutingTier.GOVERNED_AUTOMATIC.value,
                "description": "System within admin-set policy bounds — logged with policy reference",
                "actions": sorted(TIER2_ACTIONS),
            },
            {
                "name": RoutingTier.ADMIN_ONLY.value,
                "description": "Human (admin decision gate) — BLOCKED until admin approval",
                "actions": sorted(TIER3_ACTIONS),
            },
        ],
        "principle": "99.99% automatic / 0.01% admin boundary",
    }


@router.get("/classify/{action}")
async def classify_action_endpoint(
    action: str,
    _admin: Any = Depends(get_current_admin),
) -> dict[str, Any]:
    """Classify a routing action into its tier.

    বাংলা: action নাম থেকে tier classify করে। অজানা action → Tier-3 (fail-safe)।
    """
    tier = classify_tier(action)
    return {
        "action": action,
        "tier": tier.value,
        "requires_approval": tier == RoutingTier.ADMIN_ONLY,
    }


# বাংলা মন্তব্য: core লেয়ার কখনো সরাসরি gateway import করবে না (Dependency Inversion)।
# gateway বুটের সময় নিজের dual-pool টেলিমেট্রি প্রোভাইডার রেজিস্টার করে।
_dual_pool_telemetry_provider: Any = None


def register_dual_pool_telemetry_provider(provider_fn: Any) -> None:
    """Register an external live telemetry provider (called by outer gateway layer)."""
    global _dual_pool_telemetry_provider
    _dual_pool_telemetry_provider = provider_fn


@router.get("/live-state")
async def get_dual_pool_live_state(
    _admin: Any = Depends(get_current_admin),
) -> dict[str, Any]:
    """Return live 6-model Dual-Pool priority ranking, key-pool health, and switch events."""
    if callable(_dual_pool_telemetry_provider):
        return _dual_pool_telemetry_provider()
    return {
        "priority_list": [],
        "key_pool_health": {},
        "recent_events": [],
        "status": "standalone_core",
    }


@router.post("/recheck")
async def force_dual_pool_recheck(
    _admin: Any = Depends(get_current_admin),
) -> dict[str, Any]:
    """Keep legacy callers from accidentally sending billable inference probes."""
    raise HTTPException(status_code=503, detail="Legacy inference recheck is unavailable; consult Gateway readiness.")
