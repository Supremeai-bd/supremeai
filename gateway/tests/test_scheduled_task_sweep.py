"""M22 P-A tests — due-task sweep (core/scheduled_task_sweep.py).

বাংলা: plan-এর টেস্ট-প্রথম চুক্তি অনুযায়ী ত্রি-পথ (due/disabled/catch-up),
দ্বৈত-নির্বাহ-প্রতিরোধ (CAS), stale-দাবি পুনর্গ্রহ, custom-cron-এর সৎ অসমর্থন
এবং LLM-ব্যর্থতার সৎ রেকর্ড — সব ইন-মেমরি ফেক supabase client-এ যাচাই।
কোনো নেটওয়ার্ক নেই, কোনো ভুয়া সাফল্য নেই।
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import api.routes.scheduled_tasks as st_module
from core.scheduled_task_sweep import compute_due, sweep_due_tasks_once

# ---------------------------------------------------------------------------
# Fake supabase client (in-memory, supports only the surface the sweep uses)
# ---------------------------------------------------------------------------


class FakeResult:
    def __init__(self, data: list[dict[str, Any]]):
        self.data = data


class FakeQuery:
    def __init__(self, store: dict[str, list[dict[str, Any]]], table: str):
        self._store = store
        self._table = table
        self._op = "select"
        self._patch: dict[str, Any] | None = None
        self._insert_rows: list[dict[str, Any]] | None = None
        self._filters: list[tuple[str, str, Any]] = []

    # -- builder surface -----------------------------------------------------
    def select(self, *_cols: str) -> FakeQuery:
        self._op = "select"
        return self

    def insert(self, row: dict[str, Any]) -> FakeQuery:
        self._op = "insert"
        self._insert_rows = [row]
        return self

    def update(self, patch: dict[str, Any]) -> FakeQuery:
        self._op = "update"
        self._patch = patch
        return self

    def eq(self, column: str, value: Any) -> FakeQuery:
        self._filters.append(("eq", column, value))
        return self

    def is_(self, column: str, value: Any) -> FakeQuery:
        # postgrest-এর মতোই None → "null" (IS NULL)
        self._filters.append(("isnull", column, None))
        return self

    def order(self, *_args: Any, **_kwargs: Any) -> FakeQuery:
        return self

    def limit(self, *_args: Any) -> FakeQuery:
        return self

    def rpc(self, *_args: Any, **_kwargs: Any) -> FakeQuery:
        return self

    # -- execution -------------------------------------------------------------
    @staticmethod
    def _match(row: dict[str, Any], kind: str, column: str, value: Any) -> bool:
        if kind == "eq":
            return row.get(column) == value
        if kind == "isnull":
            return row.get(column) is None
        raise AssertionError(f"unknown filter kind {kind}")

    async def execute(self) -> FakeResult:
        rows = self._store.setdefault(self._table, [])
        if self._op == "insert":
            created: list[dict[str, Any]] = []
            for r in self._insert_rows or []:
                new_row = {"id": str(uuid.uuid4()), **r}
                rows.append(new_row)
                created.append(dict(new_row))
            return FakeResult(created)
        matched = [r for r in rows if all(self._match(r, k, c, v) for k, c, v in self._filters)]
        if self._op == "update":
            for r in matched:
                r.update(self._patch or {})
            return FakeResult([dict(r) for r in matched])
        return FakeResult([dict(r) for r in matched])


class FakeSupabaseClient:
    def __init__(self) -> None:
        self.store: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self.store, name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _task_row(
    *,
    schedule_type: str = "once",
    scheduled_time: str | None = None,
    is_active: bool = True,
    last_run_at: str | None = None,
    last_run_status: str | None = None,
    title: str = "t",
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "user_id": "user-1",
        "title": title,
        "prompt": "say hi",
        "schedule_type": schedule_type,
        "scheduled_time": scheduled_time,
        "cron_expression": "0 9 * * *" if schedule_type == "custom" else None,
        "conversation_id": None,
        "is_active": is_active,
        "last_run_at": last_run_at,
        "last_run_status": last_run_status,
        "created_at": _iso(datetime.now(UTC)),
        "updated_at": _iso(datetime.now(UTC)),
    }


@pytest.fixture
def fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeSupabaseClient:
    """সিঙ্গলটন supabase db-র client-কে ফেক দিয়ে বদলায় + schema-বুটস্ট্র্যাপ স্কিপ।"""
    fake = FakeSupabaseClient()
    monkeypatch.setattr(st_module.supabase_db, "client", fake, raising=False)
    monkeypatch.setattr(st_module, "_schema_bootstrapped", True)
    return fake


@pytest.fixture
def fast_llm(monkeypatch: pytest.MonkeyPatch):
    """LLM নির্বাহকে নিয়ন্ত্রিত ফলে বাঁধে — প্রকৃত gateway কল কোনোদিনও হবে না।"""

    async def _ok(prompt: str, user_id: str) -> str:
        return f"echo:{prompt}"

    monkeypatch.setattr(st_module, "_execute_task_prompt", _ok)
    return _ok


# ---------------------------------------------------------------------------
# Pure due-নির্ণয় (ত্রি-পথ)
# ---------------------------------------------------------------------------


def test_once_due_when_time_passed_and_never_ran() -> None:
    now = datetime.now(UTC)
    task = _task_row(schedule_type="once", scheduled_time=_iso(now - timedelta(hours=1)))
    assert compute_due(task, now) is True


def test_once_future_not_due() -> None:
    now = datetime.now(UTC)
    task = _task_row(schedule_type="once", scheduled_time=_iso(now + timedelta(hours=1)))
    assert compute_due(task, now) is False


def test_once_already_ran_not_due_again() -> None:
    now = datetime.now(UTC)
    task = _task_row(
        schedule_type="once",
        scheduled_time=_iso(now - timedelta(hours=2)),
        last_run_at=_iso(now - timedelta(hours=1)),
    )
    assert compute_due(task, now) is False


def test_disabled_task_never_due() -> None:
    now = datetime.now(UTC)
    task = _task_row(
        schedule_type="once", scheduled_time=_iso(now - timedelta(hours=1)), is_active=False
    )
    assert compute_due(task, now) is False


def test_daily_catchup_after_missed_slot() -> None:
    # বাংলা: গতকাল ০৯:০০-এ শেষ চলেছিল, আজকের স্লট পেরিয়ে গেছে → ক্যাচআপ due।
    now = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    yesterday_9am = now - timedelta(days=1)
    task = _task_row(
        schedule_type="daily",
        scheduled_time=_iso(yesterday_9am),
        last_run_at=_iso(yesterday_9am),
    )
    assert compute_due(task, now) is True


def test_daily_already_ran_this_slot_not_due() -> None:
    now = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    today_9am = now.replace(hour=9)
    task = _task_row(
        schedule_type="daily",
        scheduled_time=_iso(today_9am),
        last_run_at=_iso(today_9am + timedelta(minutes=5)),
    )
    assert compute_due(task, now) is False


def test_custom_cron_honestly_unsupported() -> None:
    now = datetime.now(UTC)
    task = _task_row(schedule_type="custom", scheduled_time=_iso(now - timedelta(hours=1)))
    assert compute_due(task, now) is None


# ---------------------------------------------------------------------------
# পূর্ণ sweep চক্র (ফেক DB-তে)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sweep_executes_due_once_task_and_consumes_it(fake_db, fast_llm) -> None:
    now = datetime.now(UTC)
    fake_db.store["scheduled_tasks"] = [
        _task_row(schedule_type="once", scheduled_time=_iso(now - timedelta(minutes=5)))
    ]
    stats = await sweep_due_tasks_once(now=now)
    assert stats["executed"] == 1
    assert stats["once_consumed"] == 1
    task_row = fake_db.store["scheduled_tasks"][0]
    assert task_row["is_active"] is False
    assert task_row["last_run_status"] == "success"
    execs = fake_db.store.get("scheduled_task_executions", [])
    assert len(execs) == 1 and execs[0]["status"] == "success"


@pytest.mark.asyncio
async def test_sweep_leaves_future_and_disabled_untouched(fake_db, fast_llm) -> None:
    now = datetime.now(UTC)
    fake_db.store["scheduled_tasks"] = [
        _task_row(schedule_type="once", scheduled_time=_iso(now + timedelta(hours=1))),
        _task_row(
            schedule_type="once",
            scheduled_time=_iso(now - timedelta(hours=1)),
            is_active=False,
        ),
    ]
    stats = await sweep_due_tasks_once(now=now)
    assert stats["due"] == 0 and stats["executed"] == 0
    assert fake_db.store.get("scheduled_task_executions", []) == []


@pytest.mark.asyncio
async def test_sweep_cas_prevents_double_execution(
    fake_db, fast_llm, monkeypatch: pytest.MonkeyPatch
) -> None:
    """রেস সিমুলেশন: select-এর পরে অন্য worker দাবি করে ফেললে CAS ব্যর্থ → আমরা বিরত।"""
    now = datetime.now(UTC)
    row = _task_row(schedule_type="once", scheduled_time=_iso(now - timedelta(minutes=5)))
    fake_db.store["scheduled_tasks"] = [row]

    original_execute = FakeQuery.execute

    def racing_execute(self: FakeQuery) -> Any:
        # বাংলা: select-ফল যাওয়ার পরপরই প্রতিযোগী worker-এর দাবি অনুকরণ —
        # update অপারেশনের আগে last_run_at বদলে দিলে আমাদের CAS-শর্ত মিলবে না।
        if self._op == "update" and self._table == "scheduled_tasks":
            for r in fake_db.store["scheduled_tasks"]:
                r["last_run_at"] = _iso(datetime.now(UTC))
        return original_execute(self)

    # monkeypatch-এ class-attribute প্যাচ — টেস্ট শেষে স্বয়ংক্রিয় পুনরুদ্ধার (leak নেই)।
    monkeypatch.setattr(FakeQuery, "execute", racing_execute)

    stats = await sweep_due_tasks_once(now=now)
    assert stats["claimed_by_other"] == 1
    assert stats["executed"] == 0
    assert fake_db.store.get("scheduled_task_executions", []) == []


@pytest.mark.asyncio
async def test_sweep_takes_over_stale_running_claim(fake_db, fast_llm) -> None:
    now = datetime.now(UTC)
    stale_ts = now - timedelta(seconds=3600)  # stale-সীমা (৯০০s) পেরিয়েছে
    fake_db.store["scheduled_tasks"] = [
        _task_row(
            schedule_type="once",
            scheduled_time=_iso(now - timedelta(hours=2)),
            last_run_at=_iso(stale_ts),
            last_run_status="running",
        )
    ]
    stats = await sweep_due_tasks_once(now=now)
    assert stats["stale_taken_over"] == 1
    assert stats["executed"] == 1


@pytest.mark.asyncio
async def test_sweep_skips_fresh_in_flight_claim(fake_db, fast_llm) -> None:
    now = datetime.now(UTC)
    fresh_ts = now - timedelta(seconds=30)  # stale-সীমার ভেতরে
    fake_db.store["scheduled_tasks"] = [
        _task_row(
            schedule_type="once",
            scheduled_time=_iso(now - timedelta(hours=2)),
            last_run_at=_iso(fresh_ts),
            last_run_status="running",
        )
    ]
    stats = await sweep_due_tasks_once(now=now)
    assert stats["in_flight"] == 1
    assert stats["due"] == 0 and stats["executed"] == 0


@pytest.mark.asyncio
async def test_sweep_counts_custom_tasks_unsupported_honestly(fake_db, fast_llm) -> None:
    now = datetime.now(UTC)
    fake_db.store["scheduled_tasks"] = [
        _task_row(schedule_type="custom", scheduled_time=_iso(now - timedelta(hours=1)))
    ]
    stats = await sweep_due_tasks_once(now=now)
    assert stats["unsupported_custom"] == 1
    assert stats["executed"] == 0
    assert fake_db.store["scheduled_tasks"][0]["last_run_status"] is None


@pytest.mark.asyncio
async def test_llm_failure_recorded_honestly(fake_db, monkeypatch: pytest.MonkeyPatch) -> None:
    """বাংলা: LLM ব্যর্থ হলে টাস্ক সৎভাবে failed হবে — ভুয়া success নয়, নীরব গিলে ফেলাও নয়।"""
    now = datetime.now(UTC)

    async def _boom(prompt: str, user_id: str) -> str:
        raise RuntimeError("gateway exploded")

    monkeypatch.setattr(st_module, "_execute_task_prompt", _boom)
    fake_db.store["scheduled_tasks"] = [
        _task_row(schedule_type="once", scheduled_time=_iso(now - timedelta(minutes=5)))
    ]
    stats = await sweep_due_tasks_once(now=now)
    assert stats["failed"] == 1
    assert stats["executed"] == 0
    task_row = fake_db.store["scheduled_tasks"][0]
    assert task_row["last_run_status"] == "failed"
    execs = fake_db.store.get("scheduled_task_executions", [])
    assert execs and "gateway exploded" in (execs[0].get("error") or "")


@pytest.mark.asyncio
async def test_sweep_reports_db_unavailable_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    """বাংলা: DB না থাকলে ভুয়া 'সব ঠিক' নয় — db_available=False সৎ রিপোর্ট।"""
    import database.supabase_client as db_module

    monkeypatch.setattr(db_module.db, "client", None, raising=False)
    stats = await sweep_due_tasks_once()
    assert stats["db_available"] is False
    assert stats["executed"] == 0


# ---------------------------------------------------------------------------
# M02 P-B (ERR-F01) — sweep নির্বাহ বাস্তব Run fabric-এ পর্যবেক্ষিত
# ---------------------------------------------------------------------------


def _make_sqlite_runs_ctx(monkeypatch):
    """বাস্তব RunService-এর সাথে in-memory sqlite runs fabric — integration সত্য।"""
    from sqlalchemy import event as sa_event
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from missions.models import Mission, MissionTraceEvent
    from models.base import Base
    from runs.models import Run, RunEvent

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    maker_holder = {}

    @asynccontextmanager
    async def fake_ctx():
        if not maker_holder:
            async with engine.begin() as conn:
                await conn.run_sync(
                    lambda sc: Base.metadata.create_all(
                        sc,
                        tables=[
                            Mission.__table__,
                            MissionTraceEvent.__table__,
                            Run.__table__,
                            RunEvent.__table__,
                        ],
                    )
                )
            maker_holder["maker"] = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
        async with maker_holder["maker"]() as session:
            yield session

    monkeypatch.setattr("database.session.get_db_session_context", fake_ctx)
    return engine, maker_holder


@pytest.mark.asyncio
async def test_sweep_execution_observed_as_run_in_real_fabric(fake_db, fast_llm, monkeypatch):
    from sqlalchemy import select

    from runs.models import Run

    engine, _holder = _make_sqlite_runs_ctx(monkeypatch)
    now = datetime.now(UTC)
    fake_db.store["scheduled_tasks"] = [
        _task_row(schedule_type="once", scheduled_time=_iso(now - timedelta(minutes=5)))
    ]
    task_id = fake_db.store["scheduled_tasks"][0]["id"]

    stats = await sweep_due_tasks_once(now=now)
    assert stats["executed"] == 1

    # একই context-factory ব্যবহার করে রান-সারি পড়া
    ctx = await _current_ctx()
    async with ctx() as session:
        rows = (await session.execute(select(Run).where(Run.source_ref == task_id))).scalars().all()
        assert len(rows) == 1
        run = rows[0]
        assert run.run_type == "agent"
        assert run.source_type == "scheduled_task"
        assert run.status == "succeeded"
        assert run.started_at is not None and run.terminal_at is not None


async def _current_ctx():
    import database.session as db_session_mod

    return db_session_mod.get_db_session_context


@pytest.mark.asyncio
async def test_run_observation_failure_does_not_block_execution(fake_db, fast_llm, monkeypatch):
    """বাংলা: observability ব্যর্থ হলেও টাস্ক চলে — কিন্তু লাউড-লগ, নীরব নয়।"""

    @asynccontextmanager
    async def broken_ctx():
        raise RuntimeError("runs fabric unavailable")
        yield  # pragma: no cover

    monkeypatch.setattr("database.session.get_db_session_context", broken_ctx)
    now = datetime.now(UTC)
    fake_db.store["scheduled_tasks"] = [
        _task_row(schedule_type="once", scheduled_time=_iso(now - timedelta(minutes=5)))
    ]
    stats = await sweep_due_tasks_once(now=now)
    assert stats["executed"] == 1  # টাস্ক বাস্তবেই চলেছে
