"""M2-B — ContextEngine tests: tenant filter, dedup, provenance, render."""

from __future__ import annotations

import pytest

from context.budget import ContextBudget
from context.engine import ContextEngine, RawCandidate
from context.items import ItemKind, SummaryLevel
from context.scopes import Scope, ScopeChainError, ScopeLevel
from context.sources import memory_source


def _mem_source(cands: list[RawCandidate]):
    async def source(scope: Scope, query: str) -> list[RawCandidate]:
        return cands

    return source


def _scope(level=ScopeLevel.CHAT, user="u1", chat="c1") -> Scope:
    return Scope(level=level, user_id=user, chat_id=chat)


class TestMemorySource:
    @pytest.mark.asyncio
    async def test_memory_source_maps_existing_recall_contract(self, monkeypatch):
        async def fake_recall_memories(*, task_description, user_id, limit):
            assert task_description == "deploy task"
            assert user_id == "u1"
            assert limit == 20
            return [{"id": "m1", "user_id": "u1", "summary": "deployment memory", "score": 0.8}]

        monkeypatch.setattr("context.sources.recall_memories", fake_recall_memories)
        candidates = await memory_source(_scope(level=ScopeLevel.USER, chat=None), "deploy task")
        assert len(candidates) == 1
        assert candidates[0].source_ref == "ai_memory:m1"
        assert candidates[0].kind is ItemKind.memory
        assert candidates[0].user_id == "u1"


class TestTenantFilter:
    @pytest.mark.asyncio
    async def test_foreign_user_candidate_dropped(self):
        engine = ContextEngine(
            memory_source=_mem_source(
                [
                    RawCandidate(
                        content="mine",
                        source_type="ai_memory",
                        source_ref="ai_memory:1",
                        user_id="u1",
                        kind=ItemKind.memory,
                    ),
                    RawCandidate(
                        content="theirs",
                        source_type="ai_memory",
                        source_ref="ai_memory:2",
                        user_id="attacker",
                        kind=ItemKind.memory,
                    ),
                ]
            )
        )
        bundle = await engine.assemble(scope=_scope(), query="q")
        assert [i.item_id for i in bundle.items] == ["ai_memory:1"]
        assert bundle.dropped_candidates[0]["reason"] == "tenant_mismatch"
        assert bundle.dropped_candidates[0]["claimed_user"] == "attacker"

    @pytest.mark.asyncio
    async def test_none_user_dropped_deny_by_default(self):
        engine = ContextEngine(
            memory_source=_mem_source(
                [RawCandidate(content="anon", source_type="x", source_ref="x:1", user_id=None)]
            )
        )
        bundle = await engine.assemble(scope=_scope(), query="q")
        assert bundle.items == ()

    @pytest.mark.asyncio
    async def test_public_marked_candidate_passes(self):
        engine = ContextEngine(
            memory_source=_mem_source(
                [
                    RawCandidate(
                        content="docs",
                        source_type="kb",
                        source_ref="kb:1",
                        user_id=None,
                        public=True,
                    )
                ]
            )
        )
        bundle = await engine.assemble(scope=_scope(), query="q")
        assert len(bundle.items) == 1
        assert bundle.items[0].provenance.user_id == "public"


class TestScoringAndDedup:
    @pytest.mark.asyncio
    async def test_score_composition_recorded(self):
        engine = ContextEngine(
            memory_source=_mem_source(
                [
                    RawCandidate(
                        content="c",
                        source_type="ai_memory",
                        source_ref="m:1",
                        user_id="u1",
                        base_score=1.0,
                        kind=ItemKind.memory,
                        item_scope="chat",
                    )
                ]
            )
        )
        bundle = await engine.assemble(scope=_scope(), query="q")
        item = bundle.items[0]
        assert item.score == pytest.approx(0.7 * 1.0 + 0.3 * 1.0)
        assert item.provenance.score_components == {"base": 1.0, "scope_match": 1.0}

    @pytest.mark.asyncio
    async def test_cross_source_hash_dedup_keeps_higher_score(self):
        engine = ContextEngine(
            memory_source=_mem_source(
                [
                    RawCandidate(
                        content="dup",
                        source_type="file",
                        source_ref="file:1",
                        user_id="u1",
                        base_score=0.5,
                        content_hash="h1",
                    )
                ]
            ),
            rag_source=_mem_source(
                [
                    RawCandidate(
                        content="dup",
                        source_type="rag",
                        source_ref="rag:1",
                        user_id="u1",
                        base_score=0.9,
                        content_hash="h1",
                        kind=ItemKind.rag_chunk,
                    )
                ]
            ),
        )
        bundle = await engine.assemble(scope=_scope(), query="q")
        assert [i.item_id for i in bundle.items] == ["rag:1"]
        assert any(d["reason"] == "duplicate_hash" for d in bundle.dropped_candidates)


class TestScopeValidationAndRendering:
    @pytest.mark.asyncio
    async def test_malformed_scope_raises(self):
        engine = ContextEngine()
        with pytest.raises(ScopeChainError):
            await engine.assemble(scope=Scope(level=ScopeLevel.RUN), query="q")

    @pytest.mark.asyncio
    async def test_no_sources_empty_bundle(self):
        engine = ContextEngine()
        bundle = await engine.assemble(scope=_scope(), query="q")
        assert bundle.items == ()
        assert bundle.total_tokens == 0
        assert bundle.rendered == "[context scope=chat items=0]"

    @pytest.mark.asyncio
    async def test_render_groups_by_kind_with_provenance(self):
        engine = ContextEngine(
            memory_source=_mem_source(
                [
                    RawCandidate(
                        content="memory text",
                        source_type="ai_memory",
                        source_ref="ai_memory:9",
                        user_id="u1",
                        kind=ItemKind.memory,
                        layer="l0",
                    )
                ]
            ),
            file_source=_mem_source(
                [
                    RawCandidate(
                        content="file text",
                        source_type="chat_attachment",
                        source_ref="chat_attachment:9",
                        user_id="u1",
                        kind=ItemKind.file,
                        layer="l1",
                    )
                ]
            ),
        )
        bundle = await engine.assemble(scope=_scope(), query="q")
        lines = bundle.rendered.splitlines()
        assert lines[0] == "[context scope=chat items=2]"
        assert "## memory" in lines
        assert "## file" in lines
        assert "- (l0; src=ai_memory:9) memory text" in lines
        assert "- (l1; src=chat_attachment:9) file text" in lines

    @pytest.mark.asyncio
    async def test_provenance_on_every_admitted_item(self):
        engine = ContextEngine(
            memory_source=_mem_source(
                [
                    RawCandidate(
                        content=f"t{n}",
                        source_type="ai_memory",
                        source_ref=f"ai_memory:{n}",
                        user_id="u1",
                        content_hash=f"h{n}",
                        kind=ItemKind.memory,
                    )
                    for n in range(3)
                ]
            )
        )
        bundle = await engine.assemble(scope=_scope(), query="q")
        provs = bundle.provenance_list()
        assert len(provs) == 3
        for p in provs:
            assert p["user_id"] == "u1"
            assert p["source_ref"].startswith("ai_memory:")
            assert p["content_hash"] is not None

    @pytest.mark.asyncio
    async def test_budget_respected_end_to_end(self):
        engine = ContextEngine(
            memory_source=_mem_source(
                [
                    RawCandidate(
                        content="x" * 400,
                        source_type="ai_memory",
                        source_ref=f"m:{n}",
                        user_id="u1",
                        base_score=0.9 - n * 0.1,
                        kind=ItemKind.memory,
                    )
                    for n in range(4)
                ]
            )
        )
        bundle = await engine.assemble(
            scope=_scope(), query="q", budget=ContextBudget(total_tokens=50)
        )
        assert bundle.total_tokens <= 50
        assert bundle.report.admitted_items < 4
        assert bundle.report.dropped  # honesty: drops are reported
