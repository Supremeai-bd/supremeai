"""#2708 — AutoHealer: real timeout fixer + persistent healing history.

Locked contracts:
- `_fix_timeout` performs a REAL, verifiable state change (RetryPolicy
  hardening, capped) — no more lying "increased_timeout" string.
- `_fix_rate_limit` reports honestly what it actually did.
- `auto_fix` persists each issue+fix pair to the canonical memory writer
  (fail-soft — persistence failure never breaks the healing path).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.auto_healer import AutoHealer, Issue, IssueCategory, RetryPolicy, Severity


def _issue(**kw) -> Issue:
    defaults = dict(
        id="i-2708",
        category=IssueCategory.TIMEOUT,
        severity=Severity.MEDIUM,
        title="Upstream timeout",
        description="Request timed out after 10s",
        source="svc-alpha",
        suggested_fix="harden retries",
        fix_confidence=0.9,
        automatic=True,
    )
    defaults.update(kw)
    return Issue(**defaults)


@pytest.mark.asyncio
async def test_fix_timeout_hardens_retry_policy_for_real():
    """বাংলা মন্তব্য: ফিক্সটি এখন যাচাইযোগ্য state-change — নতুন policy তৈরি হয়।"""
    healer = AutoHealer()
    assert "svc-alpha" not in healer.retry_policies

    result = await healer._fix_timeout(_issue())
    assert result.success is True
    assert result.fix_applied == "retry_policy_hardened"

    policy = healer.retry_policies["svc-alpha"]
    assert isinstance(policy, RetryPolicy)
    assert policy.max_retries == 4  # ৩ → ৪
    assert policy.max_delay == 60.0  # ৩০ → ৬০
    assert "svc-alpha" in result.message and "max_retries=4" in result.message


@pytest.mark.asyncio
async def test_fix_timeout_hardening_is_capped():
    """বারবার একই ইস্যু → ক্যাপ (retries≤৬, delay≤১২০) — রানঅ্যাওয়ে নিষিদ্ধ।"""
    healer = AutoHealer()
    for _ in range(6):
        await healer._fix_timeout(_issue())
    policy = healer.retry_policies["svc-alpha"]
    assert policy.max_retries == 6
    assert policy.max_delay == 120.0


@pytest.mark.asyncio
async def test_fix_timeout_different_sources_get_own_policies():
    healer = AutoHealer()
    await healer._fix_timeout(_issue(source="svc-a"))
    await healer._fix_timeout(_issue(source="svc-b"))
    assert set(healer.retry_policies) == {"svc-a", "svc-b"}


@pytest.mark.asyncio
async def test_fix_rate_limit_honest_report():
    """'Reduced cache TTL' মিথ্যা আর নেই — সত্য ক্রিয়া বর্ণনা করে।"""
    healer = AutoHealer()
    issue = _issue(
        category=IssueCategory.RATE_LIMIT,
        title="429 storm",
        description="429 Too Many Requests",
    )
    result = await healer._fix_rate_limit(issue)
    assert result.success is True
    assert result.fix_applied in ("cache_validated_backoff_armed", "retry_with_backoff")
    assert "Reduced cache TTL" not in result.message


@pytest.mark.asyncio
async def test_auto_fix_persists_healing_history():
    """auto_fix → canonical memory writer-এ issue+fix paired event যায়।"""
    healer = AutoHealer()
    mock_save = AsyncMock(return_value={"success": True, "id": "mem-1"})
    with patch("services.memory_service.save_healing_event", mock_save):
        result = await healer.auto_fix(_issue())

    assert result.success is True
    mock_save.assert_awaited_once()
    kw = mock_save.await_args.kwargs
    assert kw["component"] == "svc-alpha"
    assert kw["category"] == "timeout"
    assert kw["fix_applied"] == "retry_policy_hardened"
    assert kw["success"] is True


@pytest.mark.asyncio
async def test_auto_fix_persist_failure_is_fail_soft():
    """persist ব্যর্থ হলেও auto_fix-এর ফলাফল অক্ষত (healing পথ ভাঙে না)।"""
    healer = AutoHealer()
    mock_save = AsyncMock(side_effect=RuntimeError("memory store down"))
    with patch("services.memory_service.save_healing_event", mock_save):
        result = await healer.auto_fix(_issue())
    assert result.success is True
    assert result.fix_applied == "retry_policy_hardened"
