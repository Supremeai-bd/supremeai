import pytest

from core.contracts.adapters import (
    ProviderTaskState,
    ProviderTaskStatus,
    validate_artifact,
)


def test_provider_task_status_has_explicit_lifecycle_state():
    status = ProviderTaskStatus(
        provider="managed-compute",
        task_id="task-1",
        state=ProviderTaskState.RUNNING,
        retryable=True,
    )

    assert status.state is ProviderTaskState.RUNNING
    assert status.result_artifact_ids == ()
    assert status.retryable is True


def test_provider_task_states_are_serializable_values():
    assert {state.value for state in ProviderTaskState} == {
        "pending",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "unknown",
    }


def test_artifact_validation_returns_content_metadata():
    content_type, size, digest = validate_artifact("report.json", b"{}")
    assert content_type == "application/json"
    assert size == 2
    assert len(digest) == 64


@pytest.mark.parametrize("name", ["/escape.txt", "../escape.txt", "nested/../../escape.txt"])
def test_artifact_path_escape_is_rejected(name):
    with pytest.raises(ValueError):
        validate_artifact(name, b"x")


def test_artifact_size_limit_is_enforced():
    with pytest.raises(ValueError):
        validate_artifact("large.bin", b"123", max_bytes=2)
