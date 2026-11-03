import asyncio

import pytest

from core.orchestration.capability_adapters import research_handler
from core.orchestration.conversation_orchestrator import (
    Capability,
    ConversationCommand,
    ConversationOrchestrator,
)


@pytest.mark.asyncio
async def test_research_handler_rejects_missing_tenant():
    result = await research_handler(ConversationCommand("research", "u1", ""))
    assert result["status"] == "unavailable"
    assert result["tenant_id"] is None


@pytest.mark.asyncio
async def test_unknown_capability_fails_closed():
    runtime = ConversationOrchestrator()
    result = await runtime.dispatch(ConversationCommand("hello", "u1", "t1"))
    assert result.status == "failed"
    assert result.error == "Capability unavailable"
    assert result.execution is not None
    assert result.execution.status == "unavailable"
    assert result.execution.tenant_id == "t1"
    assert result.execution.evidence[0]["type"] == "orchestration.unavailable"


@pytest.mark.asyncio
async def test_destructive_capability_requires_confirmation():
    async def handler(_):
        return "done"

    runtime = ConversationOrchestrator()
    runtime.register(Capability("chat", "low", handler, destructive=True))
    result = await runtime.dispatch(ConversationCommand("hello", "u1", "t1"))
    assert result.status == "confirmation_required"
    assert result.requires_confirmation is True
    assert result.execution is not None
    assert result.execution.status == "confirmation_required"
    assert result.execution.evidence[0]["type"] == "orchestration.approval_required"


@pytest.mark.asyncio
async def test_timeout_is_explicit_and_evidenced():
    async def handler(_):
        await asyncio.sleep(0.05)
        return "late"

    runtime = ConversationOrchestrator()
    runtime.register(Capability("chat", "low", handler))
    result = await runtime.dispatch(
        ConversationCommand("hello", "u1", "tenant-1", metadata={"timeout_seconds": 0.01})
    )
    assert result.status == "failed"
    assert result.execution is not None
    assert result.execution.status == "timed_out"
    assert result.execution.evidence[0]["type"] == "orchestration.timed_out"


@pytest.mark.asyncio
async def test_capability_dispatch_is_scoped_to_principal():
    seen = {}

    async def handler(command):
        seen["tenant"] = command.tenant_id
        return "ok"

    runtime = ConversationOrchestrator()
    runtime.register(Capability("chat", "low", handler))
    result = await runtime.dispatch(ConversationCommand("hello", "u1", "tenant-1"))
    assert result.status == "completed"
    assert seen["tenant"] == "tenant-1"


@pytest.mark.asyncio
async def test_adversarial_admin_only_capability_blocks_unauthorized_user():
    """Adversarial test: standard user trying to invoke admin_only capability must fail-closed."""

    async def admin_handler(_):
        return "secret-admin-action"

    runtime = ConversationOrchestrator()
    runtime.register(Capability("admin_action", "high", admin_handler, admin_only=True))

    # Standard non-admin user
    result = await runtime.dispatch(
        ConversationCommand(
            "admin",
            user_id="attacker-user",
            tenant_id="t1",
            role="user",
            metadata={"capability": "admin_action"},
        )
    )
    assert result.status == "denied"
    assert result.error == "Admin permission required"
    assert result.execution is not None
    assert result.execution.status == "denied"
    assert result.execution.evidence[0]["type"] == "orchestration.denied"


@pytest.mark.asyncio
async def test_adversarial_destructive_bypass_without_confirmation_flag():
    """Adversarial test: destructive action attempted with confirmation=False must be blocked."""
    executed = False

    async def delete_handler(_):
        nonlocal executed
        executed = True
        return "deleted"

    runtime = ConversationOrchestrator()
    runtime.register(Capability("chat", "low", delete_handler, destructive=True))

    result = await runtime.dispatch(
        ConversationCommand("hello", user_id="u1", tenant_id="t1", confirmation=False)
    )
    assert result.status == "confirmation_required"
    assert result.requires_confirmation is True
    assert executed is False

    # Now with explicit confirmation=True, it executes
    confirmed_result = await runtime.dispatch(
        ConversationCommand("hello", user_id="u1", tenant_id="t1", confirmation=True)
    )
    assert confirmed_result.status == "completed"
    assert executed is True
