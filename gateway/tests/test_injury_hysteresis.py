"""Hysteresis: cool fast, come back only on evidence.

The defect this pins: a slot re-entered rotation purely because its cooldown
timer expired. A dead cookie was therefore re-admitted every 30s / 5min / 10min,
failed, and the pool spent its life rediscovering the same fact — while a user paid
the latency of that rediscovery on every attempt.

The rule now:

* each consecutive injury without an intervening success doubles the cooldown
  (1x, 2x, 4x, 8x, capped), so a flapping surface costs the pool less each round;
* an injured slot that has not yet succeeded is **recovering** — still servable
  (a pool with nothing else must still answer) but ranked strictly behind every
  slot with a clean record, so it gets one request to prove itself rather than
  the traffic;
* only a real success clears the count. Time alone does not.
"""

from __future__ import annotations

import time

import pytest

from gateway.service import pool as pool_module
from gateway.service.pool import (
    COOLDOWN_AUTH_ERROR,
    COOLDOWN_RATE_LIMIT,
    COOLDOWN_SERVER_ERROR,
    INJURY_COOLDOWN_CEILING_S,
    KeySlot,
    ProviderKeyPool,
    injury_backoff,
)


def _make_pool(name="test", slots=None):
    pool = ProviderKeyPool.__new__(ProviderKeyPool)
    pool.provider = name
    pool.prefixes = ["TEST_API_KEY"]
    pool.slots = slots or []
    pool._index = 0
    return pool


def _slot(name="k", provider="test", **kwargs):
    return KeySlot(name=name, key=f"key-{name}", provider=provider, **kwargs)


def _benched_for(pool, slot, status, *, now=None):
    before = time.time()
    pool.report_injury(slot, status)
    elapsed = time.time() - before
    return slot.cooldown_until - before - elapsed * 0  # measured from the injury itself


# --- the backoff curve -----------------------------------------------------


@pytest.mark.parametrize(
    ("level", "expected"),
    [(0, 1), (1, 1), (2, 2), (3, 4), (4, 8), (5, 8), (99, 8)],
)
def test_the_backoff_doubles_then_caps(level, expected):
    assert injury_backoff(level) == expected


def test_the_first_injury_costs_what_it_always_did():
    """No regression for the common case: one bad request is benched for the base."""
    pool = _make_pool()
    slot = _slot()
    pool.report_injury(slot, 429)

    assert slot.injury_level == 1
    assert slot.recovering is True
    assert COOLDOWN_RATE_LIMIT - 2 < slot.cooldown_until - time.time() <= COOLDOWN_RATE_LIMIT


def test_each_further_failure_doubles_the_bench():
    pool = _make_pool()
    slot = _slot()

    pool.report_injury(slot, 500)
    first = slot.cooldown_until - time.time()
    pool.report_injury(slot, 500)
    second = slot.cooldown_until - time.time()
    pool.report_injury(slot, 500)
    third = slot.cooldown_until - time.time()

    assert first == pytest.approx(COOLDOWN_SERVER_ERROR, abs=2)
    assert second == pytest.approx(COOLDOWN_SERVER_ERROR * 2, abs=2)
    assert third == pytest.approx(COOLDOWN_SERVER_ERROR * 4, abs=2)


def test_the_bench_is_capped_however_often_it_fails():
    pool = _make_pool()
    slot = _slot()
    for _ in range(6):
        pool.report_injury(slot, 402)  # 1200s base × 8 would be 9600s

    assert slot.cooldown_until - time.time() <= INJURY_COOLDOWN_CEILING_S
    assert slot.cooldown_until - time.time() > INJURY_COOLDOWN_CEILING_S - 5


def test_the_level_stops_growing_so_the_math_cannot_overflow():
    pool = _make_pool()
    slot = _slot()
    for _ in range(40):
        pool.report_injury(slot, 500)
    assert slot.injury_level == pool_module.MAX_INJURY_LEVEL


def test_the_backoff_is_per_slot_not_per_status():
    """A different failure is still the same surface failing."""
    pool = _make_pool()
    slot = _slot()
    pool.report_injury(slot, 429)
    pool.report_injury(slot, 403)
    assert slot.injury_level == 2


# --- recovery needs evidence ----------------------------------------------


def test_a_success_is_the_only_thing_that_ends_probation():
    pool = _make_pool()
    slot = _slot()
    pool.report_injury(slot, 403)
    assert slot.recovering

    # Time passing is not evidence: the clock alone must not clear the record.
    time.sleep(0)
    assert slot.recovering

    pool.report_success(slot, latency_ms=120.0)
    assert not slot.recovering
    assert slot.injury_level == 0
    assert slot.consecutive_failures == 0


def test_a_failure_while_recovering_escalates_from_where_it_left_off():
    pool = _make_pool()
    slot = _slot()
    pool.report_injury(slot, 429)      # level 1
    pool.report_injury(slot, 429)      # level 2 — the flapping case
    assert slot.injury_level == 2


def test_an_injured_slot_is_still_healthy_once_the_bench_expires():
    """Probation is an ordering rule, not an exclusion: one injury must not end the pool."""
    slot = _slot()
    pool = _make_pool(slots=[slot])
    pool.report_injury(slot, 500)
    slot.cooldown_until = time.time() - 1

    assert slot.is_healthy is True
    assert slot.recovering is True
    assert pool.healthy_slots == [slot]


# --- ordering -------------------------------------------------------------


def _squad_with(*pools):
    squad = pool_module.FederationSquad.__new__(pool_module.FederationSquad)
    squad.pools = {pool.provider: pool for pool in pools}
    return squad


@pytest.fixture
def approved(monkeypatch):
    """Every provider's slots are approved; approval is a different test's subject."""
    from gateway.service.providers import adapters

    monkeypatch.setattr(adapters, "eligible_chat_models", lambda *_a, **_k: ("m",))


def test_a_clean_slot_outranks_a_recovering_one_even_when_slower(approved):
    fast_but_broken = _slot("broken", "alpha", ewma_latency_ms=100.0)
    slow_but_clean = _slot("clean", "alpha", ewma_latency_ms=900.0)
    pool = _make_pool("alpha", [fast_but_broken, slow_but_clean])
    pool.report_injury(fast_but_broken, 500)
    fast_but_broken.cooldown_until = time.time() - 1

    ranked = _squad_with(pool).get_candidate_slots("alpha")

    assert [slot.name for _provider, slot in ranked] == ["clean", "broken"], (
        "latency must not put a just-failed slot back in front of a working one"
    )


def test_a_pool_of_only_recovering_slots_still_answers(approved):
    """Ordering must never turn one injury into an outage."""
    only = _slot("only", "alpha")
    pool = _make_pool("alpha", [only])
    pool.report_injury(only, 500)
    only.cooldown_until = time.time() - 1

    ranked = _squad_with(pool).get_candidate_slots("alpha")

    assert [slot.name for _provider, slot in ranked] == ["only"]


def test_a_benched_slot_is_not_a_candidate_at_all(approved):
    benched = _slot("benched", "alpha")
    pool = _make_pool("alpha", [benched])
    pool.report_injury(benched, 429)

    assert _squad_with(pool).get_candidate_slots("alpha") == []


def test_next_key_prefers_the_clean_slot():
    fresh = _slot("fresh", "alpha", ewma_latency_ms=500.0)
    recovering = _slot("recovering", "alpha", ewma_latency_ms=50.0)
    pool = _make_pool("alpha", [fresh, recovering])
    pool.report_injury(recovering, 500)
    recovering.cooldown_until = time.time() - 1

    assert pool.get_next_key().name == "fresh"


def test_stats_expose_who_is_on_probation():
    healthy = _slot("healthy", "alpha")
    recovering = _slot("recovering", "alpha")
    pool = _make_pool("alpha", [healthy, recovering])
    pool.report_injury(recovering, 500)
    recovering.cooldown_until = time.time() - 1

    row = _squad_with(pool).stats()["providers"]["alpha"]

    assert row["healthy"] == 2
    assert row["recovering"] == 1, "an operator has to be able to see probation"
