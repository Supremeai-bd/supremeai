"""M08 P-A — Deep Research two-sided SSE/history contract test.

বাংলা: ব্যাকএন্ড যা emit করে আর ফ্রন্টএন্ড (``DeepResearchPanel.tsx``) যা
parse করে — দুই পাশ এই এক চুক্তিতে বাঁধা। ভাঙলে issue #452-ধর্মী
"লাইভ স্টেপ/রিপোর্ট কখনো রেন্ডার হয় না" বা "Report not available"
নীরব-ভাঙা ফিরে আসবে — তাই প্রতিটি আকৃতি এখানে পিন করা।
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from api.routes.deep_research import (
    HISTORY_SELECT_COLUMNS,
    ResearchReport,
    ResearchStepEvent,
)

# ---------------------------------------------------------------------------
# 1) SSE "step" event — frontend reads: type, step(number), name, content
# ---------------------------------------------------------------------------


def test_step_event_schema_matches_frontend_parser() -> None:
    event = {
        "type": "step",
        "step": 1,
        "name": "Planning queries",
        "content": "Generated 3 follow-up queries",
    }
    parsed = ResearchStepEvent.model_validate(event)
    assert parsed.type == "step"
    assert parsed.step == 1
    assert parsed.name == "Planning queries"
    assert parsed.content == "Generated 3 follow-up queries"
    # Frontend guard: `event.type === 'step' && typeof event.step === 'number'`
    serialized = json.loads(parsed.model_dump_json())
    assert isinstance(serialized["step"], int)


# ---------------------------------------------------------------------------
# 2) SSE "report" event payload — frontend maps sections[].title→heading,
#    sources[].title/url, summary
# ---------------------------------------------------------------------------


def test_report_payload_matches_frontend_mapper() -> None:
    payload = {
        "title": "Report",
        "sections": [
            {"title": "Background", "content": "…", "sources": ["s1"]},
        ],
        "sources": [{"title": "Example", "url": "https://example.com"}],
        "summary": "It works",
    }
    report = ResearchReport.model_validate(payload)
    assert report.sections[0].title == "Background"
    assert report.sources[0]["url"] == "https://example.com"
    assert report.summary == "It works"


def test_report_payload_rejects_malformed_sections() -> None:
    with pytest.raises(ValidationError):
        ResearchReport.model_validate({"title": 1, "sections": "not-a-list"})


# ---------------------------------------------------------------------------
# 3) History select contract — the `report` column MUST be served so the
#    frontend ResearchHistoryItem.report hydrates (no dead history viewer).
# ---------------------------------------------------------------------------


def test_history_select_columns_include_report() -> None:
    columns = {c.strip() for c in HISTORY_SELECT_COLUMNS.split(",")}
    assert {"id", "query", "status", "created_at"} <= columns
    assert "report" in columns, (
        "GET /history অবশ্যই report কলাম দেবে — ফ্রন্টএন্ড ইতিহাস-ভিউয়ার "
        "এই ফিল্ড ছাড়া স্থায়ী 'Report not available' দেখায়"
    )
