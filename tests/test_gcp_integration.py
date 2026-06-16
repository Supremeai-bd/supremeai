import os
import tempfile

import httpx

from brain.gcp_router import GCPCloudRunRouter
from core.gcp_firestore import GCPFirestoreVerificationQueue
from core.gcp_pubsub_queue import GCPPubSubQueue
from tools.gcp_cloud_functions import GCPCloudFunctionClient


class FakeElapsed:
    def total_seconds(self):
        return 0.05


class FakeResponse:
    status_code = 200
    elapsed = FakeElapsed()
    text = '{"ok": true}'

    @property
    def is_success(self):
        return 200 <= self.status_code < 300

    def json(self):
        return {"ok": True}


class FakeClient:
    def __init__(self, timeout=None):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url):
        return FakeResponse()

    def request(self, method, url, json=None, headers=None):
        return FakeResponse()


def test_gcp_cloud_run_router_route(monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda timeout: FakeClient(timeout))
    router = GCPCloudRunRouter(base_url="https://supremeai-gcp.example.run.app")

    result = router.route("/api/v1/task/execute", {"task": "ping"})

    assert result["success"] is True
    assert result["provider"] == "gcp_cloud_run"
    assert result["data"] == {"ok": True}


def test_gcp_cloud_run_router_health(monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda timeout: FakeClient(timeout))
    router = GCPCloudRunRouter(base_url="https://supremeai-gcp.example.run.app")

    result = router.health_check(timeout=3)

    assert result["success"] is True
    assert result["status"] == "active"


def test_gcp_firestore_verification_queue_local_roundtrip():
    queue = GCPFirestoreVerificationQueue(db_path=":memory:")

    enqueue_result = queue.enqueue("task-1", {"text": "verify"}, priority=90)
    pending = queue.get_pending(limit=5)
    verified = queue.mark_verified("task-1")
    stats = queue.stats()

    assert enqueue_result["success"] is True
    assert queue.provider == "local_sqlite"
    assert pending[0]["task_id"] == "task-1"
    assert verified["verified"] == 1
    assert stats["pending"] == 0
    assert stats["verified"] == 1
    queue.close()


def test_gcp_pubsub_queue_local_roundtrip():
    queue = GCPPubSubQueue(db_path=":memory:")

    publish_result = queue.publish("task-1", {"text": "run"})
    messages = queue.pull(max_messages=5)
    ack_result = queue.ack(messages[0]["message_id"])
    stats = queue.stats()

    assert publish_result["success"] is True
    assert queue.provider == "local_sqlite"
    assert messages[0]["task_id"] == "task-1"
    assert ack_result["acked"] is True
    assert stats["pending"] == 0
    assert stats["acked"] == 1
    queue.close()


def test_gcp_cloud_function_client_trigger(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "supremeai-gcp")
    monkeypatch.setenv("GCP_REGION", "us-central1")
    monkeypatch.setenv("GCP_CLOUD_FUNCTION_NAME", "processOCR")
    monkeypatch.setattr(httpx, "Client", lambda timeout: FakeClient(timeout))
    client = GCPCloudFunctionClient()

    result = client.trigger({"imageUrls": ["https://example.com/a.png"]})

    assert result["success"] is True
    assert result["provider"] == "gcp_cloud_functions"
    assert result["function_url"].endswith("/processOCR")
