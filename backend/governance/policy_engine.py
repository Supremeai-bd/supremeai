"""Policy Engine stub (issue #4049 — full implementation; #4050 wiring).

বাংলা: এটি minimal stub — শুধু #4050 3-Tier Routing-এর জন্য প্রয়োজনীয় interface।
Full implementation #4049-এ আসবে (who/what/cost/security gate)।

এই stub শুধু RoutingDecision-কে wrap করে + structured logging করে।
"""
from __future__ import annotations

from typing import Any

from core.logging_config import logger
from governance.routing_tiers import (
    DecisionResult,
    RoutingDecision,
    RoutingTier,
    is_blocked,
    make_routing_decision,
)


def evaluate_routing(
    action: str,
    provider: str,
    task_type: str,
    agent_id: str,
    reason: str = "",
    approval_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> RoutingDecision:
    """Evaluate a routing request through the 3-Tier boundary.

    বাংলা: এটি Policy Engine-এর entry point (stub)। প্রতিটি provider call-এর
    আগে এই ফাংশন কল হবে। Tier-3 without approval → DENY/PENDING।

    Returns:
        RoutingDecision with tier + result + audit trail
    """
    decision = make_routing_decision(
        action=action,
        provider=provider,
        task_type=task_type,
        agent_id=agent_id,
        reason=reason,
        approval_id=approval_id,
        details=details,
    )

    # Structured log (per #3415 PII redaction)
    log_data = {
        "decision_id": decision.decision_id,
        "tier": decision.tier.value,
        "result": decision.result.value,
        "provider": decision.provider,
        "task_type": decision.task_type,
        "agent_id": decision.agent_id,
        "reason": decision.reason,
        "policy_reference": decision.policy_reference,
        "approval_id": decision.approval_id,
    }

    if decision.tier == RoutingTier.ADMIN_ONLY and not approval_id:
        logger.warning(f"RoutingDecision BLOCKED (Tier-3 needs approval): {log_data}")
    elif decision.tier == RoutingTier.GOVERNED_AUTOMATIC:
        logger.info(f"RoutingDecision GOVERNED: {log_data}")
    else:
        logger.debug(f"RoutingDecision AUTO: {log_data}")

    return decision


def enforce_routing(decision: RoutingDecision) -> bool:
    """Enforce a routing decision — returns True if allowed, False if blocked.

    বাংলা: routing decision enforce করে। blocked হলে False, allowed হলে True।
    """
    if is_blocked(decision):
        logger.warning(
            f"Routing ENFORCED DENY: decision={decision.decision_id} "
            f"tier={decision.tier.value} action_blocked={decision.reason}"
        )
        return False
    return True
