"""ERR-H05 contract tests — knowledge learning-loop endpoints.

The shared ``SupremeAIService`` client (packages/shared-services) posts
LearningUpload payloads to /api/knowledge/{learn,failure,feedback} and reads
/api/knowledge/stats. These tests verify the real persistence contract:
every accepted signal lands in the canonical learning-loop store and /stats
aggregates it honestly.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch) -> None:
    """Per-test learning-loop SQLite store + fresh singleton."""
    import adaptive_engine._store as store
    import adaptive_engine.learning_loop as ll

    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_DB_PATH", tmp_path / "ecosystem.db")
    monkeypatch.setattr(ll, "_loop", None)


@pytest.fixture()
def client(monkeypatch, isolated_db) -> TestClient:
    from api.routes.knowledge import router as knowledge_router

    app = FastAPI()
    app.include_router(knowledge_router, prefix="/api")
    return TestClient(app)


def _upload(upload_type: str, data: dict) -> dict:
    return {"type": upload_type, "data": data, "sessionId": "session-test-1"}


class TestLearnEndpoint:
    def test_code_edit_recorded(self, client: TestClient):
        res = client.post(
            "/api/knowledge/learn",
            json=_upload(
                "CODE_EDIT",
                {
                    "filePath": "src/app.py",
                    "language": "python",
                    "editedCode": "print('hi')",
                    "timestamp": "2026-09-16T00:00:00Z",
                },
            ),
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        assert "signal recorded" in body["message"]

        stats = client.get("/api/knowledge/stats").json()
        assert any(a["type"] == "CODE_EDIT" for a in stats["recentActivity"])
        assert any("src/app.py" in a["message"] for a in stats["recentActivity"])
        assert all({"type", "message", "timestamp"} <= set(a) for a in stats["recentActivity"])

    def test_code_analysis_recorded(self, client: TestClient):
        res = client.post(
            "/api/knowledge/learn",
            json=_upload(
                "CODE_ANALYSIS",
                {
                    "filePath": "src/util.ts",
                    "language": "typescript",
                    "code": "const x = 1;",
                    "timestamp": "2026-09-16T00:00:00Z",
                    "metrics": {"linesOfCode": 1},
                },
            ),
        )
        assert res.status_code == 200, res.text

    def test_unknown_type_400(self, client: TestClient):
        res = client.post(
            "/api/knowledge/learn",
            json=_upload("NOT_A_TYPE", {"foo": "bar"}),
        )
        assert res.status_code == 400
        assert "unknown learning type" in res.json()["detail"]

    def test_misrouted_type_400(self, client: TestClient):
        """ERROR_REPORT belongs to /failure — /learn must refuse it honestly."""
        res = client.post(
            "/api/knowledge/learn",
            json=_upload("ERROR_REPORT", {"errorType": "runtime", "errorMessage": "x"}),
        )
        assert res.status_code == 400
        assert "different knowledge endpoint" in res.json()["detail"]

    def test_empty_data_422(self, client: TestClient):
        res = client.post(
            "/api/knowledge/learn",
            json={"type": "CODE_EDIT", "data": {}, "sessionId": "s1"},
        )
        assert res.status_code == 422


class TestFailureEndpoint:
    def test_error_report_recorded(self, client: TestClient):
        res = client.post(
            "/api/knowledge/failure",
            json=_upload(
                "ERROR_REPORT",
                {
                    "errorType": "runtime",
                    "errorMessage": "TypeError: cannot read property",
                    "filePath": "src/x.ts",
                    "lineNumber": 42,
                    "severity": "error",
                    "timestamp": "2026-09-16T00:00:00Z",
                },
            ),
        )
        assert res.status_code == 200, res.text
        assert res.json()["success"] is True

        stats = client.get("/api/knowledge/stats").json()
        assert any(
            a["type"] == "ERROR_REPORT" and "TypeError: cannot read property" in a["message"]
            for a in stats["recentActivity"]
        )

    def test_rejects_non_error_types(self, client: TestClient):
        res = client.post(
            "/api/knowledge/failure",
            json=_upload("SUGGESTION_FEEDBACK", {"suggestionId": "s1", "accepted": True}),
        )
        assert res.status_code == 400


class TestFeedbackEndpoint:
    def test_feedback_recorded(self, client: TestClient):
        res = client.post(
            "/api/knowledge/feedback",
            json=_upload(
                "SUGGESTION_FEEDBACK",
                {
                    "suggestionId": "sug-77",
                    "accepted": True,
                    "taskId": "t-1",
                    "timestamp": "2026-09-16T00:00:00Z",
                },
            ),
        )
        assert res.status_code == 200, res.text
        stats = client.get("/api/knowledge/stats").json()
        assert any(
            a["type"] == "SUGGESTION_FEEDBACK" and "accepted" in a["message"]
            for a in stats["recentActivity"]
        )

    def test_rejects_non_feedback_types(self, client: TestClient):
        res = client.post(
            "/api/knowledge/feedback",
            json=_upload("CODE_EDIT", {"filePath": "a.py"}),
        )
        assert res.status_code == 400


class TestStatsEndpoint:
    def test_empty_stats_honest(self, client: TestClient):
        """No signals yet — empty activity list, never fabricated data."""
        res = client.get("/api/knowledge/stats")
        assert res.status_code == 200
        body = res.json()
        assert body["recentActivity"] == []
        assert body["total"] == 0

    def test_limit_respected(self, client: TestClient):
        for i in range(5):
            client.post(
                "/api/knowledge/learn",
                json=_upload("CODE_EDIT", {"filePath": f"f{i}.py", "language": "python"}),
            )
        body = client.get("/api/knowledge/stats", params={"limit": 3}).json()
        assert len(body["recentActivity"]) == 3
        assert body["total"] == 3
