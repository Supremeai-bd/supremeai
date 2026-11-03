"""Full-coverage tests for core/monitoring.py (Task 7-d).

Covers MetricsCollector (requests/alerts/percentiles/prometheus export),
monitor_request decorator, request_context, BudgetMonitor thresholds and
singletons. No threads/loops are started by this module; tests are pure.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import core.monitoring as mon
from core.monitoring import (
    Alert,
    AlertSeverity,
    BudgetMonitor,
    MetricsCollector,
    RequestMetrics,
    SystemHealth,
    get_budget_monitor,
    get_metrics_collector,
    monitor_request,
    request_context,
)


def _metric(**kw) -> RequestMetrics:
    defaults = dict(
        request_id="r1",
        method="GET",
        path="/api/x",
        status_code=200,
        duration_ms=12.0,
    )
    defaults.update(kw)
    return RequestMetrics(**defaults)


@pytest.fixture()
def collector():
    return MetricsCollector()


class TestDataclasses:
    def test_alert_defaults(self):
        a = Alert(id="a", severity=AlertSeverity.INFO, source="s", title="t", message="m")
        assert a.resolved is False and a.resolved_at is None and a.metadata == {}

    def test_request_metrics_defaults(self):
        m = _metric()
        assert m.cache_hit is False and m.tokens_used == 0 and m.error is None

    def test_system_health(self):
        h = SystemHealth(
            overall_status="healthy",
            components={},
            uptime_seconds=1.0,
            total_requests=0,
            errors_5m=0,
            avg_response_time_ms=0.0,
            cache_stats={},
            active_alerts=0,
        )
        assert h.overall_status == "healthy"
        assert isinstance(h.last_check, datetime)


class TestMetricsCollector:
    def test_record_request_counters_and_cache(self, collector):
        collector.record_request(_metric(cache_hit=True, estimated_cost_usd=0.5, tokens_used=120))
        collector.record_request(_metric(method="POST", status_code=500))
        with collector._lock:
            c = dict(collector._counters)
        assert c["requests_total"] == 2
        assert c["requests_GET"] == 1 and c["requests_POST"] == 1
        assert c["status_200"] == 1 and c["status_500"] == 1
        assert c["cache_hits"] == 1 and c["cache_misses"] == 1
        assert c["errors_total"] == 1
        assert collector._gauges["llm_total_cost_usd"] == pytest.approx(0.5)
        assert c["llm_tokens_total"] == 120

    def test_create_alert_logs_by_severity(self, collector):
        for sev in (
            AlertSeverity.INFO,
            AlertSeverity.WARNING,
            AlertSeverity.CRITICAL,
            AlertSeverity.EMERGENCY,
        ):
            alert = collector.create_alert(sev, "src", f"title-{sev.value}", "msg", k=1)
            assert alert.severity == sev and alert.metadata == {"k": 1}
        assert len(collector.get_active_alerts()) == 4
        with collector._lock:
            counters = dict(collector._counters)
        assert counters["alerts_emergency"] == 1

    def test_resolve_alert(self, collector):
        alert = collector.create_alert(AlertSeverity.WARNING, "s", "t", "m")
        assert collector.resolve_alert(alert.id) is True
        assert collector.resolve_alert(alert.id) is False  # already resolved
        assert collector.resolve_alert("nope") is False
        assert collector.get_active_alerts() == []

    def test_get_recent_requests_sorted_and_filtered(self, collector):
        old = _metric(request_id="old")
        old.timestamp = datetime.utcnow() - timedelta(minutes=10)
        new = _metric(request_id="new")
        collector._requests = [old, new]
        recent = collector.get_recent_requests(limit=10)
        assert [r.request_id for r in recent] == ["new"]
        assert collector.get_recent_requests(limit=0) == []

    def test_percentiles(self, collector):
        assert collector.get_percentile("missing", 0.5) == 0.0
        # KNOWN BUG (current behavior): the interpolation index `c = f + 1` is
        # never clamped, so ANY list where k lands exactly on the last index
        # (single value, or percentile=1.0) raises IndexError.
        collector._histograms["m"] = [10.0]
        with pytest.raises(IndexError):
            collector.get_percentile("m", 0.5)
        collector._histograms["m"] = [1.0, 2.0, 3.0, 4.0]
        # interpolation between index 1 and 2 at p50 works
        assert collector.get_percentile("m", 0.5) == pytest.approx(2.5)
        with pytest.raises(IndexError):
            collector.get_percentile("m", 1.0)

    def test_summary_and_prometheus(self, collector):
        collector.record_request(_metric(status_code=500, duration_ms=100.0))
        collector.record_request(_metric(cache_hit=True, duration_ms=50.0))
        summary = collector.get_summary()
        assert summary["total_requests"] == 2
        assert summary["total_errors"] == 1
        assert summary["error_rate"] == pytest.approx(50.0)
        assert summary["cache_hit_rate"] == pytest.approx(50.0)
        assert summary["response_time_p50_ms"] > 0
        assert summary["active_alerts"] == 0

        text = collector.export_prometheus()
        assert "superai_requests_total 2" in text
        assert "superai_errors_total 1" in text
        assert "superai_cache_hit_rate 50.00" in text
        assert "superai_uptime_seconds" in text
        assert 'p50="' in text

    def test_cleanup_old_metrics(self, collector):
        old = _metric(request_id="old")
        old.timestamp = datetime.utcnow() - timedelta(minutes=30)
        collector._requests = [old, _metric(request_id="new")]
        collector.cleanup_old_metrics()
        assert [r.request_id for r in collector._requests] == ["new"]
        # KNOWN BUG (current behavior): the histogram-trim branch writes to the
        # misspelled `self._histagrams` attribute → AttributeError at runtime.
        collector._histograms["response_time_ms"] = [1.0] * 1001
        with pytest.raises(AttributeError):
            collector.cleanup_old_metrics()


class TestSingleton:
    def test_get_metrics_collector_singleton(self, monkeypatch):
        monkeypatch.setattr(mon, "_collector", None)
        c1 = get_metrics_collector()
        c2 = get_metrics_collector()
        assert c1 is c2 and isinstance(c1, MetricsCollector)


class TestMonitorRequestDecorator:
    async def test_success_records_metrics(self, collector, monkeypatch):
        monkeypatch.setattr(mon, "_collector", collector)
        request = SimpleNamespace(
            method="POST",
            url=SimpleNamespace(path="/api/chat"),
            client=SimpleNamespace(host="1.2.3.4"),
            headers={"user-agent": "ua"},
        )

        @monitor_request()
        async def handler(req):
            return SimpleNamespace(status_code=201)

        result = await handler(request)
        assert result.status_code == 201
        assert collector._counters["requests_total"] == 1
        assert collector._counters["status_201"] == 1
        rec = collector._requests[0]
        assert rec.path == "/api/chat" and rec.method == "POST"
        assert rec.ip_address == "1.2.3.4" and rec.user_agent == "ua"

    async def test_exception_records_500_and_reraises(self, collector, monkeypatch):
        monkeypatch.setattr(mon, "_collector", collector)

        @monitor_request()
        async def handler(request):
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await handler(None)
        rec = collector._requests[0]
        assert rec.status_code == 500 and rec.error == "boom"
        assert rec.method == "UNKNOWN" and rec.path == "/unknown"

    async def test_no_request_object(self, collector, monkeypatch):
        monkeypatch.setattr(mon, "_collector", collector)

        @monitor_request()
        async def handler():
            return "ok"

        assert await handler() == "ok"
        assert collector._requests[0].method == "UNKNOWN"


class TestRequestContext:
    def test_correlation_id_added_and_restored(self):
        old_factory = logging.getLogRecordFactory()
        with request_context("req-42") as ctx:
            assert ctx == {"request_id": "req-42"}
            factory = logging.getLogRecordFactory()
            record = factory("n", logging.INFO, "p", 1, "m", (), None)
            assert record.correlation_id == "req-42"
        # restored
        record2 = old_factory("n", logging.INFO, "p", 1, "m", (), None)
        assert not hasattr(record2, "correlation_id")
        assert logging.getLogRecordFactory() is old_factory

    def test_generated_request_id(self):
        with request_context() as ctx:
            assert len(ctx["request_id"]) == 8


class TestBudgetMonitor:
    def test_record_spend_below_threshold(self, collector, monkeypatch):
        monkeypatch.setattr(mon, "_collector", collector)
        bm = BudgetMonitor(daily_budget_usd=10.0, alert_threshold=0.7)
        status = bm.record_spend(1.0, provider="openai")
        assert status == {"spend": 1.0, "budget": 10.0, "percentage": 10.0, "remaining": 9.0}
        assert collector.get_active_alerts() == []

    def test_record_spend_warning_threshold_alerts_once(self, collector, monkeypatch):
        monkeypatch.setattr(mon, "_collector", collector)
        bm = BudgetMonitor(daily_budget_usd=10.0, alert_threshold=0.7)
        bm.record_spend(7.5)  # 75% → warning
        bm.record_spend(0.5)  # 80% → no duplicate warning
        warnings = [a for a in collector._alerts if a.severity == AlertSeverity.WARNING]
        assert len(warnings) == 1
        assert "Approaching" in warnings[0].title

    def test_record_spend_exceeded_alerts_once(self, collector, monkeypatch):
        monkeypatch.setattr(mon, "_collector", collector)
        bm = BudgetMonitor(daily_budget_usd=10.0, alert_threshold=0.7)
        out = bm.record_spend(12.0)  # 120% → critical
        assert out["remaining"] == 0
        critical = [a for a in collector._alerts if a.severity == AlertSeverity.CRITICAL]
        assert len(critical) == 1
        bm.record_spend(5.0)  # still no second critical
        critical = [a for a in collector._alerts if a.severity == AlertSeverity.CRITICAL]
        assert len(critical) == 1

    def test_zero_budget_percentage_zero(self, collector, monkeypatch):
        monkeypatch.setattr(mon, "_collector", collector)
        bm = BudgetMonitor(daily_budget_usd=0.0)
        status = bm.record_spend(5.0)
        assert status["percentage"] == 0

    def test_midnight_reset(self, collector, monkeypatch):
        monkeypatch.setattr(mon, "_collector", collector)
        bm = BudgetMonitor(daily_budget_usd=10.0)
        bm._daily_spend = 9.0
        bm._alerts_sent.add("budget_exceeded")
        bm._reset_time = datetime.utcnow() - timedelta(seconds=1)
        bm._check_reset()
        assert bm._daily_spend == 0.0
        assert bm._alerts_sent == set()
        assert bm._reset_time > datetime.utcnow()

    def test_get_status(self, collector, monkeypatch):
        monkeypatch.setattr(mon, "_collector", collector)
        bm = BudgetMonitor(daily_budget_usd=8.0, alert_threshold=0.5)
        bm._daily_spend = 2.0
        s = bm.get_status()
        assert s["daily_budget_usd"] == 8.0
        assert s["percentage_used"] == 25.0
        assert s["remaining_usd"] == 6.0
        assert s["alert_threshold"] == 50.0
        assert "resets_at" in s

    def test_get_budget_monitor_singleton(self, monkeypatch):
        monkeypatch.setattr(mon, "_budget_monitor", None)
        monkeypatch.setenv("DAILY_BUDGET_USD", "25.5")
        monkeypatch.setenv("BUDGET_ALERT_THRESHOLD", "0.9")
        bm = get_budget_monitor()
        assert bm.daily_budget == 25.5
        assert bm.alert_threshold == pytest.approx(0.9)
        assert get_budget_monitor() is bm
