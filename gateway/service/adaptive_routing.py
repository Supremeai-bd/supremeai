"""Small, deterministic adaptive routing primitives for free-tier routes.

The scorer deliberately has no configured priority order. A route's score is
based on the remaining free budget and its observed latency; unknown quota is
neutral rather than treated as unlimited. Callers own the actual quota source
(headers, env-backed estimate, or provider telemetry).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteSnapshot:
    """A point-in-time route view used for one selection decision."""

    name: str
    available: bool = True
    latency_ms: float = 0.0
    remaining: int | None = None
    limit: int | None = None
    failures: int = 0


def route_score(route: RouteSnapshot, latency_target_ms: float = 1000.0) -> float:
    """Return a higher-is-better score using quota first, then latency.

    ``remaining=None`` means the provider did not expose a free-tier budget;
    it receives a neutral quota component and is never preferred merely because
    its quota is unknown. The small failure penalty prevents repeatedly trying
    a flapping route without introducing a fixed priority.
    """
    if not route.available:
        return float("-inf")

    if route.limit is not None and route.limit > 0 and route.remaining is not None:
        quota_score = min(1.0, max(0.0, route.remaining / route.limit))
    else:
        quota_score = 0.5

    if route.latency_ms > 0:
        latency_score = 1.0 / (1.0 + route.latency_ms / latency_target_ms)
    else:
        latency_score = 0.5

    failure_penalty = min(0.25, max(0, route.failures) * 0.05)
    return (quota_score * 0.6) + (latency_score * 0.4) - failure_penalty


def choose_route(routes: list[RouteSnapshot]) -> str | None:
    """Choose the best route without a fixed tie-breaking priority."""
    eligible = [route for route in routes if route_score(route) != float("-inf")]
    if not eligible:
        return None
    # Name is only a deterministic final tie-breaker; it is not a priority.
    return max(eligible, key=lambda route: (route_score(route), route.name)).name


@dataclass
class RouteState:
    """Runtime EWMA/failure state for a logical route."""

    name: str
    latency_ms: float = 0.0
    failures: int = 0
    remaining: int | None = None
    limit: int | None = None

    def snapshot(self, available: bool = True) -> RouteSnapshot:
        return RouteSnapshot(
            name=self.name,
            available=available and (self.remaining is None or self.remaining > 0),
            latency_ms=self.latency_ms,
            remaining=self.remaining,
            limit=self.limit,
            failures=self.failures,
        )

    def record(self, latency_ms: float, success: bool, remaining: int | None = None) -> None:
        if latency_ms > 0:
            self.latency_ms = float(latency_ms) if self.latency_ms <= 0 else self.latency_ms * 0.7 + latency_ms * 0.3
        if success:
            self.failures = 0
            if self.remaining is not None:
                self.remaining = max(0, self.remaining - 1)
        else:
            self.failures += 1
        if remaining is not None:
            self.remaining = max(0, remaining)
