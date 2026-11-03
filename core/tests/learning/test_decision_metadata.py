"""#4052 — decision metadata model contract tests.

বাংলা: Roadmap v2 §3.2 acceptance যাচাই —
  * 13-field schema সহ decision রেকর্ড হয় (fail-honest validation)
  * supersession chain — পুরোনো সিদ্ধান্ত deprecated হয়, DELETED নয়
  * verification post-task পূরণ হয়
  * query ফিল্টার (agent/task_type/outcome/since) সঠিকভাবে কাজ করে
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.learning import decision_store
from core.models.decision_metadata import DecisionMetadata

pytestmark = pytest.mark.unit


@pytest.fixture
async def decision_table():
    """শুধু decision_metadata টেবিল বানায় (global metadata-তে অসম্পূর্ণ
    অন্য মডেলের FK আছে — সেগুলো এই টেস্টের ব্যাপার নয়; isolation)।"""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from core.models.decision_metadata import (
        DecisionMetadata as DecisionMetadataModel,
    )

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: DecisionMetadataModel.__table__.create(sync_conn, checkfirst=True)
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)

    orig = decision_store.get_db_session_context

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_ctx():
        async with maker() as session:
            yield session

    decision_store.get_db_session_context = _fake_ctx
    yield maker
    decision_store.get_db_session_context = orig
    await engine.dispose()


async def _record(**overrides):
    payload = dict(
        agent_type="coder",
        task_type="ci_fix",
        decision="chose_provider_X",
        why="lowest_latency_for_task_type",
        evidence=["benchmark_run_123: 0.3s", "cost_log: $0.001"],
        confidence=0.85,
        outcome="success",
        reusability="high",
        policy_context={"cost_optimization_mode": "true", "max_cost_per_task": "0.05"},
    )
    payload.update(overrides)
    return await decision_store.record_decision(**payload)


class TestRecordDecision:
    async def test_record_with_all_13_semantic_fields(self, decision_table):
        row = await _record()
        assert row["id"]
        assert row["agent_type"] == "coder"
        assert row["task_type"] == "ci_fix"
        assert row["decision"] == "chose_provider_X"
        assert row["why"] == "lowest_latency_for_task_type"
        assert row["evidence"] == ["benchmark_run_123: 0.3s", "cost_log: $0.001"]
        assert row["confidence"] == 0.85
        assert row["outcome"] == "success"
        assert row["reusability"] == "high"
        assert row["policy_context"]["max_cost_per_task"] == "0.05"
        assert row["verification"] is None
        assert row["supersedes"] is None
        assert row["status"] == "active"

    async def test_record_is_fail_honest_without_required_fields(self, decision_table):
        with pytest.raises(ValueError):
            await decision_store.record_decision(
                agent_type="coder", task_type="ci_fix", decision="x", why=""
            )

    async def test_unknown_outcome_becomes_pending(self, decision_table):
        row = await _record(outcome="banana")
        assert row["outcome"] == "pending"

    async def test_confidence_clamped(self, decision_table):
        row = await _record(confidence=7.5)
        assert row["confidence"] == 1.0


class TestVerification:
    async def test_verification_populated_post_task(self, decision_table):
        row = await _record()
        updated = await decision_store.update_verification(
            row["id"], "pytest passed, CI green, 0 regression"
        )
        assert updated is not None
        assert "CI green" in updated["verification"]

    async def test_verification_unknown_id_is_honest_none(self, decision_table):
        assert await decision_store.update_verification("nope", "x") is None


class TestSupersession:
    async def test_supersede_marks_old_deprecated_not_deleted(self, decision_table):
        old = await _record(decision="chose_provider_A", why="was best last week")
        new = await decision_store.supersede_decision(
            dict(
                agent_type="coder",
                task_type="ci_fix",
                decision="chose_provider_B",
                why="better latency",
                evidence=["bench: newer"],
            ),
            old_decision_id=old["id"],
        )
        # new references old
        assert new["supersedes"] == old["id"]
        # old NOT deleted — deprecated
        fetched = await decision_store.get_decision(old["id"])
        assert fetched is not None, "old decision must never be deleted"
        assert fetched["status"] == "deprecated"
        # default query excludes deprecated; include_deprecated path via status=None
        active = await decision_store.query_decisions(status="active")
        assert all(d["id"] != old["id"] for d in active)
        everything = await decision_store.query_decisions(status=None)
        assert any(d["id"] == old["id"] for d in everything)

    async def test_supersede_unknown_old_fails_honest(self, decision_table):
        result = await decision_store.supersede_decision(
            dict(
                agent_type="coder",
                task_type="ci_fix",
                decision="d",
                why="w",
            ),
            old_decision_id="ghost",
        )
        assert result is None, "no provenance chain may be forged to an unknown old id"


class TestQuery:
    async def test_filters_by_agent_task_outcome(self, decision_table):
        await _record(agent_type="coder", task_type="ci_fix", outcome="success")
        await _record(agent_type="coder", task_type="code_review", outcome="fail")
        await _record(agent_type="planner", task_type="ci_fix", outcome="partial")

        hits = await decision_store.query_decisions(agent_type="coder", task_type="ci_fix")
        assert len(hits) == 1
        assert hits[0]["outcome"] == "success"

        failures = await decision_store.query_decisions(outcome="fail")
        assert len(failures) == 1
        assert failures[0]["task_type"] == "code_review"

    async def test_since_filter(self, decision_table):
        await _record()
        future = await decision_store.query_decisions(since=datetime.now(UTC) + timedelta(hours=1))
        assert future == []

    async def test_invalid_status_rejected(self, decision_table):
        with pytest.raises(ValueError):
            await decision_store.query_decisions(status="banana")


class TestSchemaShape:
    def test_model_has_all_metadata_columns(self):
        cols = {c.name for c in DecisionMetadata.__table__.columns}
        expected = {
            "id",
            "tenant_id",
            "agent_type",
            "task_type",
            "decision",
            "why",
            "evidence",
            "confidence",
            "outcome",
            "reusability",
            "expiry",
            "policy_context",
            "verification",
            "supersedes",
            "status",
            "created_at",
            "updated_at",
        }
        assert expected <= cols, f"missing: {expected - cols}"
