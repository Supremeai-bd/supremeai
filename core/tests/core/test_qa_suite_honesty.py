"""Tests for the QA-suite honesty fixes (audit B-06, 2026-09-17).

Guards against regression to fabricated assurance:
* security checks must be explicitly UNVERIFIED (never random verdicts);
* integration checks must attempt REAL connections (fail on unreachable
  targets instead of always-True simulation);
* unit-test reporting must not fabricate always-passing mock cases;
* chaos experiments must be UNVERIFIED until real fault injection is wired;
* summary gates (`is_secure`, `system_resilient`) must stay False when the
  underlying checks are unverified.
"""

import pytest

from core.testing.qa_suite import (
    ChaosEngineer,
    IntegrationTestRunner,
    QASuite,
    SecurityTester,
)

# ---------------------------------------------------------------------------
# SecurityTester — no random verdicts, explicit unverified contract
# ---------------------------------------------------------------------------


def test_security_results_are_explicitly_unverified():
    tester = SecurityTester()
    sql = tester.test_sql_injection("http://t/api/search", "query")
    xss = tester.test_xss("http://t/api/echo", "message")
    auth = tester.test_auth_bypass("http://t/api/protected")
    for res in (sql, xss, auth):
        assert res["verified"] is False
        assert res["is_vulnerable"] is False
        assert res["status"] == "not_implemented"
        assert "UNVERIFIED" in res["note"]


def test_security_results_are_deterministic_not_random():
    tester = SecurityTester()
    # Two runs must produce identical results — the old random.choice verdicts
    # could flip between calls.
    assert tester.test_sql_injection("http://t/e", "q") == tester.test_sql_injection(
        "http://t/e", "q"
    )
    assert tester.test_xss("http://t/e", "m") == tester.test_xss("http://t/e", "m")
    assert tester.test_auth_bypass("http://t/e") == tester.test_auth_bypass("http://t/e")


# ---------------------------------------------------------------------------
# IntegrationTestRunner — real probes, honest failures
# ---------------------------------------------------------------------------


async def test_database_integration_fails_honestly_on_unreachable():
    runner = IntegrationTestRunner()
    result = await runner.test_database_integration(
        "postgresql://invalid-host-nonexistent:5432/nope"
    )
    assert result is False, "unreachable DB must report failure, not simulated success"


async def test_cache_integration_fails_honestly_on_unreachable():
    runner = IntegrationTestRunner()
    result = await runner.test_cache_integration("redis://invalid-host-nonexistent:6379/0")
    assert result is False, "unreachable Redis must report failure, not simulated success"


# ---------------------------------------------------------------------------
# QASuite aggregation — unverified checks can never yield PASS gates
# ---------------------------------------------------------------------------


async def test_unit_tests_report_unverified_not_fabricated_passes():
    suite = QASuite()
    unit = await suite._run_unit_tests()
    assert unit["verified"] is False
    assert unit["summary"]["pass_rate"] == 0.0
    assert unit["results"] == []
    assert "UNVERIFIED" in unit["note"]


async def test_security_gate_false_when_checks_unverified():
    suite = QASuite()
    security = await suite._run_security_tests("http://target.invalid")
    assert security["is_secure"] is False, (
        "unverified security checks must never produce is_secure=True"
    )


async def test_resilience_gate_false_when_experiments_unverified():
    suite = QASuite()
    chaos = await suite._run_chaos_tests("http://target.invalid")
    assert chaos["system_resilient"] is False, (
        "unverified chaos experiments must never produce system_resilient=True"
    )


# ---------------------------------------------------------------------------
# ChaosEngineer — unverified results, no pointless sleeps / busy-waits
# ---------------------------------------------------------------------------


async def test_chaos_experiments_unverified_and_fast():
    engineer = ChaosEngineer()
    import asyncio
    import time

    start = time.monotonic()
    latency = await engineer.inject_network_latency("http://t", 500, 30)
    cpu = await engineer.inject_cpu_spikes("http://t", 80, 30)
    memory = await engineer.inject_memory_pressure("http://t", 50, 30)
    elapsed = time.monotonic() - start

    assert elapsed < 5, "unverified experiments must not sleep/busy-wait for the duration"
    for exp in (latency, cpu, memory):
        assert exp["status"] == "not_implemented"
        assert exp["impact_observed"] is None
        assert exp["verified"] is False
        assert "UNVERIFIED" in exp["note"]
    await asyncio.sleep(0)  # keep async context explicit


def test_summary_overall_false_for_unverified_suite():
    suite = QASuite()
    results = {
        "unit_tests": {"summary": {"pass_rate": 0.0}},
        "integration_tests": {"all_passed": False},
        "performance_tests": {"is_performing_well": False},
        "security_tests": {"is_secure": False},
        "chaos_tests": {"system_resilient": False},
    }
    summary = suite._generate_summary(results)
    assert summary["overall_status"] is False
