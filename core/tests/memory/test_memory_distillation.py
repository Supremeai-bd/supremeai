"""PLAN-004 — Letta-style write-time memory distillation tests.

বাংলা: প্রমাণ-চালিত টেস্ট সেট — distilled write, fallback-on-failure write,
malformed-JSON degradation, short-content cost guard এবং env kill-switch।
Gateway সবসময় stub করা হয় (টেস্ট টুলিং stub — প্রোডাক্টে নয়); কোনো টেস্টে
LLM কল যায় না (CI cost guard, plan rule 4)।

Provenance: Eternal Brain write path (core/unified_memory.py) — canonical
store per docs/plans/M3_MEMORY_STORE_CONSOLIDATION_DECISION_TABLE.md.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.unified_memory import (
    MEMORY_DISTILL_MIN_CONTENT_CHARS,
    UnifiedMemoryInterface,
    _extract_json_object,
    distill_content,
)

pytestmark = pytest.mark.memory

LONG_CONTENT = (
    "Audit report 2026-09-17: SyncGuard verified infrastructure blueprint drift for "
    "github.com/SaifulHaqueNiloy/supremeai; env secrets REDIS_URL, OPENAI_API_KEY and "
    "SUPABASE_URL were all synced via Infisical staging; Redis message broker reachable "
    "at render free tier; decision recorded — keep pnpm-lock.yaml authoritative, delete "
    "bun.lock; open item: knip files rule stays off until orphan triage finishes."
)


def _make_interface() -> tuple[UnifiedMemoryInterface, MagicMock]:
    """Facade with a stubbed long-term backend (no DB touched)."""
    facade = UnifiedMemoryInterface()
    backend = MagicMock(return_value=None)
    facade.long_term_memory = backend
    return facade, backend


class TestExtractJsonObject:
    def test_valid_object_extracted(self):
        text = 'prose before {"facts": ["a"], "entities": []} prose after'
        assert _extract_json_object(text) == {"facts": ["a"], "entities": []}

    def test_no_object_returns_none(self):
        assert _extract_json_object("no json here at all") is None

    def test_non_dict_json_returns_none(self):
        assert _extract_json_object("[1, 2, 3]") is None

    def test_malformed_json_returns_none(self):
        assert _extract_json_object('{"facts": ["a", oops]}') is None


class TestDistillContent:
    @pytest.mark.asyncio
    async def test_success_returns_dense_summary_and_structure(self):
        gateway = MagicMock()
        gateway.acompletion = AsyncMock(
            return_value={
                "success": True,
                "text": 'SyncGuard audit passed. {"facts": ["redis ok"], "open_items": []}',
                "model": "stub",
                "cost": 0.0,
            }
        )
        with patch("core.llm.llm_gateway.llm_gateway", gateway):
            summary, structure = await distill_content(LONG_CONTENT)
        assert "syncguard audit passed" in summary.lower()
        assert structure == {"facts": ["redis ok"], "open_items": []}

    @pytest.mark.asyncio
    async def test_gateway_exception_returns_empty_pair(self):
        gateway = MagicMock()
        gateway.acompletion = AsyncMock(side_effect=RuntimeError("all providers down"))
        with patch("core.llm.llm_gateway.llm_gateway", gateway):
            summary, structure = await distill_content(LONG_CONTENT)
        assert summary == ""
        assert structure is None


class TestStoreLongTermMemoryDistilled:
    @pytest.mark.asyncio
    async def test_distilled_write_uses_summary_and_metadata_provenance(self):
        facade, backend = _make_interface()
        gateway = MagicMock()
        gateway.acompletion = AsyncMock(
            return_value={
                "success": True,
                "text": 'Dense audit summary. {"facts": ["f1"], "entities": ["x"]}',
                "model": "stub",
                "cost": 0.0,
            }
        )
        with patch("core.llm.llm_gateway.llm_gateway", gateway):
            ok = await facade.store_long_term_memory_distilled(
                session_id="s-1",
                agent_type="SyncGuard",
                task_type="System_Audit",
                content=LONG_CONTENT,
                metadata={"status": "SYNC_OK"},
                user_id="user-1",
            )
        assert ok is True
        kwargs = backend.store_memory.call_args.kwargs
        assert kwargs["summary"] != LONG_CONTENT[:200]  # dense, not the raw truncation
        assert kwargs["metadata"]["distilled"] is True
        assert kwargs["metadata"]["memory_structure"] == {"facts": ["f1"], "entities": ["x"]}
        assert kwargs["metadata"]["status"] == "SYNC_OK"  # caller metadata preserved
        assert kwargs["content"] == LONG_CONTENT  # full content still persisted

    @pytest.mark.asyncio
    async def test_gateway_failure_falls_back_to_legacy_truncation(self):
        facade, backend = _make_interface()
        gateway = MagicMock()
        gateway.acompletion = AsyncMock(side_effect=RuntimeError("gateway down"))
        with patch("core.llm.llm_gateway.llm_gateway", gateway):
            ok = await facade.store_long_term_memory_distilled(
                session_id="s-2",
                agent_type="SyncGuard",
                task_type="System_Audit",
                content=LONG_CONTENT,
                user_id="user-1",
            )
        assert ok is True  # memory is NOT lost on distiller failure
        kwargs = backend.store_memory.call_args.kwargs
        assert kwargs["summary"] == LONG_CONTENT[:200]  # legacy truncation, byte-identical
        assert "distilled" not in kwargs["metadata"]

    @pytest.mark.asyncio
    async def test_malformed_json_writes_summary_only_without_structure(self):
        facade, backend = _make_interface()
        gateway = MagicMock()
        gateway.acompletion = AsyncMock(
            return_value={
                "success": True,
                "text": "Dense summary but broken json {facts: nope}",
                "model": "stub",
                "cost": 0.0,
            }
        )
        with patch("core.llm.llm_gateway.llm_gateway", gateway):
            ok = await facade.store_long_term_memory_distilled(
                session_id="s-3",
                agent_type="SyncGuard",
                task_type="System_Audit",
                content=LONG_CONTENT,
                user_id="user-1",
            )
        assert ok is True
        kwargs = backend.store_memory.call_args.kwargs
        assert kwargs["metadata"]["distilled"] is True
        assert "memory_structure" not in kwargs["metadata"]  # structure skipped, not faked
        assert kwargs["structure"] == "{}"

    @pytest.mark.asyncio
    async def test_short_content_skips_distiller_entirely(self):
        facade, backend = _make_interface()
        gateway = MagicMock()
        gateway.acompletion = AsyncMock(
            return_value={
                "success": True,
                "text": "should not be reached",
                "model": "stub",
                "cost": 0.0,
            }
        )
        short = "only a short note"
        assert len(short) <= MEMORY_DISTILL_MIN_CONTENT_CHARS
        with patch("core.llm.llm_gateway.llm_gateway", gateway):
            ok = await facade.store_long_term_memory_distilled(
                session_id="s-4",
                agent_type="test",
                task_type="unit",
                content=short,
                user_id="user-1",
            )
        assert ok is True
        gateway.acompletion.assert_not_awaited()  # cost guard: no LLM call
        kwargs = backend.store_memory.call_args.kwargs
        assert kwargs["summary"] == short[:200]
        assert "distilled" not in kwargs["metadata"]

    @pytest.mark.asyncio
    async def test_kill_switch_env_forces_straight_legacy(self):
        facade, backend = _make_interface()
        gateway = MagicMock()
        gateway.acompletion = AsyncMock(
            return_value={"success": True, "text": "dense summary", "model": "stub", "cost": 0.0}
        )
        env = dict(os.environ)
        env["SUPREMEAI_MEMORY_DISTILL"] = "false"
        with patch.object(os, "environ", env):
            ok = await facade.store_long_term_memory_distilled(
                session_id="s-5",
                agent_type="SyncGuard",
                task_type="System_Audit",
                content=LONG_CONTENT,
                user_id="user-1",
            )
        assert ok is True
        gateway.acompletion.assert_not_awaited()  # kill-switch bypasses the distiller
        kwargs = backend.store_memory.call_args.kwargs
        assert kwargs["summary"] == LONG_CONTENT[:200]

    @pytest.mark.asyncio
    async def test_legacy_store_failure_still_returns_false_honestly(self):
        facade, backend = _make_interface()
        backend.store_memory.side_effect = RuntimeError("db unreachable")
        ok = await facade.store_long_term_memory_distilled(
            session_id="s-6",
            agent_type="test",
            task_type="unit",
            content="short",
            user_id="user-1",
        )
        assert ok is False  # honest failure — no fabricated success (#13)


def test_event_loop_policy_isolation():
    """Guard: module-level import must not require a running loop (import safety)."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(asyncio.sleep(0))
    finally:
        loop.close()
