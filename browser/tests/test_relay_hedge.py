"""Hedged relay tiers (browser/server.py DuckAiEngine._run_tiers).

WHY THIS EXISTS
---------------
A one-word reply measured 6.2s. One contributor: the relay's tiers ran strictly
one after another, so a *successful but slow* Tier 1 (up to its 6s timeout) was
always paid in full before Tier 2 was even attempted, and a *failing* Tier 1 had
to finish timing out before Duck.ai started. Nothing overlapped.

These tests pin the hedge contract, including the property that matters most for
a free-tier product:

  FAST CASE COSTS EXACTLY ONE UPSTREAM REQUEST.

Hedging that always fired would double quota usage on every chat. It must only
cost a second request when the first is already going to be slow.

The tests use fake clocks (tiny sleeps) and stub the two tiers, so they assert
*ordering and concurrency*, not wall-clock speed — they cannot flake on a loaded
CI box.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# browser/ is a flat-layout service: server.py imports as a top-level module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server as relay_server  # noqa: E402


@pytest.fixture()
def engine(monkeypatch):
    """A DuckAiEngine whose two tiers are stubs, with a short hedge window."""
    eng = relay_server.DuckAiEngine()
    monkeypatch.setattr(relay_server, "RELAY_HEDGE_AFTER_S", 0.05)
    # The pool is irrelevant to these tests; a sentinel keeps them off the network.
    monkeypatch.setattr(relay_server, "_get_relay_client", lambda: object())
    return eng


def _run(coro):
    return asyncio.run(coro)


def _collect(engine, prompt="hi"):
    async def _go():
        out = []
        async for delta in engine._run_tiers(object(), prompt, None):
            out.append(delta)
        return out

    return _go


def test_fast_tier1_makes_exactly_one_upstream_request(engine, monkeypatch):
    """The common case must NOT touch the second tier at all (no quota doubling)."""
    calls = {"tier1": 0, "duck": 0}

    async def fast_tier1(client, prompt):
        calls["tier1"] += 1
        return "hello"

    async def duck(client, prompt, model):
        calls["duck"] += 1
        yield "should-not-run"

    monkeypatch.setattr(engine, "_ask_zero_auth_http_relay", fast_tier1)
    monkeypatch.setattr(engine, "_duck_tier", duck)

    out = _run(_collect(engine)())

    assert out == ["hello"]
    assert calls == {"tier1": 1, "duck": 0}, "fast path must not hedge"


def test_empty_tier1_falls_through_to_duck_without_waiting(engine, monkeypatch):
    """A quick 'nothing usable' must not sit out the hedge timer."""
    async def empty_tier1(client, prompt):
        return None

    async def duck(client, prompt, model):
        yield "from-duck"

    monkeypatch.setattr(engine, "_ask_zero_auth_http_relay", empty_tier1)
    monkeypatch.setattr(engine, "_duck_tier", duck)

    assert _run(_collect(engine)()) == ["from-duck"]


def test_slow_tier1_is_hedged_and_the_faster_tier_wins(engine, monkeypatch):
    """Tier 1 slower than the hedge window => Tier 2 is started and wins.

    This is the 6.2s case: without the hedge the slow tier is awaited in full.
    """
    order = []

    async def slow_tier1(client, prompt):
        order.append("tier1-start")
        await asyncio.sleep(0.4)  # far longer than the 0.05s hedge window
        order.append("tier1-finish")
        return "slow-answer"

    async def fast_duck(client, prompt, model):
        order.append("duck-start")
        yield "fast-answer"
        await asyncio.sleep(10)  # the loser would still be running

    monkeypatch.setattr(engine, "_ask_zero_auth_http_relay", slow_tier1)
    monkeypatch.setattr(engine, "_duck_tier", fast_duck)

    out = _run(_collect(engine)())

    assert out == ["fast-answer"], out
    # The hedge really did start while Tier 1 was still in flight.
    assert order[:2] == ["tier1-start", "duck-start"], order
    assert "tier1-finish" not in order, "slow tier must be cancelled, not awaited"


def test_slow_tier1_winning_race_still_yields_its_answer(engine, monkeypatch):
    """If the hedged Tier 1 answers first anyway, its answer is used."""
    async def tier1(client, prompt):
        await asyncio.sleep(0.08)  # past the hedge window, but still the winner
        return "tier1-answer"

    async def slow_duck(client, prompt, model):
        await asyncio.sleep(5)
        yield "never"

    monkeypatch.setattr(engine, "_ask_zero_auth_http_relay", tier1)
    monkeypatch.setattr(engine, "_duck_tier", slow_duck)

    assert _run(_collect(engine)()) == ["tier1-answer"]


def test_both_tiers_failing_raises_502(engine, monkeypatch):
    async def dead_tier1(client, prompt):
        await asyncio.sleep(0.2)
        return None

    async def dead_duck(client, prompt, model):
        raise relay_server.HTTPException(status_code=502, detail="upstream said no")
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(engine, "_ask_zero_auth_http_relay", dead_tier1)
    monkeypatch.setattr(engine, "_duck_tier", dead_duck)

    async def _go():
        async for _ in engine._run_tiers(object(), "hi", None):
            pass

    with pytest.raises(relay_server.HTTPException) as excinfo:
        _run(_go())
    assert excinfo.value.status_code == 502


def test_hedge_disabled_restores_strictly_serial_behaviour(engine, monkeypatch):
    """RELAY_HEDGE_AFTER_S=0 must be a true rollback: one tier, then the other."""
    monkeypatch.setattr(relay_server, "RELAY_HEDGE_AFTER_S", 0)
    order = []

    async def slow_tier1(client, prompt):
        order.append("tier1")
        await asyncio.sleep(0.05)
        return None

    async def duck(client, prompt, model):
        order.append("duck")
        yield "serial"

    monkeypatch.setattr(engine, "_ask_zero_auth_http_relay", slow_tier1)
    monkeypatch.setattr(engine, "_duck_tier", duck)

    assert _run(_collect(engine)()) == ["serial"]
    assert order == ["tier1", "duck"], "rollback path must not overlap tiers"


def test_ask_joins_stream_and_can_never_splice_two_answers(engine, monkeypatch):
    """ask() is the whole-answer contract; the hedge must yield one coherent body."""
    async def tier1(client, prompt):
        await asyncio.sleep(0.2)
        return "ONE"

    async def duck(client, prompt, model):
        yield "TWO"

    monkeypatch.setattr(engine, "_ask_zero_auth_http_relay", tier1)
    monkeypatch.setattr(engine, "_duck_tier", duck)

    reply = _run(engine.ask("hi"))
    assert reply in {"ONE", "TWO"}, reply
    assert "ONETWO" not in reply and "TWOONE" not in reply
