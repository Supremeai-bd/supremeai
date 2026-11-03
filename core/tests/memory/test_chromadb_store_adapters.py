"""ChromaDBStore adapter coverage — chromadb client paths + TF-IDF fallback integrity.

Strategy (g42c lesson): the optional ``chromadb`` package is absent in light CI, so the
module-level import fails and only the TF-IDF fallback was previously exercised. Here we:

1. Exercise the full fallback mode end-to-end (persistence, TF-IDF scoring, incremental
   hashing, delete/count/get) which is the production degradation path on Render free tier.
2. Attach a :class:`FakeCollection` directly to ``store._collection`` to cover every
   chroma-client branch (upsert/query/delete/count/get + each failure fallback) without
   a real vector database.
3. Load second copies of the module under controlled env (``LOW_MEMORY_MODE``) and with a
   fake ``chromadb`` entry injected into ``sys.modules`` to cover the import-time matrix,
   mirroring how the production container decides availability at import.

Wire-first: tests only — zero owner production code touched.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from memory.chromadb_store import ChromaDBStore

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = BACKEND_ROOT / "memory" / "chromadb_store.py"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakeCollection:
    """Canned-result chroma collection recording every call (no real I/O)."""

    def __init__(
        self,
        *,
        fail_upsert: bool = False,
        fail_query: bool = False,
        fail_delete: bool = False,
        fail_count: bool = False,
        fail_get: bool = False,
        query_result: dict[str, Any] | None = None,
        get_result: dict[str, Any] | None = None,
        count_value: int = 7,
    ) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._fail = {
            "upsert": fail_upsert,
            "query": fail_query,
            "delete": fail_delete,
            "count": fail_count,
            "get": fail_get,
        }
        self._query_result = query_result
        self._get_result = get_result
        self._count_value = count_value

    def _maybe_fail(self, op: str) -> None:
        self.calls.append((op, {}))
        if self._fail.get(op):
            raise RuntimeError(f"{op} exploded (simulated chroma outage)")

    def upsert(self, **kwargs: Any) -> None:
        self.calls.append(("upsert", kwargs))
        if self._fail["upsert"]:
            raise RuntimeError("upsert exploded (simulated chroma outage)")

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self._maybe_fail("query")
        return self._query_result or {"ids": [[]]}

    def delete(self, **kwargs: Any) -> None:
        self._maybe_fail("delete")

    def count(self) -> int:
        self._maybe_fail("count")
        return self._count_value

    def get(self, **kwargs: Any) -> dict[str, Any]:
        self._maybe_fail("get")
        return self._get_result or {}


class FakeChromaClient:
    def __init__(self, collection: FakeCollection | None = None, fail: bool = False) -> None:
        self.collection = collection or FakeCollection()
        self.fail = fail
        self.paths: list[str] = []

    def get_or_create_collection(self, **kwargs: Any) -> FakeCollection:
        self.collection_kwargs = kwargs
        if self.fail:
            raise RuntimeError("collection bootstrap exploded")
        return self.collection


class FakeChromaModule:
    """Stand-in for the ``chromadb`` package registered in sys.modules."""

    def __init__(self, client: FakeChromaClient | None = None, fail_client: bool = False) -> None:
        self.client = client or FakeChromaClient()
        self.fail_client = fail_client
        self.persistent_client_paths: list[str] = []

    def PersistentClient(self, path: str) -> FakeChromaClient:  # noqa: N802 (chroma API name)
        self.persistent_client_paths.append(path)
        if self.fail_client:
            raise RuntimeError("PersistentClient exploded (simulated chroma outage)")
        return self.client


@pytest.fixture()
def fallback_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ChromaDBStore:
    """Store guaranteed to run in TF-IDF fallback mode regardless of CI chroma."""
    monkeypatch.setattr("memory.chromadb_store._CHROMA_AVAILABLE", False)
    return ChromaDBStore(db_path=str(tmp_path / "chroma_fb"))


def _attach(store: ChromaDBStore, collection: FakeCollection) -> None:
    """Bypass _init_chroma and inject a fake chroma collection (supabase _attach pattern)."""
    store._collection = collection


def _load_second_copy(
    monkeypatch: pytest.MonkeyPatch,
    *,
    low_memory: bool = False,
    fake_chromadb: FakeChromaModule | None = None,
) -> Any:
    """Execute a fresh copy of chromadb_store.py under controlled import conditions."""
    if low_memory:
        monkeypatch.setenv("LOW_MEMORY_MODE", "true")
    else:
        monkeypatch.delenv("LOW_MEMORY_MODE", raising=False)
    if fake_chromadb is not None:
        monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)
    else:
        monkeypatch.setitem(sys.modules, "chromadb", MagicMock(spec=[]))

    name = f"chromadb_store_probe_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Group A — TF-IDF fallback end-to-end (the Render degradation path)
# ---------------------------------------------------------------------------
class TestFallbackMode:
    def test_add_and_persistence_roundtrip(self, fallback_store: ChromaDBStore, tmp_path: Path):
        fallback_store.add_document("d1", "alpha beta gamma", {"tenant": "t1"})
        fallback_store.add_documents(
            [{"id": "d2", "text": "delta epsilon", "metadata": None}, {"text": "zeta"}]
        )
        assert fallback_store.count() == 3
        # uuid4 id assigned when doc omits id
        assert any(len(k) == 36 and uuid.UUID(k) for k in fallback_store._fallback_docs)

        # on-disk artifact written and reloadable by a fresh store
        saved = json.loads((tmp_path / "chroma_fb" / "fallback_docs.json").read_text())
        assert set(saved) == set(fallback_store._fallback_docs)
        reloaded = ChromaDBStore(db_path=str(tmp_path / "chroma_fb"))
        assert "d1" in reloaded._fallback_docs
        assert reloaded.get_document("d1")["text"] == "alpha beta gamma"

    def test_unicode_roundtrip_ensure_ascii_false(self, fallback_store: ChromaDBStore):
        fallback_store.add_document("bn", "বাংলা মন্তব্য সংরক্ষণ", {"lang": "bn"})
        raw = json.dumps(fallback_store._fallback_docs, ensure_ascii=False)
        assert "বাংলা" in raw
        assert fallback_store.get_document("bn")["metadata"] == {"lang": "bn"}

    def test_query_tfidf_scoring_and_cap(self, fallback_store: ChromaDBStore):
        fallback_store.add_document("hit", "gpu vector database", {"i": 0})
        fallback_store.add_document("partial", "gpu crypto mining rig", {"i": 1})
        fallback_store.add_document("miss", "kubernetes ingress yaml", {"i": 2})
        results = fallback_store.query("gpu database", n_results=2)
        assert len(results) == 2
        assert results[0][0] == "hit"
        assert results[0][1] > results[1][1]  # sorted desc by cosine similarity
        assert results[0][2]["metadata"] == {"i": 0}

    def test_query_empty_corpus_returns_empty(self, fallback_store: ChromaDBStore):
        assert fallback_store.query("anything") == []

    def test_query_zero_denominator_guard(self, fallback_store: ChromaDBStore):
        fallback_store.add_document("d", "hello world", {})
        # punctuation-only query tokenizes to nothing → both vectors empty → 0.0 scores
        results = fallback_store.query("!!! ???", n_results=3)
        assert results and results[0][1] == 0.0

    def test_incremental_same_hash_skips(self, fallback_store: ChromaDBStore):
        text = "stable payload"
        assert fallback_store.add_document_incremental("doc", text) is True
        assert fallback_store.add_document_incremental("doc", text) is False
        assert fallback_store.count() == 1

    def test_incremental_new_hash_updates(self, fallback_store: ChromaDBStore):
        fallback_store.add_document_incremental("doc", "v1")
        assert fallback_store.add_document_incremental("doc", "v2") is True
        assert fallback_store.get_document("doc")["text"] == "v2"
        h = hashlib.sha256(b"v2").hexdigest()
        assert fallback_store._fallback_docs["doc"]["metadata"]["content_hash"] == h

    def test_delete_and_delete_missing(self, fallback_store: ChromaDBStore):
        fallback_store.add_document("gone", "bye", {})
        fallback_store.delete("gone")
        assert fallback_store.count() == 0
        fallback_store.delete("never-existed")  # no raise

    def test_get_document_missing_returns_none(self, fallback_store: ChromaDBStore):
        assert fallback_store.get_document("ghost") is None

    def test_load_fallback_corrupt_json_degrades(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("memory.chromadb_store._CHROMA_AVAILABLE", False)
        d = tmp_path / "corrupt"
        d.mkdir()
        (d / "fallback_docs.json").write_text("{not valid json!!")
        store = ChromaDBStore(db_path=str(d))
        assert store._fallback_docs == {}
        assert store.count() == 0

    def test_save_fallback_memory_guard(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("memory.chromadb_store._CHROMA_AVAILABLE", False)
        store = ChromaDBStore(db_path=":memory:")
        store.add_document("x", "text", {})
        assert not (tmp_path / ":memory:").exists()  # early-return guard honored

    def test_default_db_path_env_override(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("memory.chromadb_store._CHROMA_AVAILABLE", False)
        monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "from_env"))
        assert ChromaDBStore().db_path == str(tmp_path / "from_env")

    def test_default_db_path_derivation(self, monkeypatch):
        monkeypatch.setattr("memory.chromadb_store._CHROMA_AVAILABLE", False)
        monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)
        store = ChromaDBStore()
        assert store.db_path.endswith(str(Path("data") / "chromadb_store"))


# ---------------------------------------------------------------------------
# Group B — chroma-client branches via FakeCollection attach
# ---------------------------------------------------------------------------
class TestCollectionMode:
    def test_upsert_success_skips_fallback(self, fallback_store: ChromaDBStore):
        col = FakeCollection()
        _attach(fallback_store, col)
        fallback_store.add_documents([{"id": "a", "text": "t", "metadata": {"m": 1}}])
        op, kwargs = col.calls[0]
        assert op == "upsert"
        assert kwargs["ids"] == ["a"]
        assert kwargs["metadatas"] == [{"m": 1, "doc_id": "a"}]  # doc_id setdefault
        assert fallback_store._fallback_docs == {}

    def test_upsert_failure_falls_back_and_persists(self, fallback_store: ChromaDBStore):
        col = FakeCollection(fail_upsert=True)
        _attach(fallback_store, col)
        fallback_store.add_document("a", "payload", None)
        assert fallback_store._fallback_docs["a"]["text"] == "payload"
        assert fallback_store._fallback_docs["a"]["vector"] == {"payload": 1}
        # empty text + content-keyed doc both tolerated
        fallback_store.add_documents([{"id": "b", "content": "via-content-key"}])
        assert fallback_store._fallback_docs["b"]["text"] == "via-content-key"

    def test_incremental_same_hash_skips_upsert(self, fallback_store: ChromaDBStore):
        col = FakeCollection()
        _attach(fallback_store, col)
        text = "immutable corpus entry"
        h = hashlib.sha256(text.encode()).hexdigest()
        col._get_result = {"metadatas": [{"content_hash": h}]}
        assert fallback_store.add_document_incremental("doc", text) is False
        assert all(op != "upsert" for op, _ in col.calls)

    def test_incremental_diff_hash_upserts(self, fallback_store: ChromaDBStore):
        col = FakeCollection()
        _attach(fallback_store, col)
        col._get_result = {"metadatas": [{"content_hash": "stale"}]}
        assert fallback_store.add_document_incremental("doc", "fresh") is True
        assert any(op == "upsert" for op, _ in col.calls)

    def test_incremental_get_raises_proceeds(self, fallback_store: ChromaDBStore):
        col = FakeCollection(fail_get=True)
        _attach(fallback_store, col)
        assert fallback_store.add_document_incremental("doc", "text") is True

    def test_incremental_empty_get_proceeds(self, fallback_store: ChromaDBStore):
        col = FakeCollection(get_result={})
        _attach(fallback_store, col)
        assert fallback_store.add_document_incremental("doc", "text") is True

    def test_query_collection_parses_distances(self, fallback_store: ChromaDBStore):
        col = FakeCollection(
            query_result={
                "ids": [["d1", "d2"]],
                "distances": [[0.2, 0.5]],
                "metadatas": [[{"m": 1}, {"m": 2}]],
                "documents": [["t1", "t2"]],
            }
        )
        _attach(fallback_store, col)
        results = fallback_store.query("q", n_results=5)
        assert results[0] == ("d1", 0.8, {"text": "t1", "metadata": {"m": 1}})
        assert results[1][1] == pytest.approx(0.5)

    def test_query_collection_failure_falls_back_tfidf(self, fallback_store: ChromaDBStore):
        fallback_store.add_document("fb", "fallback corpus doc", {})
        col = FakeCollection(fail_query=True)
        _attach(fallback_store, col)
        results = fallback_store.query("fallback corpus", n_results=3)
        assert results[0][0] == "fb"

    def test_query_collection_empty_ids_falls_back(self, fallback_store: ChromaDBStore):
        fallback_store.add_document("fb", "fallback corpus doc", {})
        col = FakeCollection(query_result={"ids": [[]]})
        _attach(fallback_store, col)
        assert fallback_store.query("fallback corpus")[0][0] == "fb"

    def test_delete_success_and_failure(self, fallback_store: ChromaDBStore):
        fallback_store._fallback_docs["keep"] = {"text": "", "metadata": {}, "vector": {}}
        ok = FakeCollection()
        _attach(fallback_store, ok)
        fallback_store.delete("x")
        assert ("delete", {}) in ok.calls

        bad = FakeCollection(fail_delete=True)
        _attach(fallback_store, bad)
        fallback_store.delete("keep")
        assert "keep" not in fallback_store._fallback_docs

    def test_count_success_and_failure_sentinel(self, fallback_store: ChromaDBStore):
        _attach(fallback_store, FakeCollection(count_value=42))
        assert fallback_store.count() == 42
        _attach(fallback_store, FakeCollection(fail_count=True))
        assert fallback_store.count() == -1  # failure state distinct from empty

    def test_get_document_found_and_missing(self, fallback_store: ChromaDBStore):
        col = FakeCollection(get_result={"documents": ["body"], "metadatas": [{"k": "v"}]})
        _attach(fallback_store, col)
        assert fallback_store.get_document("d") == {
            "id": "d",
            "text": "body",
            "metadata": {"k": "v"},
        }
        # no documents key → falls through to fallback lookup
        _attach(fallback_store, FakeCollection(get_result={}))
        assert fallback_store.get_document("d") is None

    def test_get_document_raises_falls_back(self, fallback_store: ChromaDBStore):
        fallback_store._fallback_docs["local"] = {"text": "t", "metadata": {}, "vector": {}}
        _attach(fallback_store, FakeCollection(fail_get=True))
        assert fallback_store.get_document("local") == {"text": "t", "metadata": {}, "vector": {}}


# ---------------------------------------------------------------------------
# Group C — module import matrix (LOW_MEMORY_MODE + fake chromadb in sys.modules)
# ---------------------------------------------------------------------------
class TestImportMatrix:
    def test_low_memory_mode_forces_unavailable(self, monkeypatch: pytest.MonkeyPatch):
        mod = _load_second_copy(monkeypatch, low_memory=True)
        assert mod._CHROMA_AVAILABLE is False
        store = mod.ChromaDBStore(db_path=":memory:")
        assert store._collection is None

    def test_fake_chromadb_enables_persistent_client(self, tmp_path: Path, monkeypatch):
        fake_mod = FakeChromaModule()
        mod = _load_second_copy(monkeypatch, fake_chromadb=fake_mod)
        assert mod._CHROMA_AVAILABLE is True

        store = mod.ChromaDBStore(db_path=str(tmp_path / "chroma"), collection_name="c1")
        assert fake_mod.persistent_client_paths == [str(tmp_path / "chroma")]
        assert fake_mod.client.collection_kwargs == {
            "name": "c1",
            "metadata": {"hnsw:space": "cosine"},
        }
        assert store._collection is fake_mod.client.collection

    def test_persistent_client_failure_degrades_to_fallback(self, tmp_path: Path, monkeypatch):
        fake_mod = FakeChromaModule(fail_client=True)
        mod = _load_second_copy(monkeypatch, fake_chromadb=fake_mod)
        store = mod.ChromaDBStore(db_path=str(tmp_path / "boom"))
        assert store._client is None
        assert store._collection is None
        store.add_document("d", "degraded", {})  # writes via fallback + saves
        assert (tmp_path / "boom" / "fallback_docs.json").exists()
