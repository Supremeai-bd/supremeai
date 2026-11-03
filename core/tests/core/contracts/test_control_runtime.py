import pytest

from core.contracts.canonical import ExecutionContext
from core.contracts.control_plane import MemoryCandidate, RealtimeEnvelope
from core.contracts.control_runtime import LocalMemoryPromotion, LocalRealtimeStream


def context(tenant="tenant-a"):
    return ExecutionContext(
        tenant_id=tenant,
        actor_id="actor",
        workspace_id="workspace",
        correlation_id="corr",
        idempotency_key="key-" + tenant,
        capability="memory.write",
    )


def test_realtime_replay_is_tenant_scoped_and_deduplicated():
    stream = LocalRealtimeStream()
    event = RealtimeEnvelope("execution", "updated", context(), 1, {"status": "running"})
    assert stream.publish(event) is stream.publish(event)
    stream.publish(RealtimeEnvelope("execution", "updated", context("tenant-b"), 1, {}))
    assert len(stream.replay("tenant-a")) == 1
    assert len(stream.replay("tenant-b")) == 1


def test_memory_promotion_requires_both_signals():
    candidate = MemoryCandidate(context(), "fact", 0.8, "event")
    promotion = LocalMemoryPromotion()
    assert promotion.evaluate(candidate, "evaluator", 0.8).promoted
    assert not promotion.evaluate(candidate, "evaluator", 0.4).promoted
    with pytest.raises(ValueError):
        promotion.evaluate(candidate, "evaluator", 2)
