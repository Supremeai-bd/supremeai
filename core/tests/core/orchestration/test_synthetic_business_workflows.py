"""Synthetic end-to-end business workflows through the governed orchestrator.

Gap closure:
- Synthetic multi-step business flows (support lifecycle, governed evolution)
  must run end to end through ConversationOrchestrator.dispatch with tenant
  scoping, evidence chains, and durable ExecutionRecord truth units.
- Destructive-action adversarial cases: no confirmation => fail closed, replay
  of `confirmation=True` must NOT double-execute, non-admin cannot run an
  admin-only destructive capability, and a denying policy must block even an
  explicitly confirmed destructive dispatch (no approval bypass).
"""

import pytest

from core.orchestration.conversation_orchestrator import (
    Capability,
    ConversationCommand,
    ConversationOrchestrator,
)
from core.security.tool_gateway import PolicyDecision


class FakePolicy:
    """Deterministic stand-in for the ToolPolicyGateway used in dispatch."""

    def __init__(self, allowed: bool = True, reason: str | None = None):
        self.allowed = allowed
        self.reason = reason or ("allowed-by-test" if allowed else "denied-by-test")
        self.registered: list[tuple[str, str]] = []
        self.evaluated: list[dict] = []

    def register_tool(self, name: str, risk: str) -> None:
        self.registered.append((name, risk))

    async def evaluate(self, tool_name, ctx, risk=None, action=None):
        self.evaluated.append({"tool": tool_name, "ctx": dict(ctx), "risk": risk, "action": action})
        return PolicyDecision(
            allowed=self.allowed,
            tool_name=tool_name,
            user_id=ctx.get("sub"),
            tenant_id=ctx.get("tenant_id"),
            role=ctx.get("role", "user"),
            risk=risk or "low",
            reason=self.reason,
        )


def _stateful_handler(state: dict, key: str):
    """Handler that records the tenant/project/conversation view per step."""

    async def handler(command: ConversationCommand):
        state.setdefault(key, []).append(
            {
                "tenant": command.tenant_id,
                "project": command.project_id,
                "conversation": command.conversation_id,
                "user": command.user_id,
            }
        )
        return {"status": "ok", "step": key}

    return handler


@pytest.mark.asyncio
async def test_synthetic_customer_support_flow_tenant_scoped():
    """chat -> memory -> task lifecycle with deep tenant/entity scoping."""
    state: dict = {}
    runtime = ConversationOrchestrator()
    runtime.register(Capability("chat", "low", _stateful_handler(state, "chat")))
    runtime.register(Capability("memory", "low", _stateful_handler(state, "memory")))
    runtime.register(Capability("task", "medium", _stateful_handler(state, "task")))

    correlation_id = "corr_support_1"
    results = []
    for step, capability in [
        ("chat", "chat"),
        ("memory", "memory"),
        ("task", "task"),
    ]:
        result = await runtime.dispatch(
            ConversationCommand(
                f"resolve issue via {capability}",
                "user-a",
                "tenant-a",
                project_id="proj-1",
                conversation_id="conv-42",
                metadata={"correlation_id": correlation_id, "capability": capability},
            )
        )
        assert result.status == "completed", f"{step} failed: {result.error}"
        assert result.execution is not None
        assert result.execution.correlation_id == correlation_id
        assert result.execution.conversation_id == "conv-42"
        assert result.execution.tenant_id == "tenant-a"
        assert result.execution.capability == capability
        assert result.execution.evidence[-1]["type"] == "orchestration.completed"
        results.append(result)

    # One truth record per step, no collisions.
    ids = [r.execution.execution_id for r in results]
    assert len(set(ids)) == 3

    # Every handler saw the full tenant/entity scope — nothing leaked or empty.
    for key in ("chat", "memory", "task"):
        assert state[key], f"handler {key} was never invoked"
    for ctx in (*state["chat"], *state["memory"], *state["task"]):
        assert ctx == {
            "tenant": "tenant-a",
            "project": "proj-1",
            "conversation": "conv-42",
            "user": "user-a",
        }, f"scope leakage in synthetic flow: {ctx}"


@pytest.mark.asyncio
async def test_synthetic_workflow_isolates_tenants_across_parallel_flows():
    """Tenant A and tenant B flows must not cross-contaminate handler state."""
    state: dict = {}
    runtime = ConversationOrchestrator()
    runtime.register(Capability("task", "medium", _stateful_handler(state, "task")))

    for tenant, user in [("tenant-a", "user-a"), ("tenant-b", "user-b")]:
        await runtime.dispatch(
            ConversationCommand(
                "run task",
                user,
                tenant,
                project_id=f"proj-{tenant}",
                conversation_id=f"conv-{tenant}",
                metadata={"capability": "task"},
            )
        )

    assert len(state["task"]) == 2
    assert {c["tenant"] for c in state["task"]} == {"tenant-a", "tenant-b"}
    # Each tenant's own entity identifiers only — assert no cross-tenant bleed.
    by_tenant = {c["tenant"]: c for c in state["task"]}
    assert by_tenant["tenant-a"]["conversation"] == "conv-tenant-a"
    assert by_tenant["tenant-b"]["project"] == "proj-tenant-b"


@pytest.mark.asyncio
async def test_synthetic_governed_destructive_evolution_flow():
    """Destructive flow: fail closed -> confirmed -> execute (no replay bypass)."""
    calls: list[str] = []

    async def evolve_handler(_):
        calls.append("evolved")
        return {"status": "evolved"}

    runtime = ConversationOrchestrator(policy=FakePolicy(allowed=True))
    runtime.register(Capability("evolution", "high", evolve_handler, destructive=True))

    # Step 1: no confirmation -> must fail closed, handler untouched.
    blocked = await runtime.dispatch(
        ConversationCommand("improve yourself", "u1", "t1", metadata={"capability": "evolution"})
    )
    assert blocked.status == "confirmation_required"
    assert blocked.requires_confirmation is True
    assert blocked.execution is not None
    assert blocked.execution.status == "confirmation_required"
    assert blocked.execution.evidence[0]["type"] == "orchestration.approval_required"
    assert calls == []

    # Step 2: explicit confirmation -> executed exactly once.
    executed = await runtime.dispatch(
        ConversationCommand(
            "improve yourself",
            "u1",
            "t1",
            confirmation=True,
            metadata={"capability": "evolution"},
        )
    )
    assert executed.status == "completed"
    assert calls == ["evolved"]
    assert executed.execution.evidence[-1]["type"] == "orchestration.completed"

    # Step 3: replay without confirmation -> blocked again, still NO double-execute.
    replay = await runtime.dispatch(
        ConversationCommand("improve yourself", "u1", "t1", metadata={"capability": "evolution"})
    )
    assert replay.status == "confirmation_required"
    assert calls == ["evolved"], "replay must not double-execute a destructive action"


@pytest.mark.asyncio
async def test_synthetic_non_admin_blocked_from_admin_destructive_capability():
    """Approval bypass attempt 1: role escalation to admin-only destructive."""
    calls: list[str] = []

    async def admin_handler(_):
        calls.append("admin-ran")
        return "done"

    runtime = ConversationOrchestrator(policy=FakePolicy(allowed=True))
    runtime.register(Capability("admin", "high", admin_handler, admin_only=True, destructive=True))

    # Even with confirmation=True, a non-admin must be denied BEFORE execution.
    result = await runtime.dispatch(
        ConversationCommand(
            "user management",
            "u1",
            "t1",
            role="user",
            confirmation=True,
            metadata={"capability": "admin"},
        )
    )
    assert result.status == "denied"
    assert result.error == "Admin permission required"
    assert result.execution is not None
    assert result.execution.status == "denied"
    assert calls == []


@pytest.mark.asyncio
async def test_policy_denial_blocks_confirmed_destructive_dispatch():
    """Approval bypass attempt 2: policy denial overrides explicit confirmation."""
    calls: list[str] = []

    async def handler(_):
        calls.append("ran")
        return "done"

    runtime = ConversationOrchestrator(policy=FakePolicy(allowed=False))
    runtime.register(Capability("evolution", "high", handler, destructive=True, admin_only=True))

    result = await runtime.dispatch(
        ConversationCommand(
            "evolution flow",
            "u1",
            "t1",
            role="admin",
            confirmation=True,
            metadata={"capability": "evolution"},
        )
    )
    assert result.status == "denied"
    assert result.execution is not None
    assert result.execution.status == "denied"
    assert calls == [], "confirmed dispatch must still respect policy denial"
