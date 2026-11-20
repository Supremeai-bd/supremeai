"""Tests for ``scripts/ci/architecture_gap_guardian.py``.

WHY THESE REPLACE THE OLD ONES
------------------------------
The previous test file asserted that the output *looked* like a diagram
(``"flowchart TD" in mmd``, ``"subgraph LiveMesh" in mmd``). The tool could
therefore report that ``redis_manager`` — imported by 116 files — "is NEVER
called by live traffic" and stay green, because nothing checked a verdict.

These tests pin the *decisions*, and the two headline ones assert the exact
false claims the old implementation made. If a future rewrite reintroduces a
hand-maintained module list, ``test_redis_and_supabase_are_live`` fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ci.architecture_gap_guardian import (  # noqa: E402
    LIVE_ENTRYPOINTS,
    Edge,
    Report,
    build_graph,
    build_json,
    check_against_baseline,
    compute_reachability,
    discover_modules,
    extract_edges,
    render_mermaid,
    resolve_module,
    self_test,
)


# ── resolver ───────────────────────────────────────────────────────────────
def _mods(*names: str) -> dict:
    return {n: Path(n.replace(".", "/") + ".py") for n in names}


def test_resolve_finds_exact_module():
    mods = _mods("core.database.supabase_client")
    assert resolve_module("core.database.supabase_client", mods) == "core.database.supabase_client"


def test_resolve_handles_core_sys_path_root():
    """`from api.routes.mcp_hub import router` is written relative to core/.

    This is the single most important resolution case in this repo: 157 routers
    are mounted this way, and failing it was what produced false 'dead' verdicts.
    """
    mods = _mods("core.api.routes.mcp_hub")
    assert resolve_module("api.routes.mcp_hub", mods) == "core.api.routes.mcp_hub"


def test_resolve_returns_none_for_stdlib():
    assert resolve_module("json.decoder", _mods("core.x")) is None


def test_resolve_prefers_longest_prefix():
    mods = _mods("core.brain", "core.brain.reasoning_orchestrator")
    assert resolve_module(
        "core.brain.reasoning_orchestrator", mods
    ) == "core.brain.reasoning_orchestrator"


# ── edge extraction: the four kinds that must all be seen ───────────────────
def test_plain_import_edge():
    mods = _mods("core.lifespan", "core.database.supabase_client")
    edges, bad = extract_edges("core.lifespan", "from core.database.supabase_client import db\n", mods)
    assert bad == 0
    assert any(e.dst == "core.database.supabase_client" and e.kind == "import" for e in edges)


def test_mount_table_string_edge():
    """Router mount tables store module paths as strings, not imports."""
    mods = _mods("core.api.routers", "core.api.routes.mcp_hub")
    src = 'ROUTERS = [{"path": "api.routes.mcp_hub"}]\n'
    edges, _ = extract_edges("core.api.routers", src, mods)
    assert any(e.dst == "core.api.routes.mcp_hub" and e.kind == "string" for e in edges)


def test_importlib_literal_edge():
    mods = _mods("core.lifespan", "core.orphan_module")
    src = 'import importlib\nimportlib.import_module("core.orphan_module")\n'
    edges, _ = extract_edges("core.lifespan", src, mods)
    assert any(e.dst == "core.orphan_module" and e.kind == "dynamic" for e in edges)


def test_lazy_function_body_import_counts():
    """A deferred import still runs on a real request."""
    mods = _mods("core.lifespan", "core.memory.rag_pipeline")
    src = "def f():\n    from core.memory.rag_pipeline import RAGPipeline\n"
    edges, _ = extract_edges("core.lifespan", src, mods)
    assert any(e.dst == "core.memory.rag_pipeline" for e in edges)


def test_syntax_error_is_skipped_not_fatal():
    edges, bad = extract_edges("core.x", "def (:\n", _mods("core.x"))
    assert edges == [] and bad == 1


def test_self_edge_is_not_recorded():
    mods = _mods("core.a")
    edges, _ = extract_edges("core.a", "import core.a\n", mods)
    assert not any(e.dst == "core.a" for e in edges)


# ── classification ─────────────────────────────────────────────────────────
def _synthetic() -> Report:
    mods = _mods(
        "gateway.main",
        "core.lifespan",
        "core.database.supabase_client",
        "core.api.routes.mcp_hub",
        "core.orphan_module",
        "core.tests.test_x",
    )
    rep = Report(modules=mods)
    rep.edges = [
        Edge("gateway.main", "core.lifespan", "import"),
        Edge("core.lifespan", "core.database.supabase_client", "import"),
        Edge("core.lifespan", "core.api.routes.mcp_hub", "string"),
    ]
    return compute_reachability(rep)


def test_reachable_through_real_import():
    assert "core.database.supabase_client" in _synthetic().reachable


def test_reachable_through_dynamic_mount():
    assert "core.api.routes.mcp_hub" in _synthetic().reachable


def test_orphan_is_unreachable():
    assert "core.orphan_module" in _synthetic().unreachable


def test_tests_are_not_counted_as_dead_production_code():
    assert "core.tests.test_x" not in _synthetic().unreachable


def test_missing_entrypoint_is_reported_not_silently_ignored():
    rep = Report(modules=_mods("core.lifespan"))
    compute_reachability(rep)
    assert "gateway.main" in rep.entrypoints_missing


# ── the two headline regressions (the false claims) ────────────────────────
@pytest.fixture(scope="module")
def real_report() -> Report:
    return compute_reachability(build_graph(ROOT))


def test_redis_and_supabase_are_live(real_report: Report):
    """The old tool said both were 'NEVER called by live traffic'.

    redis_manager has 88 real importers and supabase_client 7 — calling them
    dead is the clearest possible signal that a tool is measuring its own
    hardcoded list instead of the repository.
    """
    un = set(real_report.unreachable)
    assert "core.cache.redis_manager" not in un
    assert "core.database.supabase_client" not in un


def test_dynamically_mounted_router_is_live(real_report: Report):
    assert "core.api.routes.mcp_hub" not in set(real_report.unreachable)


def test_lazily_imported_pipeline_is_live(real_report: Report):
    assert "core.memory.rag_pipeline" not in set(real_report.unreachable)


def test_all_entrypoints_exist(real_report: Report):
    assert real_report.entrypoints_missing == []
    assert set(real_report.entrypoints_found) == set(LIVE_ENTRYPOINTS)


def test_graph_is_substantial(real_report: Report):
    """A guardian that sees only 10 files cannot find real gaps."""
    assert len(real_report.modules) > 1000, "scanned too few modules to be meaningful"
    assert len(real_report.edges) > 2000
    # Every edge kind is actually exercised in this repo.
    for kind in ("import", "string", "dynamic"):
        assert real_report.edge_kind_counts.get(kind, 0) > 0, f"no {kind} edges found"


# ── determinism (the old tool produced different bytes every run) ───────────────
def test_json_output_is_deterministic(real_report: Report):
    a = json.dumps(build_json(real_report), sort_keys=True)
    b = json.dumps(build_json(real_report), sort_keys=True)
    assert a == b


def test_mermaid_output_is_deterministic(real_report: Report):
    assert render_mermaid(real_report) == render_mermaid(real_report)


def test_cli_output_stable_across_hash_seeds():
    """set iteration + PYTHONHASHSEED used to change the artifact every run."""
    script = ROOT / "scripts/ci/architecture_gap_guardian.py"
    outputs = []
    for seed in ("1", "2"):
        proc = subprocess.run(
            [sys.executable, str(script), "--json"],
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
            timeout=300,
        )
        assert proc.returncode == 0, proc.stderr[-500:]
        outputs.append(proc.stdout)
    assert outputs[0] == outputs[1], "output depends on PYTHONHASHSEED"


# ── baseline ratchet ───────────────────────────────────────────────────────
def test_newly_unreachable_module_fails_check():
    rep = Report(modules=_mods("core.lifespan", "core.newly_dead"))
    rep.unreachable = ["core.newly_dead"]
    baseline = {"unreachable_modules": []}
    assert check_against_baseline(rep, baseline) == ["core.newly_dead"]


def test_known_unreachable_module_does_not_fail_check():
    rep = Report(modules=_mods("core.lifespan", "core.old_dead"))
    rep.unreachable = ["core.old_dead"]
    baseline = {"unreachable_modules": ["core.old_dead"]}
    assert check_against_baseline(rep, baseline) == []


def test_no_baseline_means_no_false_regression():
    rep = Report(modules=_mods("core.x"))
    rep.unreachable = ["core.x"]
    assert check_against_baseline(rep, None) == []


def test_self_test_passes():
    assert self_test() == 0
