"""MCP server transport (stdio/SSE), prompt bodies, and import-degradation coverage.

Extends test_mcp_server_tools.py (handler-level) with the edges that need controlled
process conditions (g42b/g42c/g43b lessons):

1. Prompt templates — deploy_preflight + recall_context bodies and the
   ``arguments is None`` normalization branch (heal_error defaults).
2. Import matrix — second-copy ``exec_module`` with halted optional packages
   (``sys.modules[name] = None``) exercises every module-level ``except`` branch
   without touching the shared module instance.
3. ``main()`` transport selection — stdio (default) with loguru redirect + its
   absence-tolerant except branch; SSE app construction with fake starlette/uvicorn
   modules and direct ``handle_sse`` invocation; SSE missing-deps ``sys.exit(1)``.
4. session-stats resource with a live sliding store (get_stats present/absent) and
   the ``delete_entities`` dispatch branch (policy ALLOWed).

Wire-first: tests only — zero owner production code touched.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import sys
import types as _stdlib_types
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest

from memory import mcp_server
from memory.mcp_server import build_server

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = BACKEND_ROOT / "memory" / "mcp_server.py"


# ---------------------------------------------------------------------------
# Fakes — mirrored minimal harness (test_mcp_server_tools owns the originals)
# ---------------------------------------------------------------------------
def _mk_type(*args, **kwargs):
    obj = SimpleNamespace()
    obj.__dict__.update(kwargs)
    return obj


class _FakeServer:
    def __init__(self, name):
        self.name = name
        self.handlers = {}
        self.run_calls = []

    def _reg(self, key):
        def deco(fn):
            self.handlers[key] = fn
            return fn

        return deco

    def list_tools(self):
        return self._reg("list_tools")

    def call_tool(self):
        return self._reg("call_tool")

    def list_resources(self):
        return self._reg("list_resources")

    def read_resource(self):
        return self._reg("read_resource")

    def list_prompts(self):
        return self._reg("list_prompts")

    def get_prompt(self):
        return self._reg("get_prompt")

    def create_initialization_options(self):
        return {"server": self.name}

    async def run(self, *a, **k):
        self.run_calls.append(a)


@pytest.fixture
def fake_mcp(monkeypatch):
    fake_types = SimpleNamespace(
        Tool=_mk_type,
        TextContent=_mk_type,
        Resource=_mk_type,
        Prompt=_mk_type,
        PromptArgument=_mk_type,
        PromptMessage=_mk_type,
        GetPromptResult=_mk_type,
    )
    monkeypatch.setattr(mcp_server, "types", fake_types)
    monkeypatch.setattr(mcp_server, "Tool", _mk_type)
    monkeypatch.setattr(mcp_server, "TextContent", _mk_type)
    monkeypatch.setattr(mcp_server, "Server", _FakeServer)
    monkeypatch.setattr(mcp_server, "_MCP_AVAILABLE", True)
    for flag in ("_CHROMA_OK", "_EPISODIC_OK", "_SLIDING_OK", "_SUPABASE_OK", "_RAG_OK"):
        monkeypatch.setattr(mcp_server, flag, False)
    monkeypatch.setattr(mcp_server, "audit_tool_call", lambda *a, **k: None)
    return fake_types


@pytest.fixture
def root_logging_guard():
    """main() calls logging.basicConfig(force=True) — snapshot & restore root handlers."""
    handlers = logging.root.handlers[:]
    level = logging.root.level
    yield
    logging.root.handlers = handlers
    logging.root.setLevel(level)


def _load_mcp_copy(monkeypatch: pytest.MonkeyPatch, halted: tuple[str, ...]):
    """Execute a fresh copy of mcp_server.py with selected packages import-halted."""
    for name in halted:
        monkeypatch.setitem(sys.modules, name, None)
    probe = f"mcp_server_probe_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(probe, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, probe, module)
    spec.loader.exec_module(module)
    return module


def _mod(name: str, **attrs) -> ModuleType:
    m = ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


# ---------------------------------------------------------------------------
# Prompt bodies
# ---------------------------------------------------------------------------
class TestPrompts:
    def _get_prompt(self, server):
        return server.handlers["get_prompt"]

    def test_heal_error_none_arguments_uses_defaults(self, fake_mcp):
        server = build_server()
        result = asyncio.run(self._get_prompt(server)("heal_error", None))
        text = result.messages[0].content.text
        assert "Unknown error" in text  # error_message default
        assert "No additional context provided" in text  # context default

    def test_deploy_preflight_staging_default(self, fake_mcp):
        server = build_server()
        result = asyncio.run(self._get_prompt(server)("deploy_preflight", {}))
        assert result.description == "Deployment preflight checklist for staging"
        text = result.messages[0].content.text
        assert "Deployment Preflight Check — staging" in text
        assert "R3" in text and "REQUIRE_APPROVAL" in text  # production risk gate
        assert "Memory Health" in text and "Knowledge Graph" in text

    def test_deploy_preflight_production_target_interpolated(self, fake_mcp):
        server = build_server()
        result = asyncio.run(
            self._get_prompt(server)("deploy_preflight", {"target_environment": "production"})
        )
        assert "Deployment Preflight Check — production" in result.messages[0].content.text

    def test_recall_context_interpolates_query_and_max_results(self, fake_mcp):
        server = build_server()
        result = asyncio.run(
            self._get_prompt(server)(
                "recall_context", {"query": "redis rate limits", "max_results": 7}
            )
        )
        text = result.messages[0].content.text
        assert "Context Recall — redis rate limits" in text
        assert "n=7" in text
        assert "search_semantic" in text and "get_similar_tasks" in text

    def test_unknown_prompt_returns_graceful_message(self, fake_mcp):
        server = build_server()
        result = asyncio.run(self._get_prompt(server)("no_such_prompt", None))
        assert "Unknown prompt: no_such_prompt" in result.messages[0].content.text


# ---------------------------------------------------------------------------
# Import matrix — module-level optional-degradation branches
# ---------------------------------------------------------------------------
class TestImportMatrix:
    def test_mcp_sdk_halted_marks_unavailable(self, monkeypatch):
        mod = _load_mcp_copy(monkeypatch, halted=("mcp",))
        assert mod._MCP_AVAILABLE is False

    def test_all_memory_layers_halted_set_flags_false(self, monkeypatch):
        mod = _load_mcp_copy(
            monkeypatch,
            halted=(
                "memory.chromadb_store",
                "memory.episodic_memory",
                "memory.sliding_window",
                "memory.supabase_store",
                "memory.rag_pipeline",
            ),
        )
        assert mod._CHROMA_OK is False
        assert mod._EPISODIC_OK is False
        assert mod._SLIDING_OK is False
        assert mod._SUPABASE_OK is False
        assert mod._RAG_OK is False


# ---------------------------------------------------------------------------
# main() — transport selection
# ---------------------------------------------------------------------------
class TestMainTransport:
    def test_stdio_default_transport_runs_server_on_streams(self, monkeypatch, root_logging_guard):
        monkeypatch.delenv("MEMORY_MCP_TRANSPORT", raising=False)
        monkeypatch.setitem(sys.modules, "loguru", None)  # redirect try → except-pass

        streams = ("read", "write")
        entered = []

        class _FakeStdio:
            def __call__(self):
                return self

            async def __aenter__(self):
                entered.append(True)
                return streams

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(mcp_server, "stdio_server", _FakeStdio(), raising=False)
        fake_server = _FakeServer("stdio-probe")
        monkeypatch.setattr(mcp_server, "build_server", lambda: fake_server)

        asyncio.run(mcp_server.main())

        assert entered == [True]
        assert fake_server.run_calls == [(streams[0], streams[1], {"server": "stdio-probe"})]
        # stdio contract: root logging must target stderr (stdout stays pure for frames)
        stderr_handlers = [
            h for h in logging.root.handlers if getattr(h, "stream", None) is sys.stderr
        ]
        assert stderr_handlers, "stdio mode must route root logging to stderr"

    def test_stdio_loguru_present_is_reconfigured_to_stderr(self, monkeypatch, root_logging_guard):
        monkeypatch.delenv("MEMORY_MCP_TRANSPORT", raising=False)
        removed, added = [], []

        fake_loguru = _mod(
            "loguru",
            logger=SimpleNamespace(
                remove=lambda: removed.append(True),
                add=lambda *a, **k: added.append((a, k)),
            ),
        )
        monkeypatch.setitem(sys.modules, "loguru", fake_loguru)

        class _FakeStdio:
            def __call__(self):
                return self

            async def __aenter__(self):
                return ("r", "w")

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(mcp_server, "stdio_server", _FakeStdio(), raising=False)
        fake_server = _FakeServer("loguru-probe")
        monkeypatch.setattr(mcp_server, "build_server", lambda: fake_server)

        asyncio.run(mcp_server.main())
        assert removed == [True]
        assert added and added[0][0] == (sys.stderr,)

    def test_sse_uppercase_builds_starlette_app_and_runs_uvicorn(
        self, monkeypatch, root_logging_guard
    ):
        monkeypatch.setenv("MEMORY_MCP_TRANSPORT", "SSE")  # .lower() normalization
        monkeypatch.setenv("MEMORY_MCP_PORT", "9999")

        uvicorn_calls = []
        fake_uvicorn = _mod("uvicorn", run=lambda *a, **k: uvicorn_calls.append((a, k)))

        class _FakeSseCM:
            def __init__(self, streams):
                self.streams = streams

            async def __aenter__(self):
                return self.streams

            async def __aexit__(self, *a):
                return False

        class _FakeSseTransport:
            instances = []

            def __init__(self, path):
                self.path = path
                self.handle_post_message = lambda *a, **k: None
                _FakeSseTransport.instances.append(self)

            def connect_sse(self, scope, receive, send):
                entered.append((scope, receive, send))
                return _FakeSseCM(("sse-r", "sse-w"))

        entered = []

        class _FakeRoute:
            def __init__(self, *a, **k):
                self.args, self.kwargs = a, k

        class _FakeMount(_FakeRoute):
            pass

        class _FakeStarlette:
            instances = []

            def __init__(self, routes=None):
                self.routes = routes or []
                _FakeStarlette.instances.append(self)

        monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
        monkeypatch.setitem(
            sys.modules,
            "mcp.server.sse",
            _mod("mcp.server.sse", SseServerTransport=_FakeSseTransport),
        )
        monkeypatch.setitem(
            sys.modules,
            "starlette.applications",
            _mod("starlette.applications", Starlette=_FakeStarlette),
        )
        monkeypatch.setitem(
            sys.modules,
            "starlette.routing",
            _mod("starlette.routing", Mount=_FakeMount, Route=_FakeRoute),
        )

        fake_server = _FakeServer("sse-probe")
        monkeypatch.setattr(mcp_server, "build_server", lambda: fake_server)

        asyncio.run(mcp_server.main())

        assert _FakeSseTransport.instances[0].path == "/messages/"
        app = _FakeStarlette.instances[0]
        route, mount = app.routes
        assert route.args == ("/sse",)
        assert mount.args == ("/messages/",)
        assert uvicorn_calls and uvicorn_calls[0][1] == {"host": "0.0.0.0", "port": 9999}

        # drive the SSE handler end-to-end through the fake transport
        handle_sse = route.kwargs["endpoint"]
        request = SimpleNamespace(scope={"path": "/sse"}, receive=None, _send=None)
        asyncio.run(handle_sse(request))
        assert entered and entered[0][0] == {"path": "/sse"}
        assert fake_server.run_calls == [("sse-r", "sse-w", {"server": "sse-probe"})]

    def test_sse_missing_deps_exits_1(self, monkeypatch, root_logging_guard):
        monkeypatch.setenv("MEMORY_MCP_TRANSPORT", "sse")
        monkeypatch.setitem(sys.modules, "uvicorn", None)  # import halted
        with pytest.raises(SystemExit) as exc:
            asyncio.run(mcp_server.main())
        assert exc.value.code == 1


# ---------------------------------------------------------------------------
# Resource + dispatch branches requiring a live store
# ---------------------------------------------------------------------------
class TestResourceAndDispatch:
    def _build_with_sliding(self, monkeypatch, stats_method):
        class _FakeSliding:
            def __init__(self, config=None):
                self.config = config

            if stats_method:

                def get_stats(self):
                    return {"turns": 4, "tokens": 512}

        monkeypatch.setattr(mcp_server, "_SLIDING_OK", True)
        monkeypatch.setattr(mcp_server, "SlidingWindowMemory", _FakeSliding)
        monkeypatch.setattr(mcp_server, "SlidingWindowConfig", lambda: {"cfg": True})
        return build_server()

    def test_session_stats_resource_with_get_stats(self, fake_mcp, monkeypatch):
        server = self._build_with_sliding(monkeypatch, stats_method=True)
        raw = asyncio.run(server.handlers["read_resource"]("mcp://memory/session-stats"))
        assert json.loads(raw) == {"turns": 4, "tokens": 512}

    def test_session_stats_resource_without_get_stats_attr(self, fake_mcp, monkeypatch):
        server = self._build_with_sliding(monkeypatch, stats_method=False)
        raw = asyncio.run(server.handlers["read_resource"]("mcp://memory/session-stats"))
        assert json.loads(raw) == {"status": "active"}  # hasattr fallback

    def test_dispatch_delete_entities_executes_when_allowed(self, fake_mcp, monkeypatch):
        monkeypatch.setattr(mcp_server, "evaluate_tool", lambda name: ("ALLOW", "R1"))
        server = build_server()
        call = server.handlers["call_tool"]
        asyncio.run(
            call(
                "create_entities",
                {
                    "tenant_id": "t1",
                    "entities": [{"name": "tmp", "entityType": "t", "observations": []}],
                },
            )
        )
        result = asyncio.run(
            call("delete_entities", {"tenant_id": "t1", "names": ["tmp", "ghost"]})
        )

        def payload(r):
            return r if isinstance(r, dict) else json.loads(r[0].text)

        assert payload(result) == {"deleted": ["tmp"]}
