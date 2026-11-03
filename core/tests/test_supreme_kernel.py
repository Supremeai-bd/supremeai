import pytest

from core.kernel.dispatcher import SupremeKernel
from core.kernel.interface import CircleScope, ExecutionMode, KernelRequest


@pytest.mark.asyncio
async def test_supreme_kernel_dispatch_unregistered():
    kernel = SupremeKernel()
    req = KernelRequest(
        target_circle=CircleScope.EXECUTION,
        capability="non_existent.test_action",
        mode=ExecutionMode.SYNC,
        actor_id="test_actor",
        tenant_id="test_tenant",
    )
    res = await kernel.dispatch(req)
    assert res.request_id == req.request_id
    assert res.target_circle == CircleScope.EXECUTION
    assert res.status in ["unavailable", "failed"]
    assert res.error_code == "capability_not_registered"


@pytest.mark.asyncio
async def test_supreme_kernel_dispatch_registered_mock():
    kernel = SupremeKernel()

    def mock_handler(req):
        return {"result": "ok", "value": 42}

    # Register handler
    try:
        kernel.registry.register_handler("test.mock_action", mock_handler)
    except ValueError:
        kernel.registry.handlers["test.mock_action"] = mock_handler

    req = KernelRequest(
        target_circle=CircleScope.EXECUTION,
        capability="test.mock_action",
        mode=ExecutionMode.SYNC,
        actor_id="test_actor",
        tenant_id="test_tenant",
    )
    res = await kernel.dispatch(req)
    assert res.request_id == req.request_id
    assert res.status == "succeeded"
    assert res.data == {"result": "ok", "value": 42}


# ─── Phase-4 wave 1: kernel-owned audit primitive wiring (#2260) ──────────────


class _RecordingAudit:
    """Test double that records journalled dispatches (no DB side effects)."""

    def __init__(self):
        self.rows: list[dict] = []

    def log_decision(self, action_type: str, decision_details: str, reasoning: str):
        self.rows.append(
            {
                "action_type": action_type,
                "decision_details": decision_details,
                "reasoning": reasoning,
            }
        )

    def get_audit_trail(self) -> list:
        return list(self.rows)


class _ExplodingAudit:
    """Audit double that always fails — dispatch must never break on it."""

    def log_decision(self, action_type: str, decision_details: str, reasoning: str):
        raise RuntimeError("audit backend down")

    def get_audit_trail(self) -> list:
        raise RuntimeError("audit backend down")


@pytest.mark.asyncio
async def test_kernel_journals_dispatch_through_audit_primitive():
    audit = _RecordingAudit()
    kernel = SupremeKernel(audit_logger=audit)

    def mock_handler(req):
        return {"ok": True}

    try:
        kernel.registry.register_handler("test.audited_action", mock_handler)
    except ValueError:
        kernel.registry.handlers["test.audited_action"] = mock_handler

    req = KernelRequest(
        target_circle=CircleScope.EXECUTION,
        capability="test.audited_action",
        mode=ExecutionMode.SYNC,
        actor_id="actor_1",
        tenant_id="tenant_1",
    )
    res = await kernel.dispatch(req)
    assert res.status == "succeeded"

    assert audit.rows, "kernel dispatch must journal through the audit primitive"
    row = audit.rows[-1]
    assert row["action_type"] == "kernel_dispatch"
    assert "test.audited_action -> succeeded" in row["decision_details"]
    assert "actor=actor_1" in row["reasoning"]
    assert "tenant=tenant_1" in row["reasoning"]

    trail = kernel.audit_trail()
    assert trail == audit.rows


@pytest.mark.asyncio
async def test_kernel_audit_failure_never_breaks_dispatch():
    kernel = SupremeKernel(audit_logger=_ExplodingAudit())

    def mock_handler(req):
        return {"ok": True}

    try:
        kernel.registry.register_handler("test.audit_bomb", mock_handler)
    except ValueError:
        kernel.registry.handlers["test.audit_bomb"] = mock_handler

    req = KernelRequest(
        target_circle=CircleScope.EXECUTION,
        capability="test.audit_bomb",
        mode=ExecutionMode.SYNC,
        actor_id="actor_1",
        tenant_id="tenant_1",
    )
    res = await kernel.dispatch(req)
    assert res.status == "succeeded", "audit failure must not corrupt the dispatch result"


def test_kernel_audit_primitives_importable_from_kernel_package():
    # Blueprint ৪.৩ wave 1: canonical audit primitives live in the kernel now.
    from core.kernel import AuditLogger, compute_entry_hash, get_audit_chain_store

    assert AuditLogger is not None
    assert callable(compute_entry_hash)
    assert callable(get_audit_chain_store)
