"""Full-coverage tests for services/auto_healer.py (Task 7-d).

Covers CircuitBreaker state machine, RetryPolicy backoff, diagnosis pattern
matching, auto-fix dispatch (with subprocess fully mocked), the auto_heal
decorator (breaker open / retries / fallback), reports and singletons.
All sleeps are patched out — the whole module runs in well under a second.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import services.auto_healer as ah

REAL_SLEEP = asyncio.sleep  # un-mocked reference (autouse fixture patches asyncio.sleep)
from core.resilience.circuit_breaker import CircuitBreakerState
from services.auto_healer import (
    AutoHealer,
    CircuitBreaker,
    FixResult,
    Issue,
    IssueCategory,
    RetryPolicy,
    Severity,
    get_healer,
)


def _issue(**kw) -> Issue:
    defaults = dict(
        id="i-1",
        category=IssueCategory.RATE_LIMIT,
        severity=Severity.MEDIUM,
        title="Rate Limited",
        description="429",
        source="test",
        suggested_fix="backoff",
        fix_confidence=0.9,
        automatic=True,
    )
    defaults.update(kw)
    return Issue(**defaults)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Never actually sleep — auto_healer's retries use asyncio.sleep."""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    yield


class TestEnumsAndDataclasses:
    def test_severity_and_categories(self):
        assert Severity.CRITICAL.value == "critical"
        assert IssueCategory.RATE_LIMIT.value == "rate_limit"
        assert IssueCategory.UNKNOWN.value == "unknown"

    def test_issue_to_dict(self):
        d = _issue().to_dict()
        assert d["category"] == "rate_limit"
        assert d["severity"] == "medium"
        assert d["automatic"] is True
        assert d["occurrences"] == 1
        assert d["resolved"] is False

    def test_fix_result_defaults(self):
        fr = FixResult(success=True, issue_id="x", fix_applied="f", message="m")
        assert fr.rollback_available is False
        assert fr.timestamp is not None


class TestCircuitBreaker:
    def test_closed_allows(self):
        cb = CircuitBreaker("t", failure_threshold=2)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.can_execute() is True

    def test_opens_after_threshold_and_blocks(self):
        cb = CircuitBreaker("t", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_execute() is False

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker("t", failure_threshold=1, recovery_timeout=30)
        cb.record_failure()
        assert cb.can_execute() is False
        cb.last_failure_time = cb.last_failure_time - 60  # age past timeout
        assert cb.can_execute() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_half_open_allows_limited_calls(self):
        cb = CircuitBreaker("t", failure_threshold=1, half_open_max_calls=2)
        cb.state = CircuitBreakerState.HALF_OPEN
        assert cb.can_execute() is True
        assert cb.can_execute() is True
        assert cb.can_execute() is False  # exhausted

    def test_record_success_closes_from_half_open(self):
        cb = CircuitBreaker("t", failure_threshold=1, half_open_max_calls=2)
        cb.state = CircuitBreakerState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitBreakerState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_record_success_decrements_failure_count(self):
        cb = CircuitBreaker("t")
        cb.failure_count = 5
        cb.record_success()
        assert cb.failure_count == 4

    def test_record_failure_from_half_open_reopens(self):
        cb = CircuitBreaker("t")
        cb.state = CircuitBreakerState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_no_transition_log_when_already_open(self):
        cb = CircuitBreaker("t", failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        cb.record_failure()  # already open, no state change
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 2

    def test_status_property(self):
        cb = CircuitBreaker("t", failure_threshold=7)
        status = cb.status
        assert status["name"] == "t"
        assert status["threshold"] == 7
        assert status["state"] == CircuitBreakerState.CLOSED


class TestRetryPolicy:
    def test_delay_is_capped(self):
        rp = RetryPolicy(base_delay=10, max_delay=15, exponential_base=2, jitter=False)
        assert rp.get_delay(10) == 15

    def test_delay_exponential(self):
        rp = RetryPolicy(base_delay=1, max_delay=100, exponential_base=2, jitter=False)
        assert rp.get_delay(0) == 1
        assert rp.get_delay(3) == 8

    def test_jitter_varies_delay(self):
        rp = RetryPolicy(base_delay=1, max_delay=100, exponential_base=2, jitter=True)
        delays = {rp.get_delay(0) for _ in range(20)}
        assert len(delays) > 1  # random jitter produces multiple values
        assert all(0.5 <= d <= 2.0 for d in delays)


class TestDiagnose:
    def test_unknown_error(self):
        healer = AutoHealer()
        issue = healer.diagnose(ValueError("totally novel failure"), source="unit")
        assert issue.category == IssueCategory.UNKNOWN
        assert issue.severity == Severity.MEDIUM
        assert issue.suggested_fix is None
        assert issue.fix_confidence == 0.0
        assert healer.stats["issues_detected"] == 1

    def test_rate_limit_pattern(self):
        healer = AutoHealer()
        issue = healer.diagnose(RuntimeError("429 Too Many Requests"), source="api")
        assert issue.category == IssueCategory.RATE_LIMIT
        assert issue.automatic is True
        assert issue.fix_confidence == 0.95

    def test_timeout_pattern(self):
        healer = AutoHealer()
        issue = healer.diagnose(TimeoutError("Request timed out"))
        assert issue.category == IssueCategory.TIMEOUT

    def test_dependency_pattern(self):
        # diagnose() matches on str(error); the DEPENDENCY regex requires the
        # "ModuleNotFoundError:"/"ImportError:" prefix inside the message.
        healer = AutoHealer()
        issue = healer.diagnose(ImportError("ImportError: No module named 'requests'"))
        assert issue.category == IssueCategory.DEPENDENCY

    def test_environment_pattern(self):
        healer = AutoHealer()
        issue = healer.diagnose(ValueError("Missing environment variable: API_KEY"))
        assert issue.category == IssueCategory.ENVIRONMENT
        assert issue.automatic is False

    def test_occurrence_counting_merges_similar(self):
        healer = AutoHealer()
        i1 = healer.diagnose(RuntimeError("429 too many requests"))
        i2 = healer.diagnose(RuntimeError("429 too many requests"))
        assert i1 is i2
        assert i2.occurrences == 2
        assert len(healer.issue_history) == 1
        assert i2.stack_trace is not None

    def test_context_stored(self):
        healer = AutoHealer()
        issue = healer.diagnose(ValueError("x"), context={"endpoint": "/a"})
        assert issue.context == {"endpoint": "/a"}


class TestAutoFix:
    async def test_manual_issue_not_attempted(self):
        healer = AutoHealer()
        issue = _issue(automatic=False, suggested_fix="do it by hand")
        result = await healer.auto_fix(issue)
        assert result.success is False
        assert "manual fix" in result.message
        assert healer.stats["issues_manual_required"] == 1

    async def test_no_suggested_fix(self):
        healer = AutoHealer()
        issue = _issue(automatic=True, suggested_fix=None)
        result = await healer.auto_fix(issue)
        assert result.success is False
        assert result.message == "No automatic fix available"

    async def test_rate_limit_fix(self):
        healer = AutoHealer()
        issue = _issue(category=IssueCategory.RATE_LIMIT)
        result = await healer.auto_fix(issue)
        assert result.success is True
        # #2708: সত্য ক্রিয়া-বর্ণনা — মিথ্যা "cache_ttl_reduced" স্টাব সরানো হয়েছে
        assert result.fix_applied in ("cache_validated_backoff_armed", "retry_with_backoff")
        assert issue.resolved is True
        assert healer.stats["issues_auto_fixed"] == 1

    async def test_timeout_fix(self):
        healer = AutoHealer()
        issue = _issue(category=IssueCategory.TIMEOUT)
        result = await healer.auto_fix(issue)
        assert result.success is True
        # #2708: স্টাব আর নেই — বাস্তব RetryPolicy hardening হয়
        assert result.fix_applied == "retry_policy_hardened"
        assert issue.source in healer.retry_policies

    async def test_database_lock_fix(self):
        healer = AutoHealer()
        issue = _issue(category=IssueCategory.DATABASE)
        result = await healer.auto_fix(issue)
        assert result.success is True
        assert result.fix_applied == "retry_with_backoff"

    async def test_unhandled_category(self):
        healer = AutoHealer()
        issue = _issue(category=IssueCategory.MEMORY)
        result = await healer.auto_fix(issue)
        assert result.success is False
        assert "No auto-fix implemented" in result.message

    async def test_dependency_fix_success(self):
        healer = AutoHealer()
        issue = _issue(category=IssueCategory.DEPENDENCY, description="No module named 'left-pad'")

        proc = SimpleNamespace(returncode=0)
        communicate = AsyncMock(return_value=(b"out", b""))
        proc.communicate = communicate
        with patch.object(asyncio, "create_subprocess_shell", new=AsyncMock(return_value=proc)):
            result = await healer.auto_fix(issue)
        assert result.success is True
        assert result.fix_applied == "installed_left-pad"

    async def test_dependency_fix_failure(self):
        healer = AutoHealer()
        issue = _issue(category=IssueCategory.DEPENDENCY, description="No module named 'left-pad'")

        proc = SimpleNamespace(returncode=1)
        proc.communicate = AsyncMock(return_value=(b"", b"err output"))
        with patch.object(asyncio, "create_subprocess_shell", new=AsyncMock(return_value=proc)):
            result = await healer.auto_fix(issue)
        assert result.success is False
        assert result.fix_applied == "install_failed"
        assert "err output" in result.message

    async def test_dependency_fix_subprocess_error(self):
        healer = AutoHealer()
        issue = _issue(category=IssueCategory.DEPENDENCY, description="No module named 'x'")
        with patch.object(
            asyncio, "create_subprocess_shell", new=AsyncMock(side_effect=RuntimeError("no shell"))
        ):
            result = await healer.auto_fix(issue)
        assert result.success is False
        assert result.fix_applied == "install_error"

    async def test_dependency_fix_unknown_package(self):
        healer = AutoHealer()
        issue = _issue(category=IssueCategory.DEPENDENCY, description="nothing quoted here")
        result = await healer.auto_fix(issue)
        assert result.fix_applied == "unknown_package"

    async def test_fix_exception_captured(self):
        healer = AutoHealer()
        issue = _issue(category=IssueCategory.TIMEOUT)
        with patch.object(
            healer, "_fix_timeout", new=AsyncMock(side_effect=RuntimeError("kaboom"))
        ):
            result = await healer.auto_fix(issue)
        assert result.success is False
        assert result.fix_applied == "error"
        assert "kaboom" in result.message


class TestAutoHealDecorator:
    async def test_success_first_try(self):
        healer = AutoHealer()

        @healer.auto_heal(circuit_breaker="svc", retry_policy="rp")
        async def ok_fn():
            return "value"

        assert await ok_fn() == "value"
        assert healer.get_circuit_breaker("svc").failure_count == 0

    async def test_retries_then_succeeds(self):
        healer = AutoHealer()
        calls = {"n": 0}

        @healer.auto_heal()
        async def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("429 too many requests")
            return "finally"

        assert await flaky() == "finally"
        assert calls["n"] == 3
        assert healer.stats["issues_detected"] >= 2

    async def test_exhausted_retries_raise_last_error(self):
        healer = AutoHealer()

        @healer.auto_heal(retry_policy="quick")
        async def always_fails():
            raise ValueError("nope")

        with pytest.raises(ValueError, match="nope"):
            await always_fails()

    async def test_exhausted_retries_use_fallback(self):
        healer = AutoHealer()

        async def fallback(*a, **kw):
            return "fallback-result"

        @healer.auto_heal(fallback_fn=fallback)
        async def always_fails():
            raise ValueError("nope")

        assert await always_fails() == "fallback-result"

    async def test_open_breaker_uses_fallback(self):
        healer = AutoHealer()
        cb = healer.get_circuit_breaker("open-svc", failure_threshold=1)
        cb.record_failure()  # OPEN now

        async def fallback():
            return "from-fallback"

        executed = {"called": False}

        @healer.auto_heal(circuit_breaker="open-svc", fallback_fn=fallback)
        async def never_called():
            executed["called"] = True
            return "no"

        assert await never_called() == "from-fallback"
        assert executed["called"] is False

    async def test_open_breaker_without_fallback_raises(self):
        healer = AutoHealer()
        cb = healer.get_circuit_breaker("open-svc2", failure_threshold=1)
        cb.record_failure()

        @healer.auto_heal(circuit_breaker="open-svc2")
        async def blocked():
            return "no"

        with pytest.raises(Exception, match="Circuit breaker"):
            await blocked()

    async def test_auto_fix_attempted_on_last_retry(self):
        healer = AutoHealer()
        calls = {"n": 0}

        @healer.auto_heal()
        async def rate_limited():
            calls["n"] += 1
            raise RuntimeError("429 again")

        async def fallback(*a, **kw):
            return "fb"

        wrapped = healer.auto_heal(fallback_fn=fallback)(rate_limited)
        assert await wrapped() == "fb"
        assert any(f.fix_applied != "none" for f in healer.fix_history)


class TestMonitoringLoop:
    async def test_start_and_stop_monitoring(self):
        # NOTE: the autouse _no_sleep fixture turns asyncio.sleep into an
        # instantly-returning AsyncMock. A real monitoring task would then
        # become a never-yielding busy loop, so this test temporarily installs
        # a real-yielding sleep and drives the loop deterministically.
        healer = AutoHealer()

        async def _yield_sleep(_delay):
            await REAL_SLEEP(0)

        with patch.object(ah.asyncio, "sleep", side_effect=_yield_sleep):
            task = asyncio.create_task(healer.start_monitoring(interval_seconds=0.01))
            await REAL_SLEEP(0.02)  # yield to let the loop tick at least once
            assert healer._monitoring is True
            healer.stop_monitoring()
            await asyncio.wait_for(task, timeout=5)
        assert healer._monitoring is False

    async def test_monitoring_cancellation_breaks_loop(self):
        # CancelledError inside the loop must break it cleanly (not raise).
        healer = AutoHealer()

        async def _cancelling_sleep(_delay):
            raise asyncio.CancelledError

        with patch.object(ah.asyncio, "sleep", side_effect=_cancelling_sleep):
            task = asyncio.create_task(healer.start_monitoring(interval_seconds=5))
            await asyncio.wait_for(task, timeout=5)
        # loop exited via the CancelledError branch
        assert task.done() and not task.cancelled()


class TestRegistryAndReports:
    def test_get_circuit_breaker_and_retry_policy_cached(self):
        healer = AutoHealer()
        cb1 = healer.get_circuit_breaker("n", failure_threshold=9)
        cb2 = healer.get_circuit_breaker("n")
        assert cb1 is cb2 and cb1.failure_threshold == 9
        rp1 = healer.get_retry_policy("r", max_retries=2)
        rp2 = healer.get_retry_policy("r")
        assert rp1 is rp2 and rp1.max_retries == 2

    def test_generate_report_shape(self):
        healer = AutoHealer()
        healer.diagnose(RuntimeError("429 too many requests"))
        healer.diagnose(TimeoutError("timed out"))
        report = healer.generate_report()
        assert report["summary"]["total_issues"] == 2
        assert report["summary"]["unresolved"] == 2
        assert report["summary"]["auto_fixable"] == 2
        assert report["last_hour"]["count"] == 2
        assert report["last_24h"]["count"] == 2
        assert "recent_issues" in report
        assert isinstance(report["last_hour"]["by_severity"], dict)

    def test_count_helpers(self):
        healer = AutoHealer()
        i1 = _issue(severity=Severity.HIGH, category=IssueCategory.TIMEOUT)
        i2 = _issue(severity=Severity.HIGH, category=IssueCategory.TIMEOUT)
        assert healer._count_by_severity([i1, i2]) == {"high": 2}
        assert healer._count_by_category([i1, i2]) == {"timeout": 2}

    def test_singletons(self):
        assert AutoHealer.get_instance() is AutoHealer.get_instance()
        assert get_healer() is get_healer()
