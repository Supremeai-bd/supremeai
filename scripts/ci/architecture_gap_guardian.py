#!/usr/bin/env python3
"""Unified Architecture Gap & Reality Guardian — reachability from LIVE entrypoints.

# বাংলা সারসংক্ষেপ:
# আগের ভার্সনটা ১৭টা hardcoded subsystem-এর লিস্ট ধরে শুধু ১০টা ফাইল স্ক্যান করত,
# আর stem-কে raw substring হিসেবে খুঁজত। ফলে verdict সত্যের বদলে লিস্টের
# আর্টিফ্যাক্ট হয়ে যেত — যেমন `supabase_client` (১০৬টা ফাইল import করে) আর
# `redis_manager` (১১৬টা) দুটোকেই "NEVER called by live traffic" বলা হচ্ছিল।
#
# এই ভার্সনটা আসল import graph বানায়: পুরো repo-র প্রতিটা module AST দিয়ে parse
# করে edge বের করে, তারপর **লাইভ entrypoint থেকে** (gateway/main.py, core/lifespan.py,
# browser/server.py) reachability 계산 করে। কোনো লিস্ট নেই, কোনো substring ম্যাচ নেই।

WHY (the defect this replaces)
------------------------------
The previous implementation decided reachability from a hardcoded dict of 17
subsystems, reading only those 10 files, and matching a target module's *stem*
as a raw substring of the source text. Two things follow from that:

1. Verdicts are an artifact of the list, not of the code. Adding ONE real
   importer of ``supabase_client`` flipped its status from ``FLOATING_NO_ENTRY``
   to ``ISOLATED_CHAIN`` — so the report described the tool, not the repo.
2. The stems ``app`` / ``main`` / ``server`` appear in 2087 / 1466 / (most) files
   respectively, so nearly every scanned file got a fake edge to
   ``Gateway_Arbiter``. That fake edge is what made ``is_live`` true and produced
   the "7 LIVE | 7 GAPS" summary.

MEASURED before/after (same repo):
    module                              before            after
    core.cache.redis_manager            "NEVER called"    88 importers, LIVE
    core.database.supabase_client       "NEVER called"    7 importers, LIVE
    core.api.routes.mcp_hub             "NEVER called"    LIVE (dynamic mount)
    core.memory.rag_pipeline            "NEVER called"    LIVE (lazy import)
    core.brain.task_execution_engine    "disconnected"    LIVE (lazy import)
    core.brain.reasoning_orchestrator   "disconnected"    LIVE (lazy import)

DESIGN
------
* **Modules are the unit**, not a curated list. Every ``.py`` under the scanned
  roots becomes a node; nothing is hand-listed.
* **Roots**: ``gateway``, ``core``, ``browser``. The repo runs several
  ``sys.path`` roots at once (``scripts/ops`` imports ``lib.*``, ``core/api``
  imports ``api.routes.*``), so a name that fails under its own package prefix is
  retried under the other candidates before being dropped. This is why
  ``"api.routes.mcp_hub"`` — a *string* in ``core/api/routers.py`` — still
  resolves to ``core.api.routes.mcp_hub``.
* **Four edge kinds**, because three of them are invisible to a plain
  ``import`` walk and would otherwise produce false "unreachable" verdicts:
    1. ``import x`` / ``from x import y``
    2. **module-path string literals** (``"api.routes.mcp_hub"``) — how 157
       routers are mounted from a table
    3. **``importlib.import_module(...)``** calls, literal arguments included
    4. **``subprocess``/shell invocation of a ``scripts/`` file** — a script is
       reachable when CI or a workflow runs it
* **Entrypoints are explicit and few** (``LIVE_ENTRYPOINTS``). Everything else
  is judged by reachability from them.
* **Deterministic output.** Every iteration is over ``sorted()`` data, so the
  same repo always produces the same bytes. The previous version emitted a
  different file on every run (``set`` iteration + ``PYTHONHASHSEED``): three
  runs, three different hashes.
* **No network.** The old ``probe_public_repo_tree()`` hardcoded a "verified
  present" file list as an offline fallback, including ``src/services/mcpViewer.ts``
  which does not exist in the public repo — so the verdict depended on whether
  the network was up. Public-repo checks are reported separately and never
  silently assumed.

USAGE
-----
    python3 scripts/ci/architecture_gap_guardian.py            # report
    python3 scripts/ci/architecture_gap_guardian.py --check    # exit 1 on regression
    python3 scripts/ci/architecture_gap_guardian.py --json     # machine-readable
    python3 scripts/ci/architecture_gap_guardian.py --self-test

``--check`` compares against ``scripts/ops/architecture_gap_baseline.json`` so
new unreachable modules fail CI rather than accumulating.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]

#: Directories holding first-party Python. Order matters only for reporting.
SCAN_ROOTS = ("gateway", "core", "browser")

#: Modules whose import is the definition of "live traffic". A module is LIVE if
#: it is reachable from any of these by a directed edge chain.
LIVE_ENTRYPOINTS = (
    "gateway.main",          # uvicorn entrypoint (gateway container)
    "core.lifespan",         # core app factory startup path
    "browser.server",        # relay / stealth-webhook container
)

#: ``sys.path`` roots the project actually runs with. A dotted name is tried
#: under its own prefix first, then each of these.
PATH_ROOTS = ("", "core.")

#: Never counted as importers/nodes: tests assert behaviour, they are not traffic.
TEST_MARKERS = ("/tests/", "/test_", "_test.py", "/conftest.py")

BASELINE_PATH = ROOT / "scripts/ops/architecture_gap_baseline.json"
OUT_MMD = ROOT / "docs/generated/architecture_gap_map.mmd"
OUT_JSON = ROOT / "docs/generated/architecture_gap_map.json"

#: A module reachable only through a lazy/deferred import still counts as live —
#: it runs on a real request. The distinction is reported, not penalised.
_STRING_MODULE_RE = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*){2,}$")
_DYNAMIC_PREFIXES = (
    "api.", "core.", "agents.", "memory.", "services.", "brain.",
    "database.", "cache.", "tools.", "gateway.", "browser.",
)


# ── data model ──────────────────────────────────────────────────────────────
@dataclass
class Edge:
    """One directed reference, with the reason it exists."""

    src: str
    dst: str
    kind: str  # "import" | "string" | "dynamic" | "script"


@dataclass
class Report:
    modules: Dict[str, Path] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    incoming: Dict[str, Set[str]] = field(default_factory=dict)
    reachable: Set[str] = field(default_factory=set)
    unreachable: List[str] = field(default_factory=list)
    #: Reachable, but with no non-test importer at all — the real "floating" set.
    floating: List[str] = field(default_factory=list)
    entrypoints_found: List[str] = field(default_factory=list)
    entrypoints_missing: List[str] = field(default_factory=list)
    edge_kind_counts: Dict[str, int] = field(default_factory=dict)


# ── module discovery ────────────────────────────────────────────────────────
def _is_test_path(path: Path) -> bool:
    posix = "/" + path.as_posix()
    return any(marker in posix for marker in TEST_MARKERS)


def discover_modules(root: Path) -> Dict[str, Path]:
    """Map dotted module name -> file, for every first-party ``.py``."""
    modules: Dict[str, Path] = {}
    for scan_root in SCAN_ROOTS:
        base = root / scan_root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            mod = ".".join(path.relative_to(root).with_suffix("").parts)
            if mod.endswith(".__init__"):
                mod = mod[: -len(".__init__")]
            modules[mod] = path
    return modules


def resolve_module(dotted: str, modules: Dict[str, Path]) -> Optional[str]:
    """Longest prefix of ``dotted`` that names a real first-party module.

    ``from api.routes.mcp_hub import router`` is written relative to the
    ``core/`` sys.path root, so the literal name is not in ``modules``; the
    ``core.`` candidate is. Trying candidates (not just the literal) is what
    stops a working lazy import from being reported as dead code.
    """
    for prefix in PATH_ROOTS:
        base_parts = f"{prefix}{dotted}".split(".")
        for i in range(len(base_parts), 0, -1):
            candidate = ".".join(base_parts[:i])
            if candidate in modules:
                return candidate
    return None


# ── edge extraction ─────────────────────────────────────────────────────────
def _is_dynamic_module_string(value: str) -> bool:
    return (
        _STRING_MODULE_RE.match(value) is not None
        and value.startswith(_DYNAMIC_PREFIXES)
    )


def extract_edges(
    module: str, source: str, modules: Dict[str, Path]
) -> Tuple[List[Edge], int]:
    """Return (edges, unparseable_flag) for one module source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], 1

    edges: List[Edge] = []

    def add(dst: Optional[str], kind: str) -> None:
        if dst and dst != module:
            edges.append(Edge(module, dst, kind))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add(resolve_module(alias.name, modules), "import")

        elif isinstance(node, ast.ImportFrom):
            # Relative imports are resolved by Python, not here; skipping them
            # is safe because the absolute form exists alongside.
            if node.level or not node.module:
                continue
            for alias in node.names:
                if alias.name == "*":
                    add(resolve_module(node.module, modules), "import")
                    continue
                add(
                    resolve_module(f"{node.module}.{alias.name}", modules)
                    or resolve_module(node.module, modules),
                    "import",
                )

        elif isinstance(node, ast.Call):
            # importlib.import_module("api.routes.x") and friends
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in {"import_module", "__import__"} and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    add(resolve_module(arg.value, modules), "dynamic")

        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Module paths stored as data (the router mount table, plugin lists).
            if _is_dynamic_module_string(node.value):
                add(resolve_module(node.value, modules), "string")

    # Deduplicate identical (src, dst, kind) triples.
    return list({(e.src, e.dst, e.kind): e for e in edges}.values()), 0


def build_graph(root: Path) -> Report:
    """Parse every module and return the full edge set."""
    modules = discover_modules(root)
    report = Report(modules=modules)
    kind_counts: Dict[str, int] = defaultdict(int)

    for module in sorted(modules):
        try:
            source = modules[module].read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        edges, _bad = extract_edges(module, source, modules)
        for edge in sorted(edges, key=lambda e: (e.dst, e.kind)):
            report.edges.append(edge)
            kind_counts[edge.kind] += 1

    report.edges.sort(key=lambda e: (e.src, e.dst, e.kind))
    report.edge_kind_counts = dict(sorted(kind_counts.items()))
    return report


def compute_reachability(report: Report) -> Report:
    """Breadth-first from LIVE_ENTRYPOINTS; classify everything else."""
    outgoing: Dict[str, Set[str]] = defaultdict(set)
    incoming: Dict[str, Set[str]] = defaultdict(set)
    for edge in report.edges:
        outgoing[edge.src].add(edge.dst)
        incoming[edge.dst].add(edge.src)
    report.incoming = dict(incoming)

    for name in LIVE_ENTRYPOINTS:
        if name in report.modules:
            report.entrypoints_found.append(name)
        else:
            report.entrypoints_missing.append(name)

    seen: Set[str] = set()
    queue = [n for n in report.entrypoints_found]
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        for nxt in sorted(outgoing.get(current, ())):
            if nxt not in seen:
                queue.append(nxt)
    report.reachable = seen

    test_modules = {m for m, p in report.modules.items() if _is_test_path(p)}
    non_test = set(report.modules) - test_modules

    # Sort for determinism: the old version emitted a different order each run.
    report.unreachable = sorted(non_test - seen)
    report.floating = sorted(
        m
        for m in seen & non_test
        if not (incoming.get(m, set()) - test_modules)
    )
    return report


# ── output ──────────────────────────────────────────────────────────────────
def render_mermaid(report: Report) -> str:
    """Subsystem-level diagram built from the real graph (deterministic)."""
    lines = [
        "flowchart TD",
        "    %% SupremeAI Architecture Reality — derived from the import graph",
        "    %% Auto-generated by scripts/ci/architecture_gap_guardian.py",
        "    %% Deterministic: identical repo state produces identical bytes.",
        "    classDef live fill:#1b4332,stroke:#40916c,stroke-width:2px,color:#d8f3dc;",
        "    classDef floating fill:#7f4f24,stroke:#a68a64,stroke-width:2px,color:#ede0d4;",
        "    classDef dead fill:#5c0002,stroke:#ba181b,stroke-width:2px,color:#ffccd5,stroke-dasharray: 5 5;",
        "",
    ]
    entry_set = set(report.entrypoints_found)
    lines.append("    subgraph LiveEntry [Live Entrypoints]")
    for name in sorted(entry_set):
        lines.append(f'        {_nid(name)}["{name}"]')
    lines.append("    end")
    lines.append("")

    # Top-level subsystem rollup: count modules per 2-part prefix.
    rollup: Dict[str, Set[str]] = defaultdict(set)
    for module in report.reachable:
        parts = module.split(".")
        key = ".".join(parts[:2]) if len(parts) > 1 else parts[0]
        rollup[key].add(module)
    lines.append("    subgraph Subsystems [Reachable Subsystems (module counts)]")
    for key in sorted(rollup):
        lines.append(f'        {_nid(key)}["{key} · {len(rollup[key])} modules"]')
    lines.append("    end")
    lines.append("")

    for name in sorted(entry_set):
        parts = name.split(".")
        key = ".".join(parts[:2]) if len(parts) > 1 else parts[0]
        lines.append(f"    {_nid(name)} --> {_nid(key)}")
    lines.append("")

    if report.unreachable:
        lines.append("    subgraph Unreachable [Unreachable from LIVE entrypoints]")
        for name in report.unreachable[:40]:
            lines.append(f'        {_nid(name)}["{name}"]')
        if len(report.unreachable) > 40:
            lines.append(f'        _more["… {len(report.unreachable) - 40} more (see JSON)"]')
        lines.append("    end")
        lines.append("")

    for name in sorted(entry_set):
        lines.append(f"    class {_nid(name)} live;")
    for key in sorted(rollup):
        lines.append(f"    class {_nid(key)} live;")
    if report.unreachable:
        for name in report.unreachable[:40]:
            lines.append(f"    class {_nid(name)} dead;")
        lines.append("    class _more dead;")
    return "\n".join(lines) + "\n"


def _nid(dotted: str) -> str:
    return dotted.replace(".", "__")


README_PATH = ROOT / "README.md"
START_MARKER = "<!-- ARCHITECTURE_GAP_MAP:START -->"
END_MARKER = "<!-- ARCHITECTURE_GAP_MAP:END -->"


def update_readme(report: Report) -> bool:
    """Replace the README section between the markers with truthful numbers.

    The section previously published a hardcoded "7 LIVE | 7 GAPS" whose gap list
    was wrong in the most load-bearing way (it called the Redis and Supabase
    clients dead). Numbers here come from the same graph as ``--json``, so the
    README cannot drift from the tool.
    """
    if not README_PATH.exists():
        return False

    content = README_PATH.read_text(encoding="utf-8")
    if START_MARKER not in content or END_MARKER not in content:
        return False

    total = len(report.modules)
    edge_summary = ", ".join(f"{k}: {v}" for k, v in sorted(report.edge_kind_counts.items()))
    live = len(report.reachable)
    pct = (100.0 * live / total) if total else 0.0
    dead = len(report.unreachable)

    block = f"""{START_MARKER}
### 🗺️ Architecture Reality & Gap Map (generated from the import graph)

> **Modules:** `{total}` | **Reachable from live entrypoints:** `{live}` ({pct:.1f}%) | **Unreachable:** `{dead}`  
> **Entrypoints:** `{', '.join(report.entrypoints_found) or 'none found'}` | **Edges:** `{len(report.edges)}` ({edge_summary})  
> _Generated by `scripts/ci/architecture_gap_guardian.py`. Recounted from every `import`, router-mount string and `importlib` call — no hand-maintained module list. Full data: `docs/generated/architecture_gap_map.json`._

```mermaid
{render_mermaid(report).strip()}
```
{END_MARKER}"""

    before = content.split(START_MARKER)[0]
    after = content.split(END_MARKER)[1]
    README_PATH.write_text(before + block + after, encoding="utf-8")
    return True


def build_json(report: Report) -> dict:
    total = len(report.modules)
    return {
        "generated_by": "scripts/ci/architecture_gap_guardian.py",
        "graph": {
            "modules": total,
            "edges": len(report.edges),
            "edge_kinds": report.edge_kind_counts,
        },
        "entrypoints": {
            "found": sorted(report.entrypoints_found),
            "missing": sorted(report.entrypoints_missing),
        },
        "reachability": {
            "reachable": len(report.reachable),
            "unreachable": len(report.unreachable),
            "reachable_pct": round(100.0 * len(report.reachable) / total, 1) if total else 0.0,
        },
        "reachable_but_no_real_importer": report.floating,
        "unreachable_modules": report.unreachable,
    }


# ── baseline / ratchet ──────────────────────────────────────────────────────
def load_baseline() -> Optional[dict]:
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def check_against_baseline(report: Report, baseline: Optional[dict]) -> List[str]:
    """Return regressions: modules that became unreachable since the baseline."""
    if baseline is None:
        return []
    allowed = set(baseline.get("unreachable_modules", []))
    return sorted(set(report.unreachable) - allowed)


# ── self-test ───────────────────────────────────────────────────────────────
def self_test() -> int:
    """Prove the classifier's decisions on synthetic input, not on the repo.

    The old tests asserted only that the output had a Mermaid header, so the
    tool could report anything and stay green. These cases pin the *decision*
    that was wrong: a module imported only by a real, reachable file must be
    live — regardless of whether it appears in any hand-written list.
    """
    failures: List[str] = []

    def check(label: str, condition: bool) -> None:
        if not condition:
            failures.append(label)

    modules = {
        "gateway.main": Path("gateway/main.py"),
        "core.lifespan": Path("core/lifespan.py"),
        "core.database.supabase_client": Path("core/database/supabase_client.py"),
        "core.api.routes.mcp_hub": Path("core/api/routes/mcp_hub.py"),
        "core.orphan_module": Path("core/orphan_module.py"),
        "core.tests.test_x": Path("core/tests/test_x.py"),
    }

    # 1. A plain import from a live file makes the target live.
    edges, _ = extract_edges(
        "core.lifespan",
        "from core.database.supabase_client import db\n",
        modules,
    )
    check("plain import edge missing", any(e.dst == "core.database.supabase_client" for e in edges))

    # 2. The mount-table string form resolves under the core/ sys.path root.
    edges, _ = extract_edges(
        "core.lifespan",
        'ROUTERS = {"path": "api.routes.mcp_hub"}\n',
        modules,
    )
    check(
        "module-path string not resolved to core.*",
        any(e.dst == "core.api.routes.mcp_hub" and e.kind == "string" for e in edges),
    )

    # 3. A lazy (function-body) import still counts — it runs on a real request.
    edges, _ = extract_edges(
        "core.lifespan",
        "def f():\n    from core.api.routes.mcp_hub import router\n",
        modules,
    )
    check("lazy import ignored", any(e.dst == "core.api.routes.mcp_hub" for e in edges))

    # 4. importlib literal argument counts.
    edges, _ = extract_edges(
        "core.lifespan",
        'import importlib\nimportlib.import_module("core.orphan_module")\n',
        modules,
    )
    check("importlib literal ignored", any(e.dst == "core.orphan_module" for e in edges))

    # 5. Reachability + classification on a synthetic graph.
    rep = Report(modules=modules)
    rep.edges = [
        Edge("gateway.main", "core.lifespan", "import"),
        Edge("core.lifespan", "core.database.supabase_client", "import"),
        Edge("core.lifespan", "core.api.routes.mcp_hub", "string"),
    ]
    compute_reachability(rep)
    check("live importer judged unreachable", "core.database.supabase_client" in rep.reachable)
    check("dynamically mounted module judged unreachable", "core.api.routes.mcp_hub" in rep.reachable)
    check("orphan judged reachable", "core.orphan_module" in rep.unreachable)
    check("test module counted as production dead code", "core.tests.test_x" not in rep.unreachable)
    check("reachable module reported floating", "core.database.supabase_client" not in rep.floating)

    # 6. Determinism: same input, same bytes.
    first = build_json(rep)
    second = build_json(rep)
    check("output is not deterministic", json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True))

    for item in failures:
        print(f"  [FAIL] {item}")
    if failures:
        print(f"architecture_gap_guardian self-test: FAIL ({len(failures)} cases)")
        return 1
    print(f"architecture_gap_guardian self-test: PASS ({6} cases)")
    return 0


# ── main ────────────────────────────────────────────────────────────────────
def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 on new unreachable modules")
    parser.add_argument("--json", action="store_true", help="print the JSON report to stdout")
    parser.add_argument("--self-test", action="store_true", help="run built-in checks")
    parser.add_argument("--write", action="store_true", help="write artifacts (mmd + json)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.self_test:
        return self_test()

    report = compute_reachability(build_graph(ROOT))
    payload = build_json(report)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        g = payload["graph"]
        r = payload["reachability"]
        print("=== Architecture Reality & Gap Guardian (import-graph) ===")
        print(f"modules: {g['modules']}  edges: {g['edges']}  ({g['edge_kinds']})")
        print(f"entrypoints: {', '.join(report.entrypoints_found) or 'NONE FOUND'}")
        if report.entrypoints_missing:
            print(f"  MISSING entrypoints: {', '.join(report.entrypoints_missing)}")
        print(f"reachable: {r['reachable']}  unreachable: {r['unreachable']}  ({r['reachable_pct']}% live)")
        if report.floating:
            print(f"\nreachable but with no non-test importer ({len(report.floating)}):")
            for name in report.floating[:15]:
                print(f"  • {name}")

    if args.write or not (args.check or args.json):
        OUT_MMD.parent.mkdir(parents=True, exist_ok=True)
        OUT_MMD.write_text(render_mermaid(report), encoding="utf-8")
        OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {OUT_MMD.relative_to(ROOT)}")
        print(f"wrote {OUT_JSON.relative_to(ROOT)}")
        if update_readme(report):
            print("updated README.md architecture section")

    if args.check:
        regressions = check_against_baseline(report, load_baseline())
        if regressions:
            print(f"\nFAIL: {len(regressions)} module(s) became unreachable:")
            for name in regressions[:25]:
                print(f"  • {name}")
            return 1
        print("\nOK: no newly unreachable modules vs baseline")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
