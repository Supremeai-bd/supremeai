"""Federation bootstrap — wires circle centers into the GovernanceCore.

The FCC construction rule: the Global Governance Core stays domain-free;
ONLY this module knows both the core and the concrete centers.
"""

from collections.abc import Iterable

from core.circles.centers import CircleCenter, build_default_centers
from core.circles.centers.realtime_center import RealtimeCenter
from core.circles.contracts import CircleManifest
from core.circles.governance_core import GovernanceCore, PolicyEvaluator
from core.circles.manifests import default_manifests
from core.circles.registry import CircleRegistry


def build_circle_registry(manifests: Iterable[CircleManifest] | None = None) -> CircleRegistry:
    """Legacy flat registry (pre-FCC compatibility surface)."""
    registry = CircleRegistry()
    for manifest in manifests or default_manifests():
        registry.register(manifest)
    return registry


def build_federation(
    policy_evaluator: PolicyEvaluator | None = None,
    centers: Iterable[CircleCenter] | None = None,
) -> GovernanceCore:
    """Construct the federated control plane:

    1. one instance of every default circle center,
    2. the Global Governance Core routing between them,
    3. realtime sync: every execution event is mirrored into the
       Realtime Circle (zero-infrastructure event bus).
    """
    built = tuple(centers) if centers is not None else build_default_centers()
    core = GovernanceCore(policy_evaluator=policy_evaluator)

    realtime: RealtimeCenter | None = None
    for center in built:
        core.register_center(center)
        if isinstance(center, RealtimeCenter):
            realtime = center
    if realtime is not None:
        core.subscribe(realtime.receive)
    return core


# Fix (ruff F401 regression b1ebe2753): the import was dropped as "unused", but
# it is a deliberate re-export — composition-root singleton API consumed by
# core/tests/test_governance_core.py (issue #2476). Single source of logic: the
# implementation lives in governance_core; bootstrap only re-exports it.
from core.circles.governance_core import get_governance_core, reset_governance_core  # noqa: F401

__all__ = ["build_circle_registry", "build_federation", "get_governance_core", "reset_governance_core"]

