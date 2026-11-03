import asyncio

import pytest

from core.services import ServiceRegistry
from core.tier8 import (
    get_agent_evolution_engine,
    get_self_improvement_agent,
    get_skill_marketplace_curator,
)
from core.tier8.tier8_integration import init_tier8, shutdown_tier8


# বাংলা মন্তব্য: Tier-8 মেটা-সেলফ এজেন্টস সাবসিস্টেমের ইন্টিগ্রেশন টেস্ট
@pytest.mark.asyncio
async def test_tier8_initialization_and_registry():
    registry = ServiceRegistry()

    # Initialize tier8
    status = await init_tier8(registry=registry)

    assert status["status"] == "initialized"

    # Verify services are registered in ServiceRegistry
    assert registry.has("self_improvement_agent") is True
    assert registry.has("agent_evolution_engine") is True
    assert registry.has("skill_marketplace_curator") is True

    # Retrieve instances and verify they are correct
    self_improve = await registry.get("self_improvement_agent")
    evolution = await registry.get("agent_evolution_engine")
    marketplace = await registry.get("skill_marketplace_curator")

    assert self_improve is get_self_improvement_agent()
    assert evolution is get_agent_evolution_engine()
    assert marketplace is get_skill_marketplace_curator()

    # Graceful shutdown
    try:
        shutdown_status = await shutdown_tier8()
        assert shutdown_status["status"] == "shutdown_complete"
    except asyncio.CancelledError:
        import logging

        logging.getLogger(__name__).warning("Silenced error in except-pass block")
