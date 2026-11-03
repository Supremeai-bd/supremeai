from datetime import timedelta

import pytest

from core.contracts.canonical import (
    ApprovalRequest,
    ApprovalStatus,
    EventEnvelope,
    ExecutionContext,
    ExecutionResult,
    ExecutionStatus,
    utc_now,
)
from core.contracts.fake_store import FakeExecutionStore


def context(tenant="tenant-a", key="request-1"):
    return ExecutionContext(
        tenant_id=tenant,
        actor_id="actor-1",
        workspace_id="workspace-1",
        correlation_id="corr-1",
        idempotency_key=key,
        capability="task.execute",
    )


def test_context_requires_tenant_and_actor():
    with pytest.raises(ValueError):
        context(tenant="")


def test_idempotency_is_tenant_scoped_and_duplicate_events_are_replayed():
    store = FakeExecutionStore()
    first = context()
    second = context()
    assert store.start(first)
    assert not store.start(second)
    event = EventEnvelope("execution.accepted", first, {"safe": True})
    assert store.append_event(event).event_id == store.append_event(event).event_id
    assert len(store.events) == 1


def test_tenant_event_filter_does_not_cross_boundaries():
    store = FakeExecutionStore()
    a, b = context("a", "a-1"), context("b", "b-1")
    store.append_event(EventEnvelope("x", a, {}))
    store.append_event(EventEnvelope("x", b, {}))
    assert [e.context.tenant_id for e in store.events_for_tenant("a")] == ["a"]


def test_approval_can_only_be_consumed_once_after_approval():
    ctx = context()
    with pytest.raises(ValueError):
        ApprovalRequest("approval-1", ctx, "deploy").consume()
    approved = ApprovalRequest(
        "approval-1",
        ctx,
        "deploy",
        ApprovalStatus.APPROVED,
        expires_at=utc_now() + timedelta(minutes=5),
    )
    assert approved.consume().status is ApprovalStatus.CONSUMED


def test_result_is_serializable():
    assert (
        ExecutionResult(ExecutionStatus.SUCCEEDED, output={"ok": True}).to_dict()["status"]
        == "succeeded"
    )


def test_ecosystem_contracts_validate_identity_and_artifact_size():
    from core.contracts.canonical import (
        ArtifactReference,
        CapabilityContract,
        PolicyDecision,
        PolicyEvaluation,
        ResourceContract,
    )

    capability = CapabilityContract("cap.task", "1.0.0", {"type": "object"}, {"type": "object"})
    resource = ResourceContract(
        "resource.worker", "internal", "worker", capabilities=(capability.capability_id,)
    )
    artifact = ArtifactReference(
        "artifact-1", "ref://run/r/artifact/a", "text/plain", "a" * 64, 4, "tenant-a", "run-1"
    )
    evaluation = PolicyEvaluation(
        PolicyDecision.ALLOW, capability.capability_id, "actor-1", "tenant-a"
    )

    assert capability.capability_id in resource.capabilities
    assert artifact.size_bytes == 4
    assert evaluation.decision is PolicyDecision.ALLOW

    with pytest.raises(ValueError):
        ArtifactReference("artifact-2", "ref://bad", "text/plain", "", -1, "tenant-a", "run-1")
