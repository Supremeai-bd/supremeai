"""CI-collected coverage for the backend/memory/ package's small core modules.

বাংলা: memory/ প্যাকেজটি PR CI-র coverage measurement-এর বাইরে ছিল —
ci.yml-এর pytest invocation-এ --cov=memory ছিল না, আর
coverage_policy.yaml-এ memory/**-এর কোনো glob ছিল না (runs/**-এর মতোই
three-layer integrity gap)। এই ফাইল প্যাকেজের ছোট pure মডিউলগুলোর আসল
behavior যাচাই করে:

  - sqlite_store : pure logic + SQLite CRUD (SupabaseStore-এর base class সহ)

L2 orphan-spine pass (2026-09-17): M3/L4.1 decision table
(docs/plans/M3_MEMORY_STORE_CONSOLIDATION_DECISION_TABLE.md) অনুযায়ী
``unified_db_manager``, ``cloud_postgres_store``, ``summary_tree``,
``vector_store_config`` ও ``hierarchical_tree`` (dormant chain:
services/ingestion/context_collector সহ) ARCHIVE হয়ে delete করা হয়েছে —
প্রত্যেকটির production importer ছিল শূন্য। TestUnifiedDBManager /
TestSummaryTree / TestVectorStoreConfig / TestHierarchicalMemoryTree ক্লাসগুলো
সেই মডিউলগুলোর সাথেই সরানো হয়েছে।

mcp_server.py (1272L) ও বাকি store adapter-গুলোর ramp হলো documented follow-up।
"""

import pytest

from memory.sqlite_store import SQLiteMemoryStore

pytestmark = pytest.mark.memory


class TestSQLiteMemoryStore:
    @pytest.mark.unit
    def test_log_task_and_history_roundtrip(self, tmp_path):
        store = SQLiteMemoryStore(db_path=str(tmp_path / "mem.db"))

        store.log_task("summarize doc", "tool", True, 0.25, "ok")
        store.log_task("crawl web", "agent", False, 1.5, "timeout")

        history = store.get_task_history()
        assert len(history) == 2
        # ⚠️ পাওয়া finding (owner fix candidate): get_task_history()
        # `ORDER BY timestamp DESC` ব্যবহার করে, কিন্তু CURRENT_TIMESTAMP-এর
        # granularity 1 সেকেন্ড — same-second insert-এ "latest first" অর্ডার
        # অনির্দিষ্ট থাকে (deterministic tiebreak চাইলে `id DESC` যোগ করতে হবে)।
        # তাই এখানে order-independent contract যাচাই করা হলো:
        by_desc = {h["task_description"]: h for h in history}
        assert by_desc["crawl web"]["success"] == 0
        assert by_desc["crawl web"]["cost"] == 1.5
        assert by_desc["summarize doc"]["success"] == 1
        assert by_desc["summarize doc"]["cost"] == 0.25

    @pytest.mark.unit
    def test_save_and_get_session_messages(self, tmp_path):
        store = SQLiteMemoryStore(db_path=str(tmp_path / "mem.db"))

        store.save_message("s-1", "user", "hi")
        store.save_message("s-1", "assistant", "hello")
        # INSERT OR IGNORE — একই session id বারবার save করলেও error নেই
        store.save_message("s-1", "user", "again")
        store.save_message("s-2", "user", "other session")

        s1 = store.get_session_messages("s-1")
        assert [m["content"] for m in s1] == ["hi", "hello", "again"]  # id ASC order
        assert {m["role"] for m in s1} == {"user", "assistant"}
        assert [m["content"] for m in store.get_session_messages("s-2")] == ["other session"]

    @pytest.mark.unit
    def test_memory_mode_shares_single_connection(self):
        store = SQLiteMemoryStore(db_path=":memory:")

        store.save_message("s-1", "user", "persist across calls")
        store.log_task("t", "tool", True, 0.0, "ok")

        # :memory: mode-এ একই connection reuse হয় — দ্বিতীয় কলেও আগের ডাটা থাকে
        assert store.get_session_messages("s-1")[0]["content"] == "persist across calls"
        assert len(store.get_task_history()) == 1
        assert store.conn is not None


class TestM3ArchiveGuard:
    """L2 regression guard: M3 ARCHIVE মডিউলগুলো নীরবে ফিরে আসতে পারবে না।

    বাংলা: এই মডিউলগুলো production-importer-শূন্য অবস্থায় M3/L4.1 decision
    table-এর ARCHIVE সিদ্ধান্তে মোছা হয়েছে। কেউ আবার যোগ করতে চাইলে আগে
    decision table-এ সিদ্ধান্ত বদলাতে হবে — এই গার্ড সেটা নিশ্চিত করে (#5
    Verify Before Trust — ঘোষিত সিদ্ধান্ত কোডেও সত্য থাকতে হবে)।
    """

    @pytest.mark.unit
    def test_archived_memory_modules_stay_deleted(self):
        import importlib.util
        from pathlib import Path

        backend_root = Path(__file__).resolve().parents[2]
        archived = [
            Path("memory/unified_db_manager.py"),
            Path("memory/cloud_postgres_store.py"),
            Path("memory/summary_tree.py"),
            Path("memory/vector_store_config.py"),
            Path("memory/hierarchical_tree.py"),
            Path("services/ingestion/context_collector.py"),
        ]
        for rel in archived:
            assert not (backend_root / rel).is_file(), (
                f"{rel} was ARCHIVE-deleted per M3 decision table — do not "
                f"reintroduce without updating the decision (and this guard)"
            )
            module_name = ".".join(rel.with_suffix("").parts)
            assert importlib.util.find_spec(module_name) is None, module_name
