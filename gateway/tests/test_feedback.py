"""Feedback route (api/routes/feedback.py) এর ইউনিট টেস্ট।

বাংলা: ফিডব্যাক ইনজেস্ট এন্ডপয়েন্ট কভার করা হয়েছে। FeedbackLoop.handle_feedback
মক করে সাকসেস ও আনসাপোর্টেড টাইপ দুই ব্রাঞ্চই যাচাই করা হয়েছে।
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_client():
    from api.routes.feedback import router

    app = FastAPI()
    app.include_router(router)
    return app


def test_ingest_success():
    client = TestClient(_build_client())
    with patch("api.routes.feedback._feedback_loop") as loop:
        loop.handle_feedback.return_value = {"stored": True}
        resp = client.post(
            "/api/feedback/ingest", json={"event_type": "edit", "payload": {"file": "a.py"}}
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True


def test_ingest_unsupported_type_returns_400():
    client = TestClient(_build_client())
    with patch("api.routes.feedback._feedback_loop") as loop:
        loop.handle_feedback.return_value = {"stored": False, "reason": "Unsupported feedback type"}
        resp = client.post("/api/feedback/ingest", json={"event_type": "unknown_xyz"})
        assert resp.status_code == 400


def test_ingest_empty_payload_ok():
    client = TestClient(_build_client())
    with patch("api.routes.feedback._feedback_loop") as loop:
        loop.handle_feedback.return_value = {"stored": True}
        resp = client.post("/api/feedback/ingest", json={"event_type": "edit"})
        assert resp.status_code == 200
