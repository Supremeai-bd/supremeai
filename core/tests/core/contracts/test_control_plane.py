from core.contracts.canonical import ExecutionContext
from core.contracts.control_plane import MemoryCandidate, RealtimeEnvelope, frontend_request


def context():
    return ExecutionContext(
        tenant_id="tenant-a",
        actor_id="actor-a",
        workspace_id="workspace-a",
        correlation_id="corr-a",
        idempotency_key="key-a",
        capability="memory.write",
    )


def test_memory_candidate_is_tenant_stable():
    candidate = MemoryCandidate(context(), "important fact", 0.8, "event-1")
    assert len(candidate.fingerprint) == 64


def test_realtime_client_payload_redacts_secrets():
    envelope = RealtimeEnvelope(
        "execution", "updated", context(), 4, {"token": "secret", "status": "running"}
    )
    payload = envelope.to_client_dict()
    assert payload["payload"]["token"] == "[REDACTED]"
    assert payload["sequence"] == 4


def test_frontend_request_has_correlation_and_redaction():
    request = frontend_request(
        context(), "task.cancel", {"authorization": "secret", "task_id": "task-1"}
    )
    assert request["context"]["correlation_id"] == "corr-a"
    assert request["payload"]["authorization"] == "[REDACTED]"
