"""#1823 conversation-history split-brain — GET /conversations/ contract tests.

বাংলা: ai_memory (pgvector) এখন চ্যাট হিস্টরির একমাত্র source of truth।
GET /api/v1/conversations/ সেই store-এর read-projection (session grouping);
POST endpoints branch-metadata Supabase টেবিলেই লেখে (fork feature)।
Vector store fake দিয়ে projection contract lock করা হলো।
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeVectorStore:
    """ai_memory projection fake — list_conversation_sessions/get_session_messages রেকর্ড করে।"""

    def __init__(self, sessions: list[dict[str, Any]] | None = None) -> None:
        self.sessions = sessions or []
        self.calls: list[tuple] = []

    async def list_conversation_sessions(
        self, user_id: str, limit: int = 50, **_: Any
    ) -> list[dict]:
        self.calls.append(("list", user_id, limit))
        return self.sessions[:limit]

    async def get_session_messages(self, user_id: str, session_id: str, **_: Any) -> list[dict]:
        self.calls.append(("get", user_id, session_id))
        for session in self.sessions:
            if session["session_id"] == session_id:
                return session["exchanges"]
        return []


def _session(sid: str, exchanges: list[str], created: str, updated: str) -> dict[str, Any]:
    return {
        "session_id": sid,
        "created_at": created,
        "updated_at": updated,
        "exchanges": [{"content": c, "created_at": created} for c in exchanges],
    }


@pytest.fixture()
def client(monkeypatch):
    import api.routes.conversations as cmod
    from api.routes.conversations import router as conversations_router

    fake = FakeVectorStore(
        [
            _session(
                "sess-new",
                ["Q: How do I deploy?\nA: Use the Render pipeline."],
                "2026-01-02T10:00:00Z",
                "2026-01-02T10:00:00Z",
            ),
            _session(
                "sess-old",
                ["Q: First question\nA: First answer", "Q: Second question\nA: Second answer"],
                "2026-01-01T09:00:00Z",
                "2026-01-01T11:00:00Z",
            ),
        ]
    )
    monkeypatch.setattr(cmod, "_get_vector_store", lambda: fake)

    app = FastAPI()
    app.include_router(conversations_router, prefix="/api/v1")
    return TestClient(app), fake


class TestConversationsAiMemoryProjection:
    def test_list_is_recent_first_projection(self, client):
        tc, fake = client
        res = tc.get("/api/v1/conversations/")
        assert res.status_code == 200
        assert fake.calls[0][:2] == ("list", "test_admin@supremeai.com")
        body = res.json()
        assert [c["id"] for c in body] == ["sess-new", "sess-old"]

    def test_list_response_shape(self, client):
        tc, _ = client
        body = tc.get("/api/v1/conversations/").json()
        assert set(body[0].keys()) == {"id", "title", "created_at", "updated_at", "message_count"}

    def test_title_derived_from_oldest_user_question(self, client):
        tc, _ = client
        body = tc.get("/api/v1/conversations/").json()
        assert body[0]["title"] == "How do I deploy?"
        assert body[1]["title"] == "First question"

    def test_message_count_counts_exchanges(self, client):
        tc, _ = client
        body = tc.get("/api/v1/conversations/").json()
        assert body[0]["message_count"] == 1
        assert body[1]["message_count"] == 2

    def test_limit_forwarded_to_store(self, client):
        tc, fake = client
        tc.get("/api/v1/conversations/", params={"limit": 1})
        assert fake.calls[-1] == ("list", "test_admin@supremeai.com", 1)

    def test_detail_endpoint_parses_qa_into_turns(self, client):
        tc, fake = client
        res = tc.get("/api/v1/conversations/sess-old/messages")
        assert res.status_code == 200
        assert fake.calls[-1] == ("get", "test_admin@supremeai.com", "sess-old")
        turns = res.json()
        roles = [t["role"] for t in turns]
        assert roles == ["user", "assistant", "user", "assistant"]
        assert turns[0]["content"] == "First question"
        assert turns[1]["content"] == "First answer"

    def test_detail_unknown_session_returns_empty(self, client):
        tc, _ = client
        res = tc.get("/api/v1/conversations/nope/messages")
        assert res.status_code == 200
        assert res.json() == []

    def test_store_unavailable_degrades_to_empty_list(self, monkeypatch):
        import api.routes.conversations as cmod
        from api.routes.conversations import router as conversations_router

        monkeypatch.setattr(cmod, "_get_vector_store", lambda: None)
        app = FastAPI()
        app.include_router(conversations_router, prefix="/api/v1")
        tc = TestClient(app)
        assert tc.get("/api/v1/conversations/").json() == []


class TestParseHelpers:
    def test_parse_qa_exchange(self):
        from api.routes.conversations import parse_exchange_messages

        turns = parse_exchange_messages("Q: Hello\nA: Hi there!", "2026-01-01T00:00:00Z")
        assert [(t["role"], t["content"]) for t in turns] == [
            ("user", "Hello"),
            ("assistant", "Hi there!"),
        ]

    def test_parse_user_only_exchange(self):
        from api.routes.conversations import parse_exchange_messages

        turns = parse_exchange_messages("Q: only a question", None)
        assert [(t["role"], t["content"]) for t in turns] == [("user", "only a question")]
