"""AUD-3.2/3.3/3.6/3.8 — Tool Policy Gateway tests.

The gateway is the single canonical policy decision boundary for tool execution:
identity, tenant, role-vs-risk, and budget checks plus audit emission.
"""

import pytest

from core.security.tool_gateway import (
    PolicyDecision,
    ToolPolicyGateway,
    ToolPolicyViolation,
)


@pytest.fixture
def gateway():
    g = ToolPolicyGateway()
    g.register_tool("read.search", "low")
    g.register_tool("mcp.web_scraper", "medium")
    g.register_tool("platform_action.slack", "high")
    return g


@pytest.mark.asyncio
async def test_unauthenticated_caller_denied(gateway):
    """AUD-3.3: no identity → no execution (fail-closed)."""
    decision = await gateway.evaluate(tool_name="read.search", user=None)
    assert decision.allowed is False
    assert decision.checks["identity"] is False


@pytest.mark.asyncio
async def test_authenticated_low_risk_allowed(gateway):
    decision = await gateway.evaluate(
        tool_name="read.search", user={"sub": "user-1", "role": "user"}
    )
    assert decision.allowed is True
    assert decision.tenant_id == "user-1"


@pytest.mark.asyncio
async def test_non_admin_cannot_run_high_risk_tool(gateway):
    """AUD-3.3: high/critical risk requires the admin role."""
    decision = await gateway.evaluate(
        tool_name="platform_action.slack", user={"sub": "user-1", "role": "user"}
    )
    assert decision.allowed is False
    assert decision.checks["role"] is False
    assert "admin" in decision.reason


@pytest.mark.asyncio
async def test_admin_can_run_high_risk_tool(gateway):
    decision = await gateway.evaluate(
        tool_name="platform_action.slack", user={"sub": "admin-1", "role": "admin"}
    )
    assert decision.allowed is True


@pytest.mark.asyncio
async def test_declared_risk_cannot_downgrade_registered_risk(gateway):
    decision = await gateway.evaluate(
        tool_name="platform_action.slack",
        user={"sub": "user-1", "role": "user"},
        risk="low",
    )
    assert decision.risk == "high"
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_unregistered_tool_defaults_to_high_risk(gateway):
    """Fail-closed: unknown tools behave as high risk until classified."""
    decision = await gateway.evaluate(
        tool_name="brand_new_unknown_tool", user={"sub": "user-1", "role": "user"}
    )
    assert decision.risk == "high"
    assert decision.allowed is False  # requires admin


@pytest.mark.asyncio
async def test_budget_exhaustion_blocks(gateway, monkeypatch):
    """AUD-3.6: budget check consulted; exhausted budget blocks execution."""

    class _FakeGuard:
        async def check_budget(self, tenant_id, estimated_cost):
            return False

    import core.cost_guard as cg

    monkeypatch.setattr(cg, "cost_guard", _FakeGuard(), raising=False)

    decision = await gateway.evaluate(
        tool_name="mcp.web_scraper",
        user={"sub": "user-1", "role": "user"},
        estimated_cost=0.5,
    )
    assert decision.allowed is False
    assert decision.checks["budget"] is False


@pytest.mark.asyncio
async def test_enforce_raises_violation(gateway):
    with pytest.raises(ToolPolicyViolation) as excinfo:
        await gateway.enforce(
            tool_name="platform_action.slack", user={"sub": "user-1", "role": "user"}
        )
    decision = excinfo.value.decision
    assert isinstance(decision, PolicyDecision)
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_audited_execution_context(gateway, caplog):
    """AUD-3.8: audited execution emits decision + execution events and re-raises errors."""
    async with gateway.audited_execution(
        tool_name="read.search", user={"sub": "user-1", "role": "user"}
    ) as decision:
        assert decision.allowed is True

    with pytest.raises(RuntimeError):
        async with gateway.audited_execution(
            tool_name="read.search", user={"sub": "user-1", "role": "user"}
        ):
            raise RuntimeError("tool blew up")


@pytest.mark.asyncio
async def test_invalid_risk_registration_rejected(gateway):
    with pytest.raises(ValueError):
        gateway.register_tool("bad.tool", "extreme")
