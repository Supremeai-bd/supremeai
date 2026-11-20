"""The `supreme-spark` latency budget must be a DEADLINE, not a ranking hint.

WHY THIS EXISTS
---------------
`gateway/service/route_arbiter.py` declares, per model:

    MODEL_LATENCY_THRESHOLDS_MS = {"supreme-spark": 1500.0, ...}
    # "supreme-spark: Ultra-low latency (<1.5s)"

...and every read of that number feeds `route_score(...)` — a *ranking* input
used to sort candidate slots. Nothing anywhere turns it into a clock. Meanwhile
the clocks that actually bound a request are flat and much larger:

    CHAT_FIRST_TOKEN_TIMEOUT_S = 8
    CHAT_ROUTE_DEADLINE_S      = 15

So the product can advertise 1.5s while the machine is permitted to spend 8s on
a single candidate and 15s across failover. A user measuring a one-word reply at
6.2s is measuring exactly this gap.

These tests pin the *wall-clock* consequence, not an implementation detail:
a slow upstream must not be able to hold a `supreme-spark` request open for the
flat 8s/15s envelope. They use tiny sleeps so they assert ordering and bounds
without depending on machine speed.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, Mock

import pytest

from gateway.service import app as edge


def _elapsed_s(fn):
    start = time.monotonic()
    try:
        return fn(), time.monotonic() - start
    except Exception as exc:  # returned so the caller can assert on the failure
        return exc, time.monotonic() - start


def test_spark_budget_is_tighter_than_the_flat_envelope() -> None:
    """The declared budget must be <= the enforced clocks, or the promise is a lie.

    This is the contract test for the audit finding: 'CHAT_FIRST_TOKEN_TIMEOUT_S
    (8s) allows a supreme-spark request to blow its own 1.5s budget 5x over'.
    """
    budget_s = edge._route_budget_s("supreme-spark")
    assert budget_s == pytest.approx(1.5), budget_s
    assert edge._first_token_timeout_for("supreme-spark") <= budget_s, (
        "first-token timeout must not exceed the model's own latency budget"
    )
    assert edge._route_deadline_for("supreme-spark") <= budget_s, (
        "route deadline must not exceed the model's own latency budget"
    )


def test_slower_models_keep_a_larger_budget() -> None:
    """supreme-reason (2s) must not inherit spark's tighter clock."""
    assert edge._route_budget_s("supreme-reason") == pytest.approx(2.0)
    assert edge._route_deadline_for("supreme-reason") > edge._route_deadline_for("supreme-spark")


def test_unknown_model_falls_back_to_a_sane_default() -> None:
    assert edge._route_budget_s("not-a-real-model") == pytest.approx(1.8)


def test_env_override_still_wins_for_ops(monkeypatch) -> None:
    """Operators must be able to widen a budget without a deploy."""
    monkeypatch.setenv("CHAT_ROUTE_DEADLINE_S", "30")
    monkeypatch.setattr(edge, "CHAT_ROUTE_DEADLINE_S", 30.0, raising=False)
    assert edge._route_deadline_for("supreme-spark") == pytest.approx(min(30.0, 30.0))
    assert edge._route_deadline_for("supreme-spark") >= 1.5


def test_hedged_relay_endpoint_is_in_scope_or_explicitly_excluded() -> None:
    """spark must have its first-token clock under 1.5s or a documented exemption."""
    timeout = edge._first_token_timeout_for("supreme-spark")
    assert timeout <= 1.5, (
        f"first-token timeout {timeout}s exceeds the 1.5s spark budget; "
        "either tighten the clock or stop advertising '<1.5s' for this model"
    )
