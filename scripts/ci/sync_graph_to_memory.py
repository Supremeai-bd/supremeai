#!/usr/bin/env python3
"""Canonical Graphify AST Intelligence, Blast-Radius & Memory Bridge Engine.

বাংলা মন্তব্য:
আগে এই স্ক্রিপ্টটি কেবল `graphify extract` চালানোর একটি শেল ছিল — `--query` ও `--trace`
ফ্ল্যাগ কোডের ভেতরে সংযুক্ত ছিল না এবং উবুন্টু CI-তে `graphify` CLI না থাকায় exit 2 দিয়ে ফেল করত।
এখন এটি পুরো সিস্টেমের একক Graph Intelligence SSOT হিসেবে কাজ করে:
  ১. `load_or_build_graph()`: `graphify-out/graph.json` থাকলে সরাসরি পড়ে, আর না থাকলে
     stdlib Python AST দিয়ে মুহূর্তের মধ্যে নির্ভুল fallback dependency graph তৈরি করে (CI-safe)।
  ২. `analyze_blast_radius()`: যেকোনো `Touching files:` তালিকার জন্য 1-hop dependents,
     transitive blast count, impacted pytest ফাইলসমূহ, layer violations এবং import cycles বের করে।
  ৩. `audit_graph_health()`: পুরো রিপোর God nodes, circular import cycles, layer violations
     এবং zero-importer dead-code প্রার্থীদের রিপোর্ট তৈরি করে।
"""
from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "graph.json"
DEFAULT_DOMAINS = {
    "studio": ROOT / "studio" / "src",
    "gateway": ROOT / "gateway",
    "core": ROOT / "core",
}

DEPENDENCY_RELATIONS = frozenset(
    {"imports", "imports_from", "calls", "inherits", "references", "uses", "re_exports"}
)
IMPORT_RELATIONS = frozenset({"imports", "imports_from"})


def _normalize_rel_path(raw_path: str) -> str:
    clean = str(raw_path or "").strip().replace("\\", "/")
    while clean.startswith("./") or clean.startswith("/"):
        clean = clean[2:] if clean.startswith("./") else clean[1:]
    return clean


def _is_test_path(rel_path: str) -> bool:
    parts = rel_path.split("/")
    base = parts[-1] if parts else ""
    return (
        "tests" in parts
        or "__tests__" in parts
        or base.startswith("test_")
        or base.endswith(("_test.py", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"))
    )


def find_existing_graph_file(root: Path = ROOT) -> Path | None:
    """Locate an existing Graphify JSON artifact without triggering heavy subprocesses."""
    candidates = (
        root / "graphify-out" / "graph.json",
        root / ".cache" / "graphify-full" / "graphify-out" / "graph.json",
        root / "graph.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def build_stdlib_fallback_graph(
    root: Path = ROOT,
    scan_dirs: tuple[str, ...] = ("core", "gateway", "scripts", "tests"),
) -> dict[str, Any]:
    """বাংলা মন্তব্য: `graphify` CLI বা `graph.json` অনুপস্থিত থাকলে (যেমন CI কন্টেইনারে)
    পিওর stdlib AST দিয়ে দ্রুত ফাইল ও সিম্বল ডিপেন্ডেন্সি গ্রাফ তৈরি করে।"""
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    module_index: dict[str, str] = {}
    py_files: list[tuple[str, Path]] = []

    for dname in scan_dirs:
        base = root / dname
        if not base.is_dir():
            continue
        for fpath in sorted(base.rglob("*.py")):
            if "__pycache__" in fpath.parts:
                continue
            rel = _normalize_rel_path(str(fpath.relative_to(root)))
            py_files.append((rel, fpath))
            mod_dotted = rel[:-3].replace("/", ".")
            if mod_dotted.endswith(".__init__"):
                mod_dotted = mod_dotted[: -len(".__init__")]
            module_index[mod_dotted] = rel
            if mod_dotted.startswith("core."):
                module_index[mod_dotted[len("core.") :]] = rel
            elif mod_dotted.startswith("gateway."):
                module_index[mod_dotted[len("gateway.") :]] = rel

    for rel, fpath in py_files:
        file_node_id = f"file:{rel}"
        nodes.append(
            {
                "id": file_node_id,
                "label": Path(rel).name,
                "source_file": rel,
                "source_location": "L1",
                "_callable": False,
                "_origin": "stdlib-ast",
            }
        )
        try:
            tree = ast.parse(fpath.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue

        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                sym_id = f"{file_node_id}#{stmt.name}"
                nodes.append(
                    {
                        "id": sym_id,
                        "label": stmt.name,
                        "source_file": rel,
                        "source_location": f"L{stmt.lineno}",
                        "_callable": True,
                        "_callable_class": isinstance(stmt, ast.ClassDef),
                        "_origin": "stdlib-ast",
                    }
                )
                links.append({"source": file_node_id, "target": sym_id, "relation": "contains"})

        for node in ast.walk(tree):
            target_mods: list[str] = []
            if isinstance(node, ast.Import):
                target_mods.extend(alias.name for alias in node.names if alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                target_mods.append(node.module)
                for alias in node.names:
                    if alias.name and alias.name != "*":
                        target_mods.append(f"{node.module}.{alias.name}")
            for cand in target_mods:
                resolved_rel = module_index.get(cand)
                if resolved_rel and resolved_rel != rel:
                    links.append(
                        {
                            "source": file_node_id,
                            "target": f"file:{resolved_rel}",
                            "relation": "imports",
                        }
                    )

    return {
        "directed": True,
        "provenance": "stdlib-ast-fallback",
        "nodes": nodes,
        "links": links,
    }


def load_or_build_graph(root: Path = ROOT, refresh: bool = False) -> dict[str, Any]:
    """Load cached Graphify `graph.json` or build deterministic stdlib fallback."""
    if refresh:
        graphify = shutil.which("graphify")
        if graphify:
            subprocess.run(
                [graphify, "extract", ".", "--code-only", "--output", str(root)],
                cwd=root,
                text=True,
                timeout=300,
                check=False,
            )

    existing = find_existing_graph_file(root)
    if existing is not None:
        try:
            payload = json.loads(existing.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("nodes"):
                payload.setdefault("provenance", str(existing.relative_to(root)))
                return payload
        except (OSError, json.JSONDecodeError):
            pass

    return build_stdlib_fallback_graph(root)


def query_symbol(graph: dict[str, Any], query: str, limit: int = 25) -> list[dict[str, Any]]:
    """Search nodes matching query string in id, label, or source_file."""
    query_lower = query.lower()
    matches: list[dict[str, Any]] = []
    for n in graph.get("nodes", []):
        lbl = str(n.get("label", "")).lower()
        nid = str(n.get("id", "")).lower()
        src = str(n.get("source_file", "")).lower()
        if query_lower in lbl or query_lower in nid or query_lower in src:
            matches.append(n)
            if len(matches) >= limit:
                break
    return matches


def trace_node_relations(graph: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    """Trace incoming and outgoing links for a given node id."""
    links = (graph.get("links") or []) + (graph.get("edges") or [])
    return [
        link
        for link in links
        if link.get("source") == node_id or link.get("target") == node_id
    ]


def _build_file_adjacency(
    graph: dict[str, Any],
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]], set[str]]:
    """Return (file_out_deps, file_in_dependents, import_only_out, all_files)."""
    nodes = graph.get("nodes") or []
    links = (graph.get("links") or []) + (graph.get("edges") or [])
    node_file: dict[str, str] = {}
    all_files: set[str] = set()

    for n in nodes:
        nid = n.get("id")
        sf = _normalize_rel_path(str(n.get("source_file") or ""))
        if nid and sf:
            node_file[str(nid)] = sf
            all_files.add(sf)

    file_out: dict[str, set[str]] = defaultdict(set)
    file_in: dict[str, set[str]] = defaultdict(set)
    imp_out: dict[str, set[str]] = defaultdict(set)

    for link in links:
        rel = str(link.get("relation") or "relates_to")
        if rel not in DEPENDENCY_RELATIONS:
            continue
        sf_s = node_file.get(str(link.get("source") or ""))
        sf_t = node_file.get(str(link.get("target") or ""))
        if sf_s and sf_t and sf_s != sf_t:
            file_out[sf_s].add(sf_t)
            file_in[sf_t].add(sf_s)
            if rel in IMPORT_RELATIONS:
                imp_out[sf_s].add(sf_t)

    return file_out, file_in, imp_out, all_files


def _find_import_sccs(imp_out: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan's strongly connected components algorithm for circular import detection."""
    idx_counter = [0]
    stack: list[str] = []
    on_stack: set[str] = set()
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        index[v] = idx_counter[0]
        lowlink[v] = idx_counter[0]
        idx_counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in sorted(imp_out.get(v, ())):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                sccs.append(sorted(comp))

    for node in sorted(imp_out.keys()):
        if node not in index:
            strongconnect(node)
    return sorted(sccs)


def analyze_blast_radius(
    graph: dict[str, Any],
    target_files: list[str],
    root: Path = ROOT,
) -> dict[str, Any]:
    """বাংলা মন্তব্য: যেকোনো ফাইলে হাত দেওয়ার আগে বা PR খোলার আগে তার ডাউনস্ট্রিম ব্লাস্ট রেডিয়াস,
    কোন কোন টেস্ট চালানো আবশ্যক, এবং লেয়ার/সাইকেল ঝুঁকি নির্ধারণ করে।"""
    targets = sorted({_normalize_rel_path(f) for f in target_files if _normalize_rel_path(f)})
    file_out, file_in, imp_out, all_files = _build_file_adjacency(graph)
    target_set = set(targets)

    direct_dependents: set[str] = set()
    upstream_dependencies: set[str] = set()
    for tf in targets:
        direct_dependents.update(file_in.get(tf, set()) - target_set)
        upstream_dependencies.update(file_out.get(tf, set()) - target_set)

    two_hop_dependents: set[str] = set(direct_dependents)
    for dep in list(direct_dependents):
        two_hop_dependents.update(file_in.get(dep, set()) - target_set)

    # Impacted tests: graph-connected test files + heuristic stem match in tests/
    impacted_tests: set[str] = {
        f for f in (direct_dependents | two_hop_dependents) if _is_test_path(f)
    }
    stems = {Path(tf).stem for tf in targets if Path(tf).stem not in ("__init__", "main", "app", "index")}
    if stems:
        for known_file in all_files:
            if _is_test_path(known_file) and any(stem in Path(known_file).stem for stem in stems):
                impacted_tests.add(known_file)
        tests_dir = root / "tests"
        if tests_dir.is_dir():
            for tf_candidate in tests_dir.rglob("test_*.py"):
                if any(stem in tf_candidate.stem for stem in stems):
                    impacted_tests.add(_normalize_rel_path(str(tf_candidate.relative_to(root))))

    prod_dependents = sorted(f for f in direct_dependents if not _is_test_path(f))
    sorted_tests = sorted(impacted_tests)[:15]
    dep_count = len(prod_dependents)
    if dep_count >= 50:
        risk_level = "CRITICAL"
    elif dep_count >= 15:
        risk_level = "HIGH"
    elif dep_count >= 4:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    # Layer violation check on touched files (core -> gateway/studio/scripts)
    layer_violations: list[str] = []
    for tf in targets:
        if tf.startswith("core/") and not _is_test_path(tf):
            for out_f in sorted(file_out.get(tf, ())):
                if out_f.startswith(("gateway/", "studio/", "scripts/")):
                    layer_violations.append(f"{tf} -> {out_f}")

    # Circular dependency check touching target_files
    all_cycles = _find_import_sccs(imp_out)
    touching_cycles = [cyc for cyc in all_cycles if any(f in target_set for f in cyc)]

    py_tests = [t for t in sorted_tests if t.endswith(".py")]
    recommended_pytest_cmd = (
        f"pytest {' '.join(py_tests[:8])}" if py_tests else "pytest tests/"
    )

    return {
        "target_files": targets,
        "risk_level": risk_level,
        "direct_dependent_count": dep_count,
        "transitive_2hop_count": len(two_hop_dependents),
        "direct_dependents": prod_dependents[:25],
        "upstream_dependencies": sorted(upstream_dependencies)[:20],
        "impacted_tests": sorted_tests,
        "recommended_pytest_cmd": recommended_pytest_cmd,
        "layer_violations": layer_violations,
        "import_cycles": touching_cycles,
        "graph_provenance": graph.get("provenance", "graph.json"),
    }


def audit_graph_health(graph: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    """বাংলা মন্তব্য: পুরো কোডবেসের আর্কিটেকচারাল স্বাস্থ্য পরীক্ষা (লেয়ার ভায়োলেশন, সাইক্লিক ইমপোর্ট, হটস্পট ও ডেড-কোড প্রার্থী)।"""
    file_out, file_in, imp_out, all_files = _build_file_adjacency(graph)

    layer_violations: list[str] = []
    for src in sorted(all_files):
        if src.startswith("core/") and not _is_test_path(src):
            for tgt in sorted(file_out.get(src, ())):
                if tgt.startswith(("gateway/", "studio/", "scripts/")):
                    layer_violations.append(f"{src} -> {tgt}")

    cycles = _find_import_sccs(imp_out)
    hotspots = sorted(
        ((f, len(file_in.get(f, ()))) for f in all_files if not _is_test_path(f)),
        key=lambda item: (-item[1], item[0]),
    )[:15]

    zero_importer_candidates = sorted(
        f
        for f in all_files
        if (f.startswith("core/") or f.startswith("gateway/"))
        and not _is_test_path(f)
        and not f.endswith(("__init__.py", "main.py", "app.py"))
        and "alembic" not in f
        and len(file_in.get(f, ())) == 0
    )

    analysis_path = root / "graphify-out" / ".graphify_analysis.json"
    gods: list[Any] = []
    surprises: list[Any] = []
    if analysis_path.is_file():
        try:
            raw_a = json.loads(analysis_path.read_text(encoding="utf-8"))
            gods = raw_a.get("gods", [])[:10]
            surprises = raw_a.get("surprises", [])[:10]
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "total_files": len(all_files),
        "total_nodes": len(graph.get("nodes") or []),
        "total_links": len((graph.get("links") or []) + (graph.get("edges") or [])),
        "layer_violation_count": len(layer_violations),
        "layer_violations": layer_violations,
        "import_cycle_count": len(cycles),
        "import_cycles": cycles,
        "top_hotspots": [{"file": f, "dependents": c} for f, c in hotspots],
        "zero_importer_count": len(zero_importer_candidates),
        "zero_importer_sample": zero_importer_candidates[:30],
        "god_nodes": gods,
        "surprises": surprises,
        "graph_provenance": graph.get("provenance", "graph.json"),
    }


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
    links = (graph.get("links") or []) + (graph.get("edges") or [])
    relations = [
        {
            "from": link.get("source"),
            "to": link.get("target"),
            "relationType": link.get("relation", "relates_to"),
        }
        for link in links
    ]
    return {
        "domain": domain,
        "entity_count": len(entities),
        "relation_count": len(relations),
        "entities": entities,
        "relations": relations,
    }


def self_test() -> int:
    """Validate internal parser, blast-radius, cycle, and layer-violation invariants."""
    dummy_graph = {
        "provenance": "unit-test",
        "nodes": [
            {
                "id": "core_router",
                "label": "ModelRouter",
                "source_file": "core/brain/model_router.py",
                "source_location": "L10",
                "_callable": True,
            },
            {
                "id": "gw_chat",
                "label": "chat_endpoint",
                "source_file": "gateway/routes/chat.py",
                "source_location": "L45",
                "_callable": True,
            },
            {
                "id": "test_router",
                "label": "test_model_router_fallback",
                "source_file": "tests/test_model_router.py",
                "source_location": "L12",
                "_callable": True,
            },
            {
                "id": "cyc_a",
                "label": "A",
                "source_file": "core/a.py",
                "source_location": "L1",
            },
            {
                "id": "cyc_b",
                "label": "B",
                "source_file": "core/b.py",
                "source_location": "L1",
            },
        ],
        "links": [
            {"source": "gw_chat", "target": "core_router", "relation": "calls"},
            {"source": "test_router", "target": "core_router", "relation": "imports"},
            {"source": "cyc_a", "target": "cyc_b", "relation": "imports"},
            {"source": "cyc_b", "target": "cyc_a", "relation": "imports"},
        ],
    }
    matches = query_symbol(dummy_graph, "modelrouter")
    assert len(matches) == 1 and matches[0]["label"] == "ModelRouter"

    rels = trace_node_relations(dummy_graph, "gw_chat")
    assert len(rels) == 1 and rels[0]["relation"] == "calls"

    payload = format_entities_for_memory(dummy_graph, "core")
    assert payload["entity_count"] == 5 and payload["relation_count"] == 4

    blast = analyze_blast_radius(dummy_graph, ["core/brain/model_router.py"], root=Path("."))
    assert blast["direct_dependent_count"] == 1
    assert "gateway/routes/chat.py" in blast["direct_dependents"]
    assert "tests/test_model_router.py" in blast["impacted_tests"]
    assert "pytest tests/test_model_router.py" == blast["recommended_pytest_cmd"]

    cyc_blast = analyze_blast_radius(dummy_graph, ["core/a.py"], root=Path("."))
    assert len(cyc_blast["import_cycles"]) == 1

    health = audit_graph_health(dummy_graph, root=Path("."))
    assert health["import_cycle_count"] == 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Canonical Graphify AST Intelligence, Blast-Radius & Memory Bridge"
    )
    parser.add_argument("--self-test", action="store_true", help="Run self-tests and exit")
    parser.add_argument("--domain", choices=list(DEFAULT_DOMAINS.keys()), default="studio")
    parser.add_argument("--query", help="Search AST graph for symbol or filename")
    parser.add_argument("--trace", help="Trace all relations for a specific node ID")
    parser.add_argument(
        "--blast-radius",
        nargs="+",
        metavar="FILE",
        help="Compute downstream dependents, impacted tests, and cycle/layer risks for files",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run repo-wide graph architecture audit (cycles, layer violations, hotspots)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force fresh `graphify extract` if CLI is installed",
    )
    args, _ = parser.parse_known_args(argv)

    if args.self_test:
        rc = self_test()
        if rc == 0:
            print("sync_graph_to_memory self-test: PASS")
        return rc

    if args.query or args.trace or args.blast_radius or args.audit:
        graph = load_or_build_graph(ROOT, refresh=args.refresh)
        if args.query:
            print(json.dumps(query_symbol(graph, args.query), indent=2, ensure_ascii=False))
        elif args.trace:
            print(json.dumps(trace_node_relations(graph, args.trace), indent=2, ensure_ascii=False))
        elif args.blast_radius:
            print(
                json.dumps(
                    analyze_blast_radius(graph, args.blast_radius, root=ROOT),
                    indent=2,
                    ensure_ascii=False,
                )
            )
        elif args.audit:
            print(json.dumps(audit_graph_health(graph, root=ROOT), indent=2, ensure_ascii=False))
        return 0

    # Default sync mode (used by CI workflow regenerate-architecture-gap-baseline):
    # Try `graphify` CLI first if installed; otherwise fall back cleanly to stdlib AST graph.
    graphify = shutil.which("graphify")
    generated = ROOT / "graphify-out" / "graph.json"
    if graphify:
        extract = subprocess.run(
            [graphify, "extract", ".", "--code-only", "--output", str(ROOT)],
            cwd=ROOT,
            text=True,
            timeout=300,
            check=False,
        )
        if extract.returncode == 0 and generated.is_file():
            shutil.copyfile(generated, OUT)
            print(f"wrote {OUT} (via graphify CLI)")
            return 0

    if generated.is_file():
        shutil.copyfile(generated, OUT)
        print(f"wrote {OUT} (from cached graphify-out/graph.json)")
        return 0

    fallback_payload = build_stdlib_fallback_graph(ROOT)
    if not fallback_payload.get("nodes"):
        print("AST fallback produced an empty graph", file=sys.stderr)
        return 4
    OUT.write_text(json.dumps(fallback_payload, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT} (via stdlib AST fallback: {len(fallback_payload['nodes'])} nodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
