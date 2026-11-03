import pytest

from core.queue.task_contract import TaskEnvelope, TaskState, canonical_payload


def test_deduplication_is_tenant_scoped_and_stable():
    first = TaskEnvelope("job-1", "tenant-a", "request-1", "llm", {"b": 2, "a": 1})
    same = TaskEnvelope("job-2", "tenant-a", "request-1", "llm", {})
    other_tenant = TaskEnvelope("job-3", "tenant-b", "request-1", "llm", {})

    assert first.dedup_key == same.dedup_key
    assert first.dedup_key != other_tenant.dedup_key
    assert canonical_payload({"b": 2, "a": 1}) == '{"a":1,"b":2}'


def test_envelope_rejects_invalid_identity_and_attempts():
    with pytest.raises(ValueError):
        TaskEnvelope("", "tenant-a", "request-1", "llm", {})
    with pytest.raises(ValueError):
        TaskEnvelope("job-1", "tenant-a", "request-1", "llm", {}, attempt=6)


def test_state_serializes_as_wire_value():
    task = TaskEnvelope("job-1", "tenant-a", "request-1", "llm", {}, TaskState.RUNNING)
    assert task.to_dict()["state"] == "running"
    assert len(task.to_dict()["dedup_key"]) == 64
