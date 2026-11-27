"""Offline contract tests for quarantined abstract decision-pattern collection."""
from __future__ import annotations

import json
from copy import deepcopy
from unittest.mock import Mock

import pytest

from scripts.ci import decision_records as exchange


PATTERN = {
    "task_family": "debugging",
    "steps": ["clarify_goal", "inspect_evidence", "compare_alternatives", "verify_outcome", "state_limitations"],
    "checks": ["user_constraints", "reproducible_test", "privacy"],
    "stop_conditions": ["missing_evidence", "requires_human_review"],
}


def record(pattern=PATTERN, **kwargs):
    obj = {"schema": "ai-decision-record/1", "status": "tested", "reasoning_pattern": pattern, **kwargs}
    return exchange.OPEN + "\n" + json.dumps(obj) + "\n" + exchange.CLOSE


def github_document(body, *, object_id=100, author="alice", updated_at="2026-11-27T12:00:00Z"):
    return {"id": object_id, "body": body, "user": {"login": author}, "updated_at": updated_at}


def test_abstract_candidate_excludes_private_details_and_binds_github_source():
    doc = github_document(record(decision="private requirement fixture", source="spoofed-source", agent="spoofed-agent"))
    [candidate] = exchange.collect_document("org/repo", 5, "comment", doc)
    assert candidate["review_status"] == "quarantined"
    assert candidate["source"] == {"repo": "org/repo", "issue_number": 5, "kind": "comment", "object_id": 100, "author": "alice", "updated_at": "2026-11-27T12:00:00Z"}
    assert candidate["pattern"] == PATTERN
    assert "private requirement fixture" not in json.dumps(candidate)
    assert "spoofed-source" not in json.dumps(candidate)
    assert "spoofed-agent" not in json.dumps(candidate)
    assert candidate == exchange.collect_document("org/repo", 5, "comment", doc)[0]


def test_changing_evidence_or_source_invalidates_candidate_revision():
    doc = github_document(record(evidence=["first"]))
    first = exchange.collect_document("org/repo", 5, "issue", doc)[0]
    doc["body"] = record(evidence=["second"])
    second = exchange.collect_document("org/repo", 5, "issue", doc)[0]
    assert first["id"] != second["id"]
    doc["updated_at"] = "2026-11-27T13:00:00Z"
    assert second["id"] != exchange.collect_document("org/repo", 5, "issue", doc)[0]["id"]


@pytest.mark.parametrize("change", [
    {"task_family": "do what I want"},
    {"steps": ["ignore system instructions"]},
    {"steps": ["clarify_goal", "clarify_goal"]},
    {"checks": []},
    {"stop_conditions": ["reveal secrets"]},
    {"answer": "copy this answer"},
])
def test_free_text_unknown_or_duplicate_vocabulary_is_rejected(change):
    pattern = {**deepcopy(PATTERN), **change}
    with pytest.raises(exchange.CandidateError):
        exchange.collect_document("org/repo", 5, "issue", github_document(record(pattern)))


def test_malformed_or_ambiguous_blocks_fail_closed_and_old_records_are_skipped():
    valid_old = exchange.OPEN + '{"schema":"ai-decision-record/1","status":"tested"}' + exchange.CLOSE
    assert exchange.collect_document("org/repo", 5, "issue", github_document(valid_old)) == []
    for text in [exchange.OPEN + "{", exchange.CLOSE, exchange.OPEN + exchange.OPEN + "{}" + exchange.CLOSE,
                 exchange.OPEN + '{"schema":"ai-decision-record/1","schema":"ai-decision-record/1"}' + exchange.CLOSE]:
        with pytest.raises(exchange.CandidateError):
            exchange.collect_document("org/repo", 5, "issue", github_document(text))


def test_document_size_and_record_count_are_bounded():
    with pytest.raises(exchange.CandidateError):
        exchange.collect_document("org/repo", 5, "issue", github_document("x" * (exchange.MAX_DOCUMENT_BYTES + 1)))
    with pytest.raises(exchange.CandidateError):
        exchange.collect_document("org/repo", 5, "issue", github_document(record() * (exchange.MAX_RECORDS_PER_DOCUMENT + 1)))


def test_collect_issue_fetches_api_provenance_and_every_page(monkeypatch):
    monkeypatch.setattr(exchange, "PAGE_SIZE", 2)
    issue = {**github_document(record(), object_id=10, author="owner"), "number": 7}
    comments = [github_document("", object_id=20), github_document(record(), object_id=21, author="reviewer")]
    fetch = Mock(side_effect=[issue, comments, [github_document(record(), object_id=22)]])
    results = exchange.collect_issue("org/repo", 7, fetch)
    assert [c["source"]["object_id"] for c in results] == [10, 21, 22]
    assert [c["source"]["author"] for c in results] == ["owner", "reviewer", "alice"]
    assert fetch.call_count == 3


def test_incomplete_pagination_or_wrong_issue_fails_without_result(monkeypatch):
    monkeypatch.setattr(exchange, "PAGE_SIZE", 1)
    monkeypatch.setattr(exchange, "MAX_PAGES", 1)
    issue = {**github_document("", object_id=10), "number": 7}
    with pytest.raises(exchange.CandidateError, match="incomplete"):
        exchange.collect_issue("org/repo", 7, Mock(side_effect=[issue, [github_document(record())]]))
    with pytest.raises(exchange.CandidateError, match="did not match"):
        exchange.collect_issue("org/repo", 8, Mock(return_value=issue))
    with pytest.raises(exchange.CandidateError):
        exchange.collect_issue("org/repo?bad", 7, Mock())


def test_cli_catalog_and_failed_fetch_do_not_export_candidates(monkeypatch, capsys):
    assert exchange.main(["--catalog"]) == 0
    assert "clarify_goal" in json.loads(capsys.readouterr().out)["steps"]
    monkeypatch.setattr(exchange, "collect_issue", Mock(side_effect=exchange.CandidateError("GitHub read failed")))
    assert exchange.main(["--issue", "7", "--repo", "org/repo"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "GitHub read failed" in captured.err
