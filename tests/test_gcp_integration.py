import os
import tempfile

import httpx

import pytest

try:
    from firebase_admin import auth as firebase_admin_auth, exceptions as firebase_exceptions
    from google.cloud import firestore_v1, pubsub_v1
    HAS_FIREBASE_DEPS = True
except ImportError:
    HAS_FIREBASE_DEPS = False

from brain.gcp_router import GCPCloudRunRouter
from core.gcp_firestore import GCPFirestoreVerificationQueue
from core.gcp_pubsub_queue import GCPPubSubQueue
from tools.gcp_cloud_functions import GCPCloudFunctionClient


pytestmark = pytest.mark.skipif(not HAS_FIREBASE_DEPS, reason="firebase/google deps not installed")


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


class FakeFirestoreClient:
    def __init__(self, project=None):
        self.project = project
        self._collections: Dict[str, list] = {}

    async def collection(self, name: str):
        self._collections.setdefault(name, [])
        return FakeCollection(self._collections[name])

    async def close(self):
        return None


class FakeCollection:
    def __init__(self, _store: list):
        self._store = _store

    def document(self, doc_id: str):
        return FakeDocumentRef(self._store, doc_id)

    async def add(self, data):
        self._store.append(data)
        return None, data


class FakeDocumentRef:
    def __init__(self, store: list, doc_id):
        self._store = store
        self._id = doc_id

    async def set(self, payload):
        found = False
        for item in self._store:
            if item.get("id") == self._id or item.get("task_id") == self._id:
                item.update(payload)
                found = True
                break
        if not found:
            self._store.append(payload)

    async def get(self):
        for item in self._store:
            if item.get("id") == self._id or item.get("task_id") == self._id:
                return FakeDocumentSnapshot(item)
        return FakeDocumentSnapshot(None)


class FakeDocumentSnapshot:
    def __init__(self, data):
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self):
        return self._data or {}


class FakeFirestoreQueue:
    def __init__(self):
        self._store: Dict[str, dict] = {}

    def enqueue(self, task_id: str, payload: dict, priority: float = 1.0):
        self._store[task_id] = {"task_id": task_id, "payload": payload, "priority": priority}
        return {"enqueued": True, "task_id": task_id}

    def dequeue(self):
        for item in sorted(self._store.values(), key=lambda x: x["priority"], reverse=True):
            return item
        return None

    def mark_done(self, task_id: str):
        self._store.pop(task_id, None)
        return {"done": True, "task_id": task_id}


class FakeTopic:
    def __init__(self, messages=None):
        self._messages = messages if messages is not None else []

    def publish(self, message):
        self._messages.append(message)

    async def publish_async(self, message, **kwargs):
        self._messages.append(message)

    @property
    def name(self) -> str:
        return "projects/fake-project/topics/fake-topic"


class FakeSubscriber:
    def __init__(self, messages=None):
        self._messages = messages if messages is not None else []

    def subscribe(self, callback):
        self._callback = callback

    def pull(self, max_messages: int = 1):
        messages = []
        for message in self._messages[:max_messages]:
            msg_obj = type("FakeMessage", (), {"data": message, "ack_id": id(message)})()
            callback = getattr(self, "_callback", None)
            if callback:
                callback(msg_obj)
            messages.append(msg_obj)
        self._messages = self._messages[max_messages:]
        return messages


class FakePubSubClient:
    def __init__(self, project=None):
        self._messages = []
        self._topic = FakeTopic(self._messages)
        self._subscription = FakeSubscriber(self._messages)

    def topic(self, name: str):
        return self._topic

    def subscription(self, name: str):
        return self._subscription

    async def close(self):
        return None


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


def test_gcp_firebase_auth_token(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/fake-sa.json")
    if HAS_FIREBASE_DEPS:
        monkeypatch.setattr(firebase_admin_auth, "verify_id_token", lambda token: {"uid": "u1", "email": "u@example.com"})
        decoded = firebase_admin_auth.verify_id_token("fake-jwt")
        assert decoded["uid"] == "u1"


def test_gcp_firestore_integration_queue():
    queue = FakeFirestoreQueue()

    enqueue = queue.enqueue("ocr-1", {"text": "verify"}, priority=95)
    assert enqueue["enqueued"] is True
    assert enqueue["task_id"] == "ocr-1"

    item = queue.dequeue()
    assert item["task_id"] == "ocr-1"
    assert item["payload"]["text"] == "verify"

    done = queue.mark_done("ocr-1")
    assert done["done"] is True
    assert "ocr-1" not in queue._store


def test_gcp_pubsub_publish_pull():
    messages = []
    topic = FakeTopic(messages)
    subscription = FakeSubscriber(messages)

    result = topic.publish({"task_id": "t1", "type": "ocr"})
    assert result is None

    messages = subscription.pull(max_messages=1)
    assert len(messages) == 1
    assert messages[0].data == {"task_id": "t1", "type": "ocr"}


@pytest.mark.skipif(not HAS_FIREBASE_DEPS, reason="firebase deps missing")
def test_gcp_cloud_functions_ocr_trigger(monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda timeout: FakeClient(timeout))
    client = GCPCloudFunctionClient(
        project_id="supremeai-gcp",
        region="us-central1",
        function_name="processOCR",
    )

    result = client.trigger_ocr(
        ["https://example.com/a.png", "https://example.com/b.png"],
        project_id="proj-1",
        user_id="user-42",
        languages=["en", "bn"],
    )

    assert result["success"] is True
    assert result["provider"] == "gcp_cloud_functions"
    assert result["function_url"].endswith("/processOCR")
    assert result["data"] == {"ok": True}
