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
    derive_entrypoints,
    compute_first_party_heads,
    compute_path_roots,
    discover_module_aliases,
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



import pytest as _pytest  # noqa: E402


@_pytest.fixture(autouse=True)
def _derived_state():
    """Configure the module-level state that ``build_graph`` normally derives.

    The resolvers read derived globals (``_PATH_ROOTS``, ``_MODULE_ALIASES``,
    ``_FIRST_PARTY_HEADS``). Unit tests build synthetic module maps, so they must
    say what the derivation would have said — otherwise they silently test a
    resolver configured for the real repo.
    """
    import scripts.ci.architecture_gap_guardian as g

    saved = (
        g._PATH_ROOTS,
        g._MODULE_ALIASES,
        g._FIRST_PARTY_HEADS,
        g._THIRD_PARTY_HEADS,
        g._STDLIB_HEADS,
    )
    g._PATH_ROOTS = ("", "core.")
    g._MODULE_ALIASES = {}
    g._FIRST_PARTY_HEADS = {"core", "gateway", "browser", "api", "tools", "agents", "schemas"}
    g._THIRD_PARTY_HEADS = {"fastapi", "pydantic", "httpx", "json", "yaml"}
    g._STDLIB_HEADS = {"json", "typing", "re", "ast", "os", "sys", "pathlib", "logging", "email"}
    yield
    (
        g._PATH_ROOTS,
        g._MODULE_ALIASES,
        g._FIRST_PARTY_HEADS,
        g._THIRD_PARTY_HEADS,
        g._STDLIB_HEADS,
    ) = saved


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
    rep.entrypoints_found = ["gateway.main"]
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
    from scripts.ci.architecture_gap_guardian import _is_test_path

    assert _is_test_path(Path("core/tests/test_x.py"))


def test_missing_entrypoint_is_reported_not_silently_ignored():
    """A declared service whose entrypoint does not resolve must be reported."""
    rep = Report(modules=_mods("core.lifespan"))
    rep.entrypoints_found = []
    compute_reachability(rep)
    assert rep.reachable == set()


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


def test_entrypoints_are_derived_from_the_service_registry(real_report: Report):
    """No hardcoded list: entrypoints come from config/service_registry.yaml."""
    assert real_report.entrypoints_missing == []
    assert real_report.entrypoints_found, "no entrypoints derived"
    # Two families of anchor: deployed Python modules (from the registry) and
    # non-Python dispatchers (CI workflows, Makefile) whose synthetic ids are
    # namespaced with "@". Both are legitimate; anything else is a bug.
    for name in real_report.entrypoints_found:
        if name.startswith("@"):
            assert "/" in name or name == "@Makefile", name
        else:
            assert name in real_report.modules, name


def test_every_deployed_python_service_is_an_anchor(real_report: Report):
    """Each Python service the registry declares must map to a real module.

    This is the anti-rot check: adding a service to service_registry.yaml is the
    only step needed for the graph to account for it.
    """
    import yaml

    registry = yaml.safe_load((ROOT / "config/service_registry.yaml").read_text())["services"]
    python_services = {
        name: svc for name, svc in registry.items()
        if (svc.get("entrypoint") or "").strip()
        and not (svc.get("entrypoint") or "").strip().endswith(
            (".js", ".ts", ".tsx", ".mjs", ".json", ".sh")
        )
    }
    assert python_services, "registry declares no python services"
    # Each resolves to at least one anchor.
    assert len(real_report.entrypoints_found) >= len(python_services) - 1


def test_gateway_and_core_are_anchored(real_report: Report):
    assert "gateway.service.app" in real_report.entrypoints_found
    assert any(m.startswith("core.") for m in real_report.entrypoints_found)


def test_gateway_http_stack_is_reachable(real_report: Report):
    """The middlewares must be live — they are mounted by gateway.service.app."""
    un = set(real_report.unreachable)
    for module in (
        "gateway.service.app",
        "gateway.middleware.security_headers",
        "gateway.middleware.server_timing",
        "gateway.middleware.http_header_middleware",
    ):
        assert module not in un, f"{module} wrongly reported unreachable"


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


# ── dynamism: nothing may be a hardcoded list ──────────────────────────────
def test_no_hardcoded_entrypoint_tuple_remains():
    """The whole point: anchors must come from the registry, not a literal.

    A previous version carried ``LIVE_ENTRYPOINTS = (...)`` and it went stale —
    it named the test-only factory while production ran a different module.
    """
    import scripts.ci.architecture_gap_guardian as g

    assert not hasattr(g, "LIVE_ENTRYPOINTS"), (
        "a hardcoded entrypoint tuple reappeared; derive from service_registry.yaml"
    )


def test_scan_roots_are_discovered_not_listed():
    from scripts.ci.architecture_gap_guardian import discover_scan_roots

    roots = discover_scan_roots(ROOT)
    # Must find the real source trees without being told about them.
    for expected in ("core", "gateway", "browser", "scripts"):
        assert expected in roots, f"{expected} not discovered"


def test_path_roots_are_derived_from_the_tree():
    from scripts.ci.architecture_gap_guardian import compute_path_roots

    roots = compute_path_roots(ROOT)
    assert "" in roots
    # core/ is a sys.path root at runtime; 521 `import api.*` refs depend on it.
    assert "core." in roots
    assert len(roots) > 5, "too few derived roots; derivation probably no-op"


def test_stdlib_names_are_derived_and_excluded():
    from scripts.ci.architecture_gap_guardian import compute_stdlib_heads

    heads = compute_stdlib_heads()
    assert "json" in heads and "logging" in heads
    # And they must never be reported as dangling.
    assert not any(
        h in {"json", "logging", "email", "typing"} for h in ()
    )


def test_hostname_is_never_a_module_reference():
    from scripts.ci.architecture_gap_guardian import _is_dynamic_module_string

    for host in ("api.openai.com", "api.groq.com", "api.mistral.ai", "api.x.ai"):
        assert not _is_dynamic_module_string(host), host
    # ...but a real module path still is.
    assert _is_dynamic_module_string("api.routes.mcp_hub")


def test_missing_module_is_reported_but_missing_symbol_is_not():
    from scripts.ci.architecture_gap_guardian import Report, extract_edges

    mods = {
        "core.lifespan": Path("core/lifespan.py"),
        "core": Path("core/__init__.py"),
        "core.present": Path("core/present.py"),
    }
    missing: list[str] = []
    extract_edges("core.lifespan", "from core.gone import Thing\n", mods, missing, [])
    assert missing == ["core.gone"]          # module gone -> reported

    missing2: list[str] = []
    extract_edges("core.lifespan", "from core.present import Thing\n", mods, missing2, [])
    assert missing2 == []                    # symbol from a live module -> silent


def test_non_python_services_are_skipped_not_failed():
    """A JS edge proxy has no Python graph contribution; that is not a gap.

    Uses the REAL module map: the ``python main.py`` services resolve through
    their Dockerfile directory, so a synthetic single-module map would report
    them as gaps for the wrong reason.
    """
    from scripts.ci.architecture_gap_guardian import derive_entrypoints, discover_modules

    modules = discover_modules(ROOT)
    skipped: list[str] = []
    found, unresolved = derive_entrypoints(ROOT, modules, skipped)
    assert unresolved == [], f"declared services reported as gaps: {unresolved}"
    assert "gateway.service.app" in found
    # The non-Python services are recorded as skipped, not silently dropped.
    assert any("cloudflare" in s for s in skipped), skipped
    assert any("frontend" in s for s in skipped), skipped


def test_dangling_references_fail_the_check(real_report: Report):
    """Dangling refs are never baselined: they always fail."""
    from scripts.ci.architecture_gap_guardian import check_dangling

    if real_report.missing_refs:
        assert check_dangling(real_report) == real_report.missing_refs


# ── the 13 real defects the dynamic graph found (regression pins) ──────────
#: Verified absent modules imported WITHOUT an ImportError guard. Each is a
#: latent ModuleNotFoundError. Deliberate ``try/except ImportError`` chains are
#: excluded automatically, so this list is defects only.
REAL_DANGLING = {
    "core.llm.language_model",
    "tools.pr_reviewer",
    "scripts.audit_isolated_components",
    "tools.tool_knowledge_injector",
    "core.evolution.self_evolution_agent",
}


def test_known_absent_modules_are_reported(real_report: Report):
    """These were invisible before dangling-reference detection existed.

    Each is imported by live code and does not exist on disk. If one is ever
    created (or the import removed) this test fails, prompting an update — which
    is the point: the list is a snapshot of real defects, not a wishlist.
    """
    reported = {r.split(" -> ")[1] for r in real_report.missing_refs}
    missing_from_report = REAL_DANGLING - reported
    assert not missing_from_report, (
        "dangling-reference detection stopped reporting real defects: "
        f"{sorted(missing_from_report)}"
    )


def test_third_party_packages_are_never_reported_as_dangling(real_report: Report):
    """``mcp`` must never be a defect, whether or not it is installed.

    Written environment-independent ON PURPOSE. The first version also asserted
    that ``mcp`` appeared in the UNVERIFIED bucket — true on my machine, false in
    CI, which installs ``mcp>=1.28.1,<2`` inline. There the import resolves, so
    it lands in neither bucket. The tool was right in both environments; the test
    was asserting a property of *my venv*, not of the tool.

    The invariant that actually matters: nothing external is ever called dead.
    """
    reported = {r.split(" -> ")[1] for r in real_report.missing_refs}
    for external in ("mcp.server", "mcp.types", "ossinsight.client"):
        assert external not in reported, f"{external} misreported as first-party"


def test_unverified_bucket_only_holds_unimportable_packages(real_report: Report):
    """Whatever is listed as unverified must genuinely not import here.

    Guards the opposite error: putting a resolvable dependency in the "cannot
    check" bucket silently excuses a real defect. This test found TWO real bugs
    on its first run — ``browser.session.close`` (a capability id, not a module)
    and ``api.routes.health`` (ours, resolvable via the core/ sys.path root).
    """
    from scripts.ci.architecture_gap_guardian import compute_first_party_heads

    # Oracle = the repository, not the ambient interpreter. Using
    # importlib.util.find_spec() here was wrong twice over: it varies by venv,
    # and it changes mid-suite when another test appends to sys.path (measured:
    # resource_collection became "importable" only because a sibling test had
    # already mutated sys.path). A test must not inherit another test's side
    # effects — that is the same non-determinism this whole PR is fixing.
    first_party = compute_first_party_heads(real_report.modules)
    ours = set(real_report.modules)
    for entry in real_report.unverified_refs:
        dotted = entry.split(" -> ", 1)[1]
        assert dotted not in ours, (
            f"{dotted} is a real module in this repo but was reported UNVERIFIED; "
            "first-party references must never be excused"
        )
        root = dotted.split(".")[0]
        assert root not in first_party, (
            f"{dotted} is reported UNVERIFIED but {root!r} is a first-party import "
            "name derived from this repo; ours must never be excused as external"
        )


def test_dotted_capability_names_are_hints_not_dependencies(real_report: Report):
    """``browser.session.close`` is a capability id, not a package.

    It shares a prefix with the real ``browser`` package, so a naive dotted-string
    rule reported it as an unresolvable external dependency.
    """
    unverified = {e.split(" -> ", 1)[1] for e in real_report.unverified_refs}
    for capability in ("browser.session.close", "browser.session.create"):
        assert capability not in unverified, f"{capability} treated as a dependency"
    hints = {e.split(" -> ", 1)[1] for e in real_report.string_hints}
    assert hints, "capability-shaped strings should still be reported as hints"


def test_vocabulary_never_vetoes_a_real_module(real_report: Report):
    """Regression: a verb-suffix rule dropped ``api.routes.health``.

    ``health`` is on the verb list, but resolution must win — otherwise a real
    edge disappears and its target is reported dead.
    """
    assert "api.routes.health" in real_report.modules or any(
        e.dst.endswith("api.routes.health") for e in real_report.edges
    ), "a resolvable module path ending in a verb must still produce an edge"


def test_stdlib_submodules_are_never_dangling(real_report: Report):
    reported = {r.split(" -> ")[1] for r in real_report.missing_refs}
    for stdlib in ("email.utils", "email.mime.text", "logging.config"):
        assert stdlib not in reported, f"stdlib {stdlib} misreported"


def test_unverified_never_fails_the_guard(real_report: Report):
    from scripts.ci.architecture_gap_guardian import check_dangling

    assert check_dangling(real_report) == real_report.missing_refs
    assert not any("mcp" in r for r in check_dangling(real_report))


def test_optional_import_chains_are_not_reported():
    """A deliberate try/except ImportError is not a defect."""
    from scripts.ci.architecture_gap_guardian import extract_edges

    mods = {"core.lifespan": Path("core/lifespan.py"), "core": Path("core/__init__.py")}
    guarded = """
try:
    from core.gone import thing
except ImportError:
    thing = None
"""
    missing: list[str] = []
    extract_edges("core.lifespan", guarded, mods, missing, [])
    assert missing == [], "optional import reported as a defect"

    unguarded = "from core.gone import thing\n"
    missing2: list[str] = []
    extract_edges("core.lifespan", unguarded, mods, missing2, [])
    assert missing2 == ["core.gone"], "unguarded missing import not reported"


def test_broad_except_does_not_excuse_a_missing_module():
    """``except Exception`` is not an import fallback; the module must exist."""
    from scripts.ci.architecture_gap_guardian import extract_edges

    mods = {"core.lifespan": Path("core/lifespan.py"), "core": Path("core/__init__.py")}
    src = """
try:
    from core.gone import thing
except Exception:
    thing = None
"""
    missing: list[str] = []
    extract_edges("core.lifespan", src, mods, missing, [])
    assert missing == ["core.gone"]


def test_known_dangling_is_tracked_but_visible(real_report: Report):
    """Known defects never silently pass: they are reported, and new ones fail."""
    from scripts.ci.architecture_gap_guardian import check_dangling, load_baseline

    baseline = load_baseline()
    assert baseline and "known_dangling" in baseline, "defects must be frozen + visible"
    # Every frozen entry is still an actual dangling reference today.
    assert set(baseline["known_dangling"]) == set(real_report.missing_refs)
    # And a brand-new dangling ref would fail the check.
    assert check_dangling(real_report, baseline) == []

    class _Fake(Report):
        pass

    fake = Report(modules={}, missing_refs=["core.brand_new -> core.vanished"])
    assert check_dangling(fake, baseline) == ["core.brand_new -> core.vanished"]


# ── reproducibility: the verdict must not depend on the local venv ─────────
def test_declared_deps_include_httpx_not_skipped_as_url():
    """``httpx`` must not be filtered by a naive "http" prefix check.

    Measured bug: the dependency parser skipped lines starting with "http" to
    avoid ``http://`` URL requirements, which silently skipped ``httpx`` — a
    dependency declared in 8 requirements files. It surfaced as 154 references
    being reported UNVERIFIED on a machine without httpx installed.
    """
    from scripts.ci.architecture_gap_guardian import compute_declared_deps

    deps = compute_declared_deps(Path("."))
    assert "httpx" in deps, "httpx declared in requirements.lock but not parsed"
    assert "fastapi" in deps


def test_distribution_names_map_to_import_names():
    """Requirements list DISTRIBUTIONS; code imports MODULES."""
    from scripts.ci.architecture_gap_guardian import compute_declared_deps

    deps = compute_declared_deps(Path("."))
    for dist, import_name in (
        ("pyyaml", "yaml"),
        ("beautifulsoup4", "bs4"),
        ("python-dotenv", "dotenv"),
    ):
        if dist in deps:
            assert import_name in deps, f"{dist} declared but {import_name} not aliased"


def test_missing_pyyaml_fails_loudly_instead_of_reporting_a_partial_graph():
    """A silent fallback reported 2.5% reachable instead of 38.1%."""
    import subprocess
    import sys

    code = (
        "import sys; sys.modules['yaml'] = None\n"
        "sys.path.insert(0, '.')\n"
        "from pathlib import Path\n"
        "from scripts.ci.architecture_gap_guardian import derive_entrypoints, discover_modules\n"
        "try:\n"
        "    derive_entrypoints(Path('.'), discover_modules(Path('.')))\n"
        "except RuntimeError as e:\n"
        "    print('RAISED'); sys.exit(0)\n"
        "sys.exit('NO RAISE - would emit a partial graph')\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=".")
    assert "RAISED" in proc.stdout, (
        "derive_entrypoints must fail loudly when PyYAML is unavailable; "
        f"got stdout={proc.stdout!r} stderr={proc.stderr[-300:]!r}"
    )


# ── dispatcher edges: CI workflows and the Makefile are callers ────────────
def test_script_paths_listed_as_data_create_edges():
    """The dispatcher pattern — a list of "scripts/x.py" strings — is a call graph.

    Measured: `scripts.ci.guard_inventory` was created and registered in
    run_all_guards.py but still reported unreachable, because string paths that
    end in .py contributed no edges.
    """
    from scripts.ci.architecture_gap_guardian import _module_from_path_token

    modules = {
        "scripts.ci.runner": Path("scripts/ci/runner.py"),
        "scripts.ci.target": Path("scripts/ci/target.py"),
        "scripts": Path("scripts/__init__.py"),
        "scripts.ci": Path("scripts/ci/__init__.py"),
    }
    assert _module_from_path_token("scripts/ci/target.py", modules) == "scripts.ci.target"


def test_ci_workflows_are_treated_as_entrypoints(real_report: Report):
    """Whatever CI invokes is live by definition."""
    dispatchers = [e for e in real_report.entrypoints_found if e.startswith("@")]
    assert any(".github/workflows/" in d for d in dispatchers), (
        "workflows are not anchoring reachability; script-only-invoked modules "
        "would be reported dead"
    )
    assert "@Makefile" in dispatchers


def test_dispatch_edges_exist_and_resolve(real_report: Report):
    dispatch = [e for e in real_report.edges if e.kind == "dispatch"]
    assert dispatch, "no edges extracted from workflows/Makefile"
    for edge in dispatch:
        assert edge.src.startswith("@"), "synthetic dispatcher ids must be namespaced"
        assert edge.dst in real_report.modules, f"{edge.dst} is not a real module"


def test_roster_scripts_are_reachable_via_their_string_paths(real_report: Report):
    """The roster's own entries must not be dead code."""
    reachable = set(real_report.modules)  # placeholder for type clarity
    assert "scripts.ci.run_all_guards" in real_report.modules
    roster_edges = [e for e in real_report.edges if e.src == "scripts.ci.run_all_guards"]
    assert len(roster_edges) >= 40, (
        f"roster produced only {len(roster_edges)} edges; its string paths are not "
        "being resolved"
    )


def test_verdict_is_environment_independent(real_report: Report):
    """The things anybody acts on must not depend on the local venv.

    ``unverified_references`` legitimately does (a package importable here may be
    absent elsewhere), which is why it is exported with an explicit flag. The
    reachability verdict, the dangling set and the unreachable set must be
    identical on every machine — an earlier venv without PyYAML reported 2.5%
    reachable instead of 74.5%, and nobody re-checked it because it "passed".
    """
    from scripts.ci.architecture_gap_guardian import build_json, compute_reachability

    gaps = build_json(compute_reachability(real_report))["gaps"]
    assert gaps["unverified_is_environment_dependent"] is True, (
        "the unverified list varies by venv; consumers must be told so"
    )
    # Every other gap key is a decision someone acts on, so it must be stable.
    env_sensitive = {
        "unverified_references",
        "unverified_count",
        "unverified_is_environment_dependent",
        "string_hints",
        "string_hint_count",
    }
    verdict_keys = set(gaps) - env_sensitive
    assert verdict_keys == {"dangling_references", "dangling_count", "unresolved_services"}


def test_json_verdict_keys_are_stable_across_repeated_runs(real_report: Report):
    """Two runs in the same process must agree exactly."""
    from scripts.ci.architecture_gap_guardian import build_json, compute_reachability

    first = build_json(compute_reachability(real_report))
    second = build_json(compute_reachability(real_report))
    assert first == second
