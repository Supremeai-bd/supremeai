"""Regression tests for AgentSupervisor graceful shutdown."""

import asyncio

import pytest

from core.agent_supervisor import AgentSupervisor


@pytest.mark.asyncio
async def test_shutdown_all_swallows_expected_monitor_cancellation():
    """Cancelling the supervisor monitor is expected and must not abort shutdown."""
    supervisor = AgentSupervisor()
    supervisor._monitor_task = asyncio.create_task(asyncio.sleep(3600))

    await supervisor.shutdown_all(timeout=1)

    assert supervisor._monitor_task.cancelled()
    assert supervisor._shutdown_event.is_set()


@pytest.mark.asyncio
async def test_shutdown_all_cancels_registered_agents():
    """Registered agent tasks are cancelled and shutdown completes cleanly."""
    supervisor = AgentSupervisor()

    async def long_running_agent():
        await asyncio.sleep(3600)

    await supervisor.start_agent("test-agent", lambda: long_running_agent())

    await supervisor.shutdown_all(timeout=1)

    assert supervisor._agents == {}
    assert supervisor._health == {}
