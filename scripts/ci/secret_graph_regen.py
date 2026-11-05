"""Secret graph regen guard (Phase 6 #30): verify secret_graph_nodes/edges are in sync with audit.

Rebuilds nodes/edges from scratchpad/audit_keys_output.txt and compares to committed files.
Exit 0 if in sync (or audit missing); --strict fails on drift.

Usage:
  python scripts/ci/secret_graph_regen.py --check
  python scripts/ci/secret_graph_regen.py --regen   (rewrite graph files)
  python scripts/ci/secret_graph_regen.py --self-test
"""
import argparse
import hashlib
import json
import os
import re
import sys

AUDIT = "scratchpad/audit_keys_output.txt"
NODES = "scratchpad/secret_graph_nodes.json"
EDGES = "scratchpad/secret_graph_edges.json"


def parse_audit(path):
    data = {}
    key = None
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"^([A-Z0-9_]+)\s+\(refs:\s*(\d+)\)\s*$", line.strip())
        if m:
            key = m.group(1)
            data[key] = {"refs": int(m.group(2)), "files": set()}
            continue
        if key and line.strip().startswith("-"):
            fm = re.match(r"^-\s+(.+):\d+\s*$", line.strip())
            if fm:
                data[key]["files"].add(fm.group(1))
    return data


def build_graph(data):
    nodes = []
    edges = []
    files = set()
    for k, d in data.items():
        nodes.append({"id": "key:" + k, "type": "secret_key", "label": k, "refs": d["refs"], "file_count": len(d["files"])})
        for f in d["files"]:
            files.add(f)
    for f in files:
        nodes.append({"id": "file:" + f, "type": "file", "label": f})
    for k, d in data.items():
        for f in d["files"]:
            edges.append({"source": "key:" + k, "target": "file:" + f, "type": "references"})
    return nodes, edges


def file_hash(path):
    if not os.path.exists(path):
        return None
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def self_test():
    import tempfile
    d = tempfile.mkdtemp()
    ap = os.path.join(d, "audit.txt")
    open(ap, "w").write("FOO_KEY  (refs: 2)\n  - a.py:1\n  - b.py:2\n")
    data = parse_audit(ap)
    assert "FOO_KEY" in data and len(data["FOO_KEY"]["files"]) == 2
    nodes, edges = build_graph(data)
    assert len(nodes) == 3 and len(edges) == 2
    print("self-test: PASS (1/1)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--regen", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    if not os.path.exists(AUDIT):
        print("audit file missing; skipping")
        return 0

    data = parse_audit(AUDIT)
    nodes, edges = build_graph(data)

    if args.regen:
        json.dump(nodes, open(NODES, "w", encoding="utf-8"), indent=1)
        json.dump(edges, open(EDGES, "w", encoding="utf-8"), indent=1)
        print(f"regenerated: {len(nodes)} nodes, {len(edges)} edges")
        return 0

    if args.check:
        if not os.path.exists(NODES) or not os.path.exists(EDGES):
            print("graph files missing")
            return 1 if args.strict else 0
        cur_nodes = json.load(open(NODES, encoding="utf-8"))
        cur_edges = json.load(open(EDGES, encoding="utf-8"))
        # compare only reference edges (alias-variant edges are extra)
        cur_ref_edges = sorted([e for e in cur_edges if e.get("type") == "references"], key=lambda x: (x["source"], x["target"]))
        rebuilt_nodes = sorted(nodes, key=lambda x: x["id"])
        rebuilt_edges = sorted(edges, key=lambda x: (x["source"], x["target"]))
        cur_nodes_s = sorted(cur_nodes, key=lambda x: x["id"])
        if cur_nodes_s == rebuilt_nodes and cur_ref_edges == rebuilt_edges:
            print(f"OK: graph in sync ({len(nodes)} nodes, {len(edges)} ref edges; {len(cur_edges)-len(cur_ref_edges)} alias edges extra)")
            return 0
        print("DRIFT: graph out of sync with audit")
        print(f"  committed: {len(cur_nodes)} nodes, {len(cur_ref_edges)} ref edges")
        print(f"  rebuilt:   {len(nodes)} nodes, {len(edges)} ref edges")
        return 1 if args.strict else 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY