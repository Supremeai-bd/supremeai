"""CI-collected coverage for memory/mcp_server.py — Knowledge Graph, policy/audit
shims, tool dispatch, and the MCP handler layer (fake mcp namespace + fake stores).

বাংলা: mcp_server.py হলো memory/ প্যাকেজের সবচেয়ে বড় অদেখা ব্লক ছিল (341 stmts, 0%)।
এই টেস্টগুলো `mcp` প্যাকেজ ছাড়াই (module-global monkeypatch + fake Server) পুরো
tool surface যাচাই করে:

  - KnowledgeGraph: entity/relation CRUD, dedup, cascade delete, keyword+
    semantic search fallback, chroma failure tolerance
  - _check_policy / _audit: ALLOW → None, REQUIRE_APPROVAL/DENY → block dict,
    audit latency+tenant record
  - _dispatch: ২২টি tool-এর store mapping, unavailability error JSON, unknown tool
  - call_tool handler (fake Server দিয়ে build_server): tenant enforcement,
    policy block, exception wrap — Constitution Law #11 audit trail সহ

stdio/SSE transport (main()) নেটওয়ার্ক-বাউন্ড — documented follow-up।
"""

import asyncio
import json
import types as _stdlib_types

import pytest

import memory.mcp_server as mcp_server
from memory.mcp_server import KnowledgeGraph, _check_policy, _dispatch, build_server

pytestmark = pytest.mark.memory


# ─────────────────────────────────────────────────────────────────────────────
# Fakes — কোনো chromadb/episodic backend লাগে না
# ─────────────────────────────────────────────────────────────────────────────
class _FakeChroma:
    def __init__(self):
        self.docs: dict[str, tuple[str, dict]] = {}
        self.deleted: list[str] = []
        self.query_results: list[tuple] = []
        self.fail_delete = False

    def add_document(self, doc_id, text, metadata=None):
        self.docs[doc_id] = (text, metadata)

    def add_document_incremental(self, doc_id, text, metadata=None):
        self.docs[doc_id] = (text, metadata)
        return True

    def delete(self, doc_id):
        if self.fail_delete:
            raise RuntimeError("chroma down")
        self.deleted.append(doc_id)

    def query(self, query_text, n_results=5):
        return self.query_results[:n_results]


class _FakeEpisodic:
    def __init__(self):
        self.recorded = []
        self.similar: list = []
        self.episodes: list = []

    async def record_task(self, **kw):
        self.recorded.append(kw)
        return True

    async def get_similar_past_tasks(self, query, n=3):
        return self.similar[:n]

    def recall_episodes(self, event_type=None, min_importance=None, limit=10):
        return self.episodes[:limit]


class _FakeSliding:
    def __init__(self):
        self.cleared: list[str] = []
        self.stats = {"messages": 3}

    def build_context(self, documents, query="", session_id="default", budget=None):
        return {"session_id": session_id, "docs": len(documents), "query": query}

    def get_session_stats(self, session_id="default"):
        return self.stats

    def clear(self, session_id="default"):
        self.cleared.append(session_id)
        return True


class _FakeSupabase:
    def __init__(self):
        self.facts: list[dict] = []
        self.search_results: list = []

    def save_learned_fact(self, fact):
        self.facts.append(fact)

    def search_facts(self, query):
        return self.search_results


class _FakeRAG:
    def __init__(self):
        self.ingested: list[tuple] = []

    def ingest_document(self, doc_id, content, metadata=None):
        self.ingested.append((doc_id, content, metadata))


class _FakeServer:
    """build_server()-এর decorator surface রেকর্ড করে — কোনো mcp SDK লাগে না।"""

    def __init__(self, name):
        self.name = name
        self.handlers: dict[str, object] = {}

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
        return None


def _mk_type(*args, **kwargs):
    obj = _stdlib_types.SimpleNamespace()
    obj.__dict__.update(kwargs)
    return obj


@pytest.fixture
def fake_mcp(monkeypatch):
    """module-global mcp namespace replace — reload ছাড়াই build_server চালানো যায়।"""
    fake_types = _stdlib_types.SimpleNamespace(
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
    # সব memory layer unavailable — build_server-এর degradation path + পরে দরকারমতো inject
    for flag in ("_CHROMA_OK", "_EPISODIC_OK", "_SLIDING_OK", "_SUPABASE_OK", "_RAG_OK"):
        monkeypatch.setattr(mcp_server, flag, False)
    return fake_types


@pytest.fixture
def server(fake_mcp):
    s = build_server()
    assert isinstance(s, _FakeServer)
    return s


def call_text(result_list) -> dict:
    assert len(result_list) == 1
    return json.loads(result_list[0].text)


# ─────────────────────────────────────────────────────────────────────────────
# KnowledgeGraph — pure CRUD + search
# ─────────────────────────────────────────────────────────────────────────────
def test_kg_create_entities_dedup_and_skip_empty():
    kg = KnowledgeGraph()
    created = kg.create_entities(
        [
            {"name": "alice", "entityType": "person", "observations": ["likes tea"]},
            {"name": "alice", "entityType": "person"},  # duplicate skipped
            {"name": "", "entityType": "person"},  # empty name skipped
        ]
    )
    assert [e["name"] for e in created] == ["alice"]
    assert kg._entities["alice"]["observations"] == ["likes tea"]


def test_kg_create_entities_mirror_to_chroma():
    chroma = _FakeChroma()
    kg = KnowledgeGraph(chroma_store=chroma)
    kg.create_entities([{"name": "proj", "entityType": "project", "observations": ["fast"]}])
    assert "entity::proj" in chroma.docs
    text, meta = chroma.docs["entity::proj"]
    assert meta["type"] == "entity" and meta["entity_name"] == "proj"
    assert "fast" in text


def test_kg_delete_entities_cascades_relations_and_chroma():
    chroma = _FakeChroma()
    kg = KnowledgeGraph(chroma_store=chroma)
    kg.create_entities([{"name": "a", "entityType": "t"}, {"name": "b", "entityType": "t"}])
    kg.create_relations([{"from": "a", "to": "b", "relationType": "knows"}])
    chroma.docs["entity::a"] = ("x", {})
    deleted = kg.delete_entities(["a", "missing"])
    assert deleted == ["a"]
    assert kg._relations == []  # relation cascade
    assert "entity::a" in chroma.deleted
    chroma.fail_delete = True
    kg.create_entities([{"name": "c", "entityType": "t"}])  # chroma doc writes happen
    assert kg.delete_entities(["c"]) == ["c"]  # chroma failure tolerated


def test_kg_add_observations_dedup_missing_and_chroma():
    chroma = _FakeChroma()
    kg = KnowledgeGraph(chroma_store=chroma)
    with pytest.raises(ValueError):
        kg.add_observations("ghost", ["x"])
    kg.create_entities([{"name": "e", "entityType": "t", "observations": ["seen"]}])
    added = kg.add_observations("e", ["seen", "new"])
    assert added == ["new"]  # dedup: existing observation skipped
    assert chroma.docs["entity::e"]  # chroma updated when new obs present


def test_kg_delete_observations():
    kg = KnowledgeGraph()
    assert kg.delete_observations("ghost", ["x"]) == []
    kg.create_entities([{"name": "e", "entityType": "t", "observations": ["a", "b"]}])
    removed = kg.delete_observations("e", ["a", "never-there"])
    assert removed == ["a"]
    assert kg._entities["e"]["observations"] == ["b"]


def test_kg_relations_dedup_default_type_and_delete():
    kg = KnowledgeGraph()
    rel = {"from": "a", "to": "b"}
    created = kg.create_relations([rel, {"from": "a", "to": "b", "relationType": "related_to"}])
    assert len(created) == 1  # duplicate (default type same) skipped
    assert created[0]["relationType"] == "related_to"
    kg.create_relations([{"from": "b", "to": "c", "relationType": "knows"}])
    assert kg.delete_relations([{"from": "a", "to": "b", "relationType": "related_to"}]) == 1
    assert len(kg._relations) == 1


def test_kg_read_graph_and_open_nodes():
    kg = KnowledgeGraph()
    kg.create_entities([{"name": "a", "entityType": "t"}, {"name": "b", "entityType": "t"}])
    kg.create_relations([{"from": "a", "to": "b", "relationType": "knows"}])
    graph = kg.read_graph()
    assert {e["name"] for e in graph["entities"]} == {"a", "b"}
    opened = kg.open_nodes(["a"])
    assert [e["name"] for e in opened["entities"]] == ["a"]
    assert opened["relations"][0]["from"] == "a"


def test_kg_search_nodes_keyword_then_semantic_fallback():
    chroma = _FakeChroma()
    kg = KnowledgeGraph(chroma_store=chroma)
    kg.create_entities(
        [
            {"name": "alice", "entityType": "person", "observations": ["drinks tea"]},
            {"name": "bob", "entityType": "robot"},
        ]
    )
    assert len(kg.search_nodes("tea")) == 1  # observation keyword hit
    assert len(kg.search_nodes("robot")) == 1  # entityType hit
    # keyword miss → chroma semantic fallback, entity-typed metadata mapped
    chroma.query_results = [
        ("entity::bob", 0.9, {"metadata": {"type": "entity", "entity_name": "bob"}}),
        ("doc::1", 0.8, {"metadata": {"type": "other"}}),  # non-entity filtered
        ("entity::ghost", 0.7, {"metadata": {"type": "entity", "entity_name": "ghost"}}),
    ]
    hits = kg.search_nodes("zzz-no-keyword-match")
    assert [h["name"] for h in hits] == ["bob"]

    # chroma failure tolerated → []
    def boom(query_text, n_results=5):
        raise RuntimeError("down")

    chroma.query = boom
    assert kg.search_nodes("zzz-no-keyword-match") == []


# ─────────────────────────────────────────────────────────────────────────────
# Policy & audit shims
# ─────────────────────────────────────────────────────────────────────────────
def test_check_policy_allow_returns_none():
    assert _check_policy("create_entities") is None  # real policy: ALLOW/R1


def test_check_policy_require_approval_and_deny(monkeypatch):
    monkeypatch.setattr(mcp_server, "evaluate_tool", lambda name: ("REQUIRE_APPROVAL", "R2"))
    block = _check_policy("delete_entities")
    assert block["approval_required"] is True
    assert block["risk_level"] == "R2"
    monkeypatch.setattr(mcp_server, "evaluate_tool", lambda name: ("DENY", "R3"))
    block = _check_policy("dangerous_tool")
    assert block["approval_required"] is True
    assert "blocked by policy" in block["reason"]


def test_audit_records_latency_and_tenant(monkeypatch):
    captured = {}

    def fake_audit(name, decision, risk, latency_ms=0.0, error=None, tenant_id=""):
        captured.update(
            name=name, decision=decision, latency_ms=latency_ms, tenant_id=tenant_id, error=error
        )

    monkeypatch.setattr(mcp_server, "audit_tool_call", fake_audit)
    mcp_server._audit("create_entities", "ALLOW", "R1", 0.0, "tenant-A")
    assert captured["name"] == "create_entities"
    assert captured["tenant_id"] == "tenant-A"
    assert captured["latency_ms"] >= 0
    assert captured["error"] is None


# ─────────────────────────────────────────────────────────────────────────────
# build_server + MCP handler layer (fake Server)
# ─────────────────────────────────────────────────────────────────────────────
EXPECTED_TOOLS = {
    # ⚠️ Owner note: module docstring advertises 22 tools incl. 'recall_facts'
    # and 'save_learned_fact', but list_tools registers these 20 — the two
    # missing names are the remember_fact/search_learned_facts pair under
    # older names (docstring drift, dispatch has no branches for them).
    "create_entities",
    "create_relations",
    "add_observations",
    "delete_entities",
    "delete_observations",
    "delete_relations",
    "read_graph",
    "search_nodes",
    "open_nodes",
    "store_document",
    "search_semantic",
    "ingest_document_rag",
    "record_task",
    "get_similar_tasks",
    "get_recent_episodes",
    "build_context",
    "get_session_stats",
    "clear_session",
    "remember_fact",
    "search_learned_facts",
}


def test_build_server_raises_without_mcp(monkeypatch):
    monkeypatch.setattr(mcp_server, "_MCP_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="mcp package not installed"):
        build_server()


def test_list_tools_registers_all_22_tools(server):
    tools = asyncio.run(server.handlers["list_tools"]())
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS
    assert all(t.inputSchema.get("type") == "object" for t in tools)


def test_call_tool_requires_tenant(server):
    out = call_text(asyncio.run(server.handlers["call_tool"]("read_graph", {})))
    assert out["error"] == "tenant_id is required"
    out = call_text(
        asyncio.run(server.handlers["call_tool"]("read_graph", {"tenant_id": "default"}))
    )
    assert out["error"] == "tenant_id is required"


def test_call_tool_happy_path_kg_roundtrip(server):
    out = call_text(
        asyncio.run(
            server.handlers["call_tool"](
                "create_entities",
                {"tenant_id": "t1", "entities": [{"name": "x", "entityType": "concept"}]},
            )
        )
    )
    assert out == {"created": [{"name": "x", "entityType": "concept", "observations": []}]}
    out = call_text(asyncio.run(server.handlers["call_tool"]("read_graph", {"tenant_id": "t1"})))
    assert [e["name"] for e in out["entities"]] == ["x"]


def test_call_tool_policy_block_audited(server, monkeypatch):
    captured = []
    monkeypatch.setattr(mcp_server, "audit_tool_call", lambda *a, **k: captured.append((a, k)))
    # real policy: delete_entities = REQUIRE_APPROVAL
    out = call_text(
        asyncio.run(
            server.handlers["call_tool"]("delete_entities", {"tenant_id": "t1", "names": ["x"]})
        )
    )
    assert out["approval_required"] is True
    assert captured, "policy block must be audited"
    assert captured[0][1].get("error") == "policy_blocked"


def test_call_tool_exception_wraps_as_error_json(server, monkeypatch):
    monkeypatch.setattr(mcp_server, "audit_tool_call", lambda *a, **k: None)
    # create_entities without required 'entities' arg → KeyError inside _dispatch
    out = call_text(
        asyncio.run(server.handlers["call_tool"]("create_entities", {"tenant_id": "t1"}))
    )
    assert "error" in out and out["tool"] == "create_entities"


def test_resources_and_prompts_registered(server):
    resources = asyncio.run(server.handlers["list_resources"]())
    assert any(str(getattr(r, "uri", "")).endswith("knowledge-graph") for r in resources)
    body = asyncio.run(server.handlers["read_resource"]("mcp://memory/knowledge-graph"))
    assert "entities" in str(body)
    # session-stats resource: sliding=None → availability error JSON
    body = asyncio.run(server.handlers["read_resource"]("mcp://memory/session-stats"))
    assert "SlidingWindowMemory not available" in body
    # health resource: all layers unavailable → degraded
    body = json.loads(asyncio.run(server.handlers["read_resource"]("mcp://memory/health")))
    assert body["overall"] == "degraded"
    assert body["supabase"] == {"available": False, "connected": False}
    # unknown uri → graceful error JSON (raise হয় না)
    body = asyncio.run(server.handlers["read_resource"]("mcp://memory/unknown"))
    assert "Unknown resource" in body
    prompts = asyncio.run(server.handlers["list_prompts"]())
    assert prompts, "prompts must be registered"
    assert {p.name for p in prompts} >= {"heal_error", "deploy_preflight"}
    msg = asyncio.run(server.handlers["get_prompt"]("heal_error", {"error_message": "boom"}))
    assert msg is not None


# ─────────────────────────────────────────────────────────────────────────────
# _dispatch — tool → store mapping (fake stores injected directly)
# ─────────────────────────────────────────────────────────────────────────────
def _stores():
    return {
        "kg": KnowledgeGraph(),
        "episodic": _FakeEpisodic(),
        "sliding": _FakeSliding(),
        "supa": _FakeSupabase(),
        "chroma": _FakeChroma(),
        "rag": _FakeRAG(),
    }


def run(coro):
    return asyncio.run(coro)


def test_dispatch_kg_passthrough():
    s = _stores()
    assert run(
        _dispatch(
            "create_entities",
            {"entities": [{"name": "n", "entityType": "t"}]},
            s["kg"],
            None,
            None,
            None,
            None,
            None,
        )
    ) == {"created": [{"name": "n", "entityType": "t", "observations": []}]}
    assert run(
        _dispatch(
            "create_relations",
            {"relations": [{"from": "n", "to": "m", "relationType": "r"}]},
            s["kg"],
            None,
            None,
            None,
            None,
            None,
        )
    )["created"]
    # fresh entity for the observations flow (create is dedup-guarded)
    s["kg"].create_entities([{"name": "obs-ent", "entityType": "t", "observations": ["o1"]}])
    assert run(
        _dispatch(
            "add_observations",
            {"entity_name": "obs-ent", "observations": ["o2"]},
            s["kg"],
            None,
            None,
            None,
            None,
            None,
        )
    )["new_observations"] == ["o2"]
    assert run(
        _dispatch(
            "delete_observations",
            {"entity_name": "obs-ent", "observations": ["o1"]},
            s["kg"],
            None,
            None,
            None,
            None,
            None,
        )
    )["removed"] == ["o1"]
    assert run(
        _dispatch("delete_relations", {"relations": []}, s["kg"], None, None, None, None, None)
    ) == {"deleted_count": 0}
    assert run(_dispatch("search_nodes", {"query": "n"}, s["kg"], None, None, None, None, None))[
        "results"
    ]
    assert run(_dispatch("open_nodes", {"names": ["n"]}, s["kg"], None, None, None, None, None))[
        "entities"
    ]


def test_dispatch_vector_semantic_and_unavailability():
    s = _stores()
    assert "error" in run(
        _dispatch(
            "store_document", {"doc_id": "d", "text": "x"}, s["kg"], None, None, None, None, None
        )
    )
    assert "error" in run(
        _dispatch("search_semantic", {"query": "q"}, s["kg"], None, None, None, None, None)
    )
    assert "error" in run(
        _dispatch(
            "ingest_document_rag",
            {"doc_id": "d", "content": "c"},
            s["kg"],
            None,
            None,
            None,
            None,
            None,
        )
    )
    # incremental vs full mode
    out = run(
        _dispatch(
            "store_document",
            {"doc_id": "d", "text": "x"},
            s["kg"],
            None,
            None,
            None,
            s["chroma"],
            None,
        )
    )
    assert out == {"doc_id": "d", "indexed": True, "mode": "incremental"}
    out = run(
        _dispatch(
            "store_document",
            {"doc_id": "d2", "text": "y", "incremental": False},
            s["kg"],
            None,
            None,
            None,
            s["chroma"],
            None,
        )
    )
    assert out["mode"] == "full"
    s["chroma"].query_results = [("doc1", 0.9123, {"metadata": {}})]
    out = run(
        _dispatch(
            "search_semantic",
            {"query": "q", "n_results": 1},
            s["kg"],
            None,
            None,
            None,
            s["chroma"],
            None,
        )
    )
    assert out["results"][0]["score"] == 0.9123
    # rag happy path wires vector_store
    out = run(
        _dispatch(
            "ingest_document_rag",
            {"doc_id": "d3", "content": "c"},
            s["kg"],
            None,
            None,
            None,
            s["chroma"],
            s["rag"],
        )
    )
    assert out["status"] == "ingested"
    assert s["rag"].ingested[0][0] == "d3"


def test_dispatch_episodic_and_unavailability():
    s = _stores()
    assert "error" in run(
        _dispatch("record_task", {"task_id": "t"}, s["kg"], None, None, None, None, None)
    )
    assert "error" in run(
        _dispatch("get_similar_tasks", {"query": "q"}, s["kg"], None, None, None, None, None)
    )
    assert "error" in run(
        _dispatch("get_recent_episodes", {}, s["kg"], None, None, None, None, None)
    )
    out = run(
        _dispatch(
            "record_task",
            {"task_id": "t", "prompt": "p", "response": "r"},
            s["kg"],
            s["episodic"],
            None,
            None,
            None,
            None,
        )
    )
    assert out == {"recorded": True, "task_id": "t"}
    s["episodic"].similar = [{"task_id": "t"}]
    assert run(
        _dispatch(
            "get_similar_tasks",
            {"query": "p", "n": 1},
            s["kg"],
            s["episodic"],
            None,
            None,
            None,
            None,
        )
    )["results"]
    s["episodic"].episodes = [{"id": 1}]
    assert run(
        _dispatch(
            "get_recent_episodes", {"limit": 1}, s["kg"], s["episodic"], None, None, None, None
        )
    )["episodes"]


def test_dispatch_sliding_window_and_unavailability():
    s = _stores()
    assert "error" in run(
        _dispatch("build_context", {"documents": []}, s["kg"], None, None, None, None, None)
    )
    assert "error" in run(_dispatch("get_session_stats", {}, s["kg"], None, None, None, None, None))
    assert "error" in run(_dispatch("clear_session", {}, s["kg"], None, None, None, None, None))
    out = run(
        _dispatch(
            "build_context",
            {"documents": ["a", "b"], "query": "q", "session_id": "s1"},
            s["kg"],
            None,
            s["sliding"],
            None,
            None,
            None,
        )
    )
    assert out["context"]["docs"] == 2
    assert (
        run(
            _dispatch(
                "get_session_stats",
                {"session_id": "s1"},
                s["kg"],
                None,
                s["sliding"],
                None,
                None,
                None,
            )
        )["messages"]
        == 3
    )
    assert (
        run(
            _dispatch(
                "clear_session", {"session_id": "s1"}, s["kg"], None, s["sliding"], None, None, None
            )
        )["cleared"]
        is True
    )


def test_dispatch_facts_and_unknown_tool():
    s = _stores()
    assert "error" in run(
        _dispatch("remember_fact", {"content": "c"}, s["kg"], None, None, None, None, None)
    )
    assert "error" in run(
        _dispatch("search_learned_facts", {"query": "q"}, s["kg"], None, None, None, None, None)
    )
    out = run(
        _dispatch(
            "remember_fact",
            {"content": "c", "tags": ["x"], "id": "f1"},
            s["kg"],
            None,
            None,
            s["supa"],
            None,
            None,
        )
    )
    assert out == {"saved": True, "fact_id": "f1"}
    assert s["supa"].facts[0]["id"] == "f1"
    s["supa"].search_results = [{"content": "c"}]
    assert run(
        _dispatch(
            "search_learned_facts", {"query": "c"}, s["kg"], None, None, s["supa"], None, None
        )
    )["results"]
    assert (
        "Unknown tool"
        in run(_dispatch("no_such_tool", {}, s["kg"], None, None, None, None, None))["error"]
    )
