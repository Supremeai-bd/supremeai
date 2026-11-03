"""
Tests for core/gcp_firestore.py
Focus: CRUD queue operations and document mapping.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.storage.gcp_firestore import GCPFirestoreVerificationQueue

# ── Helpers ───────────────────────────────────────────────────────────────────


class FakeFirestoreClient:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return FakeCollection(self.collections.setdefault(name, {}))


class FakeCollection:
    def __init__(self, data):
        self.data = data

    def document(self, doc_id):
        return FakeDocument(self.data.setdefault(doc_id, {}))

    def add(self, document):
        import uuid

        doc_id = str(uuid.uuid4())
        self.data[doc_id] = document
        doc_ref = MagicMock()
        doc_ref.id = doc_id
        return None, doc_ref

    def where(self, field, op, value):
        return FakeQuery(self.data, [(field, op, value)])


class FakeQuery:
    def __init__(self, data, filters):
        self.data = data
        self.filters = filters

    def where(self, field, op, value):
        self.filters.append((field, op, value))
        return self

    def order_by(self, field, direction=None):
        return self

    def limit(self, limit):
        return self

    def stream(self):
        import copy

        results = []
        for doc_id, doc in self.data.items():
            if not doc:
                continue
            match = True
            for f_field, f_op, f_val in self.filters:
                if f_op == "==" and doc.get(f_field) != f_val:
                    match = False
                    break
            if match:
                row = MagicMock()
                row.id = doc_id
                row.to_dict.return_value = copy.deepcopy(doc)

                # Mock reference.update for mark_verified
                def make_updater(d_id):
                    def updater(val, **kwargs):
                        self.data[d_id].update(val)

                    return updater

                row.reference.update = make_updater(doc_id)

                results.append(row)
        return results


class FakeDocument:
    def __init__(self, data):
        self.data = data

    def get(self):
        doc = MagicMock()
        doc.exists = bool(self.data)
        doc.to_dict.return_value = self.data.copy()
        return doc

    def set(self, value, merge=False):
        self.data.update(value)

    def delete(self):
        self.data.clear()


# ── GCPFirestoreVerificationQueue ─────────────────────────────────────────────


def test_enqueue_adds_document():
    queue = GCPFirestoreVerificationQueue(project_id="test-project")
    mock_client = FakeFirestoreClient()
    with patch("services.storage.gcp_firestore.get_firestore_client", return_value=mock_client):
        queue.client = mock_client
        queue.enqueue("task_1", {"url": "http://example.com"}, priority=1, metadata={})

    # Verify task persisted
    tasks = queue.get_pending(limit=10)
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == "task_1"


def test_peek_does_not_remove():
    queue = GCPFirestoreVerificationQueue(project_id="test-project")
    mock_client = FakeFirestoreClient()
    with patch("services.storage.gcp_firestore.get_firestore_client", return_value=mock_client):
        queue.client = mock_client
        queue.enqueue("task_1", {}, priority=1, metadata={})
        peeked = queue.peek(limit=1)
        again = queue.peek(limit=1)

    assert len(peeked) == 1
    assert len(again) == 1


def test_mark_verified_updates_status():
    queue = GCPFirestoreVerificationQueue(project_id="test-project")
    mock_client = FakeFirestoreClient()
    with patch("services.storage.gcp_firestore.get_firestore_client", return_value=mock_client):
        queue.client = mock_client
        queue.enqueue("task_1", {}, priority=1, metadata={})
        ok = queue.mark_verified("task_1")
        assert ok["success"] is True


def test_delete_removes_task():
    queue = GCPFirestoreVerificationQueue(project_id="test-project")
    mock_client = FakeFirestoreClient()
    with patch("services.storage.gcp_firestore.get_firestore_client", return_value=mock_client):
        queue.client = mock_client
        res = queue.enqueue("task_1", {}, priority=1, metadata={})
        queue.delete(res["queue_id"])
        tasks = queue.get_pending(limit=10)
        assert len(tasks) == 0


def test_stats_returns_counts():
    queue = GCPFirestoreVerificationQueue(project_id="test-project")
    mock_client = FakeFirestoreClient()
    with patch("services.storage.gcp_firestore.get_firestore_client", return_value=mock_client):
        queue.client = mock_client
        queue.enqueue("t1", {}, priority=1, metadata={})
        queue.enqueue("t2", {}, priority=1, metadata={})
        stats = queue.stats()
    assert "pending" in stats or "total" in stats


def test_provider_name():
    queue = GCPFirestoreVerificationQueue(project_id="test-project")
    mock_client = FakeFirestoreClient()
    with patch("services.storage.gcp_firestore.get_firestore_client", return_value=mock_client):
        queue.client = mock_client
        assert "firestore" in queue.provider.lower()
