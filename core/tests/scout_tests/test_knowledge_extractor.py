import asyncio
from unittest.mock import MagicMock, patch

import scout.knowledge_extractor as ke_module


class TestKnowledgeExtractor:
    def test_init_no_st(self):
        with patch.object(ke_module, "HAS_ST", False):
            extractor = ke_module.KnowledgeExtractor()
            assert extractor is not None

    def test_extract_no_st(self):
        with patch.object(ke_module, "HAS_ST", False):
            extractor = ke_module.KnowledgeExtractor()
            result = asyncio.run(extractor.extract("test content"))
            assert result == []

    def test_extract_with_st(self):
        with patch.object(ke_module, "HAS_ST", True):
            mock_model = MagicMock()
            mock_model.return_value.encode.return_value.tolist.return_value = [0.1, 0.2]
            with patch.object(ke_module, "SentenceTransformer", mock_model, create=True):
                extractor = ke_module.KnowledgeExtractor()
                result = asyncio.run(extractor.extract("test content"))
                assert len(result) == 1
                assert "text" in result[0]
                assert "embedding" in result[0]
