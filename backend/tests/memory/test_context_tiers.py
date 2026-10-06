"""#4051 — hierarchical context tiers (L0/L1/L2) contract tests.

বাংলা: Roadmap v2 §3.1 acceptance যাচাই —
  * L0 সবসময় loaded, parsed (raw নয়), constitution hash stable + drift detect
  * L1 শুধু task assign-এ গঠিত হয়
  * L2 similarity-ranked top-K, tenant scope fail-closed, degraded store সহনশীল
  * Budget L0 > L1 > L2 ক্রমে allocate (L0 আগে reserved), composition log হয়
"""

from __future__ import annotations

from typing import Any

import pytest

from memory.context_tiers import (
    L0Context,
    L1Context,
    L2Context,
    TierLevel,
    compose_agent_context,
)

pytestmark = pytest.mark.memory


# ── helpers ────────────────────────────────────────────────────────────────

MINIMAL_CONTRACT: dict[str, Any] = {
    "version": 1,
    "task_id": "task-4051",
    "issue": 4051,
    "task_type": "IMPLEMENT",
    "objective": "Adopt hierarchical context tiers",
    "scope": {"touching_files": ["backend/memory/context_tiers.py"]},
    "acceptance": ["L0 always loaded", "budget L0 > L1 > L2"],
    "role_policy": "Coder",
}


class FakeExperienceDB:
    """find_similar contract mock — adaptive_engine.ExperienceDatabase আকৃতি।"""

    def __init__(self, hits: list[dict[str, Any]] | None = None, fail: bool = False):
        self.hits = hits or []
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def find_similar(self, query, limit=5, threshold=0.7, user_id=None):
        self.calls.append({"query": query, "limit": limit, "user_id": user_id})
        if self.fail:
            raise RuntimeError("store exploded")
        return [h for h in self.hits if h.get("user_id", user_id) == user_id][:limit]


class FakeMemoryRepo:
    """search_similar contract mock — core.ai_memory MemoryRepository আকৃতি।"""

    def __init__(self, hits: list[dict[str, Any]] | None = None, fail: bool = False):
        self.hits = hits or []
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def search_similar(self, query_text, user_id=None, limit=5, **kw):
        self.calls.append({"query": query_text, "user_id": user_id, "limit": limit})
        if self.fail:
            raise RuntimeError("repo exploded")
        return [h for h in self.hits if h.get("user_id", user_id) == user_id][:limit]


@pytest.fixture
def constitution_dir(tmp_path):
    """চারটি constitutional ফাইলসহ ছোট fake repo root।"""
    (tmp_path / "AGENTS.md").write_text(
        "# C\n\n## 1. Authority\nAdmin rule highest.\n\n## 2. Lifecycle\nClaim before PR.\n",
        encoding="utf-8",
    )
    (tmp_path / "AGENT_RULES.md").write_text(
        "# R\n\n## U1 — Scope\nWork inside scope.\n\n## U7 — Verification\nTests pass.\n",
        encoding="utf-8",
    )
    (tmp_path / "SECURITY.md").write_text(
        "# S\n\n## Secrets\nNever hardcode keys.\n", encoding="utf-8"
    )
    return tmp_path


# ── L0 ─────────────────────────────────────────────────────────────────────


class TestL0:
    def test_l0_loads_parsed_sections_from_all_sources(self, constitution_dir):
        l0 = L0Context.load(repo_root=constitution_dir)
        assert l0.source_files == ("AGENTS.md", "AGENT_RULES.md", "SECURITY.md")
        assert l0.missing_files == ()
        headings = [s.heading for s in l0.sections]
        # parsed (heading-bearing sections), not a raw single dump
        assert "AGENTS.md::1. Authority" in headings
        assert "AGENT_RULES.md::U1 — Scope" in headings
        assert "SECURITY.md::Secrets" in headings
        assert l0.token_count > 0
        assert len(l0.constitution_hash) == 64

    def test_l0_hash_stable_across_loads(self, constitution_dir):
        h1 = L0Context.load(repo_root=constitution_dir).constitution_hash
        h2 = L0Context.load(repo_root=constitution_dir).constitution_hash
        assert h1 == h2

    def test_l0_drift_detected_on_change(self, constitution_dir):
        l0 = L0Context.load(repo_root=constitution_dir)
        prev = l0.constitution_hash
        (constitution_dir / "AGENTS.md").write_text(
            "# C\n\n## 1. Authority\nAdmin rule overridden.\n", encoding="utf-8"
        )
        l0_new = L0Context.load(repo_root=constitution_dir)
        drift = l0_new.drift_check(prev)
        assert drift.changed is True
        # Tier-3: constitutional change ALWAYS demands admin approval
        assert drift.requires_admin_approval is True

    def test_l0_no_drift_when_unchanged(self, constitution_dir):
        l0 = L0Context.load(repo_root=constitution_dir)
        drift = l0.drift_check(l0.constitution_hash)
        assert drift.changed is False

    def test_l0_missing_file_is_fail_honest(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# C\n\n## A\nx\n", encoding="utf-8")
        l0 = L0Context.load(repo_root=tmp_path)
        assert "AGENT_RULES.md" in l0.missing_files
        assert "SECURITY.md" in l0.missing_files
        assert l0.sections, "loaded file must still be parsed"

    def test_l0_render_contains_headings(self, constitution_dir):
        l0 = L0Context.load(repo_root=constitution_dir)
        rendered = l0.render()
        assert "## AGENTS.md::1. Authority" in rendered


# ── L1 ─────────────────────────────────────────────────────────────────────


class TestL1:
    def test_l1_built_from_task_contract(self):
        l1 = L1Context.from_task_contract(MINIMAL_CONTRACT)
        assert l1.task_id == "task-4051"
        assert l1.issue == 4051
        assert "backend/memory/context_tiers.py" in l1.touching_files
        assert l1.token_count > 0
        rendered = l1.render()
        assert "task-4051" in rendered
        assert "Acceptance criteria:" in rendered

    def test_l1_empty_contract_is_honest_empty(self):
        l1 = L1Context.from_task_contract(None)
        assert l1.task_id == ""
        assert l1.token_count > 0  # still renders the Active Task header


# ── L2 ─────────────────────────────────────────────────────────────────────


class TestL2:
    @pytest.mark.asyncio
    async def test_l2_returns_top_k_similarity_ranked(self):
        exp = FakeExperienceDB(
            hits=[
                {"id": "1", "content": "low sim", "similarity": 0.71, "user_id": "t1"},
                {"id": "2", "content": "high sim", "similarity": 0.95, "user_id": "t1"},
            ]
        )
        repo = FakeMemoryRepo(hits=[])
        l2 = await L2Context.retrieve(
            "query", tenant_id="t1", top_k=2, experience_db=exp, memory_repo=repo
        )
        contents = [e["content"] for e in l2.entries]
        assert contents[0] == "high sim", "similarity-desc ranking required"
        assert len(l2.entries) <= 2
        assert l2.tenant_id == "t1"
        assert l2.degraded is False

    @pytest.mark.asyncio
    async def test_l2_no_tenant_is_fail_closed(self):
        exp = FakeExperienceDB(hits=[{"id": "1", "content": "x", "similarity": 0.9}])
        l2 = await L2Context.retrieve("query", tenant_id=None, experience_db=exp)
        assert l2.entries == []
        assert l2.skip_reason == "no_tenant_scope"
        assert exp.calls == [], "store must not be queried without tenant scope"

    @pytest.mark.asyncio
    async def test_l2_degraded_store_is_honest_not_fatal(self):
        exp = FakeExperienceDB(fail=True)
        repo = FakeMemoryRepo(fail=True)
        l2 = await L2Context.retrieve("query", tenant_id="t1", experience_db=exp, memory_repo=repo)
        assert l2.entries == []
        assert l2.degraded is True

    @pytest.mark.asyncio
    async def test_l2_merges_and_dedups_both_stores(self):
        exp = FakeExperienceDB(
            hits=[{"id": "e1", "content": "same content", "similarity": 0.8, "user_id": "t1"}]
        )
        repo = FakeMemoryRepo(
            hits=[{"id": "e1", "content": "same content", "similarity": 0.9, "user_id": "t1"}]
        )
        l2 = await L2Context.retrieve("q", tenant_id="t1", experience_db=exp, memory_repo=repo)
        assert len(l2.entries) == 1, "same id across stores must dedup, keeping top-sim"
        assert l2.entries[0]["similarity"] == 0.9


# ── composition / budget ───────────────────────────────────────────────────


class TestComposition:
    @pytest.mark.asyncio
    async def test_l0_always_loaded_even_without_task(self, constitution_dir):
        composed = await compose_agent_context(None, repo_root=constitution_dir)
        assert composed.l0.token_count > 0
        assert composed.l1 is None
        assert composed.total_tokens == composed.l0_tokens

    @pytest.mark.asyncio
    async def test_budget_allocation_l0_first(self, constitution_dir):
        # Tiny budget: L0 eats it all — L1/L2 get nothing, no exception.
        composed = await compose_agent_context(
            MINIMAL_CONTRACT, total_budget=10, repo_root=constitution_dir
        )
        assert composed.l0_tokens <= 10
        assert composed.l1_tokens == 0
        assert composed.truncated["L0"] is True or composed.l0.token_count <= 10

    @pytest.mark.asyncio
    async def test_budget_l0_reserved_before_l1_and_l2(self, constitution_dir):
        exp = FakeExperienceDB(
            hits=[{"id": "e", "content": "experience " * 200, "similarity": 0.9, "user_id": "t1"}]
        )
        composed = await compose_agent_context(
            MINIMAL_CONTRACT,
            retrieval_query="query",
            tenant_id="t1",
            total_budget=1500,
            experience_db=exp,
            repo_root=constitution_dir,
        )
        # L0 fully reserved (not truncated)
        assert composed.l0_tokens == composed.l0.token_count
        assert composed.truncated["L0"] is False
        # L1 fits next
        assert composed.l1 is not None
        assert composed.l1_tokens == composed.l1.token_count
        # L2 gets only the remainder — never pushes total over budget
        assert composed.total_tokens <= 1500
        assert composed.l2_tokens <= 1500 - composed.l0_tokens - composed.l1_tokens

    @pytest.mark.asyncio
    async def test_l2_skipped_without_tenant(self, constitution_dir):
        composed = await compose_agent_context(
            MINIMAL_CONTRACT,
            retrieval_query="query",
            tenant_id=None,
            experience_db=FakeExperienceDB(hits=[{"id": "1", "content": "x"}]),
            repo_root=constitution_dir,
        )
        assert composed.l2 is not None
        assert composed.l2.entries == []
        assert composed.l2_tokens == 0

    @pytest.mark.asyncio
    async def test_invalid_budget_rejected(self, constitution_dir):
        with pytest.raises(ValueError):
            await compose_agent_context(None, total_budget=0, repo_root=constitution_dir)

    @pytest.mark.asyncio
    async def test_tier_levels_are_l0_l1_l2(self):
        assert TierLevel.L0 == "L0"
        assert TierLevel.L1 == "L1"
        assert TierLevel.L2 == "L2"

    @pytest.mark.asyncio
    async def test_render_order_l0_l1_l2(self, constitution_dir):
        exp = FakeExperienceDB(
            hits=[{"id": "e", "content": "prior attempt notes", "similarity": 0.9, "user_id": "t1"}]
        )
        composed = await compose_agent_context(
            MINIMAL_CONTRACT,
            retrieval_query="query",
            tenant_id="t1",
            total_budget=4000,
            experience_db=exp,
            repo_root=constitution_dir,
        )
        rendered = composed.render()
        i0 = rendered.find("[L0")
        i1 = rendered.find("[L1")
        i2 = rendered.find("[L2")
        assert 0 <= i0 < i1 < i2, "tiers must render in L0 → L1 → L2 order"
