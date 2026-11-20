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

Nothing here touches the request path: it is a background task created beside
`free_model_discovery`'s loop and cancelled the same way at shutdown.
"""

from __future__ import annotations

import asyncio
import logging
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
    """Refresh relay engine latency forever, one pass per interval."""
    while True:
        await run_refresh(squad)
        await asyncio.sleep(interval)
