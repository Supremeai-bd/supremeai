#!/usr/bin/env python3
"""SupremeAI Memory Sidecar MCP Server (STDIO).

Standard Model Context Protocol (MCP) server providing 26 memory tools (Phase-1 SSOT save/recall + Phase-2 HITL list/confirm/reject)
for Knowledge Graph, Vector Store, Episodic Memory, and Long-Term Facts.

Stdlib-only (Python 3.10+), zero external pip requirements.
Interfaces with Supabase REST API and Qdrant REST API when configured;
gracefully falls back to in-memory persistence when offline.
"""

from __future__ import annotations

import json
import os
import re as _re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

# In-memory stores for offline fallback
_GRAPH_NODES: dict[str, dict[str, Any]] = {}
_GRAPH_EDGES: list[dict[str, Any]] = []
_DOCUMENTS: list[dict[str, Any]] = []
_LEARNED_FACTS: list[dict[str, Any]] = []
_EPISODES: list[dict[str, Any]] = []

# bridge-20261027-memory-graph-empty (#1341): TTL + recency policy for the
# in-memory episode store. Configurable via MEMORY_EPISODE_TTL_MS (<=0 disables).
_EPISODE_TTL_MS = int(os.environ.get("MEMORY_EPISODE_TTL_MS", "0") or 0)

# ── bridge-20261028-memory-graph-persistence (#1359) ──────────────────────
# P0: graph entities/relations were process-global only — every restart reset
# graph_nodes to 0 (AIQ-057/062/098). This wires a stdlib-SQLite write-through
# store: hydrate once at boot, persist on every mutation, degrade to the
# legacy in-memory graph if storage is unavailable (fail-open).
from graph_store import GraphStore, resolve_db_path

# Transient-entity TTL for the knowledge graph (task/topic nodes only; user
# created durable entities are never expired). <=0 disables (default).
_GRAPH_TTL_MS = int(os.environ.get("MEMORY_GRAPH_TTL_MS", "0") or 0)

_STORE = GraphStore(resolve_db_path())
try:
    _loaded_nodes, _loaded_edges = _STORE.load()
    if _loaded_nodes:
        _GRAPH_NODES.update(_loaded_nodes)
    if _loaded_edges:
        _GRAPH_EDGES.extend(_loaded_edges)
    if _loaded_nodes or _loaded_edges:
        sys.stderr.write(
            f"[MemorySidecar] graph hydrated from storage: "
            f"{len(_loaded_nodes)} entities, {len(_loaded_edges)} relations "
            f"({_STORE.db_path})\n"
        )
except Exception as _hydration_err:  # hydration must never kill the sidecar
    sys.stderr.write(f"[MemorySidecar] graph hydration skipped: {_hydration_err}\n")


def _node_ts_ms(node: dict[str, Any]) -> float:
    _ts = str(node.get("created_at", ""))
    try:
        from datetime import datetime

        return datetime.fromisoformat(_ts.replace("Z", "+00:00")).timestamp() * 1000.0
    except Exception:
        return 0.0


def _prune_expired_graph(now_ms: float | None = None) -> int:
    """Drop transient (task/topic) graph entities past MEMORY_GRAPH_TTL_MS.

    Durable entities (any entityType other than task/topic) are never
    auto-expired — only machine-generated working-set nodes age out.
    Mirrors the delete path so the persistent store stays in sync.
    """
    if _GRAPH_TTL_MS <= 0:
        return 0
    cutoff = (now_ms if now_ms is not None else time.time() * 1000.0) - _GRAPH_TTL_MS
    stale = [
        n
        for n, node in _GRAPH_NODES.items()
        if node.get("entityType") in ("task", "topic") and _node_ts_ms(node) < cutoff
    ]
    if not stale:
        return 0
    for n in stale:
        _GRAPH_NODES.pop(n, None)
    _GRAPH_EDGES[:] = [e for e in _GRAPH_EDGES if e.get("from") not in stale and e.get("to") not in stale]
    _STORE.delete_entities(stale)
    return len(stale)


def _episode_ts_ms(episode: dict[str, Any]) -> float:
    _ts = str(episode.get("created_at", ""))
    try:
        from datetime import datetime

        return datetime.fromisoformat(_ts.replace("Z", "+00:00")).timestamp() * 1000.0
    except Exception:
        return 0.0


def _prune_expired(now_ms: float | None = None) -> int:
    """Drop episodes past TTL (fail-loud knob: MEMORY_EPISODE_TTL_MS)."""
    if _EPISODE_TTL_MS <= 0:
        return 0
    import time as _time

    cutoff = (now_ms if now_ms is not None else _time.time() * 1000.0) - _EPISODE_TTL_MS
    before = len(_EPISODES)
    _EPISODES[:] = [e for e in _EPISODES if _episode_ts_ms(e) >= cutoff]
    return before - len(_EPISODES)



def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


SUPABASE_URL = _get_env("SUPABASE_URL")
SUPABASE_KEY = _get_env("SUPABASE_SERVICE_ROLE_KEY") or _get_env("SUPABASE_KEY")
QDRANT_URL = _get_env("QDRANT_URL")
QDRANT_KEY = _get_env("QDRANT_API_KEY")


def _supabase_request(table: str, method: str = "GET", data: Any | None = None, params: dict[str, str] | None = None) -> Any | None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except Exception as err:
        sys.stderr.write(f"[MemorySidecar] Supabase error ({table}): {err}\n")
        return None


def _supabase_rpc(function: str, payload: dict[str, Any]) -> Any | None:
    """POST /rest/v1/rpc/<function> with service-role key (Phase-1 SSOT recall)."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/{function}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except Exception as err:
        sys.stderr.write(f"[MemorySidecar] Supabase RPC error ({function}): {err}\n")
        return None


_PII_EMAIL = _re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PII_PHONE = _re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
_PII_CARD = _re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)")


def _strip_pii(text: str) -> str:
    """Best-effort PII redaction before SSOT insert (training/PII policy)."""
    out = _PII_EMAIL.sub("[EMAIL]", text)
    out = _PII_PHONE.sub("[PHONE]", out)
    out = _PII_CARD.sub("[CARD]", out)
    return out


def _tenant_owner_id(tenant_id: str) -> str:
    """Deterministic per-tenant owner UUID (workspace isolation without auth.uid)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"supremeai.memory.owner:{tenant_id}"))


def _qdrant_request(endpoint: str, method: str = "GET", data: Any | None = None) -> Any | None:
    if not QDRANT_URL:
        return None
    url = f"{QDRANT_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {"Content-Type": "application/json"}
    if QDRANT_KEY:
        headers["api-key"] = QDRANT_KEY
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except Exception as err:
        sys.stderr.write(f"[MemorySidecar] Qdrant error ({endpoint}): {err}\n")
        return None


TOOLS_SCHEMA = [
    {
        "name": "create_entities",
        "description": "Create entities in the Knowledge Graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "entityType": {"type": "string"},
                            "observations": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["name", "entityType"],
                    },
                }
            },
            "required": ["entities"],
        },
    },
    {
        "name": "create_relations",
        "description": "Create directed relations between entities.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "relations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                            "relationType": {"type": "string"},
                        },
                        "required": ["from", "to", "relationType"],
                    },
                }
            },
            "required": ["relations"],
        },
    },
    {
        "name": "add_observations",
        "description": "Add observations to an existing entity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "observations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "entityName": {"type": "string"},
                            "contents": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["entityName", "contents"],
                    },
                }
            },
            "required": ["observations"],
        },
    },
    {
        "name": "delete_entities",
        "description": "Delete entities and their relations.",
        "inputSchema": {
            "type": "object",
            "properties": {"entityNames": {"type": "array", "items": {"type": "string"}}},
            "required": ["entityNames"],
        },
    },
    {
        "name": "delete_observations",
        "description": "Remove observations from an entity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "deletions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "entityName": {"type": "string"},
                            "observations": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["entityName", "observations"],
                    },
                }
            },
            "required": ["deletions"],
        },
    },
    {
        "name": "delete_relations",
        "description": "Delete specific relations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "relations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                            "relationType": {"type": "string"},
                        },
                        "required": ["from", "to", "relationType"],
                    },
                }
            },
            "required": ["relations"],
        },
    },
    {
        "name": "read_graph",
        "description": "Return the entire Knowledge Graph.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_nodes",
        "description": "Search Knowledge Graph nodes.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "open_nodes",
        "description": "Open specific nodes and relations.",
        "inputSchema": {
            "type": "object",
            "properties": {"names": {"type": "array", "items": {"type": "string"}}},
            "required": ["names"],
        },
    },
    {
        "name": "store_document",
        "description": "Store a document in the vector store.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "search_semantic",
        "description": "Semantic search over vector store.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ingest_document_rag",
        "description": "Chunk + ingest a document into RAG.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "chunk_size": {"type": "integer"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "record_task",
        "description": "Record a task execution into episodic memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "description": {"type": "string"},
                "result": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["description"],
        },
    },
    {
        "name": "get_similar_tasks",
        "description": "Retrieve similar past task executions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_recent_episodes",
        "description": "Retrieve recent episodic records.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
    },
    {
        "name": "build_context",
        "description": "Build token-budget-aware context string.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "token_budget": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_session_stats",
        "description": "Sliding window stats for a session.",
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
        },
    },
    {
        "name": "clear_session",
        "description": "Clear sliding window memory for a session.",
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
        },
    },
    {
        "name": "remember_fact",
        "description": "Save a long-term fact (Supabase/SQLite).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string"},
                "category": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["fact"],
        },
    },
    {
        "name": "search_learned_facts",
        "description": "Search stored long-term facts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "export_memory",
        "description": "Export all stored memory for a user (knowledge-graph entities + relations, episodes, documents, learned facts) as JSON — GDPR data-portability surface (AIQ-062/098).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "wipe_memory",
        "description": "GDPR-compliant hard wipe: deletes graph entities + relations (persistent store included) and, with scope=all, clears episodes, documents and learned facts (AIQ-098).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "enum": ["all", "graph"], "description": "graph = knowledge graph only; all (default) = every memory lane"},
            },
        },
    },
    {
        "name": "save_memory",
        "description": "Phase-1 SSOT write: insert one row into public.memories (status=candidate, HITL confirm later). PII is stripped before insert; training never auto-confirms. owner_id derived from tenant_id when omitted (workspace isolation).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Memory text content (required)."},
                "kind": {"type": "string", "enum": ["fact", "decision", "task", "preference", "contact", "doc_chunk"], "description": "Memory kind (default: fact)."},
                "workspace_id": {"type": "string", "description": "Optional workspace UUID for team-shared memories."},
                "source_ref": {"type": "string", "description": "Optional source message/thread id."},
                "source_quote": {"type": "string", "description": "Optional verbatim quote for citation."},
                "confidence": {"type": "number", "description": "Optional confidence 0..1."},
                "owner_id": {"type": "string", "description": "Optional auth.users UUID; defaults to deterministic tenant-derived owner."},
                "tenant_id": {"type": "string", "description": "Injected by control tower (never trust client)."},
            },
            "required": ["content"],
        },
    },
    {
        "name": "recall_memories",
        "description": "Phase-1 SSOT read: hybrid recall over public.memories via RPC match_memories (vector + FTS + recency). Works with query_text only (embedding optional).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text query for FTS/hybrid recall (required)."},
                "limit": {"type": "integer", "description": "Max rows (default 5, cap 50)."},
                "min_score": {"type": "number", "description": "Optional score floor 0..1 (applied client-side after RPC)."},
                "tenant_id": {"type": "string", "description": "Injected by control tower (never trust client)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_candidates",
        "description": "Phase-2 HITL queue: list memories by status (default candidate) for confirm/reject review. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["candidate", "confirmed", "rejected", "superseded"], "description": "Default: candidate."},
                "limit": {"type": "integer", "description": "Max rows (default 20, cap 100)."},
                "tenant_id": {"type": "string", "description": "Injected by control tower (never trust client)."},
            },
        },
    },
    {
        "name": "confirm_memory",
        "description": "Phase-2 HITL: set status=confirmed and write memory_events.confirmed. training_opt_in stays false unless explicitly true (default-off training gate).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Memory UUID (required)."},
                "training_opt_in": {"type": "boolean", "description": "Explicit user opt-in for training use (default false)."},
                "note": {"type": "string", "description": "Optional review note stored in event context."},
                "tenant_id": {"type": "string", "description": "Injected by control tower (never trust client)."},
            },
            "required": ["id"],
        },
    },
    {
        "name": "reject_memory",
        "description": "Phase-2 HITL: set status=rejected and write memory_events.rejected (with optional reason).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Memory UUID (required)."},
                "reason": {"type": "string", "description": "Optional rejection reason (event context)."},
                "tenant_id": {"type": "string", "description": "Injected by control tower (never trust client)."},
            },
            "required": ["id"],
        },
    },
]


def handle_tool(name: str, args: dict[str, Any]) -> Any:
    global _GRAPH_EDGES
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # --- Knowledge Graph Tools ---
    if name == "create_entities":
        created = []
        for e in args.get("entities", []):
            ename = str(e.get("name", "")).strip()
            if ename:
                _GRAPH_NODES[ename] = {
                    "name": ename,
                    "entityType": e.get("entityType", "concept"),
                    "observations": list(e.get("observations", [])),
                    "created_at": now,
                }
                created.append(_GRAPH_NODES[ename])
                # (#1359) write-through: durable entity row (upsert)
                _STORE.upsert_entity(ename, _GRAPH_NODES[ename]["entityType"], _GRAPH_NODES[ename]["observations"], now)
        return {"created": created, "count": len(created)}

    elif name == "create_relations":
        created = []
        for r in args.get("relations", []):
            rel = {
                "from": str(r.get("from", "")).strip(),
                "to": str(r.get("to", "")).strip(),
                "relationType": str(r.get("relationType", "related")),
                "created_at": now,
            }
            if rel["from"] and rel["to"]:
                _GRAPH_EDGES.append(rel)
                created.append(rel)
                # (#1359) write-through: durable relation row (UNIQUE-deduped)
                _STORE.insert_relation(rel["from"], rel["to"], rel["relationType"], now)
        return {"created": created, "count": len(created)}

    elif name == "add_observations":
        updated = []
        for o in args.get("observations", []):
            ename = str(o.get("entityName", "")).strip()
            contents = list(o.get("contents", []))
            if ename in _GRAPH_NODES:
                _GRAPH_NODES[ename].setdefault("observations", []).extend(contents)
                updated.append(_GRAPH_NODES[ename])
                # (#1359) write-through: keep the stored observation list in sync
                _STORE.update_observations(ename, _GRAPH_NODES[ename].get("observations", []))
        return {"updated": updated, "count": len(updated)}

    elif name == "delete_entities":
        names = set(args.get("entityNames", []))
        for n in names:
            _GRAPH_NODES.pop(n, None)
        _GRAPH_EDGES = [e for e in _GRAPH_EDGES if e.get("from") not in names and e.get("to") not in names]
        # (#1359) write-through: cascade removal in the persistent store too
        _STORE.delete_entities(sorted(names))
        return {"deleted": list(names)}

    elif name == "delete_observations":
        for d in args.get("deletions", []):
            ename = str(d.get("entityName", "")).strip()
            obs = set(d.get("observations", []))
            if ename in _GRAPH_NODES:
                _GRAPH_NODES[ename]["observations"] = [o for o in _GRAPH_NODES[ename].get("observations", []) if o not in obs]
                # (#1359) write-through: persist the filtered observation list
                _STORE.delete_observations(ename, _GRAPH_NODES[ename]["observations"])
        return {"status": "ok"}

    elif name == "delete_relations":
        to_del = {(r.get("from"), r.get("to"), r.get("relationType")) for r in args.get("relations", [])}
        _GRAPH_EDGES = [e for e in _GRAPH_EDGES if (e.get("from"), e.get("to"), e.get("relationType")) not in to_del]
        # (#1359) write-through: exact-tuple removal in the persistent store
        _STORE.delete_relations(sorted(to_del))
        return {"status": "ok"}

    elif name == "read_graph":
        return {"entities": list(_GRAPH_NODES.values()), "relations": _GRAPH_EDGES}

    elif name == "search_nodes":
        q = str(args.get("query", "")).lower()
        matches = [n for n in _GRAPH_NODES.values() if q in n.get("name", "").lower() or any(q in o.lower() for o in n.get("observations", []))]
        return {"matches": matches, "count": len(matches)}

    elif name == "open_nodes":
        names = set(args.get("names", []))
        nodes = [_GRAPH_NODES[n] for n in names if n in _GRAPH_NODES]
        rels = [e for e in _GRAPH_EDGES if e.get("from") in names or e.get("to") in names]
        return {"entities": nodes, "relations": rels}

    # --- Vector & RAG Tools ---
    elif name == "store_document":
        doc_id = str(uuid.uuid4())
        doc = {
            "id": doc_id,
            "title": args.get("title", "Untitled Document"),
            "content": args.get("content", ""),
            "metadata": args.get("metadata", {}),
            "created_at": now,
        }
        _DOCUMENTS.append(doc)
        # Attempt Supabase sync
        _supabase_request("documents", method="POST", data=doc)
        return {"id": doc_id, "status": "stored", "title": doc["title"]}

    elif name == "search_semantic":
        q = str(args.get("query", "")).lower()
        limit = int(args.get("limit", 5))
        matches = [d for d in _DOCUMENTS if q in d.get("content", "").lower() or q in d.get("title", "").lower()][:limit]
        return {"results": matches, "query": q, "count": len(matches)}

    elif name == "ingest_document_rag":
        content = str(args.get("content", ""))
        title = str(args.get("title", "RAG Document"))
        chunk_size = int(args.get("chunk_size", 500))
        chunks = [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]
        stored_chunks = []
        for idx, chunk in enumerate(chunks):
            cid = str(uuid.uuid4())
            item = {"id": cid, "title": f"{title} (Part {idx + 1})", "content": chunk, "chunk_index": idx}
            _DOCUMENTS.append(item)
            stored_chunks.append(item)
        return {"status": "ingested", "chunks_count": len(stored_chunks)}

    # --- Episodic Memory Tools ---
    elif name == "record_task":
        tid = args.get("task_id") or f"task-{uuid.uuid4().hex[:8]}"
        episode = {
            "task_id": tid,
            "description": args.get("description", ""),
            "result": args.get("result", ""),
            "metadata": args.get("metadata", {}),
            "created_at": now,
        }
        _EPISODES.append(episode)

        # ── bridge-20261027-memory-graph-empty (#1341): write-through ──
        # Episodes previously never fed the knowledge graph, so graph_nodes
        # stayed 0 forever and cross-session recall (read_graph/search_nodes)
        # had nothing to read. Every recorded task now lands as a namespaced
        # task entity plus up to 5 topic entities linked via "mentions" edges.
        _ns = str(args.get("tenant_id") or "tenant_default")
        _sess = str(args.get("session_id") or "default")
        _task_name = f"{_ns}:{_sess}:task:{tid}"
        _GRAPH_NODES[_task_name] = {
            "name": _task_name,
            "entityType": "task",
            "observations": [
                str(episode.get("description", ""))[:300],
                f"result: {str(episode.get('result', ''))[:300]}",
                f"at: {now}",
            ],
            "created_at": now,
        }
        # (#1359) write-through: task entities survive restarts too
        _STORE.upsert_entity(_task_name, "task", _GRAPH_NODES[_task_name]["observations"], now)
        _topic_pool = _re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", f"{episode.get('description', '')} {episode.get('result', '')}")
        _topics: list[str] = []
        for _raw in _topic_pool:
            _t = f"{_ns}:topic:{_raw.lower()}"
            if _t not in _topics:
                _topics.append(_t)
            if len(_topics) >= 5:
                break
        for _t in _topics:
            if _t not in _GRAPH_NODES:
                _GRAPH_NODES[_t] = {
                    "name": _t,
                    "entityType": "topic",
                    "observations": [f"mentioned by task {tid} at {now}"],
                    "created_at": now,
                }
                # (#1359) write-through: topic entities survive restarts too
                _STORE.upsert_entity(_t, "topic", _GRAPH_NODES[_t]["observations"], now)
            _GRAPH_EDGES.append({"from": _task_name, "to": _t, "relationType": "mentions", "created_at": now})
            _STORE.insert_relation(_task_name, _t, "mentions", now)

        return {"task_id": tid, "status": "recorded", "graph_nodes_written": 1 + len(_topics)}

    elif name == "get_similar_tasks":
        q = str(args.get("query", "")).lower()
        limit = int(args.get("limit", 5))
        matches = [e for e in _EPISODES if q in e.get("description", "").lower() or q in e.get("result", "").lower()][:limit]
        return {"tasks": matches, "count": len(matches)}

    elif name == "get_recent_episodes":
        limit = int(args.get("limit", 10))
        return {"episodes": _EPISODES[-limit:]}

    elif name == "build_context":
        q = str(args.get("query", "")).lower()
        budget = int(args.get("token_budget", 2000))
        facts = [f.get("fact", "") for f in _LEARNED_FACTS if q in f.get("fact", "").lower()]
        tasks = [t.get("description", "") for t in _EPISODES if q in t.get("description", "").lower()]
        context_str = "Learned Facts:\n" + "\n".join(facts) + "\nPast Tasks:\n" + "\n".join(tasks)
        return {"context": context_str[: budget * 4], "facts_used": len(facts), "tasks_used": len(tasks)}

    elif name == "get_session_stats":
        sid = args.get("session_id", "default")
        # Latent-bug fix (#1359): _prune_expired expects epoch-ms; the ISO
        # string `now` only worked because TTL defaulted to 0 (early return).
        # Any operator setting MEMORY_EPISODE_TTL_MS>0 hit a TypeError here.
        _prune_expired()
        _prune_expired_graph()
        return {"session_id": sid, "active_episodes": len(_EPISODES), "graph_nodes": len(_GRAPH_NODES)}

    elif name == "export_memory":
        # (#1359, AIQ-062/098) GDPR data portability: one call returns every
        # stored lane. Graph comes straight from the persistent store when
        # available (independent of the hydrated cache) so the export is the
        # honest durable state, not a process-local view.
        _prune_expired()
        _prune_expired_graph()
        if _STORE.available:
            graph = _STORE.export_all()
        else:
            graph = {"entities": list(_GRAPH_NODES.values()), "relations": list(_GRAPH_EDGES)}
        return {
            "exported_at": now,
            "graph": graph,
            "episodes": list(_EPISODES),
            "documents": list(_DOCUMENTS),
            "learned_facts": list(_LEARNED_FACTS),
        }

    elif name == "wipe_memory":
        # (#1359, AIQ-098) GDPR hard wipe. Persistent store first (fail-open
        # inside), then the in-process mirrors — so a wiped graph cannot
        # resurrect via hydration on the next boot.
        scope = str(args.get("scope", "all"))
        _STORE.wipe()
        _GRAPH_NODES.clear()
        _GRAPH_EDGES.clear()
        cleared = {"graph": True}
        if scope != "graph":
            _EPISODES.clear()
            _DOCUMENTS.clear()
            _LEARNED_FACTS.clear()
            cleared.update(episodes=True, documents=True, learned_facts=True)
        return {"status": "wiped", "scope": scope, "cleared": cleared}

    elif name == "clear_session":
        sid = args.get("session_id", "default")
        _EPISODES.clear()
        return {"session_id": sid, "cleared": True}

    # --- Long-Term Learned Facts Tools ---
    elif name == "remember_fact":
        fact_text = str(args.get("fact", "")).strip()
        fid = str(uuid.uuid4())
        record = {
            "id": fid,
            "fact": fact_text,
            "category": args.get("category", "general"),
            "confidence": float(args.get("confidence", 1.0)),
            "created_at": now,
        }
        _LEARNED_FACTS.append(record)
        # Attempt Supabase sync to learned_facts
        _supabase_request("learned_facts", method="POST", data={"content": fact_text, "source": "mcp_sidecar", "confidence": record["confidence"]})
        return {"id": fid, "status": "saved", "fact": fact_text}

    elif name == "search_learned_facts":
        q = str(args.get("query", "")).lower()
        limit = int(args.get("limit", 10))
        # 1. Try Supabase
        sb_facts = _supabase_request("learned_facts", method="GET", params={"content": f"ilike.*{q}*", "limit": str(limit)})
        if sb_facts and isinstance(sb_facts, list):
            return {"facts": sb_facts, "source": "supabase"}
        # 2. In-memory fallback
        matches = [f for f in _LEARNED_FACTS if q in f.get("fact", "").lower()][:limit]
        return {"facts": matches, "source": "memory"}

    # --- Phase 1: memories SSOT (Phase 0 tables) ---
    elif name == "save_memory":
        content_raw = str(args.get("content", "")).strip()
        if not content_raw:
            return {"error": "content is required"}
        kind = str(args.get("kind") or "fact")
        if kind not in ("fact", "decision", "task", "preference", "contact", "doc_chunk"):
            return {"error": f"invalid kind: {kind}"}
        tenant = str(args.get("tenant_id") or "tenant_default").strip() or "tenant_default"
        owner_id = str(args.get("owner_id") or "").strip() or _tenant_owner_id(tenant)
        # validate uuid shape (fail closed before REST)
        try:
            uuid.UUID(owner_id)
        except Exception:
            return {"error": "owner_id must be a UUID"}
        workspace_id = str(args.get("workspace_id") or "").strip() or None
        if workspace_id:
            try:
                uuid.UUID(workspace_id)
            except Exception:
                return {"error": "workspace_id must be a UUID"}
        content = _strip_pii(content_raw)
        confidence = args.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
                if not (0.0 <= confidence <= 1.0):
                    return {"error": "confidence must be in [0,1]"}
            except Exception:
                return {"error": "confidence must be a number"}
        row = {
            "owner_id": owner_id,
            "workspace_id": workspace_id,
            "kind": kind,
            "content": content,
            "source_type": str(args.get("source_type") or "mcp"),
            "source_ref": args.get("source_ref"),
            "source_quote": args.get("source_quote"),
            "created_by": f"agent:{tenant}",
            "status": "candidate",  # HITL confirm later; never auto-confirm for training
            "confidence": confidence,
        }
        if not SUPABASE_URL or not SUPABASE_KEY:
            # offline fallback — not durable, clearly marked
            fid = str(uuid.uuid4())
            _LEARNED_FACTS.append({
                "id": fid,
                "fact": content,
                "category": kind,
                "confidence": confidence if confidence is not None else 1.0,
                "created_at": now,
                "lane": "memories_ssot_offline",
            })
            return {
                "id": fid,
                "status": "candidate",
                "source": "offline_fallback",
                "warning": "Supabase not configured; row not in memories SSOT",
                "owner_id": owner_id,
                "kind": kind,
                "content": content,
            }
        inserted = _supabase_request("memories", method="POST", data=row)
        if inserted is None:
            return {"error": "supabase insert failed", "status": "candidate_not_saved"}
        if isinstance(inserted, list) and inserted:
            saved = inserted[0]
        elif isinstance(inserted, dict):
            saved = inserted
        else:
            saved = {"status": "candidate"}
        return {
            "id": saved.get("id"),
            "status": saved.get("status", "candidate"),
            "source": "supabase",
            "owner_id": owner_id,
            "kind": kind,
            "content": content,
            "pii_stripped": content != content_raw,
        }

    elif name == "recall_memories":
        query = str(args.get("query") or "").strip()
        if not query:
            return {"error": "query is required"}
        try:
            limit = int(args.get("limit", 5))
        except Exception:
            return {"error": "limit must be an integer"}
        limit = max(1, min(limit, 50))
        tenant = str(args.get("tenant_id") or "tenant_default").strip() or "tenant_default"
        owner_id = _tenant_owner_id(tenant)
        min_score = args.get("min_score")
        # Phase-0 RPC signature: match_memories(query_embedding, query_text, k, owner)
        # (Phase-1 wrongly sent match_threshold/match_count — PostgREST rejected them.)
        payload: dict[str, Any] = {
            "query_embedding": None,
            "query_text": query,
            "k": limit,
            "owner": owner_id,
        }
        if not SUPABASE_URL or not SUPABASE_KEY:
            return {"error": "Supabase not configured", "memories": [], "source": "none"}
        rows = _supabase_rpc("match_memories", payload)
        if rows is None:
            # Fallback: direct REST filter (FTS-ish ilike) if RPC unavailable
            fallback = _supabase_request(
                "memories",
                method="GET",
                params={
                    "owner_id": f"eq.{owner_id}",
                    "or": f"(content.ilike.*{query}*,content.ilike.*{query.replace(' ', '%')}*)",
                    "status": "in.(candidate,confirmed)",
                    "order": "created_at.desc",
                    "limit": str(limit),
                    "select": "id,kind,content,source_type,source_ref,source_quote,status,confidence,created_at",
                },
            )
            if isinstance(fallback, list):
                return {"memories": fallback, "source": "rest_fallback", "owner_id": owner_id}
            return {"error": "recall failed", "memories": [], "source": "none"}
        # attach owner for transparency + optional client-side score floor
        out = []
        floor = None
        if min_score is not None:
            try:
                floor = float(min_score)
            except Exception:
                floor = None
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, dict):
                r = dict(r)
                r.setdefault("owner_id", owner_id)
                if floor is not None and r.get("score") is not None:
                    try:
                        if float(r["score"]) < floor:
                            continue
                    except Exception as exc:
                        import logging
                        logging.getLogger(__name__).debug("Suppressed exception (%s)", type(exc).__name__)
                out.append(r)
        return {"memories": out, "count": len(out), "source": "rpc:match_memories", "owner_id": owner_id}

    # --- Phase 2: HITL confirm/reject + candidate queue ---
    elif name == "list_candidates":
        status = str(args.get("status") or "candidate")
        if status not in ("candidate", "confirmed", "rejected", "superseded"):
            return {"error": f"invalid status: {status}"}
        try:
            limit = int(args.get("limit", 20))
        except Exception:
            return {"error": "limit must be an integer"}
        limit = max(1, min(limit, 100))
        tenant = str(args.get("tenant_id") or "tenant_default").strip() or "tenant_default"
        owner_id = _tenant_owner_id(tenant)
        if not SUPABASE_URL or not SUPABASE_KEY:
            return {"error": "Supabase not configured", "memories": [], "source": "none"}
        rows = _supabase_request(
            "memories",
            method="GET",
            params={
                "owner_id": f"eq.{owner_id}",
                "status": f"eq.{status}",
                "order": "created_at.desc",
                "limit": str(limit),
                "select": "id,kind,content,source_type,source_ref,source_quote,status,confidence,training_opt_in,created_at",
            },
        )
        if rows is None:
            return {"error": "list failed", "memories": [], "source": "none"}
        if not isinstance(rows, list):
            rows = []
        return {"memories": rows, "count": len(rows), "status": status, "owner_id": owner_id, "source": "supabase"}

    elif name == "confirm_memory" or name == "reject_memory":
        mid = str(args.get("id") or "").strip()
        try:
            uuid.UUID(mid)
        except Exception:
            return {"error": "id must be a UUID"}
        tenant = str(args.get("tenant_id") or "tenant_default").strip() or "tenant_default"
        owner_id = _tenant_owner_id(tenant)
        if not SUPABASE_URL or not SUPABASE_KEY:
            return {"error": "Supabase not configured"}
        is_confirm = name == "confirm_memory"
        new_status = "confirmed" if is_confirm else "rejected"
        event_name = "confirmed" if is_confirm else "rejected"

        # Load current row (service role; scope by owner for isolation)
        current = _supabase_request(
            "memories",
            method="GET",
            params={"id": f"eq.{mid}", "owner_id": f"eq.{owner_id}", "select": "id,status,training_opt_in,content"},
        )
        if not isinstance(current, list) or not current:
            return {"error": "memory not found or owner mismatch", "id": mid}
        row0 = current[0]
        before_status = str(row0.get("status") or "")

        update: dict[str, Any] = {"status": new_status}
        context: dict[str, Any] = {"tenant": tenant, "actor": f"agent:{tenant}"}
        if is_confirm:
            # training opt-in: default false; only explicit true flips the gate
            opt_in = bool(args.get("training_opt_in", False))
            update["training_opt_in"] = opt_in
            context["training_opt_in"] = opt_in
            note = str(args.get("note") or "").strip()
            if note:
                context["note"] = note[:500]
        else:
            reason = str(args.get("reason") or "").strip()
            if reason:
                context["reason"] = reason[:500]

        patched = _supabase_request("memories", method="PATCH", data=update, params={"id": f"eq.{mid}", "owner_id": f"eq.{owner_id}"})
        if patched is None:
            return {"error": "status update failed", "id": mid}

        # Audit event (memory_events) — fail-soft: status change already done
        event_ok = False
        ev = _supabase_request(
            "memory_events",
            method="POST",
            data={
                "memory_id": mid,
                "actor": f"agent:{tenant}",
                "event": event_name,
                "before": before_status,
                "after": new_status,
                "context": context,
            },
        )
        event_ok = ev is not None

        result = {
            "id": mid,
            "status": new_status,
            "event": event_name,
            "event_recorded": event_ok,
            "owner_id": owner_id,
            "source": "supabase",
        }
        if is_confirm:
            result["training_opt_in"] = bool(update.get("training_opt_in", False))
        return result

    return {"error": f"Unknown tool: {name}"}


def main():
    """Main MCP STDIO loop handling JSON-RPC requests."""
    sys.stderr.write("[MemorySidecar] Python memory MCP sidecar started (ready for STDIO)\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as err:
            sys.stderr.write(f"[MemorySidecar] Parse error: {err}\n")
            continue

        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        # Handle MCP Handshake / Capabilities
        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "supremeai-memory-sidecar",
                        "version": "1.0.0",
                    },
                },
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            # Handshake notification, no response required
            pass

        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS_SCHEMA},
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            try:
                data = handle_tool(tool_name, tool_args)
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data),
                            }
                        ]
                    },
                }
            except Exception as ex:
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": f"Error: {ex}"}],
                    },
                }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "ping":
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {}}) + "\n")
            sys.stdout.flush()

        else:
            if msg_id is not None:
                err_res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
                sys.stdout.write(json.dumps(err_res) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    main()
