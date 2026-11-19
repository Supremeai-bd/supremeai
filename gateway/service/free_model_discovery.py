"""Refresh explicit zero-price catalog evidence; never probe with inference."""

import asyncio
import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from .free_route_policy import CATALOG_REQUIRED, approved_route
from .providers.adapters import PROVIDER_CONFIGS

logger = logging.getLogger("supremeai.free_model_discovery")
REFRESH_INTERVAL_S = 900
CATALOG_TTL_S = REFRESH_INTERVAL_S + 60
REFRESH_DEADLINE_S = 45


def _extract_free_aggregator_model(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    model, pricing = item.get("id"), item.get("pricing")
    if not isinstance(model, str) or not model.endswith(":free") or not isinstance(pricing, dict):
        return None
    if not {"prompt", "completion"} <= pricing.keys():
        return None
    try:
        # Reject unknown/missing amounts and nonzero request/image/search fees too.
        if all(Decimal(str(price)) == 0 for price in pricing.values()):
            return model
    except InvalidOperation:
        pass
    return None


async def validate_slot(slot: Any, client: httpx.AsyncClient) -> None:
    provider = slot.provider
    if provider not in CATALOG_REQUIRED:
        return
    # Keep the credential used for the request aligned with the evidence even
    # if the slot or the operator's binding key rotates while the GET is pending.
    credential = slot.key
    route = approved_route(provider, PROVIDER_CONFIGS[provider]["base_url"], credential)
    if route is None:
        slot.catalog_valid_until = 0.0
        return
    _, base_url, _ = route.identity
    try:
        response = await client.get(base_url + "/models", headers={"Authorization": f"Bearer {credential}"})
        response.raise_for_status()
        document = response.json()
        listings = document.get("data", []) if isinstance(document, dict) else []
        if not isinstance(listings, list):
            raise ValueError("invalid model catalog")
        free = {_extract_free_aggregator_model(item) for item in listings}
        # A conflicting price record for the same slug cannot prove zero cost.
        free.difference_update(
            item["id"] for item in listings
            if isinstance(item, dict) and isinstance(item.get("id"), str) and _extract_free_aggregator_model(item) is None
        )
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        slot.catalog_valid_until = 0.0
        logger.warning("Free catalog unavailable for %s (%s)", provider, type(exc).__name__)
        return
    slot.discovered_models = [model for model in route.models if model in free]
    slot.catalog_identity = route.identity
    slot.catalog_valid_until = time.monotonic() + CATALOG_TTL_S


async def run_discovery(squad: Any) -> None:
    if squad is None:
        return
    slots = [slot for pool in squad.pools.values() for slot in pool.slots if slot.provider in CATALOG_REQUIRED]
    if not slots:
        return
    limit = asyncio.Semaphore(6)
    # The number of slots is bounded by configured credentials, and the whole
    # pass has a deadline independently of per-connection timeouts.
    async with httpx.AsyncClient(timeout=6.0, follow_redirects=False) as client:
        async def refresh(slot: Any) -> None:
            async with limit:
                await validate_slot(slot, client)

        try:
            await asyncio.wait_for(asyncio.gather(*(refresh(slot) for slot in slots)), REFRESH_DEADLINE_S)
        except asyncio.TimeoutError:
            logger.warning("Free catalog refresh reached its pass deadline")


async def discovery_loop(squad: Any) -> None:
    while True:
        await run_discovery(squad)
        await asyncio.sleep(REFRESH_INTERVAL_S)
