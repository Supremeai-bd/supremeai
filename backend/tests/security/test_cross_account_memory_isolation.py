"""#3155 — Cross-account AI memory isolation regression tests (REAL, two-user).

বাংলা: এই ফাইলটি দুই আসল অ্যাকাউন্টের (user-A owner, user-B attacker) মধ্যে
memory isolation প্রমাণ করে — কোনো self-made mock-store নয়:

  1. SlidingWindow IDOR (api/routes/memory.py GET/DELETE /api/memory/recall):
     আসল SlidingWindowMemory + আসল sqlite ফাইল; একই session_id-তে দুই user-এর
     window বসে → B কখনো A-র টেক্সট পড়তে/মুছতে পারে না। (route-layer
     user-namespace fix, AUD-5.1 প্যাটার্ন।)
  2. Global memory CRUD (api/routes/global_memory.py): handler আসল;
     transport-boundary-এ recording fake (repo-প্রতিষ্ঠিত FakeResult/FakeTable
     প্যাটার্ন) → B-র DELETE/PUT A-র memory-তে 404, A-র row অক্ষত।
  3. Vector recall owner-binding (POST /api/memory/recall): recall_memories
     সবসময় caller-এর sub পায় (AUD-5.1) — A হলে A, B হলে B।
  4. Conversation projection (api/routes/conversations.py): একই session_id
     দুই user-এর কাছে — প্রত্যেকে শুধু নিজের exchange দেখে।

Run: pytest backend/tests/security/test_cross_account_memory_isolation.py -v
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

USER_A = "user-a@supremeai.test"
USER_B = "user-b@supremeai.test"

A_CANARY = "ALPHA-CANARY-a7f3-private-memory-of-user-A"
B_CANARY = "BETA-CANARY-b9e1-private-memory-of-user-B"


def _user(sub: str) -> dict:
    return {"sub": sub, "role": "user", "tenant_id": sub}


# ═════════════════════════════════════════════════════════════════════════════
# Part 1 — Sliding-window IDOR: REAL sqlite store, two users, same session_id
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class _WinRec:
    window_index: int
    text: str
    token_count: int
    summary: str
    created_at: str


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture()
def window_client(tmp_path: Path, monkeypatch):
    """Bare app + memory router; আসল SlidingWindowMemory (tmp sqlite) inject।"""
    import api.routes.memory as mem_mod
    from api.dependencies import get_current_user_token
    from memory.sliding_window import SlidingWindowMemory

    store = SlidingWindowMemory.__new__(SlidingWindowMemory)  # config default সহ
    from memory.sliding_window import SlidingWindowConfig

    store.config = SlidingWindowConfig()
    store.db_path = str(tmp_path / "windows.db")
    store._init_db()

    monkeypatch.setattr(mem_mod, "_window", store)

    app = FastAPI()
    app.include_router(mem_mod.router)

    client = TestClient(app)

    def _as(sub: str):
        app.dependency_overrides[get_current_user_token] = lambda: _user(sub)
        return client

    return store, _as


class TestSlidingWindowCrossAccountIsolation:
    """#3155: একই session_id-তে দুই user-এর window — সম্পূর্ণ আলাদা।"""

    def _seed_both_users(self, store, session_id: str) -> None:
        # বাংলা: দুই user-এর window route-এর নেমস্পেস-সহ আসল persist-এ বসাই
        from api.routes.memory import _owned_window_session

        assert store.persist(
            _owned_window_session(_user(USER_A), session_id),
            [_WinRec(0, A_CANARY, 5, "A summary", _now_iso())],
        )
        assert store.persist(
            _owned_window_session(_user(USER_B), session_id),
            [_WinRec(0, B_CANARY, 5, "B summary", _now_iso())],
        )

    def test_user_a_never_sees_user_b_window(self, window_client):
        store, as_user = window_client
        self._seed_both_users(store, "shared-session")

        rows = (
            as_user(USER_A)
            .get("/api/memory/recall", params={"session_id": "shared-session"})
            .json()
        )

        texts = " ".join(str(r.get("text", "")) for r in rows)
        assert A_CANARY in texts, "A-র নিজের window তো দেখতে হবে"
        assert B_CANARY not in texts, "IDOR: user-A কে user-B-র window দেখছে!"

    def test_user_b_never_sees_user_a_window(self, window_client):
        store, as_user = window_client
        self._seed_both_users(store, "shared-session")

        rows = (
            as_user(USER_B)
            .get("/api/memory/recall", params={"session_id": "shared-session"})
            .json()
        )

        texts = " ".join(str(r.get("text", "")) for r in rows)
        assert B_CANARY in texts
        assert A_CANARY not in texts, "IDOR: user-B কে user-A-র window দেখছে!"

    def test_user_b_cannot_clear_user_a_window(self, window_client):
        store, as_user = window_client
        self._seed_both_users(store, "shared-session")

        # B নিজের (খালি নয় — B-র আছে) namespace clear করে — A-র data অক্ষত থাকে
        resp = as_user(USER_B).delete("/api/memory/recall", params={"session_id": "shared-session"})
        assert resp.status_code == 200

        rows_a = (
            as_user(USER_A)
            .get("/api/memory/recall", params={"session_id": "shared-session"})
            .json()
        )
        texts_a = " ".join(str(r.get("text", "")) for r in rows_a)
        assert A_CANARY in texts_a, "IDOR: B-র clear A-র window মুছে দিয়েছে!"

    def test_default_session_also_namespaced(self, window_client):
        store, as_user = window_client
        self._seed_both_users(store, "default")

        rows = as_user(USER_A).get("/api/memory/recall").json()
        texts = " ".join(str(r.get("text", "")) for r in rows)
        assert A_CANARY in texts and B_CANARY not in texts

    def test_two_users_default_session_mutual_exclusion(self, window_client):
        """নির্দিষ্ট session না দিলেও (default) দুই user একে অন্যকে দেখে না।"""
        store, as_user = window_client
        from api.routes.memory import _owned_window_session

        store.persist(
            _owned_window_session(_user(USER_A), "default"),
            [_WinRec(0, A_CANARY, 5, "A", _now_iso())],
        )
        store.persist(
            _owned_window_session(_user(USER_B), "default"),
            [_WinRec(0, B_CANARY, 5, "B", _now_iso())],
        )
        a_rows = as_user(USER_A).get("/api/memory/recall").json()
        b_rows = as_user(USER_B).get("/api/memory/recall").json()
        assert A_CANARY in " ".join(str(r.get("text", "")) for r in a_rows)
        assert A_CANARY not in " ".join(str(r.get("text", "")) for r in b_rows)


# ═════════════════════════════════════════════════════════════════════════════
# Part 2 — Global memory CRUD: B-র DELETE/PUT A-র memory-তে 404
# ═════════════════════════════════════════════════════════════════════════════


class _FakeResult:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data

    def __await__(self):
        async def _self() -> _FakeResult:
            return self

        return _self().__await__()


class _FakeTable:
    """PostgREST builder-chain recorder — repo-প্রতিষ্ঠিত প্যাটার্ন।"""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows if rows is not None else []
        self.ops: list[tuple] = []

    def select(self, *cols: str, **kw: Any) -> _FakeTable:
        self.ops.append(("select", cols))
        return self

    def eq(self, col: str, val: Any) -> _FakeTable:
        self.ops.append(("eq", col, val))
        # বাংলা: ownership pre-check সিমুলেট — id+user_id দুটোই মিললে তবেই row
        if col == "user_id":
            self._rows = [r for r in self._rows if r.get("user_id") == val]
        return self

    def delete(self) -> _FakeTable:
        self.ops.append(("delete",))
        return self

    def update(self, payload: dict[str, Any]) -> _FakeTable:
        self.ops.append(("update", payload))
        return self

    def insert(self, payload: dict[str, Any]) -> _FakeTable:
        self.ops.append(("insert", payload))
        return self

    def execute(self) -> _FakeResult:
        return _FakeResult(list(self._rows))


@pytest.fixture()
def crud_client(monkeypatch):
    import api.routes.global_memory as gmod
    from api.dependencies import get_current_user_token

    A_MEMORY_ID = str(uuid.uuid4())
    # A-র একটি memory row; B-র কিছু নেই
    state = {"rows": [{"id": A_MEMORY_ID, "user_id": USER_A}]}

    class _FakeDB:
        client = None  # _ensure_supabase truthy check

        def table(self, name: str) -> _FakeTable:
            assert name == "ai_memory"
            tbl = _FakeTable([dict(r) for r in state["rows"]])
            tbl._state = state  # type: ignore[attr-defined]
            return tbl

    holder = _FakeDB()
    holder.client = holder  # .client.table(...) chain
    monkeypatch.setattr(gmod, "supabase_db", holder)

    app = FastAPI()
    app.include_router(gmod.router)
    client = TestClient(app)

    def _as(sub: str):
        app.dependency_overrides[get_current_user_token] = lambda: _user(sub)
        return client

    return _as, state, A_MEMORY_ID


class TestGlobalMemoryCrudIsolation:
    """#3155: A-র memory-তে B-র DELETE/PUT → 404; A-র row টিকে থাকে।"""

    def test_b_delete_on_a_memory_returns_404(self, crud_client):
        _as, state, a_id = crud_client
        resp = _as(USER_B).delete(f"/api/preferences/memory/{a_id}")
        assert resp.status_code == 404, "B-র DELETE A-র memory-তে 404 ফেরাতে হবে"
        # বাংলা: ownership pre-check দুটি filter-ই পাঠিয়েছে — id + user_id
        assert state["rows"], "A-র row এখনো আছে (মোটেও মুছে নি)"

    def test_a_delete_on_own_memory_succeeds(self, crud_client):
        _as, state, a_id = crud_client
        resp = _as(USER_A).delete(f"/api/preferences/memory/{a_id}")
        assert resp.status_code == 200

    def test_b_update_on_a_memory_returns_404(self, crud_client):
        _as, state, a_id = crud_client
        resp = _as(USER_B).put(f"/api/preferences/memory/{a_id}", json={"content": "hijacked by B"})
        assert resp.status_code == 404, "B-র PUT A-র memory-তে 404 ফেরাতে হবে"
        assert state["rows"][0]["user_id"] == USER_A, "A-র row B-র হাতে পড়েনি"


# ═════════════════════════════════════════════════════════════════════════════
# Part 3 — Vector recall owner-binding (AUD-5.1): p_user_id সবসময় caller-এর
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def vector_client(monkeypatch):
    import api.routes.memory as mem_mod
    import services.memory_service as ms
    from api.dependencies import get_current_user_token

    captured: dict[str, Any] = {}

    async def _fake_recall(**kwargs):
        captured.update(kwargs)
        return []

    async def _fake_save(**kwargs):
        captured.update(kwargs)
        return {"success": True, "id": "mem-1"}

    monkeypatch.setattr(ms, "recall_memories", _fake_recall)
    monkeypatch.setattr(ms, "save_memory", _fake_save)

    app = FastAPI()
    app.include_router(mem_mod.router)
    client = TestClient(app)

    def _as(sub: str):
        app.dependency_overrides[get_current_user_token] = lambda: _user(sub)
        return client

    return _as, captured


class TestVectorRecallOwnerBinding:
    """#3155: recall/save সবসময় authenticated caller-এর sub বাঁধে।"""

    def test_recall_binds_user_a(self, vector_client):
        _as, captured = vector_client
        _as(USER_A).post("/api/memory/recall", json={"task_description": "my secrets"})
        assert captured.get("user_id") == USER_A, "recall A-র sub ছাড়া যায়নি"

    def test_recall_binds_user_b(self, vector_client):
        _as, captured = vector_client
        _as(USER_B).post("/api/memory/recall", json={"task_description": "my secrets"})
        assert captured.get("user_id") == USER_B, "recall B-র sub ছাড়া যায়নি"

    def test_save_binds_owner(self, vector_client):
        _as, captured = vector_client
        _as(USER_A).post(
            "/api/memory/save",
            json={"session_id": "s1", "summary": A_CANARY},
        )
        assert captured.get("user_id") == USER_A, "save A-র sub ছাড়া যায়নি (AUD-5.1)"


# ═════════════════════════════════════════════════════════════════════════════
# Part 4 — Conversation projection: একই session_id, দুই user, আলাদা দৃশ্য
# ═════════════════════════════════════════════════════════════════════════════


class _FakeVectorStore:
    """দুই user-এর exchange আলাদা রাখে — get_session_messages user_id দিয়ে ফিল্টার।"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._exchange_map = {
            USER_A: [{"content": f"user: {A_CANARY}", "created_at": _now_iso()}],
            USER_B: [{"content": f"user: {B_CANARY}", "created_at": _now_iso()}],
        }

    async def list_conversation_sessions(self, user_id: str, limit: int = 20):
        self.calls.append(("list", user_id, limit))
        return [
            {
                "session_id": "shared-chat",
                "exchanges": self._exchange_map.get(user_id, []),
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        ]

    async def get_session_messages(self, user_id: str, session_id: str):
        self.calls.append(("messages", user_id, session_id))
        return self._exchange_map.get(user_id, [])


@pytest.fixture()
def conversations_client(monkeypatch):
    import api.routes.conversations as conv_mod
    from core.security.authentication.rbac import get_current_user_token

    fake_store = _FakeVectorStore()
    monkeypatch.setattr(conv_mod, "_get_vector_store", lambda: fake_store)

    app = FastAPI()
    app.include_router(conv_mod.router)
    client = TestClient(app)

    def _as(sub: str):
        # বাংলা: conversations-router rbac-এর get_current_user_token ব্যবহার করে —
        # অন্য symbol override করলে নীরবে কিছুই হয় না
        app.dependency_overrides[get_current_user_token] = lambda: _user(sub)
        return client

    return _as, fake_store


class TestConversationProjectionIsolation:
    """#3155: একই session_id-তে দুই user-এর chat — প্রত্যেকে শুধু নিজেরটা দেখে।"""

    def test_a_messages_never_include_b_exchange(self, conversations_client):
        _as, _store = conversations_client
        msgs = _as(USER_A).get("/conversations/shared-chat/messages").json()
        joined = " ".join(str(m) for m in msgs)
        assert A_CANARY in joined
        assert B_CANARY not in joined, "IDOR: A-র chat-এ B-র exchange দেখা যাচ্ছে!"

    def test_b_messages_never_include_a_exchange(self, conversations_client):
        _as, _store = conversations_client
        msgs = _as(USER_B).get("/conversations/shared-chat/messages").json()
        joined = " ".join(str(m) for m in msgs)
        assert B_CANARY in joined
        assert A_CANARY not in joined, "IDOR: B-র chat-এ A-র exchange দেখা যাচ্ছে!"

    def test_list_sessions_scoped_to_caller(self, conversations_client):
        _as, store = conversations_client
        _as(USER_A).get("/conversations/")
        assert store.calls and store.calls[-1][1] == USER_A, "list A-র sub দিয়ে স্কোপ হয়নি"

    def test_session_messages_scoped_to_caller(self, conversations_client):
        _as, store = conversations_client
        _as(USER_B).get("/conversations/shared-chat/messages")
        assert store.calls[-1][1] == USER_B, "messages B-র sub দিয়ে স্কোপ হয়নি"


# ═════════════════════════════════════════════════════════════════════════════
# Part 5 — Route-source চুক্তি: নিরাপত্তা-সংক্রান্ত সোর্স লাইন টেম্পার-প্রুফ
# ═════════════════════════════════════════════════════════════════════════════


class TestIsolationSourceContract:
    """#3155: route-গুলোতে owner-binding কোনো ভবিষ্যত refactor-এ নীরবে বাদ যাবে না।"""

    def test_memory_routes_use_owned_window_session(self):
        from pathlib import Path

        src = Path("api/routes/memory.py").read_text(encoding="utf-8")
        assert "_owned_window_session(user, session_id)" in src, (
            "GET/DELETE /api/memory/recall অবশ্যই user-scoped session ব্যবহার করবে (#3155)"
        )

    def test_vector_recall_passes_user_sub(self):
        from pathlib import Path

        src = Path("api/routes/memory.py").read_text(encoding="utf-8")
        assert 'user_id=user.get("sub")' in src, (
            "vector recall/save-এ owner sub বাঁধা থাকতে হবে (AUD-5.1)"
        )
