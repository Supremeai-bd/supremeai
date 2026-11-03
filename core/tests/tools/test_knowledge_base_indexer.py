from unittest.mock import MagicMock, patch

import pytest

from tools.knowledge.knowledge_base_indexer import KnowledgeBaseIndexer

SAMPLE_PYTHON_CODE = '''
"""Module docstring."""

def top_level_function():
    """A top-level function."""

class SampleClass:
    """A sample class."""

    def method_one(self):
        """Method one docstring."""
        pass

    def method_two(self):
        pass
'''


class TestKnowledgeBaseIndexer:
    """Tests for tools/knowledge_base_indexer.py"""

    @pytest.fixture
    def indexer(self, tmp_path):
        mock_store = MagicMock()
        indexer = KnowledgeBaseIndexer(vector_store=mock_store)
        indexer._indexed_hashes = {}
        return indexer

    def test_init(self, indexer):
        assert indexer.vector_store is not None
        assert "seed_data" in indexer.seed_dir

    def test_extract_documents_from_file(self, indexer, tmp_path):
        py_file = tmp_path / "sample.py"
        py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")
        docs = indexer._extract_documents_from_file(str(py_file))
        assert len(docs) >= 3

    def test_extract_documents_syntax_error(self, indexer, tmp_path):
        py_file = tmp_path / "bad.py"
        py_file.write_text("def invalid(:", encoding="utf-8")
        docs = indexer._extract_documents_from_file(str(py_file))
        assert len(docs) == 1

    def test_extract_documents_file_not_found(self, indexer):
        docs = indexer._extract_documents_from_file("/nonexistent/path/file.py")
        assert docs == []

    def test_extract_documents_module_hash(self, indexer, tmp_path):
        py_file = tmp_path / "sample.py"
        py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")
        indexer._extract_documents_from_file(str(py_file))
        assert str(py_file) in indexer._indexed_hashes
        assert len(indexer._indexed_hashes[str(py_file)]) == 32

    def test_extract_documents_no_docstring_method(self, indexer, tmp_path):
        code = """
class NoDoc:
    def method_without_doc(self):
        pass
"""
        py_file = tmp_path / "nodoc.py"
        py_file.write_text(code, encoding="utf-8")
        docs = indexer._extract_documents_from_file(str(py_file))
        doc_ids = [d["id"] for d in docs]
        assert "nodoc.py::NoDoc" in doc_ids

    def test_extract_documents_function_def(self, indexer, tmp_path):
        code = '''
"""Module docstring."""

def standalone_function():
    """Standalone function docstring."""
    pass
'''
        py_file = tmp_path / "standalone.py"
        py_file.write_text(code, encoding="utf-8")
        docs = indexer._extract_documents_from_file(str(py_file))
        doc_ids = [d["id"] for d in docs]
        assert "standalone.py::standalone_function" in doc_ids

    def test_index_seed_data(self, indexer, tmp_path):
        py_file = tmp_path / "sample.py"
        py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")
        indexer.seed_dir = str(tmp_path)

        with patch.object(indexer.vector_store, "add_documents") as mock_add:
            result = indexer.index_seed_data(str(tmp_path))
        assert result["indexed"] > 0
        mock_add.assert_called_once()

    def test_index_seed_data_no_dir(self, indexer):
        result = indexer.index_seed_data("/nonexistent/dir")
        assert result["indexed"] is False
        assert "not found" in result["reason"]

    def test_index_seed_data_with_errors(self, indexer, tmp_path):
        py_file = tmp_path / "sample.py"
        py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")
        indexer.seed_dir = str(tmp_path)

        with patch.object(indexer.vector_store, "add_documents", side_effect=Exception("DB error")):
            result = indexer.index_seed_data(str(tmp_path))
        assert len(result["errors"]) > 0

    def test_index_scraped_data(self, indexer):
        data = [
            {"text": "Doc 1", "metadata": {"source": "web"}},
            {"text": "Doc 2", "metadata": {"category": "external"}},
            {"text": "", "metadata": {}},
        ]
        with patch.object(indexer.vector_store, "add_documents") as mock_add:
            result = indexer.index_scraped_data(data)
        assert result["indexed"] == 2
        mock_add.assert_called_once()

    def test_index_scraped_data_empty(self, indexer):
        result = indexer.index_scraped_data([])
        assert result["indexed"] == 0
        assert "No data" in result["reason"]

    def test_index_scraped_data_with_id(self, indexer):
        data = [{"id": "custom-1", "text": "Doc 1", "metadata": {}}]
        with patch.object(indexer.vector_store, "add_documents") as mock_add:
            result = indexer.index_scraped_data(data)
        assert result["indexed"] == 1
        added = mock_add.call_args[0][0]
        assert added[0]["id"] == "scraped::custom-1"

    def test_index_scraped_data_generates_md5(self, indexer):
        data = [{"text": "hash me", "metadata": {}}]
        with patch.object(indexer.vector_store, "add_documents") as mock_add:
            indexer.index_scraped_data(data)
        added = mock_add.call_args[0][0]
        assert added[0]["id"].startswith("scraped::")

    def test_search_knowledge(self, indexer):
        indexer.vector_store.query.return_value = [
            ("doc-1", 0.9, {"text": "Result 1", "metadata": {}}),
            ("doc-2", 0.7, {"text": "Result 2", "metadata": {"source": "web"}}),
        ]
        results = indexer.search_knowledge("test query", n_results=2)
        assert len(results) == 2
        assert results[0]["doc_id"] == "doc-1"
        assert results[1]["score"] == 0.7
        assert results[1]["metadata"]["source"] == "web"

    def test_search_knowledge_exception(self, indexer):
        indexer.vector_store.query.side_effect = Exception("search error")
        results = indexer.search_knowledge("test query")
        assert results == []

    def test_record_search_feedback(self, indexer):
        indexer.vector_store.query.return_value = [
            ("doc-1", 0.9, {"text": "Result 1", "metadata": {}}),
        ]
        feedback = indexer.record_search_feedback("session-1", "test query", top_k=1)
        assert feedback["session_id"] == "session-1"
        assert feedback["query"] == "test query"
        assert feedback["retrieved_count"] == 1
        assert feedback["top_doc_ids"] == ["doc-1"]
        assert "Result 1" in feedback["retrieved_chunks"]

    def test_record_search_feedback_with_rating(self, indexer):
        indexer.vector_store.query.return_value = []
        feedback = indexer.record_search_feedback("session-1", "query", top_k=1, rating=4.0)
        assert feedback["user_rating"] == 4.0

    def test_record_thumbs_helpful(self, indexer):
        indexer.vector_store.get_document.return_value = {
            "id": "doc-1",
            "text": "text",
            "metadata": {"helpful_votes": 2, "negative_votes": 1},
        }
        with patch.object(indexer.vector_store, "add_document") as mock_add:
            result = indexer.record_thumbs("session-1", "query", "doc-1", helpful=True)
        assert result["helpful"] is True
        assert result["rating"] == 1.0
        assert result["recorded"] is True
        mock_add.assert_called_once()

    def test_record_thumbs_not_helpful(self, indexer):
        indexer.vector_store.get_document.return_value = {
            "id": "doc-1",
            "text": "text",
            "metadata": {"helpful_votes": 2},
        }
        with patch.object(indexer.vector_store, "add_document"):
            result = indexer.record_thumbs("session-1", "query", "doc-1", helpful=False)
        assert result["helpful"] is False
        assert result["rating"] == 0.0

    def test_record_thumbs_no_metadata(self, indexer):
        indexer.vector_store.get_document.return_value = {
            "id": "doc-1",
            "text": "text",
            "metadata": {},
        }
        with patch.object(indexer.vector_store, "add_document"):
            result = indexer.record_thumbs("session-1", "query", "doc-1", helpful=True)
        assert result["recorded"] is True

    def test_record_thumbs_no_doc(self, indexer):
        indexer.vector_store.get_document.return_value = None
        result = indexer.record_thumbs("session-1", "query", "doc-1", helpful=True)
        assert result["recorded"] is True

    def test_prune_low_quality_live_collection(self, indexer):
        indexer.vector_store._collection = MagicMock()
        result = indexer.prune_low_quality()
        assert result["pruned"] == 0
        assert "not implemented" in result["note"]

    def test_prune_low_quality_prunes(self, indexer):
        indexer.vector_store._collection = None
        indexer.vector_store._fallback_docs = {
            "doc-1": {"metadata": {"helpful_votes": 0, "negative_votes": 5}},
            "doc-2": {"metadata": {"helpful_votes": 5, "negative_votes": 0}},
        }
        with patch.object(indexer.vector_store, "delete") as mock_delete:
            result = indexer.prune_low_quality(min_helpful_ratio=0.5, min_votes=3)
        assert result["pruned"] == 1
        mock_delete.assert_called_once_with("doc-1")

    def test_prune_low_quality_no_prune(self, indexer):
        indexer.vector_store._collection = None
        indexer.vector_store._fallback_docs = {
            "doc-1": {"metadata": {"helpful_votes": 5, "negative_votes": 1}},
        }
        result = indexer.prune_low_quality(min_helpful_ratio=0.5, min_votes=3)
        assert result["pruned"] == 0

    def test_rebuild_index_live_collection(self, indexer):
        indexer.vector_store._collection = MagicMock()
        indexer.vector_store._client = MagicMock()
        indexer.vector_store.collection_name = "test"
        indexer.vector_store._init_chroma = MagicMock()

        with patch.object(indexer, "index_seed_data", return_value={"indexed": 5}) as mock_index:
            result = indexer.rebuild_index()
        assert "indexed" in result
        mock_index.assert_called_once()

    def test_rebuild_index_fallback(self, indexer):
        indexer.vector_store._collection = None
        indexer.vector_store._fallback_docs = MagicMock()
        indexer.vector_store._save_fallback = MagicMock()

        with patch.object(indexer, "index_seed_data", return_value={"indexed": 3}) as mock_index:
            result = indexer.rebuild_index()
        assert "indexed" in result
        mock_index.assert_called_once()
