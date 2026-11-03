"""
Tests for services/knowledge_qa.py — KnowledgeQAService
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from services.knowledge_qa import Citation, KnowledgeQAService


class TestCitation:
    def test_as_dict_with_all_fields(self):
        citation = Citation(
            document_id="doc-123",
            source="https://example.com/doc",
            chunk_index=0,
            score=0.95,
        )
        result = citation.as_dict()
        assert result["document_id"] == "doc-123"
        assert result["source"] == "https://example.com/doc"
        assert result["chunk_index"] == 0
        assert result["score"] == 0.95

    def test_as_dict_with_none_chunk_index(self):
        citation = Citation(
            document_id="doc-456",
            source="https://example.com/other",
            chunk_index=None,
            score=0.5,
        )
        result = citation.as_dict()
        assert result["chunk_index"] is None

    def test_score_rounding(self):
        citation = Citation(
            document_id="doc-789",
            source="source",
            chunk_index=1,
            score=0.95555,
        )
        result = citation.as_dict()
        assert result["score"] == 0.9556


class TestKnowledgeQAService:
    @pytest.fixture
    def service(self):
        return KnowledgeQAService(vector_store=MagicMock(), gateway=MagicMock())

    def test_init(self, service):
        assert service.vector_store is not None
        assert service.gateway is not None

    def test_init_with_defaults(self):
        service = KnowledgeQAService()
        assert hasattr(service, "gateway")

    def test_min_retrieval_score_constant(self):
        from services.knowledge_qa import MIN_RETRIEVAL_SCORE

        assert MIN_RETRIEVAL_SCORE == 0.05

    def test_max_context_chars_constant(self):
        from services.knowledge_qa import MAX_CONTEXT_CHARS

        assert MAX_CONTEXT_CHARS == 12_000


# ---------------------------------------------------------------------------
# M23 P-A regression — governance `__init__`-এ পুনরুত্থান (প্রতি-কলে 500 অবসান)
# ---------------------------------------------------------------------------


class FakeChroma:
    """নির্ধারিত ফল ফেরানো ফেক vector store — কোনো বাহ্যিক নির্ভরতা নেই।"""

    def __init__(self, results):
        self._results = results

    def query(self, query, n_results=3):
        return self._results


class FakeGateway:
    def __init__(self, text=" grounded answer "):
        self._text = text
        self.calls: list[dict] = []

    async def acompletion(self, **kwargs):
        self.calls.append(kwargs)
        return {"text": self._text}


class FakeAudit:
    def __init__(self):
        self.events: list[tuple] = []

    def log_decision(self, *args):
        self.events.append(args)


class TestGovernanceResurrectionM23PA:
    """বাংলা: প্রকৃত manifest দিয়ে প্রকৃত সার্ভিস — mock দিয়ে এই বাগ কখনো ধরা পড়েনি।"""

    def _service(self, results=None):
        return KnowledgeQAService(
            vector_store=FakeChroma(results or []),
            gateway=FakeGateway(),
            audit_logger=FakeAudit(),
        )

    def test_governance_initialized_from_real_manifest(self):
        # আগে: self.governance ছিল না → _authorize-এ AttributeError → /ask 500।
        service = self._service()
        assert service.governance["allowed_roles"] == ["standard_user", "manager", "admin"]

    def test_role_authorization_is_case_insensitive(self):
        # আগে: manifest 'Admin' বনাম টোকেন-রোল 'admin' case-মিল না → ভুল 403।
        service = self._service()
        tenant_id, role = service._authorize({"tenant_id": "t1", "sub": "u1", "role": "Admin"})
        assert tenant_id == "t1" and role == "admin"

    async def test_answer_403_for_disallowed_role_not_500(self):
        # বাংলা: অননুমোদিত রোল → সৎ 403 — 500/AttributeError নয়।
        from fastapi import HTTPException

        service = self._service()
        with pytest.raises(HTTPException) as exc_info:
            await service.answer("q", {"tenant_id": "t1", "sub": "u1", "role": "guest"}, 3)
        assert exc_info.value.status_code == 403

    async def test_answer_empty_tenant_401(self):
        from fastapi import HTTPException

        service = self._service()
        with pytest.raises(HTTPException) as exc_info:
            await service.answer("q", {"tenant_id": "", "sub": "", "role": "admin"}, 3)
        assert exc_info.value.status_code == 401

    async def test_answer_e2e_grounded_with_fake_chroma(self):
        # বাংলা: allowed document (tenant+namespace+role মিল) → grounded True + citation।
        results = [
            (
                "doc-1",
                0.9,
                {
                    "text": "SupremeAI zero-cost doctrine",
                    "metadata": {
                        "tenant_id": "t1",
                        "namespace": "public_sops",
                        "source": "handbook",
                        "chunk_index": 0,
                    },
                },
            )
        ]
        service = self._service(results)
        payload = await service.answer(
            "zero cost?", {"tenant_id": "t1", "sub": "u1", "role": "standard_user"}, 3
        )
        assert payload["grounded"] is True
        assert payload["citations"][0]["document_id"] == "doc-1"
        assert payload["citations"][0]["source"] == "handbook"

    async def test_answer_no_matches_returns_honest_empty(self):
        # বাংলা: কোনো অনুমোদিত chunk না পেলে ভুয়া উত্তর নয় — grounded False।
        results = [
            (
                "doc-x",
                0.9,
                {"text": "secret", "metadata": {"tenant_id": "other-tenant", "namespace": "hr"}},
            )
        ]
        service = self._service(results)
        payload = await service.answer(
            "q", {"tenant_id": "t1", "sub": "u1", "role": "standard_user"}, 3
        )
        assert payload["grounded"] is False
        assert payload["citations"] == []

    async def test_answer_vector_store_failure_is_honest_503(self):
        # Wave 4.7 (issue #1282): vector-store/infrastructure ব্যর্থ হলে raw 500
        # নয় — সৎ 503 হবে (HTTPException হিসেবে), কখনোই unhandled traceback নয়।
        service = self._service([])
        service.vector_store.query = MagicMock(side_effect=RuntimeError("pgvector RPC unreachable"))
        with pytest.raises(HTTPException) as exc:
            await service.answer("q", {"tenant_id": "t1", "sub": "u1", "role": "standard_user"}, 3)
        assert exc.value.status_code == 503
        assert "temporarily unavailable" in exc.value.detail

    async def test_answer_authorization_errors_pass_through(self):
        # HTTPException (401/403) must NOT be swallowed by the 503 guard.
        service = self._service([])
        with pytest.raises(HTTPException) as exc:
            await service.answer("q", {"tenant_id": "", "sub": "", "role": "x"}, 3)
        assert exc.value.status_code == 401
