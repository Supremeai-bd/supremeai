"""Relay engine latency ingest — turn the relay's measurements into routing input.

The router ranks providers by latency, but every web engine's number was a
hand-written constant (1400/1200/2500 ms in `dual_pool_priority_router`), while
`browser/server.py` was already measuring the truth: `GET /models` returns
`{"data": [{"id": "duck", "latency_ms": ...}, {"id": "gemini-web", ...}]}` from
its own `_engine_latency` bookkeeping. This module pulls that over the same 30
minute cycle an operator expects, and feeds it into the pool's unmeasured slots.

Three deliberate limits, so this cannot turn into a lie:

* **Seeds only.** A slot that has served real traffic keeps its measured EWMA.
  The relay's number is one hop's view of an engine, not a per-provider
  measurement, so overwriting evidence with a proxy would be corruption.
* **Never marks health.** A fast engine is not a live session; only a real
  request (or the session probe) can say a cookie works. This module touches
  latency and nothing else.
* **Failure is a warning, not an empty dict written over good state.** If the
  relay is down, last known values stay and the log says so once per pass.

An expired session is the failure this repo keeps paying for: the request
returns, the user sees "unavailable", and nothing stops the next request from
trying the same dead cookie. So the same pass also reads the relay's `/health`
session evidence and cools the slots behind a dead engine — using the pool's own
`report_injury()` cooldowns (403 → auth cooldown, 429 → rate-limit cooldown)
instead of inventing a second backoff scheme. Only `EXPIRED` and `CHALLENGED`
act; `OK` deliberately does **not** clear a cooldown, because cooling is undone
by evidence (a real success, or the cooldown expiring), not by a status string.

Nothing here touches the request path: it is a background task created beside
`free_model_discovery`'s loop and cancelled the same way at shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Mapping

import httpx

from .providers.web_engines import WEB_ENGINES, relay_base_url

logger = logging.getLogger("supremeai.web_engine_health")

# 30 minutes: sessions and engine speeds change on that scale, and a tighter
# loop only adds load to a free-tier relay.
ENGINE_REFRESH_S = 1800.0
REFRESH_DEADLINE_S = 20.0
REQUEST_TIMEOUT_S = 8.0


def engine_providers() -> dict[str, tuple[str, ...]]:
    """Relay engine id → the provider names routed to it."""
    grouped: dict[str, list[str]] = {}
    for engine in WEB_ENGINES:
        grouped.setdefault(engine.engine, []).append(engine.provider)
    return {engine: tuple(providers) for engine, providers in grouped.items()}


def parse_engine_latency(document: Any) -> dict[str, float]:
    """Extract `{engine: latency_ms}` from the relay's `/models` payload.

    Anything that is not a positive number is dropped rather than coerced to 0:
    a zero would rank the engine first, which is precisely the wrong reaction to
    "we do not know".
    """
    if not isinstance(document, dict):
        return {}
    rows = document.get("data")
    if not isinstance(rows, list):
        return {}
    latencies: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        engine, latency = row.get("id"), row.get("latency_ms")
        if not isinstance(engine, str) or not engine:
            continue
        try:
            value = float(latency)
        except (TypeError, ValueError):
            continue
        if value > 0:
            latencies[engine] = round(value, 1)
    return latencies


def seed_latency(squad: Any, latencies: Mapping[str, float]) -> int:
    """Seed `ewma_latency_ms` on slots that have never been measured.

    Returns how many slots were seeded, so the caller can log a real number
    instead of claiming a refresh happened.
    """
    if squad is None or not latencies:
        return 0
    seeded = 0
    for engine, providers in engine_providers().items():
        latency = latencies.get(engine)
        if latency is None:
            continue
        for provider in providers:
            pool = getattr(squad, "pools", {}).get(provider)
            for slot in getattr(pool, "slots", ()) or ():
                if getattr(slot, "ewma_latency_ms", 0.0) <= 0:
                    slot.ewma_latency_ms = latency
                    seeded += 1
    return seeded


async def fetch_engine_latency(
    base_url: str,
    *,
    client: Any = None,
    timeout: float = REQUEST_TIMEOUT_S,
) -> dict[str, float]:
    """GET the relay's `/models`; empty mapping on any failure (never raises)."""
    url = f"{base_url.rstrip('/')}/models"
    try:
        if client is not None:
            response = await client.get(url, timeout=timeout)
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as owned:
                response = await owned.get(url)
        if response.status_code != 200:
            logger.warning("Relay /models returned HTTP %s; keeping last known latencies",
                           response.status_code)
            return {}
        return parse_engine_latency(response.json())
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        # ValueError covers invalid JSON: a relay serving HTML must not crash the loop.
        logger.warning("Relay latency refresh unavailable (%s); keeping last known values",
                       type(exc).__name__)
        return {}


# The only two states that justify taking a surface out of rotation. `UNKNOWN`
# is deliberately absent: "we could not tell" must never cool a healthy engine.
SESSION_INJURY_STATUS: dict[str, int] = {"EXPIRED": 403, "CHALLENGED": 429}

# The operator's switch, as published by the relay. It is not an injury — no
# request failed — so it gets its own mechanism: park the slots for one refresh
# interval without touching `total_errors` or `consecutive_failures`, because a
# deliberate decision must not look like a broken credential in the stats.
DISABLED_STATE = "DISABLED"
DISABLED_PARK_S = ENGINE_REFRESH_S

# A session injury is capped at one refresh interval (not the pool's hour): a
# cookie can be renewed at any time, and the *only* way to find out is to send the
# engine a request. A longer bench would hide the recovery for two probe cycles,
# because a cooled slot is precisely what the probe stops choosing.
SESSION_INJURY_CEILING_S = ENGINE_REFRESH_S

# (provider, slot name) → (cooldown before parking, cooldown we set). Only slots
# *we* parked are ever released, and only while our value is still the one in
# place: an auth cooldown that arrived while the engine was off must survive
# re-enabling, which is why the previous value is restored conditionally.
_DISABLED_PARKS: dict[tuple[str, str], tuple[float, float]] = {}


def reset_disabled_parks() -> None:
    """Forget which slots are parked (tests, and a full squad rebuild)."""
    _DISABLED_PARKS.clear()


def parked_slots() -> tuple[tuple[str, str], ...]:
    """Which slots are parked by the switch right now (operator view, tests)."""
    return tuple(sorted(_DISABLED_PARKS))


def parse_session_states(document: Any) -> dict[str, str]:
    """Extract `{engine: state}` from the relay's `/health` payload."""
    if not isinstance(document, dict):
        return {}
    sessions = document.get("sessions")
    if not isinstance(sessions, dict):
        return {}
    states: dict[str, str] = {}
    for engine, entry in sessions.items():
        if not isinstance(engine, str) or not isinstance(entry, dict):
            continue
        if entry.get("disabled") is True:
            # The switch wins over the last request outcome: an engine the
            # operator turned off is off, whatever it managed before that.
            states[engine] = DISABLED_STATE
            continue
        state = entry.get("state")
        if isinstance(state, str) and state in {*SESSION_INJURY_STATUS, "OK", "UNKNOWN"}:
            states[engine] = state
    return states


async def fetch_session_states(base_url: str, *, client: Any = None, timeout: float = REQUEST_TIMEOUT_S) -> dict[str, str]:
    """GET the relay's `/health`; empty mapping on any failure (never raises)."""
    url = f"{base_url.rstrip('/')}/health"
    try:
        if client is not None:
            response = await client.get(url, timeout=timeout)
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as owned:
                response = await owned.get(url)
        if response.status_code != 200:
            logger.warning("Relay /health returned HTTP %s; sessions left as they were",
                           response.status_code)
            return {}
        return parse_session_states(response.json())
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("Relay session status unavailable (%s); sessions left as they were",
                       type(exc).__name__)
        return {}


def apply_session_states(squad: Any, states: Mapping[str, str], *, now: float | None = None) -> int:
    """Park slots behind a switched-off engine, cool slots behind a dead one.

    Returns how many slots were cooled for injury. Parking is reported through
    the log and `parked_slots()` rather than the return value, because an
    operator decision is not a request outcome.

    A slot already in cooldown is skipped for injury: re-injuring it every pass
    would keep resetting the clock and record a failure that did not happen.
    """
    if squad is None or not states:
        return 0
    clock = time.time() if now is None else now
    disabled = {engine for engine, state in states.items() if state == DISABLED_STATE}

    parked = 0
    released = 0
    for engine, providers in engine_providers().items():
        for provider in providers:
            pool = getattr(squad, "pools", {}).get(provider)
            for slot in getattr(pool, "slots", ()) or ():
                key = (provider, getattr(slot, "name", ""))
                if engine in disabled:
                    if key in _DISABLED_PARKS:
                        continue
                    before = getattr(slot, "cooldown_until", 0.0)
                    park_until = max(before, clock + DISABLED_PARK_S)
                    _DISABLED_PARKS[key] = (before, park_until)
                    slot.cooldown_until = park_until
                    parked += 1
                elif key in _DISABLED_PARKS:
                    before, park_until = _DISABLED_PARKS.pop(key)
                    if getattr(slot, "cooldown_until", 0.0) == park_until:
                        slot.cooldown_until = before
                        released += 1
    if parked:
        logger.warning("Operator disabled %s; parked %s slot(s)", sorted(disabled), parked)
    if released:
        logger.info("Operator re-enabled %s; released %s parked slot(s)", sorted(disabled), released)

    cooled = 0
    for engine, state in states.items():
        if engine in disabled:
            continue
        status = SESSION_INJURY_STATUS.get(state)
        if status is None:
            continue
        for provider in engine_providers().get(engine, ()):
            pool = getattr(squad, "pools", {}).get(provider)
            for slot in getattr(pool, "slots", ()) or ():
                if getattr(slot, "cooldown_until", 0.0) > clock:
                    continue
                pool.report_injury(slot, status, ceiling_s=SESSION_INJURY_CEILING_S)
                cooled += 1
    if cooled:
        logger.warning("Relay reported dead sessions; cooled %s slot(s)", cooled)
    return cooled


async def run_session_refresh(
    squad: Any, *, client: Any = None, base_url: str | None = None
) -> dict[str, str]:
    """One pass over the relay's session evidence; returns `{engine: state}`."""
    base = base_url or relay_base_url()
    try:
        states = await asyncio.wait_for(
            fetch_session_states(base, client=client), timeout=REFRESH_DEADLINE_S
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Relay session check exceeded %.0fs; sessions left as they were", REFRESH_DEADLINE_S
        )
        return {}
    apply_session_states(squad, states)
    return states


async def run_refresh(squad: Any, *, client: Any = None, base_url: str | None = None) -> dict[str, float]:
    """One pass: fetch, seed, report. Returns the observed engine latencies."""
    base = base_url or relay_base_url()
    try:
        latencies = await asyncio.wait_for(
            fetch_engine_latency(base, client=client), timeout=REFRESH_DEADLINE_S
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Relay latency refresh exceeded %.0fs; keeping last known values", REFRESH_DEADLINE_S
        )
        latencies = {}
    if latencies:
        seeded = seed_latency(squad, latencies)
        logger.info("Relay latency refresh: %s engine(s) observed, %s slot(s) seeded",
                    len(latencies), seeded)
    return latencies


async def web_engine_health_loop(squad: Any, *, interval: float = ENGINE_REFRESH_S) -> None:
    """Refresh relay latency and session evidence forever, one pass per interval."""
    while True:
        await run_refresh(squad)
        await run_session_refresh(squad)
        await asyncio.sleep(interval)
