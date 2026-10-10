# backend/tests/core/test_proactive_health_guardian.py
"""#2706 (Gap-G) — Proactive Health Guardian পরীক্ষা।

বাংলা মন্তব্য: তিনটি সংযোগ-বিন্দুর regression lock:
১. PrecognitiveWatcher.scan_system_health() — ৬টি আসল মেট্রিক (কেবল
   circle_registry নয়) + bounded alert বাফার + status-অবজারভেবিলিটি;
২. Orchestrator (PeriodicTaskScheduler) — সুইপ-টাস্ক এখন production tick-এ
   শিডিউলড; anomaly হলে healer-cycle ব্রিজ হয়;
৩. AutoHealer.proactive_guardian_cycle() — anomaly → structured Issue →
   (critical+automatic হলে) AutoPRPipeline.create_patch_pr() আসল কল।
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services.auto_healer import AutoHealer, IssueCategory, Severity
from workers.precognitive_watcher import PrecognitiveWatcher, SentinelAlert


def _alert(severity: str = "warning", service: str = "test_svc", **kw) -> SentinelAlert:
    defaults = dict(
        alert_id="alert_t1",
        severity=severity,
        service=service,
        message="probe message",
        suggested_action="probe action",
    )
    defaults.update(kw)
    return SentinelAlert(**defaults)


# ═══════════════════════════════════════════════════════════════════════
# ১. Watcher — ৬-মেট্রিক সুইপ
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_scan_checks_at_least_five_real_metrics(monkeypatch):
    """প্রতিটি প্রোবকে anomaly-অবস্থায় চালিয়ে আলাদা alert আসে কি না যাচাই।"""
    watcher = PrecognitiveWatcher()

    # মেট্রিক ১: registry খালি
    import core.circles.registry as registry_mod

    monkeypatch.setattr(registry_mod.circle_registry, "manifests", lambda: [])

    # মেট্রিক ২: DLQ backlog critical
    import core.messaging.event_bus as bus_mod

    monkeypatch.setattr(
        bus_mod.error_event_bus,
        "stats",
        lambda: {"dlq_current_size": 250, "total_emitted": 900, "registered_listeners": 3},
    )

    # মেট্রিক ৩: 5xx error-rate critical
    import core.observability.metrics_registry as metrics_mod

    monkeypatch.setattr(
        metrics_mod,
        "get_window_metrics",
        lambda: {"window_seconds": 60, "error_rate": 33.3, "requests_in_window": 30},
    )

    # মেট্রিক ৪: latency p95 critical
    monkeypatch.setattr(metrics_mod.metrics_engine, "latency_history", [9.5] * 100, raising=False)

    # মেট্রিক ৫: একটি OPEN circuit breaker
    from core.resilience.circuit_breaker import CircuitBreakerState

    open_cb = SimpleNamespace(state=CircuitBreakerState.OPEN)
    monkeypatch.setattr(
        "services.auto_healer.get_healer",
        lambda: SimpleNamespace(circuit_breakers={"payments": open_cb}),
    )

    alerts = await watcher.scan_system_health()
    services_alerted = {a.service for a in alerts}
    # অন্তত ৫টি ভিন্ন মেট্রিক-সেবা থেকে alert এসেছে (CI প্রোব env-gated স্কিপ)
    assert len(services_alerted) >= 5, f"expected ≥5 metric services, got {services_alerted}"
    assert "circle_registry" in services_alerted
    assert "error_event_bus" in services_alerted
    assert "http_traffic" in services_alerted
    assert "latency" in services_alerted
    assert "circuit_breakers" in services_alerted


@pytest.mark.asyncio
async def test_scan_healthy_state_returns_no_alerts(monkeypatch):
    """সব মেট্রিক সুস্থ থাকলে কোনো ভান-alert নয় (Honesty over polish)।"""
    watcher = PrecognitiveWatcher()
    import core.circles.registry as registry_mod

    monkeypatch.setattr(registry_mod.circle_registry, "manifests", lambda: [object()] * 5)
    import core.messaging.event_bus as bus_mod

    monkeypatch.setattr(
        bus_mod.error_event_bus,
        "stats",
        lambda: {"dlq_current_size": 0, "total_emitted": 10, "registered_listeners": 2},
    )
    import core.observability.metrics_registry as metrics_mod

    monkeypatch.setattr(
        metrics_mod,
        "get_window_metrics",
        lambda: {"window_seconds": 60, "error_rate": 0.0, "requests_in_window": 50},
    )
    monkeypatch.setattr(metrics_mod.metrics_engine, "latency_history", [0.05] * 10, raising=False)
    monkeypatch.setattr(
        "services.auto_healer.get_healer",
        lambda: SimpleNamespace(circuit_breakers={}),
    )

    alerts = await watcher.scan_system_health()
    assert alerts == []
    assert watcher.get_status()["sweep_count"] == 1
    assert watcher.get_status()["last_sweep_at"] is not None


@pytest.mark.asyncio
async def test_alert_buffer_bounded():
    """alert-বাফার ৫০০-এ বাউন্ডেড — মেমরি-ব্লোট রোধ (Rule #2)।"""
    watcher = PrecognitiveWatcher()
    watcher._alerts = [
        SentinelAlert(
            alert_id=f"a{i}", severity="info", service="s", message="m", suggested_action="x"
        )
        for i in range(600)
    ]
    await watcher.scan_system_health()
    assert len(watcher._alerts) <= 500


@pytest.mark.asyncio
async def test_ci_probe_skips_without_env(monkeypatch):
    """GITHUB_TOKEN/REPOSITORY না থাকলে CI প্রোব সৎভাবে স্কিপ — কোনো ভান-সংখ্যা নয়।"""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    watcher = PrecognitiveWatcher()
    result = await watcher._probe_ci_red_count(12345)
    assert result is None


# ═══════════════════════════════════════════════════════════════════════
# ২. Scheduler — production-শিডিউলড সুইপ
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_orchestrator_schedules_precognitive_sweep():
    """_tasks তালিকায় সুইপ-টাস্ক এখন আছে — supervisor-চালিত tick-এ চলবে।"""
    from core.orchestration.periodic_task_scheduler import Orchestrator

    orch = Orchestrator()
    assert any(t.__name__ == "_run_precognitive_sweep" for t in orch._tasks), (
        "Precognitive sweep must be in the orchestrator tick task list (#2706)"
    )


@pytest.mark.asyncio
async def test_sweep_task_bridges_alerts_to_healer(monkeypatch):
    """alert থাকলে সুইপ-টাস্ক healer.proactive_guardian_cycle-কে ডাকে।"""
    from core.orchestration.periodic_task_scheduler import Orchestrator

    orch = Orchestrator()
    fake_alert = _alert(severity="critical")

    async def fake_scan():
        return [fake_alert]

    cycle_mock = AsyncMock(return_value={"prs_attempted": 0, "prs_opened": 0})

    import workers.precognitive_watcher as watcher_mod

    monkeypatch.setattr(watcher_mod.precognitive_watcher, "scan_system_health", fake_scan)
    monkeypatch.setattr(
        "services.auto_healer.get_healer",
        lambda: SimpleNamespace(proactive_guardian_cycle=cycle_mock),
    )

    await orch._run_precognitive_sweep()
    cycle_mock.assert_awaited_once()
    sent_alerts = cycle_mock.await_args.args[0]
    assert sent_alerts == [fake_alert]


@pytest.mark.asyncio
async def test_sweep_task_never_breaks_tick(monkeypatch):
    """সুইপ-ব্যর্থতা non-fatal — orchestrator tick চলতেই থাকবে (Rule #3)।"""
    from core.orchestration.periodic_task_scheduler import Orchestrator

    orch = Orchestrator()

    async def exploding_scan():
        raise RuntimeError("probe exploded")

    import workers.precognitive_watcher as watcher_mod

    monkeypatch.setattr(watcher_mod.precognitive_watcher, "scan_system_health", exploding_scan)

    # exception প্রোপাগেট করবে না — ভেতরেই গিলে যায়
    await orch._run_precognitive_sweep()


# ═══════════════════════════════════════════════════════════════════════
# ৩. Healer — proactive_guardian_cycle → AutoPRPipeline
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_guardian_cycle_records_issue_without_pr_for_warning():
    """warning anomaly → structured Issue হ্যাঁ, কিন্তু ভান-PR নয়।"""
    healer = AutoHealer()
    alert = _alert(severity="warning", service="error_event_bus", message="backlog growing")
    summary = await healer.proactive_guardian_cycle([alert])

    assert summary["alerts_received"] == 1
    assert summary["issues_created"] == 1
    assert summary["prs_attempted"] == 0
    assert healer.issue_history[-1].source == "precognitive_watcher"
    assert healer.stats["issues_detected"] == 1


@pytest.mark.asyncio
async def test_guardian_cycle_calls_auto_pr_pipeline_for_critical_automatic(monkeypatch):
    """critical + automatic-pattern anomaly → AutoPRPipeline.create_patch_pr আসল কল।"""
    healer = AutoHealer()
    # ERROR_PATTERNS-এর automatic=True deadlock-প্যাটার্ন — বার্তা ম্যাচ করতে হবে
    alert = _alert(
        severity="critical",
        service="database",
        message="deadlock detected: table locked during payment batch",
        suggested_action="Retry with backoff and close stale connections",
    )

    pipeline_mock = SimpleNamespace(
        create_patch_pr=AsyncMock(
            return_value={
                "status": "success",
                "pr_url": "https://github.com/x/pull/1",
                "pr_number": 1,
            }
        )
    )
    monkeypatch.setattr("tools.code.auto_pr_pipeline.AutoPRPipeline", lambda: pipeline_mock)

    summary = await healer.proactive_guardian_cycle([alert])

    pipeline_mock.create_patch_pr.assert_awaited_once()
    call_kwargs = pipeline_mock.create_patch_pr.await_args.kwargs
    assert call_kwargs["branch_name"].startswith("guardian/auto-fix-")
    assert "proactive" in call_kwargs["pr_title"]
    assert summary["prs_attempted"] == 1
    assert summary["prs_opened"] == 1
    assert summary["pr_urls"] == ["https://github.com/x/pull/1"]
    # issue resolved চিহ্নিত
    assert healer.issue_history[-1].resolved is True


@pytest.mark.asyncio
async def test_guardian_cycle_honest_when_token_missing(monkeypatch):
    """Token না থাকলে সৎ failed-স্ট্যাটাস — সাফল্যের ভান নয়।"""
    healer = AutoHealer()
    alert = _alert(
        severity="critical",
        service="database",
        message="deadlock detected: table locked during batch",
        suggested_action="Retry",
    )
    pipeline_mock = SimpleNamespace(
        create_patch_pr=AsyncMock(
            return_value={
                "status": "failed",
                "reason": "GitHub token not configured.",
                "pr_url": None,
            }
        )
    )
    monkeypatch.setattr("tools.code.auto_pr_pipeline.AutoPRPipeline", lambda: pipeline_mock)

    summary = await healer.proactive_guardian_cycle([alert])
    assert summary["prs_opened"] == 0
    assert any("token" in str(s.get("reason", "")) for s in summary["skipped"])


@pytest.mark.asyncio
async def test_guardian_cycle_isolates_per_alert_failure():
    """একটি alert প্রসেসিং ব্যর্থ হলেও বাকিগুলো প্রসেস হবে।"""

    class ExplodingAlert:
        alert_id = "boom"
        severity = "critical"
        service = "x"
        message = "database is locked"
        suggested_action = "y"

        # ইচ্ছাকৃতভাবে বিকৃত: message পড়ার সময় exception ছুড়বে
        @property
        def message(self):  # type: ignore[override]
            raise RuntimeError("malformed alert")

    good = _alert(severity="warning", service="ok_svc", message="fine")
    healer = AutoHealer()
    summary = await healer.proactive_guardian_cycle([ExplodingAlert(), good])

    assert summary["alerts_received"] == 2
    assert summary["issues_created"] == 1  # good alert প্রসেস হয়েছে
    assert any(s.get("reason", "").startswith("error") for s in summary["skipped"])


@pytest.mark.asyncio
async def test_guardian_cycle_dedups_recurring_anomaly():
    """একই anomaly বারবার এলে নতুন Issue নয় — occurrences বাড়ে।"""
    healer = AutoHealer()
    alert = _alert(severity="warning", service="latency", message="p95 high")
    await healer.proactive_guardian_cycle([alert])
    await healer.proactive_guardian_cycle([alert])

    assert len(healer.issue_history) == 1
    assert healer.issue_history[-1].occurrences == 2
