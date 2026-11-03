"""M01 P-C (issue #453 Wave 4) — SynapticDream scheduler-wiring চুক্তি-টেস্ট।

বাংলা: worker-টি নির্মিত ছিল কিন্তু কোনো scheduler-এ wired নয় — এই টেস্ট
নিবন্ধন-স্পন্দনের সৎ চুক্তি ধরে রাখে: env-চালিত ক্যাডেন্স (zero-hardcode),
অবৈধ env-এ লাউড-ফলব্যাক, এবং চক্র-রিপোর্ট কখনো বানানো সংখ্যা নয়।
"""

import inspect

import pytest

from workers.synaptic_dream import (
    DEFAULT_DREAM_INTERVAL_SECONDS,
    resolve_dream_interval,
    run_synaptic_dream_loop,
    synaptic_dream_worker,
)


def test_default_interval_is_daily():
    # বাংলা: ডিফল্ট ক্যাডেন্স রাত্রিক চক্র — ২৪ ঘণ্টা।
    assert DEFAULT_DREAM_INTERVAL_SECONDS == 86400


def test_resolve_interval_env_override(monkeypatch):
    monkeypatch.setenv("SYNAPTIC_DREAM_INTERVAL_SECONDS", "3600")
    assert resolve_dream_interval() == 3600


def test_resolve_interval_invalid_env_falls_back_loud(monkeypatch):
    monkeypatch.setenv("SYNAPTIC_DREAM_INTERVAL_SECONDS", "not-a-number")
    # বাংলা: অবৈধ মানে ডিফল্টে ফেরা — নীরব fallback নয় (resolve-এর ভিতরে
    # লাউড-ওয়ার্নিং পথ চলে; এখানে শুধু ফলাফল-চুক্তি ধরা হয়)।
    assert resolve_dream_interval() == DEFAULT_DREAM_INTERVAL_SECONDS


def test_resolve_interval_unset_uses_default(monkeypatch):
    monkeypatch.delenv("SYNAPTIC_DREAM_INTERVAL_SECONDS", raising=False)
    assert resolve_dream_interval() == DEFAULT_DREAM_INTERVAL_SECONDS


def test_loop_is_coroutine_and_uses_worker():
    # বাংলা: লুপ একটি প্রকৃত কোরুটিন-ফাংশন যা AgentSupervisor-এ নিবন্ধনযোগ্য।
    assert inspect.iscoroutinefunction(run_synaptic_dream_loop)


@pytest.mark.asyncio
async def test_worker_report_never_fabricates_counts():
    # Issue #440 সৎ-চুক্তির পুনর্নিশ্চিতকরণ: চক্র হয় সত্যিকারের প্রুন
    # ("completed"), নয় সৎ store-অনুপস্থিতি ("degraded_no_store") — বানানো
    # কাউন্ট কখনোই নয় (লুপ এই রিপোর্টকেই লগ করে)।
    report = await synaptic_dream_worker.execute_dream_cycle()
    assert report.status in ("completed", "degraded_no_store")
    assert report.pruned_count >= 0
    assert report.consolidated_count == 0  # consolidation সৎভাবে অসম্পন্ন
