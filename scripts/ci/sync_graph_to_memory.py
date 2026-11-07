#!/usr/bin/env python3
"""Build the deterministic AST graph required by root diagnostics and bridge local Graphify AST graphs with SupremeAI agent memory."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "graph.json"
DEFAULT_DOMAINS = {
    "studio": ROOT / "studio" / "src",
    "gateway": ROOT / "gateway",
    "core": ROOT / "core",
}


def query_symbol(graph: dict[str, Any], query: str) -> list[dict[str, Any]]:
    """Search nodes matching query string in id, label, or source_file."""
    query_lower = query.lower()
    matches: list[dict[str, Any]] = []
    for n in graph.get("nodes", []):
        lbl = str(n.get("label", "")).lower()
        nid = str(n.get("id", "")).lower()
        src = str(n.get("source_file", "")).lower()
        if query_lower in lbl or query_lower in nid or query_lower in src:
            matches.append(n)
    return matches


def trace_node_relations(graph: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    """Trace incoming and outgoing links for a given node id."""
    links = graph.get("links", []) + graph.get("edges", [])
    return [
        link
        for link in links
        if link.get("source") == node_id or link.get("target") == node_id
    ]


def format_entities_for_memory(graph: dict[str, Any], domain: str) -> dict[str, Any]:
    """Format nodes and edges into MCP memory entity payload."""
    entities = [
        {
            "name": n.get("label") or n.get("id"),
            "entityType": "CodeSymbol",
            "observations": [
                f"Domain: {domain}",
                f"Source: {n.get('source_file')}:{n.get('source_location')}",
                f"Callable: {n.get('_callable', False)}",
                f"Community: {n.get('community', 'default')}",
            ],
        }
        for n in graph.get("nodes", [])
    ]
    links = graph.get("links", []) + graph.get("edges", [])
    relations = [
        {
            "from": l.get("source"),
            "to": l.get("target"),
            "relationType": l.get("relation", "relates_to"),
        }
        for l in links
    ]
    return {
        "domain": domain,
        "entity_count": len(entities),
        "relation_count": len(relations),
        "entities": entities,
        "relations": relations,
    }


def self_test() -> int:
    """Validate internal parser and data transformation invariants."""
    dummy_graph = {
        "nodes": [
            {
                "id": "service_api_login",
                "label": "login",
                "source_file": "services/api.ts",
                "source_location": "L45",
                "_callable": True,
            },
            {
                "id": "comp_chat",
                "label": "GuestChat",
                "source_file": "components/GuestChat.tsx",
                "source_location": "L12",
            },
        ],
        "links": [
            {"source": "comp_chat", "target": "service_api_login", "relation": "calls"},
        ],
    }
    matches = query_symbol(dummy_graph, "login")
    assert len(matches) == 1, f"Expected 1 match, got {len(matches)}"
    assert matches[0]["label"] == "login"

    rels = trace_node_relations(dummy_graph, "comp_chat")
    assert len(rels) == 1
    assert rels[0]["relation"] == "calls"

    payload = format_entities_for_memory(dummy_graph, "studio")
    assert payload["entity_count"] == 2
    assert payload["relation_count"] == 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync Graphify AST graph with SupremeAI agent memory & root diagnostics"
    )
    parser.add_argument("--self-test", action="store_true", help="Run self-tests and exit")
    parser.add_argument("--domain", choices=list(DEFAULT_DOMAINS.keys()), default="studio")
    parser.add_argument("--query", help="Search AST graph for symbol or filename")
    parser.add_argument("--trace", help="Trace all relations for a specific node ID")
    args, _ = parser.parse_known_args(argv)

    if args.self_test:
        return self_test()

    graphify = shutil.which("graphify")
    if not graphify:
        print("graphify is not installed; graph remains unavailable", file=sys.stderr)
        return 2
    extract = subprocess.run(
        [graphify, "extract", ".", "--output", str(OUT)],
        cwd=ROOT,
        text=True,
        timeout=300,
    )
    if extract.returncode != 0 or not OUT.exists():
        print("graphify extraction failed; no placeholder graph was created", file=sys.stderr)
        return extract.returncode or 3
    payload = json.loads(OUT.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        print("graphify produced an empty graph; refusing to mark intelligence ready", file=sys.stderr)
        return 4
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
