"""#2681 Finding 2 — health_aggregation schema-drift probe টেস্ট।

বাংলা মন্তব্য: প্রোবের ৪টি অবস্থা (ok/drift/error/skipped) + TTL ক্যাশ +
remediation ইভেন্ট emit (spam-guard সহ) + recovery ইভেন্ট যাচাই।
Session factory injectable, তাই কোনো আসল DB লাগে না।
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from api.routes.health_aggregation import (
    SchemaDriftStatus,
    _fingerprint_rows,
    probe_schema_drift,
)


def _reset_state() -> None:
    """বাংলা মন্তব্য: মডিউল-লেভেল স্টেট প্রতি টেস্টে ফ্রেশ করা — টেস্ট আইসোলেশন।"""
    import api.routes.health_aggregation as ha

    ha._schema_state.update(
        baseline=None,
        fingerprint=None,
        status="skipped",
        tables=0,
        columns=0,
        detail="",
        probed_at=0.0,
        alert_key=None,
    )


class _FakeResult:
    """বাংলা মন্তব্য: SQLAlchemy result-এর Minimal fetchall মক।"""

    def __init__(self, rows: list[tuple]):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSession:
    """বাংলা মন্তব্য: dialect-aware fake session — sqlite/postgresql উভয় পথ পরীক্ষাযোগ্য।"""

    def __init__(self, dialect: str, script: dict[str, list[tuple]]):
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect))
        self._script = script
        self.queries: list[str] = []

    async def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        if sql in self._script:
            return _FakeResult(self._script[sql])
        raise AssertionError(f"unexpected SQL in fake session: {sql[:80]}")


def _factory(script_by_dialect: dict[str, dict]):
    """বাংলা মন্তব্য: প্রতি কলে নতুন session — প্রোবের session_factory ইনজেকশনের জন্য।"""
    state = {"calls": 0}

    def _make_factory():
        async def _session_cm():
            state["calls"] += 1
            dialect, script = next(iter(script_by_dialect.items()))
            return _FakeSession(dialect, script)

            # unreachable — async context manager প্যাটার্ন

        class _CM:
            async def __aenter__(self):
                return await _session_cm()

            async def __aexit__(self, *exc):
                return False

        return _CM

    # বাংলা মন্তব্য: _make_factory নিজেই (call করে নয়) return — টেস্ট factory() করে class পায়।
    return _make_factory, state


def test_fingerprint_rows_deterministic_and_order_insensitive():
    """#2681: একই স্কিমা (ভিন্ন সারি-ক্রমে) → একই ফিঙ্গারপ্রিন্ট; বদলালে ভিন্ন।"""
    rows_a = [("users", "id", "INTEGER"), ("users", "name", "TEXT"), ("events", "ts", "TIMESTAMP")]
    rows_b = list(reversed(rows_a))
    assert _fingerprint_rows(rows_a) == _fingerprint_rows(rows_b)
    changed = rows_a + [("users", "email", "TEXT")]
    assert _fingerprint_rows(rows_a) != _fingerprint_rows(changed)


@pytest.mark.asyncio
async def test_probe_first_success_sets_baseline_ok():
    """#2681: প্রথম সফল প্রোব = baseline; একই স্কিমা পরেও = ok।"""
    _reset_state()
    sqlite_script = {
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'": [
            ("users",)
        ],
        'PRAGMA table_info("users")': [
            (0, "id", "INTEGER", 0, None, 1),
            (1, "name", "TEXT", 0, None, 0),
        ],
    }
    factory, _state = _factory({"sqlite": sqlite_script})

    first = await probe_schema_drift(force=True, session_factory=factory())
    assert first.status == "ok"
    assert first.fingerprint == first.baseline_fingerprint
    assert first.tables == 1
    assert first.columns == 2

    second = await probe_schema_drift(force=True, session_factory=factory())
    assert second.status == "ok"
    assert second.fingerprint == first.fingerprint


@pytest.mark.asyncio
async def test_probe_detects_drift_and_emits_event_once():
    """#2681: schema বদলালে drift + ERROR ইভেন্ট ঠিক একবার (spam-guard)।"""
    _reset_state()
    base_script = {
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'": [
            ("users",)
        ],
        'PRAGMA table_info("users")': [(0, "id", "INTEGER", 0, None, 1)],
    }
    drifted_script = {
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'": [
            ("users",)
        ],
        'PRAGMA table_info("users")': [
            (0, "id", "INTEGER", 0, None, 1),
            (1, "email", "TEXT", 0, None, 0),
        ],
    }

    with patch("core.messaging.event_bus.error_event_bus.emit") as mock_emit:
        ok = await probe_schema_drift(
            force=True, session_factory=_factory({"sqlite": base_script})[0]()
        )
        assert ok.status == "ok"
        assert not mock_emit.called

        drifted = await probe_schema_drift(
            force=True, session_factory=_factory({"sqlite": drifted_script})[0]()
        )
        assert drifted.status == "drift"
        assert drifted.fingerprint != drifted.baseline_fingerprint
        assert mock_emit.call_count == 1
        emitted = mock_emit.call_args[0][0]
        assert emitted.error_type == "SCHEMA_DRIFT"
        assert emitted.severity == "ERROR"
        assert "connection-pool recycle" in emitted.context["remediation"]

        # বাংলা মন্তব্য: একই drift-অবস্থা পুনরায় প্রোব করলে আবার emit হবে না।
        again = await probe_schema_drift(
            force=True, session_factory=_factory({"sqlite": drifted_script})[0]()
        )
        assert again.status == "drift"
        assert mock_emit.call_count == 1


@pytest.mark.asyncio
async def test_probe_recovery_emits_resolved_event():
    """#2681: drift থেকে baseline-এ ফিরলে resolved=True INFO ইভেন্ট।"""
    _reset_state()
    base_script = {
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'": [("t",)],
        'PRAGMA table_info("t")': [(0, "id", "INTEGER", 0, None, 1)],
    }
    drifted_script = {
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'": [("t",)],
        'PRAGMA table_info("t")': [(0, "id", "INTEGER", 0, None, 1), (1, "x", "TEXT", 0, None, 0)],
    }

    with patch("core.messaging.event_bus.error_event_bus.emit") as mock_emit:
        await probe_schema_drift(force=True, session_factory=_factory({"sqlite": base_script})[0]())
        await probe_schema_drift(
            force=True, session_factory=_factory({"sqlite": drifted_script})[0]()
        )
        assert mock_emit.call_count == 1  # drift-ইভেন্ট

        recovered = await probe_schema_drift(
            force=True, session_factory=_factory({"sqlite": base_script})[0]()
        )
        assert recovered.status == "ok"
        assert mock_emit.call_count == 2
        resolved_event = mock_emit.call_args_list[1][0][0]
        assert resolved_event.resolved is True
        assert resolved_event.severity == "INFO"


@pytest.mark.asyncio
async def test_probe_error_path_never_raises():
    """#2681: DB নেমা থাকলে status=error — এন্ডপয়েন্ট বা প্রোব কখনো crash করে না।"""

    def _broken_factory():
        async def _boom():
            raise ConnectionError("db down")

            # unreachable

        class _CM:
            async def __aenter__(self):
                return await _boom()

            async def __aexit__(self, *exc):
                return False

        return _CM  # বাংলা মন্তব্য: class — probe নিজে instance বানাবে

    _reset_state()
    with patch("core.messaging.event_bus.error_event_bus.emit") as mock_emit:
        result = await probe_schema_drift(force=True, session_factory=_broken_factory())
        assert result.status == "error"
        assert "db down" in result.detail
        assert mock_emit.call_count == 1
        assert mock_emit.call_args[0][0].error_type == "SCHEMA_PROBE_FAILED"


@pytest.mark.asyncio
async def test_probe_unsupported_dialect_skipped():
    """#2681: অজানা dialect → skipped (এজেন্ট-মক dialect দিয়ে)।"""
    _reset_state()

    def _odd_factory():
        class _CM:
            async def __aenter__(self):
                return _FakeSession("mysql", {})

            async def __aexit__(self, *exc):
                return False

        return _CM  # বাংলা মন্তব্য: class — probe নিজে instance বানাবে

    result = await probe_schema_drift(force=True, session_factory=_odd_factory())
    assert result.status == "skipped"
    assert "unsupported dialect" in result.detail


@pytest.mark.asyncio
async def test_probe_ttl_cache_avoids_reprobe():
    """#2681: TTL উইন্ডোর ভেতরে দ্বিতীয় কল আসল DB প্রোব করে না (সস্তা)।"""
    _reset_state()
    sqlite_script = {
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'": [("t",)],
        'PRAGMA table_info("t")': [(0, "id", "INTEGER", 0, None, 1)],
    }
    factory, state = _factory({"sqlite": sqlite_script})

    await probe_schema_drift(force=True, session_factory=factory())
    assert state["calls"] == 1

    cached = await probe_schema_drift(session_factory=factory())  # force=False
    assert state["calls"] == 1  # বাংলা মন্তব্য: নতুন session খোলা হয়নি — ক্যাশ হিট।
    assert cached.status == "ok"


@pytest.mark.asyncio
async def test_postgresql_path_uses_information_schema():
    """#2681: postgres dialect এক কুয়েরিতে information_schema মারে (cheap probe)।"""
    from api.routes.health_aggregation import _collect_schema_rows

    pg_script = {
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
        "ORDER BY table_name, column_name": [
            ("users", "id", "integer"),
            ("users", "email", "text"),
        ],
    }
    session = _FakeSession("postgresql", pg_script)
    # বাংলা মন্তব্য: asyncio.get_event_loop() sync-টেস্টে CI-python-এ ভাঙে —
    # native await-ই নিরাপদ (pytest-asyncio AUTO)।
    rows = await _collect_schema_rows(session)
    assert rows == [("users", "id", "integer"), ("users", "email", "text")]


def test_schema_drift_status_model_defaults():
    """#2681: response মডেলের optional ফিল্ড — backward-compat নিশ্চিত।"""
    s = SchemaDriftStatus(status="ok")
    assert s.fingerprint is None
    assert s.tables == 0
    # বাংলা মন্তব্য: HealthAggregationResponse-এ schema_drift=None ডিফল্ট —
    # পুরনো কনস্ট্রাক্টর-কলগুলো ভাঙে না।
    from api.routes.health_aggregation import HealthAggregationResponse

    assert "schema_drift" in HealthAggregationResponse.model_fields
