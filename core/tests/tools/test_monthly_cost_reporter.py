"""Tests for tools/billing/monthly_cost_reporter.py — MonthlyCostReporter.

The reporter aggregates real per-task cost rows from the local SQLite store
(``tools/data/supreme_memory.db``) and pushes a formatted summary to the
admin Telegram chat. Suites in this lineage use REAL boundary fakes only:
here the boundary is SQLite file location (redirected into tmp_path so tests
never touch the repository tree) and the Telegram HTTP client; everything
between — SQL aggregation, ISO-timestamp windowing, month-range arithmetic
(leap February, non-leap February, December year rollover), formatting and
credential gating — runs REAL.

Branch targets (coverage.py, 2 branches):
- ``"-" in month`` — both parse formats ("YYYY-MM" and "YYYYMM")
- ``not self.telegram_bot_token or not self.admin_chat_id`` — token-missing
  arm, chat-missing arm, and the both-set (False) arm
"""

from __future__ import annotations

import importlib
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

import tools.billing.monthly_cost_reporter as mcr_mod
from tools.billing.monthly_cost_reporter import MonthlyCostReporter

MODULE_NAME = "tools.billing.monthly_cost_reporter"


# ─────────────────────────────────────────────────────────────────────────────
# Fakes


class RecorderLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def info(self, msg: str, *a: Any, **k: Any) -> None:
        self.records.append(("info", msg))

    def warning(self, msg: str, *a: Any, **k: Any) -> None:
        self.records.append(("warning", msg))

    def error(self, msg: str, *a: Any, **k: Any) -> None:
        self.records.append(("error", msg))


class FakeAsyncClient:
    """Stands in for httpx.AsyncClient; records the outbound Telegram POST."""

    last_post: dict[str, Any] | None = None
    fail: bool = False

    def __init__(self, timeout: Any = None) -> None:
        FakeAsyncClient.init_timeout = timeout

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any]) -> None:
        if FakeAsyncClient.fail:
            raise RuntimeError("telegram unreachable")
        FakeAsyncClient.last_post = {"url": url, "json": json}


class FixedDateTime(datetime):
    """datetime subclass whose now() is pinned; strptime stays real."""

    @classmethod
    def now(cls, tz: Any = None) -> FixedDateTime:
        return cls(2026, 3, 15, 12, 0, 0, tzinfo=tz if tz is not None else UTC)


def load_module():
    return importlib.import_module(MODULE_NAME)


@pytest.fixture()
def reporter_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    mod = load_module()
    logger = RecorderLogger()
    monkeypatch.setattr(mod, "logger", logger)
    monkeypatch.setattr(mod, "datetime", FixedDateTime)
    # Settings credentials default to UNCONFIGURED for most tests.
    monkeypatch.setattr(mod, "settings", mod.settings, raising=False)
    monkeypatch.setattr("core.config.settings.admin_telegram_chat_id", "", raising=False)
    monkeypatch.setattr("core.config.settings.telegram_bot_token", "", raising=False)

    rep = MonthlyCostReporter()
    # Redirect the SQLite store into tmp_path (public attrs, documented).
    rep.data_dir = str(tmp_path / "data")
    rep.db_path = str(tmp_path / "data" / "supreme_memory.db")
    # Pre-provision the store so every test starts from a valid empty DB.
    _create_empty_tasks_table(rep.db_path)
    return {"mod": mod, "rep": rep, "logger": logger, "tmp": tmp_path}


def _seed_tasks(db_path: str, rows: list[tuple[str, float]]) -> None:
    import os as _os

    _os.makedirs(_os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS tasks (timestamp TEXT, cost REAL)")
    conn.executemany("INSERT INTO tasks (timestamp, cost) VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


def _create_empty_tasks_table(db_path: str) -> None:
    import os as _os

    _os.makedirs(_os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS tasks (timestamp TEXT, cost REAL)")
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Construction / connection


def test_init_paths_derived_from_module_location(monkeypatch) -> None:
    load_module()
    rep = MonthlyCostReporter()
    import os as _os

    import tools.billing as tools_pkg

    base = _os.path.dirname(_os.path.dirname(_os.path.abspath(tools_pkg.__file__)))
    assert rep.data_dir == _os.path.join(base, "data")
    assert rep.db_path == _os.path.join(base, "data", "supreme_memory.db")
    # Never defaults to configured credentials when settings lack them.
    assert rep.admin_chat_id == ""
    assert rep.telegram_bot_token == ""


def test_get_connection_creates_dir_and_row_factory(reporter_env) -> None:
    rep = reporter_env["rep"]
    conn = rep._get_connection()
    try:
        assert reporter_env["tmp"].joinpath("data").is_dir()
        assert conn.row_factory is sqlite3.Row
    finally:
        conn.close()


def test_settings_credentials_are_read_into_reporter(monkeypatch) -> None:
    load_module()
    monkeypatch.setattr("core.config.settings.admin_telegram_chat_id", "12345", raising=False)
    monkeypatch.setattr("core.config.settings.telegram_bot_token", "tok", raising=False)
    rep = MonthlyCostReporter()
    assert rep.admin_chat_id == "12345"
    assert rep.telegram_bot_token == "tok"


# ─────────────────────────────────────────────────────────────────────────────
# _month_range — REAL calendar arithmetic


def test_month_range_dash_format(reporter_env) -> None:
    start, end = reporter_env["rep"]._month_range("2026-03")
    assert start == datetime(2026, 3, 1)
    assert end == datetime(2026, 4, 1)


def test_month_range_compact_format(reporter_env) -> None:
    start, end = reporter_env["rep"]._month_range("202603")
    assert start == datetime(2026, 3, 1)
    assert end == datetime(2026, 4, 1)


def test_month_range_leap_february(reporter_env) -> None:
    start, end = reporter_env["rep"]._month_range("2024-02")
    assert start == datetime(2024, 2, 1)
    assert end == datetime(2024, 3, 1)  # 29-day Feb rolls correctly


def test_month_range_non_leap_february(reporter_env) -> None:
    start, end = reporter_env["rep"]._month_range("2025-02")
    assert start == datetime(2025, 2, 1)
    assert end == datetime(2025, 3, 1)


def test_month_range_december_year_rollover(reporter_env) -> None:
    start, end = reporter_env["rep"]._month_range("2026-12")
    assert start == datetime(2026, 12, 1)
    assert end == datetime(2027, 1, 1)


def test_month_range_30_and_31_day_months(reporter_env) -> None:
    rep = reporter_env["rep"]
    assert rep._month_range("2026-04")[1] == datetime(2026, 5, 1)
    assert rep._month_range("2026-08")[1] == datetime(2026, 9, 1)


def test_month_range_rejects_garbage(reporter_env) -> None:
    with pytest.raises(ValueError):
        reporter_env["rep"]._month_range("not-a-month")


# ─────────────────────────────────────────────────────────────────────────────
# generate_report — REAL SQLite aggregation


def test_generate_report_empty_database_yields_zeros(reporter_env) -> None:
    rep = reporter_env["rep"]
    _create_empty_tasks_table(rep.db_path)  # store provisioned, zero rows
    report = rep.generate_report("2026-03")
    assert report["month"] == "2026-03"
    assert report["total_cost_usd"] == 0.0
    assert report["total_calls"] == 0
    assert report["average_cost_per_call"] == 0.0
    assert report["period_start"] == "2026-03-01T00:00:00"
    assert report["period_end"] == "2026-04-01T00:00:00"
    # generated_at is pinned by FixedDateTime and ISO-parseable
    assert datetime.fromisoformat(report["generated_at"]) == datetime(
        2026, 3, 15, 12, 0, 0, tzinfo=UTC
    )


def test_generate_report_aggregates_only_in_window(reporter_env) -> None:
    rep = reporter_env["rep"]
    _seed_tasks(
        rep.db_path,
        [
            ("2026-03-01T10:00:00", 0.10),
            ("2026-03-15T10:00:00", 0.25),
            ("2026-03-31T23:59:59", 0.25),
            ("2026-02-28T23:59:59", 999.0),  # before window
            ("2026-04-01T00:00:00", 999.0),  # at/after end — excluded
        ],
    )
    report = rep.generate_report("2026-03")
    assert report["total_cost_usd"] == pytest.approx(0.6, abs=1e-9)
    assert report["total_calls"] == 3
    assert report["average_cost_per_call"] == pytest.approx(0.2, abs=1e-9)


def test_generate_report_rounds_to_four_decimals(reporter_env) -> None:
    rep = reporter_env["rep"]
    _seed_tasks(rep.db_path, [("2026-03-05T00:00:00", 0.123456)])
    report = rep.generate_report("2026-03")
    assert report["total_cost_usd"] == 0.1235
    assert report["average_cost_per_call"] == 0.1235


def test_generate_report_handles_null_costs(reporter_env) -> None:
    # SUM over NULL cost rows returns NULL -> the `row[0] or 0.0` guard applies.
    rep = reporter_env["rep"]
    conn = sqlite3.connect(rep.db_path)  # store pre-provisioned by fixture
    conn.execute("INSERT INTO tasks (timestamp, cost) VALUES ('2026-03-05T00:00:00', NULL)")
    conn.commit()
    conn.close()
    report = rep.generate_report("2026-03")
    assert report["total_cost_usd"] == 0.0
    assert report["total_calls"] == 1


def test_generate_report_compact_month_argument(reporter_env) -> None:
    rep = reporter_env["rep"]
    _seed_tasks(rep.db_path, [("2026-03-10T00:00:00", 2.0)])
    assert rep.generate_report("202603")["total_calls"] == 1


def test_generate_report_missing_table_raises(reporter_env, tmp_path) -> None:
    # An unprovisioned store (no table) — the reporter lets the operational
    # error surface (Anti-Silent-Failure): callers must provision first.
    rep = reporter_env["rep"]
    rep.db_path = str(tmp_path / "unprovisioned" / "none.db")
    with pytest.raises(sqlite3.OperationalError):
        rep.generate_report("2026-03")


# ─────────────────────────────────────────────────────────────────────────────
# send_to_admin — credential gating + Telegram delivery


async def test_send_skipped_when_token_missing(reporter_env) -> None:
    FakeAsyncClient.last_post = None
    _create_empty_tasks_table(reporter_env["rep"].db_path)
    report = reporter_env["rep"].generate_report("2026-03")
    ok = await reporter_env["rep"].send_to_admin(report)
    assert ok is False
    assert FakeAsyncClient.last_post is None
    assert any(
        "Telegram credentials not configured" in m for _, m in reporter_env["logger"].records
    )


async def test_send_skipped_when_chat_missing_but_token_set(reporter_env, monkeypatch) -> None:
    monkeypatch.setattr("core.config.settings.telegram_bot_token", "tok", raising=False)
    rep = reporter_env["rep"]
    rep.admin_chat_id = ""
    report = rep.generate_report("2026-03")
    FakeAsyncClient.last_post = None
    assert await rep.send_to_admin(report) is False
    assert FakeAsyncClient.last_post is None


async def test_send_posts_formatted_report(reporter_env, monkeypatch) -> None:
    rep = reporter_env["rep"]
    rep.admin_chat_id = "555"
    rep.telegram_bot_token = "SECRET"
    _seed_tasks(rep.db_path, [("2026-03-05T00:00:00", 1.5), ("2026-03-06T00:00:00", 0.5)])
    report = rep.generate_report("2026-03")
    FakeAsyncClient.last_post = None
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    ok = await rep.send_to_admin(report)
    assert ok is True
    posted = FakeAsyncClient.last_post
    assert posted is not None
    assert posted["url"] == "https://api.telegram.org/botSECRET/sendMessage"
    assert posted["json"]["chat_id"] == "555"
    text = posted["json"]["text"]
    assert "Monthly Cost Report - 2026-03" in text
    assert "Total cost: $2.0000" in text
    assert "Total calls: 2" in text
    assert "Avg cost/call: $1.0000" in text


async def test_send_failure_is_reported_not_raised(reporter_env, monkeypatch) -> None:
    rep = reporter_env["rep"]
    rep.admin_chat_id = "555"
    rep.telegram_bot_token = "SECRET"
    report = rep.generate_report("2026-03")
    FakeAsyncClient.fail = True
    FakeAsyncClient.last_post = None
    try:
        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
        ok = await rep.send_to_admin(report)
    finally:
        FakeAsyncClient.fail = False
    assert ok is False
    assert any("Failed to send monthly cost report" in m for _, m in reporter_env["logger"].records)


async def test_send_timeout_is_configured_at_ten_seconds(reporter_env, monkeypatch) -> None:
    # Contract lock: the Telegram client must not hang longer than 10s.
    rep = reporter_env["rep"]
    rep.admin_chat_id = "555"
    rep.telegram_bot_token = "SECRET"
    report = rep.generate_report("2026-03")
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    await rep.send_to_admin(report)
    assert FakeAsyncClient.init_timeout == 10.0


# ─────────────────────────────────────────────────────────────────────────────
# schedule_monthly


def test_schedule_monthly_logs_next_month_run(reporter_env) -> None:
    reporter_env["rep"].schedule_monthly()
    infos = [m for lvl, m in reporter_env["logger"].records if lvl == "info"]
    assert any("2026-04-01T00:00:00" in m for m in infos)
    assert any("Monthly cost run scheduled" in m for m in infos)


def test_module_loads_and_exports_class() -> None:
    mod = load_module()
    assert hasattr(mod, "MonthlyCostReporter")
