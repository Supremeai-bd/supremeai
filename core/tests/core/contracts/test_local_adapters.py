import pytest

from core.contracts.adapters import ArtifactKind
from core.contracts.canonical import ExecutionContext
from core.contracts.local_adapters import (
    LocalArtifactStore,
    LocalBrowserAdapter,
    LocalTaskAdapter,
)


def context(tenant="tenant-a"):
    return ExecutionContext(
        tenant_id=tenant,
        actor_id="actor",
        workspace_id="workspace",
        correlation_id="corr",
        idempotency_key="key-" + tenant,
        capability="task.execute",
    )


def test_artifacts_are_tenant_scoped():
    store = LocalArtifactStore()
    artifact = store.put(context(), "result.txt", b"result", ArtifactKind.OUTPUT)
    assert store.get(context(), artifact.artifact_id) == b"result"
    with pytest.raises(KeyError):
        store.get(context("tenant-b"), artifact.artifact_id)


def test_tasks_are_cancelable_only_by_owner():
    adapter = LocalTaskAdapter()
    task_id = adapter.enqueue(context(), "demo", {"safe": True})
    adapter.cancel(context(), task_id)
    assert adapter.tasks[task_id]["state"] == "cancelled"
    with pytest.raises(KeyError):
        adapter.cancel(context("tenant-b"), task_id)


def test_browser_restricts_urls_and_tenants():
    browser = LocalBrowserAdapter("/tmp/workspace")
    session = browser.open(context(), "https://example.com")
    with pytest.raises(KeyError):
        browser.close(context("tenant-b"), session)
    with pytest.raises(ValueError):
        browser.open(context(), "file:///etc/passwd")
