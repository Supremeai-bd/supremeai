"""3-Tier Auto-Routing boundary — Gateway Re-export (SSOT #4050).

বাংলা মন্তব্য:
gateway.agents.governance.routing_tiers হল core.governance.routing_tiers-এর
একটি ক্যানোনিকাল SSOT রি-এক্সপোর্ট (DRY নীতি অনুযায়ী কোড ডুপ্লিকেশন নির্মূল করা হয়েছে)।
"""

from __future__ import annotations

# Re-export everything from the canonical single source of truth in core.governance.routing_tiers
from core.governance.routing_tiers import (  # noqa: F401
    TIER1_ACTIONS,
    TIER2_ACTIONS,
    TIER3_ACTIONS,
    DecisionResult,
    RoutingDecision,
    RoutingTier,
    classify_tier,
    make_routing_decision,
)

__all__ = [
    "DecisionResult",
    "RoutingDecision",
    "RoutingTier",
    "TIER1_ACTIONS",
    "TIER2_ACTIONS",
    "TIER3_ACTIONS",
    "classify_tier",
    "make_routing_decision",
]
