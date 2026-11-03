"""Full-coverage tests for tools/mcp/mcp_supabase.py (Task 7-f).

The MCP tool functions are decorated with ``FastMCP.tool`` which returns
the original function, so the underlying coroutines are callable
directly.  All database access is faked: ``psycopg2.connect`` is
monkeypatched (see conftest — psycopg2 itself is only an optional
dependency) and admin authorization is controlled through the
``ADMIN_AUTHORIZED`` env var that ``utils.environment.is_admin_authorized``
reads.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

import tools.mcp.mcp_supabase as ms

# ──────────────────────────────── fake objects ────────────────────────────────


class FakeCursor:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn
        self.description = None
        self.rowcount = 0
        self._rows: list[tuple] = []

    def execute(self, query: Any, params: Any = None) -> None:
        self.conn.executed.append((str(query), params))
        script = self.conn.script
        if script is not None:
            self._rows = list(script.get("rows", []))
            self.description = script.get("description")
            self.rowcount = script.get("rowcount", 0)
            if script.get("raise"):
                raise script["raise"]

    def fetchone(self) -> tuple | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple]:
        return list(self._rows)

    def close(self) -> None:
        self.closed = True


class FakeConn:
    """Configurable stand-in for a psycopg2 connection."""

    def __init__(self, script: dict[str, Any] | None = None, close_raises: bool = False):
        self.script = script or {}
        self.executed: list[tuple[str, Any]] = []
        self.committed = False
        self.close_raises = close_raises
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        if self.close_raises:
            raise RuntimeError("close boom")
        self.closed = True


def _authorized(monkeypatch, on: bool = True) -> None:
    monkeypatch.setenv("ADMIN_AUTHORIZED", "true" if on else "false")


def _db_url(monkeypatch, url: str | None = "postgresql://u:p@db.example/testdb") -> None:
    if url is None:
        # Simulate "no URL configured anywhere" (DATABASE_URL sqlite fallback blanked too)
        monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("SUPABASE_DATABASE_URL", url)


def _connect(monkeypatch, conn: FakeConn | None) -> None:
    if conn is None:
        monkeypatch.setattr(ms.psycopg2, "connect", lambda *a, **kw: None)
    else:
        monkeypatch.setattr(ms.psycopg2, "connect", lambda *a, **kw: conn)


def _jq(payload: str) -> dict[str, Any]:
    return json.loads(payload)


# ───────────────────────────────── unit helpers ───────────────────────────────


@pytest.mark.unit
class TestHelpers:
    def test_get_supabase_db_url_unauthorized_empty(self, monkeypatch):
        _authorized(monkeypatch, on=False)
        _db_url(monkeypatch, "postgresql://x")
        assert ms._get_supabase_db_url() == ""

    def test_get_supabase_db_url_from_env(self, monkeypatch):
        _authorized(monkeypatch)
        _db_url(monkeypatch, "postgresql://env-url")
        assert ms._get_supabase_db_url() == "postgresql://env-url"

    def test_get_connection_sqlite_returns_none(self, monkeypatch):
        _authorized(monkeypatch)
        _db_url(monkeypatch, "sqlite+aiosqlite:////tmp/x.db")
        assert ms._get_connection() is None

    def test_get_connection_connect_failure_returns_none(self, monkeypatch):
        _authorized(monkeypatch)
        _db_url(monkeypatch, "postgresql://bad")

        def boom(*a, **kw):
            raise RuntimeError("connection refused now")

        monkeypatch.setattr(ms.psycopg2, "connect", boom)
        assert ms._get_connection() is None

    def test_handle_db_error_mapping(self):
        assert "connection failed" in ms._handle_db_error(Exception("Connection reset")).lower()
        assert "syntax" in ms._handle_db_error(Exception("syntax error at")).lower()
        # "parse" maps to the same syntax-error message (checked before permission)
        assert "syntax" in ms._handle_db_error(Exception("cannot parse query")).lower()
        assert "permission" in ms._handle_db_error(Exception("permission denied")).lower()
        generic = ms._handle_db_error(Exception("weird failure"))
        assert generic.startswith("Error: Database operation failed")

    def test_response_format_enum(self):
        assert ms.ResponseFormat("markdown") is ms.ResponseFormat.MARKDOWN
        assert ms.ResponseFormat("json") is ms.ResponseFormat.JSON

    def test_input_models_validation(self):
        with pytest.raises(Exception):
            ms.ExecuteQueryInput(query="")  # min_length=1
        with pytest.raises(Exception):
            ms.CreateTableInput(table_name="", columns="id int")
        with pytest.raises(Exception):
            ms.MigrationInput(migration_name="", up_sql="SELECT 1", down_sql="SELECT 1")
        q = ms.ExecuteQueryInput(query="  select 1  ")
        assert q.query == "select 1"  # str_strip_whitespace


# ─────────────────────────── supabase_execute_sql ─────────────────────────────


@pytest.mark.unit
class TestExecuteSql:
    async def test_destructive_requires_admin(self, monkeypatch):
        _authorized(monkeypatch, on=False)
        out = _jq(await ms.supabase_execute_sql(ms.ExecuteQueryInput(query="DROP TABLE users")))
        assert out["error"].startswith("Admin authorization required")

    async def test_no_url_configured(self, monkeypatch):
        _authorized(monkeypatch)
        _db_url(monkeypatch, None)
        out = _jq(await ms.supabase_execute_sql(ms.ExecuteQueryInput(query="SELECT 1")))
        assert out == {"error": "SUPABASE_DATABASE_URL not configured"}

    async def test_connect_failure(self, monkeypatch):
        _authorized(monkeypatch)
        _connect(monkeypatch, None)
        out = _jq(await ms.supabase_execute_sql(ms.ExecuteQueryInput(query="SELECT 1")))
        assert out == {"error": "Failed to connect to database"}

    async def test_select_markdown_with_rows(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(
            script={
                "rows": [(1, "alpha"), (2, "beta")],
                "description": [("id",), ("name",)],
            }
        )
        _connect(monkeypatch, conn)
        out = await ms.supabase_execute_sql(ms.ExecuteQueryInput(query="SELECT id, name FROM t"))
        assert out.startswith("# Query Results")
        assert "| 1 | alpha |" in out
        assert hasattr(conn.cursor(), "close")

    async def test_select_markdown_empty(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(script={"rows": [], "description": [("id",)]})
        _connect(monkeypatch, conn)
        out = await ms.supabase_execute_sql(ms.ExecuteQueryInput(query="SELECT id FROM t"))
        assert out == "# Query Results\n\nNo rows returned."

    async def test_select_markdown_pagination_over_100(self, monkeypatch):
        _authorized(monkeypatch)
        rows = [(i, f"v{i}") for i in range(130)]
        conn = FakeConn(script={"rows": rows, "description": [("id",), ("v",)]})
        _connect(monkeypatch, conn)
        out = await ms.supabase_execute_sql(ms.ExecuteQueryInput(query="SELECT * FROM big"))
        assert "Showing 100 of 130 rows" in out

    async def test_select_json_format(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(script={"rows": [(1, 2)], "description": [("a",), ("b",)]})
        _connect(monkeypatch, conn)
        out = _jq(
            await ms.supabase_execute_sql(
                ms.ExecuteQueryInput(
                    query="SELECT a, b FROM t", response_format=ms.ResponseFormat.JSON
                )
            )
        )
        assert out == {"columns": ["a", "b"], "rows": [[1, 2]], "row_count": 1}

    async def test_select_json_no_description(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(script={"rows": [(1,)]})
        _connect(monkeypatch, conn)
        out = _jq(
            await ms.supabase_execute_sql(
                ms.ExecuteQueryInput(query="SELECT 1", response_format=ms.ResponseFormat.JSON)
            )
        )
        assert out["columns"] == []
        assert out["rows"] == [[1]]

    async def test_non_select_success(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(script={"rowcount": 3})
        _connect(monkeypatch, conn)
        out = _jq(
            await ms.supabase_execute_sql(ms.ExecuteQueryInput(query="INSERT INTO t VALUES (1)"))
        )
        assert out["success"] is True
        assert out["affected_rows"] == 3
        assert conn.committed is True

    async def test_execute_exception_maps_error(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(script={"raise": RuntimeError("syntax error near FROM")})
        _connect(monkeypatch, conn)
        out = await ms.supabase_execute_sql(ms.ExecuteQueryInput(query="SELECT bogus"))
        assert "SQL syntax error" in out

    async def test_close_failure_is_swallowed(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(script={"rowcount": 1}, close_raises=True)
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_execute_sql(ms.ExecuteQueryInput(query="UPDATE t SET a = 1")))
        assert out["success"] is True  # close error must not break the result


# ─────────────────────────── supabase_create_table ────────────────────────────


@pytest.mark.unit
class TestCreateTable:
    async def test_requires_admin(self, monkeypatch):
        _authorized(monkeypatch, on=False)
        out = _jq(
            await ms.supabase_create_table(ms.CreateTableInput(table_name="t", columns="id int"))
        )
        assert "Admin authorization required" in out["error"]

    async def test_no_url(self, monkeypatch):
        _authorized(monkeypatch)
        _db_url(monkeypatch, None)
        out = _jq(
            await ms.supabase_create_table(ms.CreateTableInput(table_name="t", columns="id int"))
        )
        assert out == {"error": "SUPABASE_DATABASE_URL not configured"}

    async def test_success_with_and_without_if_not_exists(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn()
        _connect(monkeypatch, conn)
        out = _jq(
            await ms.supabase_create_table(
                ms.CreateTableInput(table_name="items", columns="id serial")
            )
        )
        assert out["success"] is True
        assert "CREATE TABLE IF NOT EXISTS items" in conn.executed[0][0]

        conn2 = FakeConn()
        _connect(monkeypatch, conn2)
        await ms.supabase_create_table(
            ms.CreateTableInput(table_name="items", columns="id serial", if_not_exists=False)
        )
        assert "CREATE TABLE  items" in conn2.executed[0][0]

    async def test_no_connection(self, monkeypatch):
        _authorized(monkeypatch)
        _connect(monkeypatch, None)
        out = _jq(
            await ms.supabase_create_table(ms.CreateTableInput(table_name="t", columns="id int"))
        )
        assert out == {"error": "Failed to connect to database"}

    async def test_db_error(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(script={"raise": RuntimeError("permission denied for schema public")})
        _connect(monkeypatch, conn)
        out = await ms.supabase_create_table(ms.CreateTableInput(table_name="t", columns="id int"))
        assert "Permission denied" in out


# ─────────────────────────── supabase_run_migration ──────────────────────────


@pytest.mark.unit
class TestRunMigration:
    def _mig(self, **kw) -> ms.MigrationInput:
        base = dict(
            migration_name="m1", up_sql="ALTER TABLE t ADD c int", down_sql="ALTER TABLE t DROP c"
        )
        base.update(kw)
        return ms.MigrationInput(**base)

    async def test_requires_admin(self, monkeypatch):
        _authorized(monkeypatch, on=False)
        out = _jq(await ms.supabase_run_migration(self._mig()))
        assert "Admin authorization required" in out["error"]

    async def test_no_url(self, monkeypatch):
        _authorized(monkeypatch)
        _db_url(monkeypatch, None)
        out = _jq(await ms.supabase_run_migration(self._mig()))
        assert out == {"error": "SUPABASE_DATABASE_URL not configured"}

    async def test_already_applied(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(script={"rows": [(1,)]})
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_run_migration(self._mig()))
        assert out["message"].endswith("already applied")
        assert conn.closed is True

    async def test_success(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn()
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_run_migration(self._mig()))
        assert out["success"] is True
        assert out["migration"] == "m1"
        assert conn.committed is True
        assert conn.closed is True

    async def test_no_connection(self, monkeypatch):
        _authorized(monkeypatch)
        _connect(monkeypatch, None)
        out = _jq(await ms.supabase_run_migration(self._mig()))
        assert out == {"error": "Failed to connect to database"}

    async def test_error_mapped(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(script={"raise": RuntimeError("connection lost mid-flight")})
        _connect(monkeypatch, conn)
        out = await ms.supabase_run_migration(self._mig())
        assert "connection failed" in out.lower()


# ──────────────────────────── supabase_list_tables ───────────────────────────


@pytest.mark.unit
class TestListTables:
    async def test_no_url(self, monkeypatch):
        _db_url(monkeypatch, None)
        monkeypatch.delenv("ADMIN_AUTHORIZED", raising=False)
        out = _jq(await ms.supabase_list_tables())
        assert out == {"error": "SUPABASE_DATABASE_URL not configured"}

    async def test_success(self, monkeypatch):
        _authorized(monkeypatch)
        conn = FakeConn(script={"rows": [("alpha", "BASE TABLE"), ("beta", "VIEW")]})
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_list_tables())
        assert out["count"] == 2
        assert out["tables"][0] == {"name": "alpha", "type": "BASE TABLE"}

    async def test_no_connection_and_error(self, monkeypatch):
        _authorized(monkeypatch)
        _connect(monkeypatch, None)
        out = _jq(await ms.supabase_list_tables())
        assert out == {"error": "Failed to connect to database"}

        conn = FakeConn(script={"raise": RuntimeError("parse failure")})
        _connect(monkeypatch, conn)
        out2 = await ms.supabase_list_tables()
        assert "syntax" in out2.lower() or "parse" in out2.lower()


# ─────────────────────────── supabase_explain_query ──────────────────────────


@pytest.mark.unit
class TestExplainQuery:
    async def test_no_connection(self, monkeypatch):
        _connect(monkeypatch, None)
        out = _jq(await ms.supabase_explain_query(ms.ExplainQueryInput(query="SELECT * FROM t")))
        assert out == {"error": "Failed to connect to database"}

    async def test_plan_without_analyze(self, monkeypatch):
        conn = FakeConn(script={"rows": ([{"Plan": {"Node": "Seq Scan"}}],)})
        _connect(monkeypatch, conn)
        out = _jq(
            await ms.supabase_explain_query(
                ms.ExplainQueryInput(query="SELECT * FROM t", analyze=False)
            )
        )
        assert out["plan"] == {"Plan": {"Node": "Seq Scan"}}
        executed = conn.executed[0][0]
        assert executed.startswith("EXPLAIN (FORMAT JSON)")

    async def test_plan_with_analyze(self, monkeypatch):
        conn = FakeConn(script={"rows": ([{"Plan": "X"}],)})
        _connect(monkeypatch, conn)
        out = _jq(
            await ms.supabase_explain_query(
                ms.ExplainQueryInput(query="SELECT * FROM t", analyze=True)
            )
        )
        assert out["plan"] == {"Plan": "X"}
        assert conn.executed[0][0].startswith("EXPLAIN (ANALYZE, FORMAT JSON)")

    async def test_no_plan_returned(self, monkeypatch):
        conn = FakeConn(script={"rows": []})
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_explain_query(ms.ExplainQueryInput(query="SELECT * FROM t")))
        assert out == {"error": "No execution plan returned."}

    async def test_error_mapped(self, monkeypatch):
        conn = FakeConn(script={"raise": RuntimeError("connection down")})
        _connect(monkeypatch, conn)
        out = await ms.supabase_explain_query(ms.ExplainQueryInput(query="SELECT * FROM t"))
        assert "connection failed" in out.lower()


# ─────────────────────────── supabase_describe_table ─────────────────────────


@pytest.mark.unit
class TestDescribeTable:
    def _conn(self, columns: list, indexes: list = None) -> FakeConn:
        # two sequential queries → script returns first rows for columns then indexes
        conn = FakeConn()
        results = [
            {"rows": columns, "description": None},
            {"rows": indexes or [], "description": None},
        ]

        class MultiCursor(FakeCursor):
            _call = 0

            def execute(self, query, params=None):  # noqa: ANN001
                type(self)._call += 1
                script = results[min(type(self)._call - 1, len(results) - 1)]
                self._rows = list(script["rows"])
                self.description = script["description"]

        conn.cursor = lambda: MultiCursor(conn)  # type: ignore[method-assign]
        return conn

    async def test_no_connection(self, monkeypatch):
        _connect(monkeypatch, None)
        out = _jq(await ms.supabase_describe_table(ms.DescribeTableInput(table_name="t")))
        assert out == {"error": "Failed to connect to database"}

    async def test_not_found(self, monkeypatch):
        conn = self._conn(columns=[])
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_describe_table(ms.DescribeTableInput(table_name="ghost")))
        assert out == {"error": "Table 'ghost' not found"}

    async def test_found_with_indexes(self, monkeypatch):
        conn = self._conn(
            columns=[("id", "integer", "NO", None), ("name", "text", "YES", "'x'")],
            indexes=[("t_pkey", "CREATE INDEX ...")],
        )
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_describe_table(ms.DescribeTableInput(table_name="t")))
        assert out["table"] == "t"
        assert out["columns"][0]["nullable"] is False
        assert out["columns"][1]["nullable"] is True
        assert out["indexes"][0]["name"] == "t_pkey"

    async def test_error_mapped(self, monkeypatch):
        conn = FakeConn(script={"raise": RuntimeError("permission denied")})
        _connect(monkeypatch, conn)
        out = await ms.supabase_describe_table(ms.DescribeTableInput(table_name="t"))
        assert "Permission denied" in out


@pytest.mark.unit
def test_character_limit_and_module_shape():
    assert ms.CHARACTER_LIMIT == 25000
    assert ms.ResponseFormat.MARKDOWN.value == "markdown"
    # FastMCP registration keeps the tool names discoverable
    names = (
        {t.name for t in ms.mcp._tool_manager.list_tools()}
        if hasattr(ms.mcp, "_tool_manager")
        else set()
    )
    if names:  # newer mcp SDK exposes a tool manager
        assert {"supabase_execute_sql", "supabase_create_table"} <= names


@pytest.mark.unit
def test_get_supabase_db_url_settings_fallback(monkeypatch):
    """When env is empty the settings attribute is used (admin only)."""
    from types import SimpleNamespace

    monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
    monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
    monkeypatch.setattr(
        ms, "settings", SimpleNamespace(supabase_database_url="postgresql://from-settings")
    )
    assert ms._get_supabase_db_url() == "postgresql://from-settings"


# ───────────────────── nested loguru-fallback error blocks ───────────────────


@pytest.mark.unit
class TestLoguruFallbackBlocks:
    """Cover the ``import loguru`` fallback inside the finally-close handlers.

    ``sys.modules["loguru"] = None`` makes ``import loguru`` raise ImportError
    so the inner ``except`` (logger.warning("Exception suppressed")) runs.
    """

    async def test_execute_sql_close_error(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "loguru", None)
        conn = FakeConn(script={"rowcount": 1}, close_raises=True)
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_execute_sql(ms.ExecuteQueryInput(query="UPDATE t SET a=1")))
        assert out["success"] is True

    async def test_create_table_close_error(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "loguru", None)
        conn = FakeConn(close_raises=True)
        _connect(monkeypatch, conn)
        out = _jq(
            await ms.supabase_create_table(ms.CreateTableInput(table_name="t", columns="id int"))
        )
        assert out["success"] is True

    async def test_run_migration_close_error(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "loguru", None)
        conn = FakeConn()
        conn.close_raises = True
        _connect(monkeypatch, conn)
        out = _jq(
            await ms.supabase_run_migration(
                ms.MigrationInput(migration_name="m", up_sql="SELECT 1", down_sql="SELECT 1")
            )
        )
        assert out["success"] is True

    async def test_list_tables_close_error(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "loguru", None)
        conn = FakeConn(script={"rows": [("t", "BASE TABLE")]}, close_raises=True)
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_list_tables())
        assert out["count"] == 1

    async def test_explain_close_error(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "loguru", None)
        conn = FakeConn(script={"rows": ([{"plan": 1}],)}, close_raises=True)
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_explain_query(ms.ExplainQueryInput(query="SELECT * FROM t")))
        assert out["plan"] == {"plan": 1}

    async def test_describe_close_error(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "loguru", None)
        conn = TestDescribeTable()._conn(columns=[("id", "integer", "NO", None)], indexes=[])
        conn.close_raises = True
        _connect(monkeypatch, conn)
        out = _jq(await ms.supabase_describe_table(ms.DescribeTableInput(table_name="t")))
        assert out["table"] == "t"
