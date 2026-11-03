"""CI-collected coverage for memory/supabase_store.py — provider detection,
the SQLite degradation path, and the Supabase/pgvector code paths (fake client).

বাংলা: supabase_store.py হলো memory/ প্যাকেজের সবচেয়ে বড় store adapter —
এখানকার SQLite fallback-ই হলো production DB-degradation policy-র বাস্তব
রূপ: Supabase credential/স্কিমা অনুপস্থিত থাকলে সাইলেন্টলি লোকাল SQLite-এ
নেমে আসতে হবে, কখনো রাইট হারাতে পারবে না। এই টেস্টগুলো সেই contract
যাচাই করে — কোনো নেটওয়ার্ক/আসল Supabase ছাড়াই (fake client inject করে):

  - provider detection: URL শ্রেণিবিন্যাস, db. প্রিফিক্স/হোস্ট ডেরিভেশন,
    key অনুপস্থিত, pgvector RPC ব্যর্থ, unusable client — প্রতিটির পতন পথ
  - SQLite path: conversation/learned-fact roundtrip, auto id + created_at,
    batch accounting (mixed success/failure)
  - Supabase path: tenant enforcement, upsert payload, RPC সার্চ parse,
    RPC ব্যর্থতায় ilike fallback, দ্বৈত ব্যর্থতায় re-raise
  - embedding chain: সব পদ্ধতি ব্যর্থ হলে None (কখনো exception নয়)

mcp_server.py-সহ বাকি adapter-দের ramp documented follow-up।
"""

import asyncio
import json
import sqlite3
import sys
import time
import types

import pytest

from memory.supabase_store import SupabaseStore

pytestmark = pytest.mark.memory


# ─────────────────────────────────────────────────────────────────────────────
# Fake Supabase client — chainable table()/rpc() builders, কোনো নেটওয়ার্ক নেই।
# ─────────────────────────────────────────────────────────────────────────────
class _FakeResult:
    def __init__(self, data=None):
        self.data = list(data or [])


class _FakeTableBuilder:
    def __init__(self, backend, table):
        self._b, self._t = backend, table

    def upsert(self, payload):
        self._b.upserts.append((self._t, payload))
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def ilike(self, *a, **k):
        return self

    def execute(self):
        err = self._b.table_errors.get(self._t)
        if err is not None:
            raise err
        return _FakeResult(self._b.table_data.get(self._t, []))


class _FakeRPCBuilder:
    def __init__(self, backend):
        self._b = backend

    def execute(self):
        if self._b.rpc_error is not None:
            raise self._b.rpc_error
        return _FakeResult(self._b.rpc_data)


class _FakeSupabaseClient:
    def __init__(self):
        self.upserts: list[tuple[str, dict]] = []
        self.table_data: dict[str, list[dict]] = {}
        self.table_errors: dict[str, Exception] = {}
        self.rpc_data: list[dict] = []
        self.rpc_error: Exception | None = None

    def table(self, name):
        return _FakeTableBuilder(self, name)

    def rpc(self, name, params):
        return _FakeRPCBuilder(self)


def _install_fake_supabase_module(monkeypatch, create_client):
    mod = types.ModuleType("supabase")
    mod.create_client = create_client
    monkeypatch.setitem(sys.modules, "supabase", mod)


def _attach_client(store, client, pgvector=True):
    """Unit-level state injection: provider নির্ধারণের init-flow বাইপাস করে।"""
    store._provider = "supabase"
    store._supabase_client = client
    store._pgvector_available = pgvector
    # _get_supabase_client-এর health-check reconnection ট্রিগার এড়াতে
    store._last_health_check = time.time()


@pytest.fixture
def store(tmp_path, monkeypatch):
    for var in (
        "SUPABASE_DATABASE_URL_POOLER",
        "SUPABASE_DATABASE_URL",
        "SUPABASE_DB_URL",
        "SQLITE_PATH",
    ):
        monkeypatch.delenv(var, raising=False)
    s = SupabaseStore(database_url="", local_path=str(tmp_path / "mem.db"))
    assert s.provider == "sqlite"  # empty URL → সরাসরি SQLite degradation
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Provider detection — URL শ্রেণিবিন্যাস ও পতন পথ
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://abcdefgh.supabase.co", True),
        ("postgresql://postgres:pw@db.myproject.supabase.co:5432/postgres", True),
        ("postgresql://u:p@aws-0-eu-central-1.pooler.supabase.com:6543/postgres", True),
        ("postgresql://localhost:5432/supremeai", False),
        ("https://example.com/db", False),
        ("", False),
    ],
)
def test_is_supabase_url_classification(store, url, expected):
    assert store._is_supabase_url(url) is expected


def test_client_url_derivation_strips_db_prefix(tmp_path, monkeypatch):
    recorded = {}

    def fake_create_client(url, key):
        recorded["url"], recorded["key"] = url, key
        return _FakeSupabaseClient()

    _install_fake_supabase_module(monkeypatch, fake_create_client)
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    s = SupabaseStore(
        database_url="https://db.myproject.supabase.co:5432/postgres",
        local_path=str(tmp_path / "mem.db"),
    )
    assert recorded["url"] == "https://myproject.supabase.co"
    assert recorded["key"] == "test-key"
    assert s.provider == "supabase"  # fake RPC সফল → pgvector ready


def test_client_url_derivation_plain_https_url(tmp_path, monkeypatch):
    recorded = {}

    def fake_create_client(url, key):
        recorded["url"] = url
        return _FakeSupabaseClient()

    _install_fake_supabase_module(monkeypatch, fake_create_client)
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    SupabaseStore(
        database_url="https://myproject.supabase.co/",
        local_path=str(tmp_path / "mem.db"),
    )
    assert recorded["url"] == "https://myproject.supabase.co"  # trailing / rstrip


def test_no_key_degrades_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_KEY", "")  # key নেই → Supabase অব্যবহারযোগ্য
    s = SupabaseStore(
        database_url="https://myproject.supabase.co",
        local_path=str(tmp_path / "mem.db"),
    )
    assert s.provider == "sqlite"
    stats = s.get_stats()
    assert stats["provider"] == "sqlite"
    assert stats["pgvector_enabled"] is False


def test_non_supabase_url_cannot_derive_client(tmp_path, monkeypatch):
    # hostname supabase.co নয় এবং scheme http/https নয় → url ডেরাইভ অসম্ভব
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    s = SupabaseStore(
        database_url="postgresql://user:pw@db.internal.example.com:5432/app",
        local_path=str(tmp_path / "mem.db"),
    )
    assert s.provider == "sqlite"


def test_pgvector_rpc_failure_degrades_to_sqlite(tmp_path, monkeypatch):
    client = _FakeSupabaseClient()
    client.rpc_error = RuntimeError("rpc match_learned_facts missing")

    def fake_create_client(url, key):
        return client

    _install_fake_supabase_module(monkeypatch, fake_create_client)
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    s = SupabaseStore(
        database_url="https://myproject.supabase.co",
        local_path=str(tmp_path / "mem.db"),
    )
    assert s.provider == "sqlite"  # client আছে, কিন্তু স্কিমা নেই → পতন


def test_unusable_client_missing_table_rpc(tmp_path, monkeypatch):
    class _BareClient:
        pass  # table/rpc অ্যাট্রিবিউট নেই

    _install_fake_supabase_module(monkeypatch, lambda url, key: _BareClient())
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    s = SupabaseStore(
        database_url="https://myproject.supabase.co",
        local_path=str(tmp_path / "mem.db"),
    )
    assert s.provider == "sqlite"


def test_corrupted_module_create_client_not_callable(tmp_path, monkeypatch):
    _install_fake_supabase_module(monkeypatch, None)  # create_client=None
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    s = SupabaseStore(
        database_url="https://myproject.supabase.co",
        local_path=str(tmp_path / "mem.db"),
    )
    assert s.provider == "sqlite"


def test_create_client_exception_degrades_to_sqlite(tmp_path, monkeypatch):
    def boom(url, key):
        raise RuntimeError("network unreachable")

    _install_fake_supabase_module(monkeypatch, boom)
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    s = SupabaseStore(
        database_url="https://myproject.supabase.co",
        local_path=str(tmp_path / "mem.db"),
    )
    assert s.provider == "sqlite"


# ─────────────────────────────────────────────────────────────────────────────
# SQLite path — conversation ও learned-fact persistence
# ─────────────────────────────────────────────────────────────────────────────
def test_conversation_sqlite_roundtrip(store):
    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    store.save_conversation("sess-1", msgs)
    got = store.get_conversation("sess-1")
    assert [(m["role"], m["content"]) for m in got] == [
        ("user", "hello"),
        ("assistant", "hi there"),
    ]


def test_save_learned_fact_sqlite_auto_id_and_created_at(store):
    fact = {"content": "deploy uses canary", "tags": ["ops"]}
    store.save_learned_fact(fact)
    fact_id = fact["id"]
    assert fact_id.startswith("fact_")
    assert fact["created_at"]  # ISO timestamp injected
    rows = [r for r in store.get_task_history() if r.get("task_type") == "learned_fact"]
    assert len(rows) == 1
    payload = json.loads(rows[0]["task_description"])
    assert payload["id"] == fact_id  # আসল TEXT id JSON payload-এ সংরক্ষিত
    assert payload["content"] == "deploy uses canary"
    assert store.get_stats()["sqlite_fallback"] == 1


def test_save_learned_fact_replaces_same_id(store):
    # BUGFIX regression: TEXT fact_id এখন stable integer row id-তে ম্যাপ হয় —
    # একই fact_id দুইবার সেভ করলে REPLACE হবে, ডুপ্লিকেট row তৈরি হবে না।
    fact = {"id": "fact_fixed_id", "content": "version one"}
    store.save_learned_fact(fact)
    fact["content"] = "version two"
    store.save_learned_fact(fact)
    with sqlite3.connect(store.local_path) as conn:
        count, payload = conn.execute(
            "SELECT COUNT(*), task_description FROM tasks WHERE task_type = 'learned_fact' GROUP BY id"
        ).fetchone()
    assert count == 1
    assert json.loads(payload)["content"] == "version two"
    assert json.loads(payload)["id"] == "fact_fixed_id"  # আসল id JSON-এ সংরক্ষিত


def test_search_facts_sqlite_provider_returns_empty(store):
    store.save_learned_fact({"content": "needle in sqlite"})
    assert store.search_facts("needle") == []  # sqlite path: সিমান্টিক সার্চ নেই


def test_batch_save_facts_mixed_accounting(store):
    good1 = {"content": "fact one"}
    good2 = {"content": "fact two"}
    poison = {"content": "unserializable", "tags": {1, 2, 3}}  # set → json fails
    report = store.batch_save_facts([good1, good2, poison])
    assert report["success"] == 2
    assert report["failed"] == 1
    assert len(report["errors"]) == 1


def test_save_learned_fact_async_runs_in_executor(store):
    fact = {"content": "async persistence works"}
    asyncio.run(store.save_learned_fact_async(fact))
    assert fact["id"].startswith("fact_")
    assert store.get_stats()["sqlite_fallback"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Supabase path — tenant enforcement, payload, fallback chain
# ─────────────────────────────────────────────────────────────────────────────
def test_supabase_conversation_requires_tenant(store):
    client = _FakeSupabaseClient()
    _attach_client(store, client)
    with pytest.raises(ValueError):
        store.save_conversation("sess-1", [{"role": "user", "content": "x"}])
    with pytest.raises(ValueError):
        store.save_conversation("sess-1", [], tenant_id="default")
    with pytest.raises(ValueError):
        store.save_conversation("sess-1", [], tenant_id="   ")


def test_supabase_conversation_upserts_tenant_payload(store):
    client = _FakeSupabaseClient()
    _attach_client(store, client)
    store.save_conversation("sess-9", [{"role": "user", "content": "hi"}], tenant_id="tenant-A")
    assert len(client.upserts) == 1
    table, payload = client.upserts[0]
    assert table == "conversations"
    assert payload["tenant_id"] == "tenant-A"
    assert payload["session_id"] == "sess-9"
    assert json.loads(payload["messages"])[0]["content"] == "hi"
    assert payload["updated_at"]


def test_supabase_get_conversation_parses_json(store):
    client = _FakeSupabaseClient()
    client.table_data["conversations"] = [
        {"messages": json.dumps([{"role": "user", "content": "remote"}])}
    ]
    _attach_client(store, client)
    assert store.get_conversation("sess-2") == [{"role": "user", "content": "remote"}]


def test_supabase_get_conversation_empty(store):
    _attach_client(store, _FakeSupabaseClient())
    assert store.get_conversation("missing") == []


def test_supabase_save_fact_with_embedding(store, monkeypatch):
    client = _FakeSupabaseClient()
    _attach_client(store, client)
    embedding = [0.1] * 1536
    monkeypatch.setattr(store, "_generate_embedding", lambda text: embedding)
    fact = {"id": "f-1", "content": "vector fact", "tags": ["t"]}
    store.save_learned_fact(fact)
    table, payload = client.upserts[0]
    assert table == "learned_facts"
    assert payload["embedding"] == embedding
    assert payload["id"] == "f-1"
    assert json.loads(payload["tags"]) == ["t"]


def test_supabase_save_fact_failure_degrades_to_sqlite(store):
    client = _FakeSupabaseClient()
    client.table_errors["learned_facts"] = RuntimeError("upsert down")
    _attach_client(store, client)
    fact = {"content": "must survive"}
    store.save_learned_fact(fact)  # exception নয় — SQLite fallback
    survived = [
        r
        for r in store.get_task_history()
        if r.get("task_type") == "learned_fact"
        and json.loads(r["task_description"])["id"] == fact["id"]
    ]
    assert len(survived) == 1
    stats = store.get_stats()
    assert stats["pgvector_failure"] == 1
    assert stats["sqlite_fallback"] == 1


def test_supabase_save_fact_double_failure_raises(store):
    client = _FakeSupabaseClient()
    client.table_errors["learned_facts"] = RuntimeError("upsert down")
    _attach_client(store, client)
    poison = {"content": "broken", "tags": {1, 2}}  # sqlite fallback-ও json ব্যর্থ
    with pytest.raises(TypeError):
        store.save_learned_fact(poison)


def test_supabase_search_facts_rpc_parses_rows(store, monkeypatch):
    client = _FakeSupabaseClient()
    client.rpc_data = [
        {"content": json.dumps({"id": "f1", "content": "hit one"})},
        {"content": {"id": "f2", "content": "hit two"}},  # dict সরাসরি
    ]
    _attach_client(store, client)
    monkeypatch.setattr(store, "_generate_embedding", lambda text: [0.2] * 1536)
    hits = store.search_facts("hit")
    assert hits[0]["id"] == "f1"
    assert hits[1]["content"] == "hit two"
    assert store.get_stats()["pgvector_success"] == 1


def test_supabase_search_facts_rpc_failure_falls_back_to_ilike(store, monkeypatch):
    client = _FakeSupabaseClient()
    client.rpc_error = RuntimeError("rpc timeout")
    client.table_data["learned_facts"] = [
        {"content": json.dumps({"id": "f3", "content": "ilike hit"})}
    ]
    _attach_client(store, client)
    monkeypatch.setattr(
        store, "_generate_embedding", lambda text: (_ for _ in ()).throw(RuntimeError("no embed"))
    )
    hits = store.search_facts("ilike")
    assert hits[0]["id"] == "f3"
    assert store.get_stats()["pgvector_failure"] == 1


def test_supabase_search_facts_total_failure_returns_empty(store):
    client = _FakeSupabaseClient()
    client.rpc_error = RuntimeError("rpc down")
    client.table_errors["learned_facts"] = RuntimeError("table down")
    _attach_client(store, client)
    assert store.search_facts("anything") == []


def test_similarity_search_fallback_without_pgvector(store):
    store.save_learned_fact({"content": "fallback fact"})
    _attach_client(store, _FakeSupabaseClient(), pgvector=False)
    assert store.similarity_search("fallback fact") == []  # → search_facts → sqlite []


def test_similarity_search_uses_rpc_when_pgvector_ready(store, monkeypatch):
    client = _FakeSupabaseClient()
    client.rpc_data = [{"content": json.dumps({"id": "f9", "content": "sem"})}]
    _attach_client(store, client, pgvector=True)
    monkeypatch.setattr(store, "_generate_embedding", lambda text: [0.3] * 1536)
    hits = store.similarity_search("sem", threshold=0.5, limit=3)
    assert hits[0]["id"] == "f9"


def test_force_reconnect_rechecks_provider(tmp_path, monkeypatch):
    # init-এ key নেই → sqlite; পরে key + fake module দিয়ে reconnect → supabase
    monkeypatch.setenv("SUPABASE_KEY", "")
    s = SupabaseStore(
        database_url="https://myproject.supabase.co",
        local_path=str(tmp_path / "mem.db"),
    )
    assert s.provider == "sqlite"
    assert s.force_reconnect() is False  # এখনো key নেই

    def fake_create_client(url, key):
        return _FakeSupabaseClient()

    _install_fake_supabase_module(monkeypatch, fake_create_client)
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    assert s.force_reconnect() is True
    assert s.provider == "supabase"


# ─────────────────────────────────────────────────────────────────────────────
# Embedding chain — তিন স্তরের fallback, সব ব্যর্থ হলে None
# ─────────────────────────────────────────────────────────────────────────────
def test_generate_embedding_primary_path(store, monkeypatch):
    import core.embeddings as emb

    monkeypatch.setattr(emb, "embed_for_pgvector", lambda text, pg_dim: [0.5] * pg_dim)
    result = store._generate_embedding("hello")
    assert result == [0.5] * 384
    assert store.get_stats()["embeddings_generated"] == 1


def test_generate_embedding_all_methods_fail_returns_none(store, monkeypatch):
    import core.embeddings as emb

    monkeypatch.setattr(
        emb,
        "embed_for_pgvector",
        lambda text, pg_dim: (_ for _ in ()).throw(RuntimeError("no api")),
    )
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # import ব্যর্থ
    monkeypatch.setitem(sys.modules, "litellm", None)
    assert store._generate_embedding("hello") is None
    assert store.get_stats()["embeddings_generated"] == 1
