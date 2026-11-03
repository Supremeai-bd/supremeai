from __future__ import annotations

from core.feedback_loop import FeedbackLoop


def test_record_edit():
    loop = FeedbackLoop()
    event = loop.record_edit("main.py", "added print statement")
    assert event["type"] == "edit"
    assert event["file"] == "main.py"
    assert event["diff"] == "added print statement"
    assert "timestamp" in event
    assert loop.metrics()["edits"] == 1


def test_record_suggestion_feedback_accepted():
    loop = FeedbackLoop()
    event = loop.record_suggestion_feedback(accepted=True, context={"task": "refactor"})
    assert event["type"] == "suggestion_feedback"
    assert event["accepted"] is True
    assert loop.metrics()["accepts"] == 1
    assert loop.events("suggestion_feedback") == [event]


def test_record_suggestion_feedback_rejected():
    loop = FeedbackLoop()
    event = loop.record_suggestion_feedback(accepted=False)
    assert event["accepted"] is False
    assert loop.metrics()["rejects"] == 1


def test_record_error_report():
    loop = FeedbackLoop()
    exc = ValueError("invalid input")
    event = loop.record_error_report(error=exc, context={"user": "admin"})
    assert event["type"] == "error"
    assert event["message"] == "invalid input"
    assert loop.metrics()["errors_reported"] == 1
    assert loop.events("error") == [event]


def test_metrics_returns_copy():
    loop = FeedbackLoop()
    metrics1 = loop.metrics()
    metrics1["edits"] = 9999
    metrics2 = loop.metrics()
    assert metrics2["edits"] == 0


def test_events_no_filter_returns_all():
    loop = FeedbackLoop()
    loop.record_edit("a.py", "edit a")
    loop.record_suggestion_feedback(accepted=True)
    loop.record_error_report(Exception("err"), {})
    all_events = loop.events()
    assert len(all_events) == 3


def test_events_filter_by_type():
    loop = FeedbackLoop()
    loop.record_edit("a.py", "edit a")
    loop.record_suggestion_feedback(accepted=True)
    loop.record_error_report(Exception("err"), {})
    edit_events = loop.events("edit")
    assert len(edit_events) == 1
    assert edit_events[0]["file"] == "a.py"


def test_events_filter_no_match():
    loop = FeedbackLoop()
    loop.record_edit("a.py", "edit a")
    result = loop.events("nonexistent")
    assert result == []


def test_handle_feedback_suggestion_accepted():
    loop = FeedbackLoop()
    payload = {"type": "suggestion_feedback", "accepted": True, "context": {"id": 1}}
    result = loop.handle_feedback(payload)
    assert result["stored"] is True
    assert result["event"]["accepted"] is True
    assert loop.metrics()["accepts"] == 1


def test_handle_feedback_suggestion_rejected_records_error():
    loop = FeedbackLoop()
    payload = {
        "type": "suggestion_feedback",
        "accepted": False,
        "error": "user rejected",
        "context": {"id": 1},
    }
    result = loop.handle_feedback(payload)
    assert result["stored"] is True
    assert loop.metrics()["rejects"] == 1
    assert loop.metrics()["errors_reported"] == 1


def test_handle_feedback_edit():
    loop = FeedbackLoop()
    payload = {"type": "edit", "file": "main.py", "diff": "changed line"}
    result = loop.handle_feedback(payload)
    assert result["stored"] is True
    assert result["event"]["file"] == "main.py"
    assert loop.metrics()["edits"] == 1


def test_handle_feedback_error_type():
    loop = FeedbackLoop()
    payload = {
        "type": "error",
        "message": "network timeout",
        "context": {"endpoint": "api"},
    }
    result = loop.handle_feedback(payload)
    assert result["stored"] is True
    assert "network timeout" in result["event"]["message"]
    assert loop.metrics()["errors_reported"] == 1


def test_handle_feedback_unsupported_type():
    loop = FeedbackLoop()
    payload = {"type": "unknown_event"}
    result = loop.handle_feedback(payload)
    assert result["stored"] is False
    assert "Unsupported" in result["reason"]


def test_handle_feedback_empty_payload():
    loop = FeedbackLoop()
    result = loop.handle_feedback({})
    assert result["stored"] is False


def test_handle_feedback_none_payload():
    loop = FeedbackLoop()
    result = loop.handle_feedback(None)
    assert result["stored"] is False


def test_suggestion_feedback_with_message_field():
    loop = FeedbackLoop()
    payload = {
        "type": "suggestion_feedback",
        "accepted": False,
        "message": "bad suggestion",
    }
    result = loop.handle_feedback(payload)
    assert result["stored"] is True
    assert loop.metrics()["errors_reported"] == 1
