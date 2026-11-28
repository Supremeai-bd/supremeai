"""Offline tests for the Owner Action Queue guard (issue #966 protocol)."""

from __future__ import annotations

from scripts.ci.owner_action_queue_guard import lint_queue, self_test
from scripts.ci.owner_action_queue_guard import SELF_TEST_BODIES


def test_clean_queue_has_no_problems():
    assert lint_queue(SELF_TEST_BODIES["clean"]) == []


def test_duplicate_ids_are_flagged():
    problems = lint_queue(SELF_TEST_BODIES["duplicate_id"])
    assert any("duplicate task id OA-001" in p for p in problems)


def test_agent_marked_done_is_flagged():
    problems = lint_queue(SELF_TEST_BODIES["agent_marked_done"])
    assert any("done without done_by: admin" in p for p in problems)


def test_missing_marker_is_flagged():
    assert lint_queue(SELF_TEST_BODIES["no_marker"]) == ["missing marker: <!-- owner-action-queue v1 -->"]


def test_section_status_mismatch_is_flagged():
    body = (
        "<!-- owner-action-queue v1 -->\n"
        "### Pending\n"
        "- [ ] id: OA-010 | title: x | added_by: agent:x | date: 2026-11-28 | status: done\n"
        "<!-- /owner-action-queue v1 -->\n"
    )
    problems = lint_queue(body)
    assert any("sits in the Pending section" in p for p in problems)


def test_missing_required_fields_are_flagged():
    body = (
        "<!-- owner-action-queue v1 -->\n"
        "### Pending\n"
        "- [ ] id: OA-011 | status: pending\n"
        "<!-- /owner-action-queue v1 -->\n"
    )
    problems = lint_queue(body)
    for fragment in ("missing title", "missing added_by", "missing date"):
        assert any(fragment in p for p in problems)


def test_self_test_contract_holds():
    assert self_test() == 0


def test_entry_outside_marker_block_is_flagged():
    problems = lint_queue(SELF_TEST_BODIES["entry_outside_marker"])
    assert any("OUTSIDE the marker block" in p for p in problems)
