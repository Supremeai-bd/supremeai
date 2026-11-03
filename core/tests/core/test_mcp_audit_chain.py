"""Tests: MCP audit hash-chain store — tamper-evident per-agent audit (issue #928).

Covers issue #928 acceptance criteria:
  - 10 sampled tool calls → 10 chained events
  - audit_verify detects a tampered record
  - audit_query per-agent report < 1s
  - anomaly rule #1 (failure-rate spike → needs-human-review) live
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.kernel.audit_chain import MCPAuditChainStore, args_fingerprint, compute_entry_hash
from models.base import Base
from models.mcp_audit_event import MCPAuditEvent

TENANT = "tenant-audit-test"


@pytest_asyncio.fixture
async def store() -> AsyncIterator[MCPAuditChainStore]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[MCPAuditEvent.__table__])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield MCPAuditChainStore(session_maker=maker)
    await engine.dispose()


def _ev(agent: str = "agent-1", status: str = "ok", tool: str = "graph_query") -> dict:
    return {
        "tenant_id": TENANT,
        "tool": tool,
        "agent_id": agent,
        "client_role": "agent",
        "provider": "test-provider",
        "args_hash": args_fingerprint({"tool": tool, "q": agent}),
        "result_status": status,
    }


# ── Acceptance 1: 10 tool calls → 10 chained events ──────────────────────────


@pytest.mark.asyncio
async def test_ten_chained_events(store: MCPAuditChainStore) -> None:
    events = [await store.append(**_ev(agent=f"agent-{i % 3}")) for i in range(10)]
    assert len(events) == 10

    # চেইন লিংক যাচাই: প্রতিটি event-এর prev_hash = আগেরটার entry_hash
    prev = ""
    for e in events:
        assert e["prev_hash"] == prev
        prev = e["entry_hash"]

    report = await store.verify(TENANT)
    assert report["checked"] == 10
    assert report["chain_intact"] is True
    assert report["tampered_events"] == []

    # entry_hash আসলেই payload-নির্ধারিত (deterministic) — এক রেকর্ড পুনঃগণনা
    first = events[0]
    assert first["entry_hash"] == compute_entry_hash(
        "",
        {
            "ts": first["ts"],
            "tenant_id": TENANT,
            "agent_id": "agent-0",
            "client_role": "agent",
            "provider": "test-provider",
            "server": "supremeai-mcp",
            "tool": "graph_query",
            "args_hash": first["args_hash"],
            "result_status": "ok",
            "result_ref": None,
            "error": None,
            "hitl_required": False,
            "hitl_approver": None,
        },
    )


# ── Acceptance 2: tamper detection ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_tamper_detection(store: MCPAuditChainStore) -> None:
    for i in range(5):
        await store.append(**_ev(agent=f"agent-{i}"))

    report_before = await store.verify(TENANT)
    assert report_before["chain_intact"] is True

    # টেম্পার ডেমো: store.append বাইপাস করে ভুয়া entry_hash-সহ একটি event
    # সরাসরি insert করা হচ্ছে (attacker simulation)। verify() এটা ধরতে হবে।
    forged = MCPAuditEvent(
        id=uuid.uuid4(),
        ts=datetime.now(UTC),
        tenant_id=TENANT,
        agent_id="ghost-agent",
        client_role="agent",
        provider="attacker",
        server="supremeai-mcp",
        tool="mesh_dispatch_task",
        args_hash="0" * 64,
        result_status="ok",
        prev_hash="forged-prev",
        entry_hash="forged-entry",
    )
    maker = store._session_maker  # type: ignore[attr-defined] — টেস্ট-শুধু access
    assert maker is not None
    async with maker() as s:
        s.add(forged)
        await s.commit()

    report = await store.verify(TENANT)
    assert report["chain_intact"] is False
    assert len(report["tampered_events"]) == 1
    assert report["tampered_events"][0]["event_id"] == str(forged.id)
    assert report["tampered_events"][0]["reason"] in (
        "entry_hash_mismatch",
        "prev_hash_link_broken",
    )


# ── Acceptance 3: per-agent query < 1s ───────────────────────────────────────


@pytest.mark.asyncio
async def test_query_per_agent_under_1s(store: MCPAuditChainStore) -> None:
    for i in range(12):
        await store.append(**_ev(agent=f"agent-{i % 4}"))

    start = time.monotonic()
    rows = await store.query(TENANT, agent_id="agent-1")
    elapsed = time.monotonic() - start

    assert len(rows) == 3
    assert all(r["agent_id"] == "agent-1" for r in rows)
    assert elapsed < 1.0, f"per-agent query took {elapsed:.3f}s (>1s)"


# ── Acceptance 4: anomaly rule #1 (failure-rate) live ────────────────────────


@pytest.mark.asyncio
async def test_anomaly_failure_rate_rule(store: MCPAuditChainStore) -> None:
    # agent-bad: ১০টি call-এর ৮টি failed (৮০% ≥ ৫০% থ্রেশহোল্ড) → flag
    statuses = ["error", "ok", "error", "error", "error", "ok", "error", "error", "error", "ok"]
    for st in statuses:
        await store.append(**_ev(agent="agent-bad", status=st))
    # agent-good: সব ok → flag নয়
    for _ in range(5):
        await store.append(**_ev(agent="agent-good", status="ok"))

    report = await store.verify(TENANT)
    flags = report["anomaly_flags"]
    bad = [f for f in flags if f["agent_id"] == "agent-bad"]
    good = [f for f in flags if f["agent_id"] == "agent-good"]
    assert bad and bad[0]["rule"] == "failure_rate_spike"
    assert bad[0]["action"] == "needs-human-review"
    assert not good


# ── Unit: hash determinism + fingerprint stability ───────────────────────────


def test_hash_determinism() -> None:
    p = {"tool": "t", "tenant_id": "x"}
    a = compute_entry_hash("", p)
    b = compute_entry_hash("", p)
    c = compute_entry_hash(a, p)
    assert a == b
    assert a != c
    assert args_fingerprint({"b": 2, "a": 1}) == args_fingerprint(
        {"a": 1, "b": 2}
    )  # key-order নিরপেক্ষ
    assert compute_entry_hash("x", p) != compute_entry_hash("y", p)  # prev_hash-নির্ভর


def test_query_time_window(store: MCPAuditChainStore) -> None:
    async def run() -> None:
        old = await store.append(**_ev(agent="agent-t"))
        assert old["ts"] is not None
        cutoff = datetime.now(UTC) - timedelta(minutes=1)
        fresh = await store.query(TENANT, since=cutoff)
        assert len(fresh) >= 1

    asyncio.run(run())
