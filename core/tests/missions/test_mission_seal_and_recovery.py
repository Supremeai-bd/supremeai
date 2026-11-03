"""Task 14-e (Wave 4 Moat) — failure-mode missions, part 2: সিল ও ডিগ্রেডেশন।

বাংলা: দুটি mission-level ব্যর্থতা-দৃশ্য, উভয়ই আসল অ্যাপ-ইঞ্জিন (sqlite
test.db) ও আসল পলিসি কোড চালায় — অফলাইন, deterministic, sleep-মুক্ত।

Mission C — concurrent cancel-vs-finalize সিল: একই run id-তে দুটি টার্মিনাল
অপারেশন (সফল-সমাপ্তি/বাতিল/সিল) asyncio.gather-এ প্রতিযোগিতা করলে স্টেট
মেশিনের সিল-অপরিবর্তনীয়তা ভাঙতে পারে না — ঠিক একটিই টার্মিনাল ফল, হারোয়ান
হয় নথিভুক্ত conflict (IllegalTransition) অথবা নথিভুক্ত no-op
(cancel_ignored), ইভেন্ট-স্ট্রিমে কোনো দ্বৈত সাইড-এফেক্ট নেই। আসর: আসল
RunService + আসল sqlite ইঞ্জিন; ইন্টারলিভিং নিয়ন্ত্রণে get_run-এ
রেন্ডেজভাস-হুক (দুটি লোড শেষ না হলে কেউ মিউটেশনে যায় না) — ঘুম ছাড়াই
নিশ্চিত ক্রম।

Mission D — degraded-state recovery: ইঞ্জিন-সংযোগ ভেঙে দিলে অ্যাপের সৎ
সংকেত (probe → unhealthy, /ready → 503 core-এর জন্য, সহনশীল role-এ দৃশ্যমান
"degraded"), আর ইঞ্জিন ফিরে এলেই সংকেত সুস্থ হয়ে যায় (কোনো আটকে-থাকা
ডিগ্রেডেড-ক্যাশ মিথ্যা বলে না)। আসর: আসল _check_database / check_engine_health /
db_failure_readiness + আসল HTTP প্রোব — শুধু ইঞ্জিন প্রতিস্থাপনই ফেক।
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

# ---------------------------------------------------------------------------
# Shared fixtures — runs tables on the real app engine (missions-test pattern)
# ---------------------------------------------------------------------------

_runs_tables_ready = False


@pytest_asyncio.fixture
async def runs_tables(client):
    """আসল অ্যাপ-ইঞ্জিনের sqlite test.db-তে runs টেবিল তৈরি রাখে (একবারই)।"""
    global _runs_tables_ready
    if not _runs_tables_ready:
        import database.session as dbs
        from models.base import Base
        from runs.models import Run, RunEvent

        dbs.init_engine()
        engine = dbs.engine
        assert engine.url.get_backend_name() == "sqlite", (
            f"expected sqlite test engine, got {engine.url}"
        )
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    sync_conn, tables=[Run.__table__, RunEvent.__table__]
                )
            )
        _runs_tables_ready = True
    yield


# ---------------------------------------------------------------------------
# Mission C — concurrent cancel-vs-finalize seal
# ---------------------------------------------------------------------------


def _install_pair_staging(monkeypatch) -> tuple[Callable[[], None], Callable[[], None]]:
    """প্রতিযোগিতার জানালা নিয়ন্ত্রণ: get_run-এ রেন্ডেজভাস + _emit-এ মিউটেক্স।

    বাংলা: দুটি অপারেশনের 'সিদ্ধান্ত-উইন্ডো' ইচ্ছা করে ওভারল্যাপ করানো হয় —
    দুটি লোডই শেষ না হওয়া পর্যন্ত কেউ মিউটেট করে না (তাই দ্বিতীয় সিদ্ধান্তকারী
    প্রথমজনের মিউটেশন সহ শেয়ার্ড ইনস্ট্যান্সই দেখে — এটাই আসল সুরক্ষা-ব্যবস্থা)।
    আর _emit-মিউটেক্স নিশ্চিত করে এক সেশনে দুজন কখনো ফ্লাশ-স্টেজে ওভারল্যাপ
    করতে পারে না (SQLAlchemy re-entrancy সতর্কতা → filterwarnings=error)।
    ক্রম নিশ্চিত: রেডি-কিউ FIFO-তে দ্বিতীয় আর্গুমেন্টই আগে মিউটেট করে; কোনো
    sleep/ঘুমানো টাইমার নেই। রিটার্ন (arm, disarm) — জোড়ার ঠিক আগে arm(),
    শেষ হলে সাথে সাথে disarm() (নইলে একা লোড আটকায়)।
    """
    from runs.service import RunService

    original_get_run = RunService.get_run
    original_emit = RunService._emit
    emit_lock = asyncio.Lock()
    state: dict = {"count": 0, "gate": None}

    async def staged_get_run(svc, session, run_id):
        run = await original_get_run(svc, session, run_id)
        gate = state["gate"]
        if gate is None:  # অস্ত্রসজ্জার বাইরের লোড — সরাসরি যাও
            return run
        state["count"] += 1
        if state["count"] >= 2:
            gate.set()
        else:
            await gate.wait()
        return run

    async def locked_emit(self, session, run, event, **kwargs):
        async with emit_lock:
            return await original_emit(self, session, run, event, **kwargs)

    monkeypatch.setattr(RunService, "get_run", staged_get_run)
    monkeypatch.setattr(RunService, "_emit", locked_emit)

    def arm() -> None:
        state["count"] = 0
        state["gate"] = asyncio.Event()

    def disarm() -> None:
        state["gate"] = None

    return arm, disarm


async def _make_running_run(session) -> uuid.UUID:
    """নতুন run তৈরি করে running অবস্থায় নিয়ে যায় (কমিটসহ)।"""
    from runs.service import RunService
    from runs.state_machine import PLANNED, POLICY_CHECKED, RUNNING

    svc = RunService()
    run = await svc.create_run(session, run_type="tool", user_id="mission-seal-user")
    for nxt in (POLICY_CHECKED, PLANNED, RUNNING):
        await svc.transition(session, run.id, nxt)
    await session.commit()
    return run.id


async def _stream(session, run_id: uuid.UUID) -> list[tuple[str, dict | None]]:
    """রানের ইভেন্ট-স্ট্রিম (event, detail) তালিকা — seq ক্রমানুসারে।"""
    from runs.models import RunEvent

    rows = (
        (
            await session.execute(
                select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.seq)
            )
        )
        .scalars()
        .all()
    )
    return [(row.event, row.detail) for row in rows]


class TestMissionConcurrentSeal:
    async def test_interleaved_terminal_ops_keep_exactly_one_outcome(
        self, runs_tables, monkeypatch
    ):
        """বাংলা: একই run-এ সফল-সমাপ্তি বনাম বাতিলের সমকালীন প্রতিযোগিতা —
        উভয় ক্রমেই অপরিবর্তনীয়তা ভাঙে না: ঠিক একটি টার্মিনাল ফল, হারোয়ান
        নথিভুক্ত পথে যায় (বাতিল হারলে cancel_ignored no-op, সমাপ্তি হারলে
        IllegalTransition conflict), ইভেন্ট-স্ট্রিম দ্বৈত-মুক্ত।"""
        import database.session as dbs
        from runs.service import RunService
        from runs.state_machine import CANCELLED, SUCCEEDED, IllegalTransition

        arm_pair, disarm_pair = _install_pair_staging(monkeypatch)
        svc = RunService()

        # ── ক্রম ১: gather(বাতিল, সফল) → সমাপ্তি আগে মিউটেট করে ────────────
        async with dbs.AsyncSessionLocal() as session:
            rid = await _make_running_run(session)
            arm_pair()
            results = await asyncio.gather(
                svc.cancel(session, rid, actor="canceller", reason="mission drill"),
                svc.transition(session, rid, SUCCEEDED, actor="executor"),
                return_exceptions=True,
            )
            disarm_pair()
            cancelled_res, succeeded_res = results
            # হারোয়ান বাতিল: টার্মিনাল দেখে নথিভুক্ত no-op — স্টেট লেখেনি।
            assert not isinstance(cancelled_res, BaseException)
            assert cancelled_res.status == SUCCEEDED
            assert not isinstance(succeeded_res, BaseException)
            assert succeeded_res.status == SUCCEEDED
            await session.commit()

        async with dbs.AsyncSessionLocal() as reader:
            from runs.models import Run, RunEvent

            stream = await _stream(reader, rid)
            kinds = [k for k, _ in stream]
            assert kinds.count("cancelled") == 0
            assert kinds.count("cancel_ignored") == 1
            assert kinds.count("finalized") == 0
            finals = [
                d
                for k, d in stream
                if k == "status_transition"
                and d
                and d.get("to") in ("succeeded", "failed", "cancelled")
            ]
            assert len(finals) == 1 and finals[0]["to"] == SUCCEEDED
            seqs = [
                int(s)
                for (s,) in (
                    await reader.execute(
                        select(RunEvent.seq).where(RunEvent.run_id == rid).order_by(RunEvent.seq)
                    )
                ).all()
            ]
            assert seqs == list(range(1, len(seqs) + 1))  # দ্বৈত seq নেই
            persisted = await reader.get(Run, rid)
            assert persisted.status == SUCCEEDED
            assert persisted.terminal_at is not None

        # ── ক্রম ২: gather(সফল, বাতিল) → বাতিল আগে মিউটেট করে ───────────────
        async with dbs.AsyncSessionLocal() as session:
            rid2 = await _make_running_run(session)
            arm_pair()
            results = await asyncio.gather(
                svc.transition(session, rid2, SUCCEEDED, actor="executor"),
                svc.cancel(session, rid2, actor="canceller", reason="mission drill"),
                return_exceptions=True,
            )
            disarm_pair()
            succeeded_res, cancelled_res = results
            # হারোয়ান সমাপ্তি: সিল-গার্ড নথিভুক্ত conflict ছুড়ে দেয় (→409)।
            assert isinstance(succeeded_res, IllegalTransition)
            assert "cancelled" in str(succeeded_res)
            assert not isinstance(cancelled_res, BaseException)
            assert cancelled_res.status == CANCELLED
            await session.commit()

        async with dbs.AsyncSessionLocal() as reader:
            from runs.models import Run

            stream = await _stream(reader, rid2)
            kinds = [k for k, _ in stream]
            assert kinds.count("cancelled") == 1
            assert kinds.count("cancel_ignored") == 0
            # বাস্তব চুক্তি: টার্মিনাল ফল তিন আকারে আসে — transition-পথে
            # "status_transition"(to=…), বাতিল-জয়ে "cancelled", সিল-জয়ে
            # "finalized"। ঠিক একটি টার্মিনাল ইভেন্টই অপরিবর্তনীয়তার প্রমাণ।
            terminal_events = [
                (k, d)
                for k, d in stream
                if k in ("cancelled", "finalized")
                or (
                    k == "status_transition"
                    and d
                    and d.get("to") in ("succeeded", "failed", "cancelled")
                )
            ]
            assert len(terminal_events) == 1
            assert terminal_events[0][0] == "cancelled"  # বাতিলই জিতেছে
            persisted = await reader.get(Run, rid2)
            assert persisted.status == CANCELLED
            assert persisted.terminal_at is not None

    async def test_seal_wins_over_late_cancel_and_is_audit_locked(self, runs_tables, monkeypatch):
        """বাংলা: বাতিল-হওয়া run-এ সিল (finalize) বনাম দেরিতে বাতিল — সিলই
        জেতে: স্টেট finalized, ঠিক একটি finalized ইভেন্ট, দেরিতে বাতিল শুধুই
        নথিভুক্ত cancel_ignored no-op; সিলের পরে আর কোনো মিউটেশন/দ্বিতীয় সিল
        সম্ভব নয় (audit-lock)।"""
        import database.session as dbs
        from runs.service import RunService
        from runs.state_machine import CANCELLED, FINALIZED, RUNNING, IllegalTransition

        arm_pair, disarm_pair = _install_pair_staging(monkeypatch)
        svc = RunService()

        async with dbs.AsyncSessionLocal() as session:
            rid = await _make_running_run(session)
            await svc.cancel(session, rid, actor="canceller", reason="pre-seal")
            await session.commit()

            arm_pair()
            results = await asyncio.gather(
                svc.finalize(session, rid, actor="auditor"),
                svc.cancel(session, rid, actor="late-canceller", reason="too late"),
                return_exceptions=True,
            )
            disarm_pair()
            finalize_res, late_cancel_res = results
            assert not isinstance(finalize_res, BaseException)
            assert finalize_res.status == FINALIZED
            assert finalize_res.finalized_at is not None
            assert not isinstance(late_cancel_res, BaseException)
            # দেরিতে বাতিল নথিভুক্ত no-op — প্রথম ফলই টিকে থাকে।
            assert late_cancel_res.status == FINALIZED
            await session.commit()

        async with dbs.AsyncSessionLocal() as reader:
            from runs.models import Run

            stream = await _stream(reader, rid)
            kinds = [k for k, _ in stream]
            assert kinds.count("finalized") == 1
            assert kinds.count("cancelled") == 1  # সেটআপের বাতিল, সিলের আগের
            assert kinds.count("cancel_ignored") == 1
            persisted = await reader.get(Run, rid)
            assert persisted.status == FINALIZED

        # সিলের পরে: audit-lock — কোনো আউটগোয়িং এজ নেই।
        async with dbs.AsyncSessionLocal() as session:
            for attempt in (RUNNING, CANCELLED, FINALIZED):
                with pytest.raises(IllegalTransition):
                    await svc.transition(session, rid, attempt)
            with pytest.raises(IllegalTransition):
                await svc.finalize(session, rid)  # দ্বিতীয়বার সিল অসম্ভব
            still = await svc.get_run(session, rid)
            assert still.status == FINALIZED


# ---------------------------------------------------------------------------
# Mission D — degraded-state recovery
# ---------------------------------------------------------------------------


class _SeveredConnection:
    """ভাঙা ইঞ্জিনের সংযোগ — ব্যবহারের মুহূর্তেই সংযোগ-বিচ্ছিন্নতা জানায়।"""

    async def __aenter__(self):
        raise SQLAlchemyError("engine wire severed (mission drill)")

    async def __aexit__(self, *args):
        return False


class _SeveredEngine:
    """প্রোব-যোগ্য ভাঙা ইঞ্জিন: connect() চলে, কিন্তু কাজ শুরু মাত্রই ভাঙে।"""

    def connect(self):
        return _SeveredConnection()


class TestMissionDegradedRecovery:
    async def test_engine_failure_honest_signal_then_recovery_restores_ready(
        self, runs_tables, client, monkeypatch
    ):
        """বাংলা: ভাঙা ইঞ্জিন → সৎ degraded সংকেত (প্রোব unhealthy, /ready 503
        core-এর জন্য fail-closed, সহনশীল role-এ দৃশ্যমান role-tolerated);
        ইঞ্জিন ফিরে এলে একই প্রোব সুস্থ সংকেত দেয় — সততা দুই দিকেই সত্য।"""
        import database.session as dbs
        from api.routes.health import _check_database
        from database.session import check_engine_health

        real_engine = dbs._engine_instance
        assert real_engine is not None  # অ্যাপ ইঞ্জিন বুট হয়েই আছে
        monkeypatch.setattr(dbs, "_engine_instance", _SeveredEngine())

        # ── ধাপ ১: ভাঙা ইঞ্জিনে সৎ degraded সংকেত ───────────────────────────
        assert await check_engine_health() is False
        assert await _check_database() == "unhealthy"

        ready = await client.get("/api/v1/ready")
        assert ready.status_code == 503
        assert "not ready" in ready.json()["detail"]

        # /api/v1/health লিগ্যাসি অ্যালায়েস দ্বারা আচ্ছাদিত (core health রাউটার),
        # তাই গভীর স্বাস্থ্য পরীক্ষার দ্ব্যর্থহীন পথ হলো /api/v1/deep।
        deep = await client.get("/api/v1/deep")
        assert deep.status_code == 503
        deep_body = deep.json()
        assert deep_body["status"] != "healthy"
        assert deep_body["persistence_mode"] == "unavailable"
        assert deep_body["services"]["database"]["status"] == "unhealthy"

        # ── ধাপ ২: সহনশীল role — ডিগ্রেডেশন নীরব নয়, দৃশ্যমান ও সৎ ─────────
        monkeypatch.setenv("SUPREMEAI_SERVICE_ROLE", "worker")
        tolerated = await client.get("/api/v1/ready")
        assert tolerated.status_code == 200
        tolerated_body = tolerated.json()
        assert tolerated_body["status"] == "degraded"
        assert tolerated_body["persistence_mode"] == "unavailable"
        assert tolerated_body["readiness_policy"]["decision"] == "role-tolerated"

        # ── ধাপ ৩: রিকভারি — ইঞ্জিন ফিরলেই সংকেত সুস্থ (আটকে-থাকা ক্যাশ নেই) ──
        monkeypatch.setattr(dbs, "_engine_instance", real_engine)
        monkeypatch.delenv("SUPREMEAI_SERVICE_ROLE", raising=False)

        assert await check_engine_health() is True
        assert await _check_database() == "healthy"

        recovered = await client.get("/api/v1/ready")
        assert recovered.status_code == 200
        recovered_body = recovered.json()
        assert recovered_body["status"] == "ok"
        assert recovered_body["persistence_mode"] == "healthy"
