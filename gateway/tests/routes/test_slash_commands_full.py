"""Full-coverage tests for api/routes/slash_commands.py (Task 7-c).

Strategy:
    - Minimal FastAPI app mounting ONLY slash_commands.router
      (prefix /api/commands, auth bypassed deterministically).
    - ``database.supabase_client.get_db`` is replaced with a dict-backed
      fake at the source module (handlers import it lazily at call time).
    - LLM gateway, KnowledgeBaseIndexer and HFImageGenerator are patched.

All nine command handlers are exercised (success, arg-validation errors and
downstream-failure branches) plus dispatch/401/unknown-command paths.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import api.routes.slash_commands as sc
from api.deps import get_current_user_token

SUB = "user-1"


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]):
        self.data = rows


class FakeTable:
    def __init__(self, rows: list[dict[str, Any]], ops: list[tuple], fail: bool = False):
        self._rows = rows
        self._ops = ops
        self._fail = fail

    def _rec(self, name, *a, **k):
        self._ops.append((name, a, k))
        return self

    def select(self, *a, **k):
        return self._rec("select", *a, **k)

    def eq(self, *a, **k):
        return self._rec("eq", *a, **k)

    def order(self, *a, **k):
        return self._rec("order", *a, **k)

    def limit(self, *a, **k):
        return self._rec("limit", *a, **k)

    def delete(self, *a, **k):
        return self._rec("delete", *a, **k)

    def execute(self) -> FakeResult:
        self._ops.append(("execute", (), {}))
        if self._fail:
            raise RuntimeError("delete failed")
        return FakeResult(list(self._rows))


class FakeSupabaseDB:
    """Replacement for database.supabase_client.get_db() results (SupabaseDB instances)."""

    def __init__(
        self,
        tables: dict[str, list[dict[str, Any]]] | None = None,
        fail_on: set[str] | None = None,
    ):
        self.tables = tables if tables is not None else {}
        self.fail_on = fail_on or set()
        self.ops: list[tuple] = []
        FakeSupabaseDB.last = self

    @property
    def client(self):
        holder = self

        class _Client:
            def table(self, name):
                return FakeTable(
                    holder.tables.get(name, []),
                    holder.ops,
                    fail=name in holder.fail_on,
                )

        return _Client()


@pytest_asyncio.fixture
async def commands_env(monkeypatch):
    app = FastAPI()
    app.include_router(sc.router)

    async def fake_user():
        return {"sub": SUB, "role": "user"}

    app.dependency_overrides[get_current_user_token] = fake_user

    llm_calls: list[dict[str, Any]] = []

    async def fake_acompletion(**kwargs):
        llm_calls.append(kwargs)
        return {"text": "LLM says: done"}

    monkeypatch.setattr("core.llm.llm_gateway.llm_gateway.acompletion", fake_acompletion)

    shared_tables: dict[str, list[dict[str, Any]]] = {
        "conversations": [{"id": "conv-1", "title": "My Chat", "user_id": SUB}],
        "messages": [
            {"role": "user", "content": "hello " * 120, "created_at": "t1"},
            {"role": "assistant", "content": "hi there", "created_at": "t2"},
        ],
    }
    monkeypatch.setattr(
        "database.supabase_client.get_db",
        lambda: FakeSupabaseDB(shared_tables),
    )

    kb_calls: list[tuple] = []

    class FakeIndexer:
        def search_knowledge(self, query, n_results=5):
            kb_calls.append((query, n_results))
            return [{"text": "kb snippet", "metadata": {"type": "doc"}}]

    monkeypatch.setattr("tools.knowledge.knowledge_base_indexer.KnowledgeBaseIndexer", FakeIndexer)

    class FakeImageGen:
        async def generate_image(self, prompt=None, model=None, output_path=None):
            return {"success": True, "image_path": output_path, "prompt": prompt}

    monkeypatch.setattr("tools.media.image_generator.HFImageGenerator", FakeImageGen)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, llm_calls, kb_calls, shared_tables

    app.dependency_overrides.clear()


async def execute(http: AsyncClient, command: str, args: dict | None = None) -> dict:
    resp = await http.post("/api/commands/execute", json={"command": command, "args": args or {}})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.unit
class TestRegistry:
    async def test_list_commands(self, commands_env):
        http, *_ = commands_env
        resp = await http.get("/api/commands/")
        assert resp.status_code == 200
        commands = resp.json()
        assert len(commands) == 9
        by_id = {c["id"] for c in commands}
        assert by_id == {
            "research",
            "summarize",
            "image",
            "code",
            "translate",
            "think",
            "export",
            "clear",
            "help",
        }
        research = next(c for c in commands if c["id"] == "research")
        assert research["name"] == "/research"
        assert {p["name"] for p in research["parameters"]} == {"query", "depth"}


@pytest.mark.unit
class TestDispatch:
    async def test_unknown_command_400(self, commands_env):
        http, *_ = commands_env
        resp = await http.post("/api/commands/execute", json={"command": "/nope"})
        assert resp.status_code == 400
        assert "Unknown command" in resp.json()["detail"]
        assert "/help" in resp.json()["detail"]

    async def test_command_name_normalization(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "///HELP  ")
        assert body["status"] == "success"
        assert body["command"] == "///HELP  "

    async def test_invalid_token_401(self, commands_env):
        http, *_ = commands_env
        app = http._transport.app
        app.dependency_overrides[get_current_user_token] = lambda: {}
        try:
            resp = await http.post("/api/commands/execute", json={"command": "/help"})
        finally:

            async def fake_user():
                return {"sub": SUB}

            app.dependency_overrides[get_current_user_token] = fake_user
        assert resp.status_code == 401

    async def test_handler_exception_500(self, commands_env, monkeypatch):
        http, *_ = commands_env

        async def boom(args, user_id):
            raise RuntimeError("handler exploded")

        monkeypatch.setitem(sc._HANDLERS, "help", boom)
        resp = await http.post("/api/commands/execute", json={"command": "/help"})
        assert resp.status_code == 500
        assert "handler exploded" in resp.json()["detail"]


@pytest.mark.unit
class TestResearchCommand:
    async def test_missing_query_error(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/research", {})
        assert body["status"] == "error"
        assert body["result"]["error"] == "Query is required for /research"

    async def test_success_with_kb_and_llm(self, commands_env):
        http, llm_calls, kb_calls, _ = commands_env
        body = await execute(http, "/research", {"query": "llm agents", "depth": "deep"})
        assert body["status"] == "success"
        result = body["result"]
        assert result["summary"] == "LLM says: done"
        assert result["kb_results_count"] == 1
        assert result["depth"] == "deep"
        assert kb_calls == [("llm agents", 10)]  # deep → n_results=10
        assert llm_calls[0]["context"].task_type == "research"

    async def test_llm_failure_fallback_summary(self, commands_env, monkeypatch):
        http, _, kb_calls, _ = commands_env

        async def boom(**kwargs):
            raise RuntimeError("llm down")

        monkeypatch.setattr("core.llm.llm_gateway.llm_gateway.acompletion", boom)
        body = await execute(http, "/research", {"query": "topic"})
        assert body["status"] == "success"
        result = body["result"]
        assert "Knowledge base returned 1 results" in result["summary"]
        assert "LLM synthesis unavailable" in result["summary"]


@pytest.mark.unit
class TestSummarizeCommand:
    async def test_default_conversation_and_llm(self, commands_env):
        http, llm_calls, _, shared = commands_env
        body = await execute(http, "/summarize", {})
        assert body["status"] == "success"
        result = body["result"]
        assert result["conversation_id"] == "conv-1"
        assert result["message_count"] == 2
        assert result["summary"] == "LLM says: done"
        assert llm_calls[0]["context"].task_type == "summarization"

    async def test_no_conversations_error(self, commands_env):
        http, _, _, shared = commands_env
        shared["conversations"].clear()
        body = await execute(http, "/summarize", {})
        assert body["status"] == "error"
        assert body["result"]["error"] == "No conversations found"

    async def test_no_messages_empty_summary(self, commands_env):
        http, _, _, shared = commands_env
        shared["messages"].clear()
        body = await execute(http, "/summarize", {"conversation_id": "conv-1"})
        assert body["status"] == "success"
        assert "no messages" in body["result"]["summary"]

    async def test_llm_failure_fallback_truncation(self, commands_env, monkeypatch):
        http, *_ = commands_env

        async def boom(**kwargs):
            raise RuntimeError("llm down")

        monkeypatch.setattr("core.llm.llm_gateway.llm_gateway.acompletion", boom)
        body = await execute(http, "/summarize", {"conversation_id": "conv-1"})
        result = body["result"]["summary"]
        assert result.endswith("...")
        assert len(result) == 203  # first 200 chars + "..."


@pytest.mark.unit
class TestImageCommand:
    async def test_missing_prompt_error(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/image", {})
        assert body["status"] == "error"

    async def test_success(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/image", {"prompt": "a cat", "model": "sdxl"})
        assert body["status"] == "success"
        assert body["result"]["success"] is True
        assert body["result"]["prompt"] == "a cat"
        assert body["result"]["image_path"].startswith("data/generated_")

    async def test_generation_failure(self, commands_env, monkeypatch):
        http, *_ = commands_env

        class BrokenGen:
            async def generate_image(self, **kwargs):
                raise RuntimeError("gpu missing")

        monkeypatch.setattr("tools.media.image_generator.HFImageGenerator", BrokenGen)
        body = await execute(http, "/image", {"prompt": "a cat"})
        assert body["status"] == "error"
        assert "gpu missing" in body["result"]["error"]


@pytest.mark.unit
class TestSimpleCommands:
    async def test_code_mode(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/code", {"framework": "react"})
        assert body["result"] == {
            "mode": "code",
            "framework": "react",
            "message": (
                "Code mode activated with react framework. Your next message "
                "will be treated as code instructions."
            ),
        }

    async def test_think_invalid_mode_defaults(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/think", {"mode": "bogus"})
        assert body["result"]["reasoning_engine"] == "tree_of_thought"

    async def test_think_valid_mode(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/think", {"mode": "debate"})
        assert body["result"]["reasoning_engine"] == "debate"


@pytest.mark.unit
class TestTranslateCommand:
    async def test_missing_args(self, commands_env):
        http, *_ = commands_env
        no_text = await execute(http, "/translate", {"target_language": "fr"})
        assert no_text["result"]["error"] == "Text is required for /translate"
        no_target = await execute(http, "/translate", {"text": "hi"})
        assert no_target["result"]["error"] == ("Target language is required for /translate")

    async def test_success(self, commands_env):
        http, llm_calls, *_ = commands_env
        body = await execute(http, "/translate", {"text": "hello", "target_language": "Spanish"})
        assert body["result"]["translated"] == "LLM says: done"
        assert body["result"]["target_language"] == "Spanish"
        assert llm_calls[0]["context"].task_type == "translation"

    async def test_failure_error_result(self, commands_env, monkeypatch):
        http, *_ = commands_env

        async def boom(**kwargs):
            raise RuntimeError("provider down")

        monkeypatch.setattr("core.llm.llm_gateway.llm_gateway.acompletion", boom)
        body = await execute(http, "/translate", {"text": "hello", "target_language": "fr"})
        assert body["status"] == "error"
        assert "Translation failed: provider down" in body["result"]["error"]


@pytest.mark.unit
class TestExportCommand:
    async def test_markdown_success(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/export", {})
        assert body["result"]["format"] == "markdown"
        assert body["result"]["message_count"] == 2
        assert body["result"]["content"].startswith("# My Chat")
        assert "### User" in body["result"]["content"]

    async def test_no_conversations_error(self, commands_env):
        http, _, _, shared = commands_env
        shared["conversations"].clear()
        body = await execute(http, "/export", {})
        assert body["result"]["error"] == "No conversations found to export"

    async def test_no_messages_error(self, commands_env):
        http, _, _, shared = commands_env
        shared["messages"].clear()
        body = await execute(http, "/export", {})
        assert body["result"]["error"] == "No messages to export"

    async def test_explicit_conversation_unknown_title(self, commands_env):
        http, _, _, shared = commands_env
        shared["conversations"].clear()
        body = await execute(http, "/export", {"conversation_id": "conv-1"})
        # conversation lookup returns nothing → title falls back to "Export"
        assert body["result"]["content"].startswith("# Export")

    async def test_pdf_export(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/export", {"format": "pdf"})
        assert body["result"]["format"] == "pdf"
        raw = bytes.fromhex(body["result"]["content_base64"])
        assert raw.startswith(b"%PDF")

    async def test_docx_export(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/export", {"format": "docx"})
        assert body["result"]["format"] == "docx"
        raw = bytes.fromhex(body["result"]["content_base64"])
        assert raw[:2] == b"PK"  # zip magic of a docx container

    async def test_unsupported_format(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/export", {"format": "rtf"})
        assert "Unsupported export format: rtf" in body["result"]["error"]


@pytest.mark.unit
class TestClearCommand:
    async def test_clear_success(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/clear", {})
        assert body["result"] == {
            "status": "cleared",
            "conversation_id": "conv-1",
            "message": "Conversation cleared successfully.",
        }
        fake_db = FakeSupabaseDB.last
        assert ("delete", (), {}) in fake_db.ops

    async def test_clear_no_conversations(self, commands_env):
        http, _, _, shared = commands_env
        shared["conversations"].clear()
        body = await execute(http, "/clear", {})
        assert body["result"]["error"] == "No conversations found to clear"

    async def test_clear_delete_failure(self, commands_env, monkeypatch):
        http, *_ = commands_env

        def broken_db():
            return FakeSupabaseDB(
                tables={"conversations": [{"id": "conv-1"}]},
                fail_on={"messages"},
            )

        monkeypatch.setattr("database.supabase_client.get_db", broken_db)
        body = await execute(http, "/clear", {"conversation_id": "conv-1"})
        assert "Failed to clear conversation" in body["result"]["error"]


@pytest.mark.unit
class TestHelpCommand:
    async def test_help_lists_all(self, commands_env):
        http, *_ = commands_env
        body = await execute(http, "/help")
        result = body["result"]
        assert result["total"] == 9
        names = {c["name"] for c in result["commands"]}
        assert "/image" in names
        by_name = {c["name"]: c for c in result["commands"]}
        assert "parameters" not in by_name["/help"]  # help has no parameters
        assert by_name["/image"]["parameters"][0]["required"] is True
