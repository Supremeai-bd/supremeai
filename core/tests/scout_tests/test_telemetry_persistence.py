"""M08 P-C + P-D — provider-সত্য ও telemetry-persistence চুক্তি-টেস্ট।

বাংলা: ddgs প্যাকেজ এখন pyproject-ঘোষিত (provider-1 পথ মৃত নয়);
CrawlerTelemetry.emit_event প্রতিটি ইভেন্ট crawl_events-এ persist করে
(fire-and-forget — ক্রলার-নির্বাহ কখনো ব্লক নয়); loop-অনুপস্থিতে লাউড।
"""

from __future__ import annotations

import asyncio

import pytest

from scout.models import CrawlEventType
from scout.telemetry import _PENDING_PERSIST_TASKS, CrawlerTelemetry


def test_ddgs_provider_available_when_declared():
    """P-C: pyproject-ঘোষিত ddgs প্যাকেজ থাকলে client তৈরি হয় (provider-1 জীবন্ত)।"""
    from core.search import _ddgs_client

    pytest.importorskip("ddgs")
    client = _ddgs_client()
    assert client is not None


def test_web_search_unavailable_returns_empty_not_crash(monkeypatch):
    """P-C সৎ-চুক্তি: provider অনুপস্থিত/ব্যর্থ → খালি তালিকা + লাউড-লগ, ক্র্যাশ নয়।"""
    from core import search as core_search

    monkeypatch.setattr(core_search, "_ddgs_client", lambda: None)
    assert core_search.web_search("anything", max_results=3) == []


@pytest.mark.asyncio
async def test_emit_event_persists_via_record_event(monkeypatch):
    """P-D: emit_event → scout.persistence.record_event প্রোডাকশন-কল (সৎ মান)।"""
    captured: dict = {}

    async def fake_record_event(**kwargs):
        captured.update(kwargs)

    import scout.persistence as persistence

    monkeypatch.setattr(persistence, "record_event", fake_record_event)

    telemetry = CrawlerTelemetry(tenant_id="t1", task_id="task-9")
    telemetry.emit_event(
        CrawlEventType.NAV_START,
        "policy nav begin",
        severity="INFO",
        metadata={"url": "https://example.com"},
    )
    # fire-and-forget task শেষ হওয়া পর্যন্ত অপেক্ষা (দানাদার টেস্ট-সিঙ্ক)।
    for _ in range(50):
        if captured:
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.01)

    assert captured.get("tenant_id") == "t1"
    assert captured.get("task_id") == "task-9"
    assert captured.get("event_type") == CrawlEventType.NAV_START.value
    assert captured.get("message") == "policy nav begin"
    assert captured.get("metadata", {}).get("url") == "https://example.com"


@pytest.mark.asyncio
async def test_persist_failure_never_blocks_emit(monkeypatch):
    """P-D সৎ-ব্যর্থতা: record_event ব্যর্থ হলেও emit_event ব্যতিক্রম ছোঁড়ে না।"""

    async def boom(**kwargs):
        raise RuntimeError("store down")

    import scout.persistence as persistence

    monkeypatch.setattr(persistence, "record_event", boom)

    telemetry = CrawlerTelemetry(tenant_id="t1", task_id="task-9")
    # ব্যতিক্রম ছোঁড়বে না — persistence ব্যর্থতা লাউড-লগে, ক্রলার অপ্রভাবিত।
    telemetry.emit_event(CrawlEventType.NAV_COMPLETE, "nav done", severity="INFO")
    for task in list(_PENDING_PERSIST_TASKS):
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
        except Exception:
            break
