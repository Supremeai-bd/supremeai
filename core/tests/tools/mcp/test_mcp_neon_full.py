"""Full-coverage tests for tools/mcp/mcp_neon.py (Task 7-f).

DB access faked via the shared fake ``psycopg2`` module (conftest) and
Neon REST API access faked by monkeypatching ``httpx.AsyncClient`` with
an in-memory stub — no real network anywhere.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import tools.mcp.mcp_neon as mn


class FakeCursor:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn
        self.description = None
        self.rowcount = 0
        self._rows: list[tuple] = []

    def execute(self, query: Any, params: Any = None) -> None:
        self.conn.executed.append((str(query), params))
        self._rows = list(self.conn.script.get("rows", []))
        self.description = self.conn.script.get("description")
        self.rowcount = self.conn.script.get("rowcount", 0)
        if self.conn.script.get("raise"):
            raise self.conn.script["raise"]

    def fetchall(self) -> list[tuple]:
        return list(self._rows)

    def close(self) -> None:
        self.closed = True


class FakeConn:
    def __init__(self, script: dict[str, Any] | None = None):
        self.script = script or {}
        self.executed: list[tuple[str, Any]] = []
        self.committed = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload)

    def json(self) -> Any:
        return self._payload


class FakeAsyncClient:
    """Async context manager standing in for httpx.AsyncClient."""

    last_instance: FakeAsyncClient | None = None

    def __init__(self, response: FakeResponse | None = None, **kwargs):
        self.response = response or FakeResponse()
        self.calls: list[tuple[str, str, dict]] = []
        FakeAsyncClient.last_instance = self

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("GET", url, kwargs))
        return self.response

    async def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return self.response

    async def delete(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("DELETE", url, kwargs))
        return self.response


def _jq(payload: str) -> Any:
    return json.loads(payload)


def _admin(monkeypatch, on: bool = True) -> None:
    monkeypatch.setenv("ADMIN_AUTHORIZED", "true" if on else "false")


def _connect(monkeypatch, conn: FakeConn | None) -> None:
    if conn is None:
        monkeypatch.setattr(mn.psycopg2, "connect", lambda *a, **kw: None)
    else:
        monkeypatch.setattr(mn.psycopg2, "connect", lambda *a, **kw: conn)


@pytest.fixture
def fake_http(monkeypatch):
    """Install the fake httpx.AsyncClient and return the response factory."""
    holder: dict[str, FakeResponse] = {}

    def install(status_code: int = 200, payload: Any = None, text: str = ""):
        holder["resp"] = FakeResponse(status_code, payload, text)
        monkeypatch.setattr(
            "httpx.AsyncClient", lambda **kw: FakeAsyncClient(response=holder["resp"])
        )
        return holder["resp"]

    return install


# ───────────────────────────── unit helpers ──────────────────────────────────


@pytest.mark.unit
class TestHelpers:
    def test_neon_db_url_unauthorized(self, monkeypatch):
        _admin(monkeypatch, on=False)
        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://n")
        assert mn._get_neon_db_url() == ""

    def test_neon_db_url_from_env(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://n1")
        assert mn._get_neon_db_url() == "postgresql://n1"

    def test_neon_api_key_unauthorized_and_missing(self, monkeypatch):
        _admin(monkeypatch, on=False)
        monkeypatch.setenv("NEON_API_KEY", "k")
        assert mn._get_neon_api_key() == ""
        _admin(monkeypatch)
        monkeypatch.delenv("NEON_API_KEY", raising=False)
        assert mn._get_neon_api_key() == ""

    def test_neon_api_key_from_env(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_API_KEY", "secret-key")
        assert mn._get_neon_api_key() == "secret-key"

    def test_get_connection_sqlite(self, monkeypatch):
        assert mn._get_connection("sqlite:////tmp/x") is None
        assert mn._get_connection(None) is None  # no url configured

    def test_get_connection_error(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://bad")

        def boom(*a, **kw):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(mn.psycopg2, "connect", boom)
        assert mn._get_connection() is None

    def test_handle_db_error_mapping(self):
        assert "connection failed" in mn._handle_db_error(Exception("Connection closed"))
        assert "syntax" in mn._handle_db_error(Exception("syntax error"))
        assert "Permission" in mn._handle_db_error(Exception("permission denied"))
        assert mn._handle_db_error(Exception("x")).startswith("Error: Database operation")


# ─────────────────────────── neon_execute_sql ────────────────────────────────


@pytest.mark.unit
class TestNeonExecuteSql:
    async def test_destructive_requires_admin(self, monkeypatch):
        _admin(monkeypatch, on=False)
        out = _jq(await mn.neon_execute_sql(mn.ExecuteQueryInput(query="TRUNCATE users")))
        assert out["error"].startswith("Admin authorization required")

    async def test_no_url(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
        out = _jq(await mn.neon_execute_sql(mn.ExecuteQueryInput(query="SELECT 1")))
        assert out == {"error": "NEON_DATABASE_URL not configured"}

    async def test_explicit_database_url_bypasses_env(self, monkeypatch):
        _admin(monkeypatch, on=False)  # destructive check skipped for SELECT anyway
        conn = FakeConn(script={"rows": [(1,)], "description": [("one",)]})
        _connect(monkeypatch, conn)
        out = await mn.neon_execute_sql(
            mn.ExecuteQueryInput(query="SELECT 1", database_url="postgresql://branch")
        )
        assert out.startswith("| one |")

    async def test_no_connection(self, monkeypatch):
        _admin(monkeypatch)
        _connect(monkeypatch, None)
        out = _jq(await mn.neon_execute_sql(mn.ExecuteQueryInput(query="SELECT 1")))
        assert out == {"error": "Failed to connect to Neon database"}

    async def test_select_markdown(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://n")
        conn = FakeConn(script={"rows": [(1, "a")], "description": [("id",), ("v",)]})
        _connect(monkeypatch, conn)
        out = await mn.neon_execute_sql(mn.ExecuteQueryInput(query="SELECT id, v FROM t"))
        assert out.startswith("| id | v |")
        assert "| 1 | a |" in out
        assert conn.closed is True

    async def test_select_markdown_empty(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://n")
        conn = FakeConn(script={"rows": [], "description": [("id",)]})
        _connect(monkeypatch, conn)
        out = await mn.neon_execute_sql(mn.ExecuteQueryInput(query="SELECT id FROM t"))
        assert out == "No results found."

    async def test_select_json(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://n")
        conn = FakeConn(script={"rows": [(5, "x")], "description": [("id",), ("v",)]})
        _connect(monkeypatch, conn)
        out = _jq(
            await mn.neon_execute_sql(
                mn.ExecuteQueryInput(
                    query="SELECT id, v FROM t", response_format=mn.ResponseFormat.JSON
                )
            )
        )
        assert out == [{"id": 5, "v": "x"}]

    async def test_non_select_success(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://n")
        conn = FakeConn(script={"rowcount": 7})
        _connect(monkeypatch, conn)
        out = _jq(await mn.neon_execute_sql(mn.ExecuteQueryInput(query="DELETE FROM t")))
        assert out["success"] is True
        assert out["affected_rows"] == 7
        assert conn.committed is True

    async def test_error_mapped(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://n")
        conn = FakeConn(script={"raise": RuntimeError("cannot parse statement")})
        _connect(monkeypatch, conn)
        out = await mn.neon_execute_sql(mn.ExecuteQueryInput(query="SELECT bogus"))
        assert "syntax" in out.lower() or "parse" in out.lower()


# ─────────────────────────── neon_list_tables ────────────────────────────────


@pytest.mark.unit
class TestNeonListTables:
    async def test_no_url(self, monkeypatch):
        monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
        _admin(monkeypatch, on=False)
        out = _jq(await mn.neon_list_tables())
        assert out == {"error": "NEON_DATABASE_URL not configured"}

    async def test_success(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://n")
        conn = FakeConn(script={"rows": [("t1", "BASE TABLE")]})
        _connect(monkeypatch, conn)
        out = _jq(await mn.neon_list_tables())
        assert out["count"] == 1 and out["tables"][0]["name"] == "t1"

    async def test_no_connection_and_error(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://n")
        _connect(monkeypatch, None)
        out = _jq(await mn.neon_list_tables())
        assert out == {"error": "Failed to connect to Neon database"}
        conn = FakeConn(script={"raise": RuntimeError("connection broke")})
        _connect(monkeypatch, conn)
        out2 = await mn.neon_list_tables()
        assert "connection failed" in out2.lower()


# ──────────────────────────── neon branch API ────────────────────────────────


@pytest.mark.unit
class TestNeonBranchApi:
    async def test_list_branches_no_api_key(self, monkeypatch):
        _admin(monkeypatch, on=False)
        out = _jq(await mn.neon_list_branches(mn.ListBranchesInput(project_id="p1")))
        assert out == {"error": "NEON_API_KEY not configured"}

    async def test_list_branches_success(self, monkeypatch, fake_http):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_API_KEY", "k1")
        fake_http(200, {"branches": [{"id": "b1"}]})
        out = _jq(await mn.neon_list_branches(mn.ListBranchesInput(project_id="p1")))
        assert out["branches"][0]["id"] == "b1"
        client = FakeAsyncClient.last_instance
        assert client.calls[0][1].endswith("/projects/p1/branches")
        assert client.calls[0][2]["headers"]["Authorization"] == "Bearer k1"

    async def test_list_branches_api_error(self, monkeypatch, fake_http):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_API_KEY", "k1")
        fake_http(500, {}, text="boom")
        out = _jq(await mn.neon_list_branches(mn.ListBranchesInput(project_id="p1")))
        assert out["error"] == "Neon API error: 500"

    async def test_create_branch_requires_admin(self, monkeypatch):
        _admin(monkeypatch, on=False)
        out = _jq(
            await mn.neon_create_branch(mn.CreateBranchInput(project_id="p", branch_name="feat"))
        )
        assert "Admin authorization required" in out["error"]

    async def test_create_branch_no_key(self, monkeypatch):
        _admin(monkeypatch)
        monkeypatch.delenv("NEON_API_KEY", raising=False)
        out = _jq(
            await mn.neon_create_branch(mn.CreateBranchInput(project_id="p", branch_name="feat"))
        )
        assert out == {"error": "NEON_API_KEY not configured"}

    async def test_create_branch_success_with_parent(self, monkeypatch, fake_http):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_API_KEY", "k1")
        fake_http(201, {"branch": {"id": "b9"}})
        out = _jq(
            await mn.neon_create_branch(
                mn.CreateBranchInput(project_id="p", branch_name="feat", parent_id="parent-1")
            )
        )
        assert out["branch"]["id"] == "b9"
        client = FakeAsyncClient.last_instance
        assert client.calls[0][2]["json"]["branch"]["parent_id"] == "parent-1"

    async def test_create_branch_api_error(self, monkeypatch, fake_http):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_API_KEY", "k1")
        fake_http(403, {}, text="forbidden")
        out = _jq(
            await mn.neon_create_branch(mn.CreateBranchInput(project_id="p", branch_name="feat"))
        )
        assert out["error"] == "Neon API error: 403"

    async def test_delete_branch_requires_admin(self, monkeypatch):
        _admin(monkeypatch, on=False)
        out = _jq(await mn.neon_delete_branch(mn.DeleteBranchInput(project_id="p", branch_id="b")))
        assert "Admin authorization required" in out["error"]

    async def test_delete_branch_success(self, monkeypatch, fake_http):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_API_KEY", "k1")
        fake_http(204)
        out = _jq(await mn.neon_delete_branch(mn.DeleteBranchInput(project_id="p", branch_id="b1")))
        assert out == {"success": True, "deleted_branch_id": "b1"}
        client = FakeAsyncClient.last_instance
        assert client.calls[0][0] == "DELETE"
        assert "/projects/p/branches/b1" in client.calls[0][1]

    async def test_delete_branch_api_error(self, monkeypatch, fake_http):
        _admin(monkeypatch)
        monkeypatch.setenv("NEON_API_KEY", "k1")
        fake_http(404, {}, text="missing")
        out = _jq(await mn.neon_delete_branch(mn.DeleteBranchInput(project_id="p", branch_id="b1")))
        assert out["error"] == "Neon API error: 404"


@pytest.mark.unit
def test_neon_constants():
    assert mn.CHARACTER_LIMIT == 25000
    assert mn.NEON_API_BASE == "https://console.neon.tech/api/v2"
