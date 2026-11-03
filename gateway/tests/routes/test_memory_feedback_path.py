"""#1834 — memory-path dead code removal + feedback_loop wiring tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest


class TestChatMemoryPath:
    def test_ltm_noop_block_removed_from_chat_route(self):
        chat = (Path(__file__).resolve().parents[3] / "api" / "routes" / "chat.py").read_text(
            encoding="utf-8"
        )
        assert "LongTermMemory" not in chat, "dead LTM construction must stay out of the hot path"
        assert "recall_memories" in chat, "the real pgvector recall remains the memory path"

    def test_no_wasted_supabase_init_per_request(self):
        """The removed block was the only per-request MemoryManager/Supabase init."""
        chat = (Path(__file__).resolve().parents[3] / "api" / "routes" / "chat.py").read_text(
            encoding="utf-8"
        )
        assert "MemoryManager()" not in chat


class TestFeedbackWiring:
    @pytest.fixture()
    def route_module(self, monkeypatch):
        import importlib

        for m in [k for k in list(sys.modules) if k.endswith("routes.knowledge")]:
            del sys.modules[m]
        return importlib.import_module("api.routes.knowledge")

    @pytest.mark.asyncio
    async def test_feedback_handler_writes_to_evolution_engine(self, route_module, monkeypatch):
        recorded: list[tuple] = []

        class FakeEngine:
            def record_feedback(self, session_id, query, chunks, rating):
                recorded.append((session_id, query, chunks, rating))
                return {"recorded": True}

        monkeypatch.setattr("core.self_evolution.evolution_engine.EvolutionEngine", FakeEngine)
        payload: dict[str, Any] = {
            "type": "SUGGESTION_FEEDBACK",
            "sessionId": "sess-1",
            "userId": "u-1",
            "data": {"query": "how to deploy", "retrieved_chunks": "chunk-a", "rating": 4.5},
        }
        response = await route_module.record_feedback(
            route_module.LearningUpload(**payload), user={"sub": "u-1"}
        )
        assert response["success"] is True
        assert recorded == [("sess-1", "how to deploy", "chunk-a", 4.5)]

    @pytest.mark.asyncio
    async def test_dual_write_fails_open(self, route_module, monkeypatch):
        class BrokenEngine:
            def __init__(self, *a, **k):
                raise RuntimeError("engine down")

        monkeypatch.setattr("core.self_evolution.evolution_engine.EvolutionEngine", BrokenEngine)
        payload = {
            "type": "SUGGESTION_FEEDBACK",
            "sessionId": "sess-2",
            "data": {"rating": 1.0},
        }
        response = await route_module.record_feedback(
            route_module.LearningUpload(**payload), user={"sub": "u-1"}
        )
        assert response["success"] is True, "learning-signal ingestion survives engine failure"


class TestSingleFeedbackPipeline:
    def test_feedback_loop_writer_is_reachable(self):
        engine = (
            Path(__file__).resolve().parents[3] / "core" / "self_evolution" / "evolution_engine.py"
        ).read_text(encoding="utf-8")
        assert "def record_feedback" in engine
        assert "insert_feedback" in engine
