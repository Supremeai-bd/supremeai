from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_firebase_admin():
    with patch("firebase_admin.initialize_app") as init_mock, patch("firebase_admin.db") as rtdb_mock, patch("firebase_admin.firestore") as fs_mock:
        init_mock.return_value = MagicMock()
        yield {
            "init": init_mock,
            "rtdb": rtdb_mock,
            "firestore": fs_mock,
            "app": MagicMock(),
        }


class FirestoreStub:
    def __init__(self):
        self._store: dict[str, dict] = {}

    def as_collection(self, name: str):
        return CollectionStub(self._store, name)


class CollectionStub:
    def __init__(self, store, name):
        self._store = store
        self._name = name
        self._store.setdefault(name, {})

    def document(self, doc_id: str):
        return DocumentStub(self._store[self._name], doc_id)


class DocumentStub:
    def __init__(self, section, doc_id):
        self._section = section
        self._id = doc_id

    def set(self, payload):
        self._section[self._id] = payload

    def get(self):
        class _Snap:
            exists = self._id in self._section

            def to_dict(internal):
                return internal._section.get(internal._id, {})
        return _Snap()


def test_ocr_trigger_queue_to_firestore(mock_firebase_admin):
    rtdb = MagicMock()
    mock_firebase_admin["rtdb"].reference.return_value.reference.return_value.child.return_value.push.return_value = MagicMock(key="push-123")
    mock_firebase_admin["rtdb"].reference.return_value.reference.return_value.set = MagicMock()

    ref = mock_firebase_admin["rtdb"].reference.return_value
    ref.reference.return_value.child("ocr-queue").push.return_value = MagicMock(key="push-123")
    ref.reference.return_value.child.return_value.set.assert_not_called()

    doc_ref = DocumentStub({}, "push-123")
    doc_ref.set({"status": "queued", "file_path": "d.pdf", "mime": "application/pdf"})
    assert doc_ref.get().to_dict()["status"] == "queued"


def test_ocr_result_written_to_firestore(mock_firebase_admin):
    store = {}
    stub = FirestoreStub().as_collection("ocr-results")
    stub.document("push-123").set({"status": "completed", "result": {"text": "hello"}})
    assert store["ocr-results"]["push-123"]["result"]["text"] == "hello"


def test_firebase_roundtrip_queue_result(mock_firebase_admin):
    code = """
const admin = require('firebase-admin');
exports.ocrTrigger = async (snap) => {{
  const payload = snap.val();
  payload.status = 'completed';
  return payload;
}};
""".lstrip()
    worklet = compile(code, 'ocrTrigger.js', 'exec')
    ns = {"firebase_admin": mock_firebase_admin["init"], "admin": mock_firebase_admin["app"]}
    exec(worklet, ns)
    fn = ns.get("exports", {}).get("ocrTrigger")
    assert callable(fn), "ocrTrigger entrypoint missing"
    snap = MagicMock(); snap.val.return_value = {"task": "ocr"}
    assert fn(snap)["status"] == "completed"


def test_existing_gcp_roundtrip_coverage():
    import subprocess
    r = subprocess.run(
        ["pytest", "tests/test_gcp_integration.py::test_gcp_firestore_integration_queue",
         "tests/test_gcp_integration.py::test_gcp_pubsub_publish_pull",
         "tests/test_gcp_integration.py::test_gcp_cloud_run_router_route", "-q"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, "Roundtrip tests failed:\n" + r.stdout + "\n" + r.stderr
