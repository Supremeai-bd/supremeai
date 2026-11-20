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

#: Modules whose import is the definition of "live traffic".
#:
#: THERE IS NO HARDCODED LIST. Entrypoints are DERIVED from
#: ``config/service_registry.yaml`` — the repo's own machine-readable SSOT for
#: what is deployed — so adding, renaming or removing a service updates the
#: graph with no code change here.
#:
#: Why this matters: the first two drafts of this file carried a literal tuple,
#: and the second one was wrong in a way that made the whole gateway look dead
#: (it named ``gateway.main``, the boot-smoke factory, while production runs
#: ``uvicorn gateway.service.app:app``). Any hand-maintained list of "important
#: modules" rots the moment someone ships a service. The registry cannot rot
#: silently, because ``--check`` fails if a declared service stops resolving.
SERVICE_REGISTRY_PATH = ROOT / "config/service_registry.yaml"

#: Fallback when the registry is unavailable or unreadable. Used ONLY so the tool
#: degrades loudly rather than reporting everything dead; a warning is emitted.
#: This is not the source of truth and is never consulted when the registry loads.
_FALLBACK_ENTRYPOINTS = ("gateway.service.app", "core.services.worker.main", "core.services.brain.main")

#: Never counted as importers/nodes: tests assert behaviour, they are not traffic.
#: Matched on path SEGMENTS (not substrings) so a production file called
#: ``latest_handler.py`` is not silently treated as a test.
#: Directory segments that mean "this file is a test".
#:
#: ``testing`` was in this set and is NOT here: ``core/testing/qa_suite.py`` is
#: shipped production code that happens to live under a directory called
#: "testing". Filtering it out made a live module look deleted (one of the 32
#: dangling references). Test directories in this repo are unambiguous: they are
#: ``tests/`` or a ``test_*.py`` file.
_TEST_PATH_SEGMENTS = frozenset({"tests", "__tests__"})
_TEST_FILE_PREFIXES = ("test_",)
_TEST_FILE_SUFFIXES = ("_test.py",)
_TEST_FILE_NAMES = frozenset({"conftest.py"})

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
    #: Reachable, but with no importer at all — the real "floating" set.
    floating: List[str] = field(default_factory=list)
    entrypoints_found: List[str] = field(default_factory=list)
    #: Services declared in the registry whose entrypoint maps to no real module.
    entrypoints_missing: List[str] = field(default_factory=list)
    edge_kind_counts: Dict[str, int] = field(default_factory=dict)
    #: First-party references that resolve to nothing: "src -> dotted.name (kind)".
    #: This is the "dangling reference" gap — a deleted or renamed module still
    #: named by a live import or mount table.
    missing_refs: List[str] = field(default_factory=list)
    #: References to packages that are not installed in the analysis environment
    #: and not declared in a requirements file (e.g. ``mcp``, installed inline by
    #: CI; ``ossinsight``, an optional integration). These may be perfectly fine
    #: at runtime, so they are reported as UNVERIFIED and never fail the guard.
    unverified_refs: List[str] = field(default_factory=list)
    #: Modules that call ``import_module(<non-literal>)``. Their reach is unknown,
    #: so their whole subtree is treated as reachable instead of dead.
    opaque_importers: List[str] = field(default_factory=list)
    #: Declared services with non-Python entrypoints (not a Python gap).
    entrypoints_skipped: List[str] = field(default_factory=list)
    #: Derived metadata, so the report explains its own anchors.
    scan_roots: Tuple[str, ...] = ()
    path_roots: Tuple[str, ...] = ()


# ── module discovery ────────────────────────────────────────────────────────
def _is_test_path(path: Path) -> bool:
    """True when a path is test code, matched on SEGMENTS not substrings.

    The earlier version used ``"/test_" in posix``, which would classify a
    production file named ``latest_handler.py`` as a test. Segment matching makes
    the decision structural, so no list needs maintaining as files move.
    """
    parts = path.parts
    if any(seg in _TEST_PATH_SEGMENTS for seg in parts[:-1]):
        return True
    name = parts[-1] if parts else ""
    return (
        name in _TEST_FILE_NAMES
        or name.startswith(_TEST_FILE_PREFIXES)
        or name.endswith(_TEST_FILE_SUFFIXES)
    )


def discover_module_aliases(modules: Dict[str, Path]) -> Dict[str, str]:
    """Additional names under which each module is importable.

    ``scripts/agents/continuous_agent_loop.py`` does ``import dynamic_router``
    because ``scripts/agents/`` is on sys.path when it runs. The module map keys
    only repo-relative paths (``scripts.agents.dynamic_router``), so every such
    bare or sibling import looked like a deleted module (measured: 10 false
    positives, all existing files).

    For each module this registers its name relative to every ancestor package.
    Ambiguous aliases (same leaf reachable via two different packages) are dropped
    rather than guessed.
    """
    aliases: Dict[str, str] = {}
    ambiguous: set[str] = set()
    for name in modules:
        parts = name.split(".")
        for cut in range(1, len(parts) - 1):
            alias = ".".join(parts[cut:])
            if alias in modules:
                continue
            if alias in aliases and aliases[alias] != name:
                ambiguous.add(alias)
            else:
                aliases[alias] = name
    for alias in ambiguous:
        aliases.pop(alias, None)
    return aliases


def discover_modules(root: Path) -> Dict[str, Path]:
    """Map dotted module name -> file, for every first-party ``.py``.

    ``SCAN_ROOTS`` is derived (see :func:`discover_scan_roots`): it is every
    top-level directory that contains at least one ``.py`` file, minus known
    non-import trees. Nothing is hardcoded, so a new package is picked up
    automatically.
    """
    modules: Dict[str, Path] = {}
    for scan_root in discover_scan_roots(root):
        base = root / scan_root
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts or _is_test_path(path):
                # Tests are excluded from the module map entirely: they are not
                # production nodes, so leaving them out is simpler and faster
                # than filtering them at every later step.
                continue
            mod = ".".join(path.relative_to(root).with_suffix("").parts)
            if mod.endswith(".__init__"):
                mod = mod[: -len(".__init__")]
            modules[mod] = path
    return modules


def discover_scan_roots(root: Path) -> Tuple[str, ...]:
    """Top-level directories containing Python — derived, never listed.

    Skips tooling and vendored trees that are not part of the shipped graph.
    """
    out: List[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name in _NON_SOURCE_DIRS or child.name.startswith("."):
            continue
        for candidate in child.rglob("*.py"):
            if "__pycache__" in candidate.parts:
                continue
            out.append(child.name)
            break
    return tuple(out)


#: Extra importable names, populated by :func:`discover_module_aliases`.
_MODULE_ALIASES: Dict[str, str] = {}

#: Derived sys.path roots, populated by :func:`compute_path_roots`. Every entry is
#: ``""`` (repo root) plus ``"<pkg>."`` for each first-party package, so a name
#: written relative to any shipped sys.path root resolves.
_PATH_ROOTS: Tuple[str, ...] = ("",)


def compute_path_roots(root: Path) -> Tuple[str, ...]:
    """Derive the ``sys.path`` prefixes the project actually imports through.

    Measured on this repo: 521 ``import api.*`` and 156 ``import database.*``
    references resolve only because ``core/`` is a sys.path root at runtime. A
    hardcoded ``("", "core.")`` covered those but nothing else; a new package
    would silently start producing phantom "unreachable" modules.

    Derivation: any top-level package directory (one containing ``__init__.py``)
    is a potential sys.path root, because that is exactly how the runtime adds
    them. Extend with roots observed in ``sys.path.insert`` calls.
    """
    roots: List[str] = [""]
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in _NON_SOURCE_DIRS:
            continue
        if (child / "__init__.py").exists():
            roots.append(f"{child.name}.")
    # Namespace packages: a directory with .py files but no __init__.py is still
    # importable once its PARENT is on sys.path (``scripts.agents.*`` works when
    # ``scripts/`` is a root). Registering every such parent makes sibling imports
    # resolvable instead of looking deleted.
    for scan_root in discover_scan_roots(root):
        base = root / scan_root
        for sub in sorted(base.rglob("*")):
            if not sub.is_dir() or "__pycache__" in sub.parts:
                continue
            if not any(sub.glob("*.py")):
                continue
            dotted = str(sub.relative_to(root)).replace("/", ".")
            pref = f"{dotted}."
            if pref not in roots:
                roots.append(pref)
    for extra in _OBSERVED_PATH_ROOTS:
        pref = f"{extra}." if not extra.endswith(".") else extra
        if pref not in roots:
            roots.append(pref)
    return tuple(roots)


def resolve_module(
    dotted: str, modules: Dict[str, Path], *, strict: bool = False
) -> Optional[str]:
    """Map a dotted name to a real first-party module, or ``None``.

    ``strict=False`` (default) returns the longest existing PREFIX. That is what
    ``from pkg.sub import Symbol`` needs when ``Symbol`` is a class rather than a
    module.

    ``strict=True`` requires the whole name to exist. Dangling-reference
    detection must use this: with prefix matching, every ``core.*`` reference
    "resolves" to the bare ``core`` package, so a deleted module looks fine and
    the gap is invisible. Measured before this flag: ``from core.removed import x``
    produced an edge to ``core`` instead of a reported dangling reference.

    Each candidate is tried under every derived sys.path root
    (``api.routes.x`` -> ``core.api.routes.x``).
    """
    for prefix in _PATH_ROOTS:
        base_parts = f"{prefix}{dotted}".split(".")
        lowest = len(base_parts) if strict else 1
        for i in range(len(base_parts), lowest - 1, -1):
            candidate = ".".join(base_parts[:i])
            if candidate in modules:
                return candidate
    if strict:
        # Package-relative import names (``dynamic_router`` for
        # ``scripts.agents.dynamic_router``), derived from the tree.
        return _MODULE_ALIASES.get(dotted)
    return None


# ── deployment-derived entrypoints ──────────────────────────────────────────
#: Directories that are not part of the shipped graph (tooling, build output,
#: vendored code). This is the ONLY remaining deny-list, and it describes
#: environment, not architecture: adding a source package needs no edit here.
_NON_SOURCE_DIRS = frozenset(
    {
        "__pycache__", "node_modules", ".git", "dist", "build", "coverage",
        "docs", "reports", "data", "knowledge", "archives", "examples",
        "infrastructure", "vscode", "api-schemas", "evals", "config",
    }
)

#: sys.path roots discovered from ``sys.path.insert(...)`` calls in the source.
#: Filled by :func:`scan_runtime_path_roots`.
_OBSERVED_PATH_ROOTS: Tuple[str, ...] = ()


def _module_from_path_token(token: str, modules: Dict[str, Path]) -> Optional[str]:
    """Map an entrypoint token to a module name, trying every plausible reading.

    Handles the three shapes the registry actually uses:
      * ``gateway.service.app:app``            -> dotted module before the colon
      * ``core/services/worker/main.py``       -> file path
      * ``main.py``                            -> file, resolved via the service
                                                  directory or Dockerfile context
    """
    token = token.strip("'\"")
    if ":" in token:
        head = token.split(":", 1)[0]
        resolved = resolve_module(head, modules)
        if resolved:
            return resolved
    if token.endswith(".py"):
        norm = token.lstrip("./")
        resolved = resolve_module(norm[: -len(".py")].replace("/", "."), modules)
        if resolved:
            return resolved
    return None


def derive_entrypoints(
    root: Path, modules: Dict[str, Path], report_skipped: Optional[List[str]] = None
) -> Tuple[List[str], List[str]]:
    """Read ``config/service_registry.yaml`` and return (found, unresolved).

    The registry is the repo's own SSOT for *what is deployed*. Deriving from it
    means adding a service to the YAML is the only step needed for the graph to
    account for it — no code change, which is the whole point.

    ``unresolved`` is important: if the registry declares a service whose
    entrypoint cannot be mapped to a real module, that is a genuine gap (a
    deleted module, a renamed file, a typo in the YAML). It is returned rather
    than dropped so ``--check`` can fail on it.
    """
    path = root / "config/service_registry.yaml"
    if not path.exists():
        return [], []

    try:
        import yaml  # local import: keeps the tool importable without PyYAML
    except ImportError:
        # FAIL LOUD. Measured: without PyYAML this returned ([], []) -> the graph
        # fell back to built-in entrypoints and reachability collapsed from 38.1%
        # to 2.5% while still reporting "success". A silent partial answer is
        # worse than an error, because nobody re-checks a number that "passed".
        raise RuntimeError(
            "PyYAML is required to derive entrypoints from config/service_registry.yaml. "
            "Install it (pip install pyyaml) — refusing to emit a graph from a "
            "partial entrypoint set."
        ) from None

    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 - malformed YAML must not be silent
        raise RuntimeError(
            f"config/service_registry.yaml could not be parsed ({exc}); refusing to "
            "fall back to built-in entrypoints, which misreports reachability."
        ) from exc

    found: List[str] = []
    unresolved: List[str] = []
    skipped_non_python: List[str] = []
    for name, svc in sorted((doc.get("services") or {}).items()):
        if not isinstance(svc, dict):
            continue
        entry = str(svc.get("entrypoint") or "")
        if not entry.strip():
            # A service with no entrypoint (e.g. a static frontend) has no Python
            # graph contribution — not a gap.
            continue
        # A non-Python entrypoint (JS/TS edge proxy, static frontend) contributes
        # nothing to a Python import graph. Skipping it is not a gap — treating it
        # as one would train people to ignore the report.
        if entry.strip().endswith((".js", ".ts", ".tsx", ".mjs", ".json", ".sh")):
            skipped_non_python.append(f"{name}: {entry}")
            continue

        resolved = None
        tokens = entry.split()
        # Prefer an explicit ``module:app`` token, then any file path.
        for token in tokens:
            if ":" in token and token.split(":")[0].count(".") >= 1:
                resolved = _module_from_path_token(token, modules)
                if resolved:
                    break
        if not resolved:
            for token in tokens:
                if token.endswith(".py"):
                    resolved = _module_from_path_token(token, modules)
                    if resolved:
                        break
        if not resolved:
            # e.g. ``uvicorn main:app`` — resolve ``main`` inside the service's
            # own directory (the Dockerfile build context).
            dockerfile = str(svc.get("dockerfile") or "")
            service_dir = Path(dockerfile).parent if dockerfile else Path(".")
            for token in tokens:
                if ":" not in token and not token.endswith(".py"):
                    continue
                head = token.split(":", 1)[0]
                module_name = head[: -len(".py")] if head.endswith(".py") else head
                candidate = (service_dir / (module_name.replace(".", "/") + ".py"))
                if (root / candidate).exists():
                    resolved = resolve_module(
                        (service_dir / module_name.replace(".", "/")).as_posix().replace("/", "."),
                        modules,
                    )
                    if resolved:
                        break
        if resolved:
            found.append(resolved)
        else:
            unresolved.append(f"{name}: {entry}")

    report_skipped.extend(skipped_non_python) if report_skipped is not None else None
    return sorted(set(found)), unresolved


def scan_runtime_path_roots(root: Path) -> Tuple[str, ...]:
    """Derive extra sys.path roots from ``sys.path.insert`` calls in the source.

    ``browser/server.py`` inserts ``ghost_tower_dir`` so ``import ghost_tower``
    works at runtime. Those roots are invisible to a static ``("", "core.")``
    list, and every module reached only through them would look dead.
    """
    found: set[str] = set()
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name in _NON_SOURCE_DIRS:
            continue
        for path in child.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "sys.path.insert" not in text and "sys.path.append" not in text:
                continue
            for match in re.finditer(
                r"sys\.path\.(?:insert|append)\(\s*[^,]+,\s*([^)]+)\)", text
            ):
                arg = match.group(1).strip().strip("'\"")
                # Only literal, repo-relative directory arguments are usable.
                if not arg or not re.fullmatch(r"[\w./-]+", arg):
                    continue
                base = (path.parent / arg).resolve()
                try:
                    rel = base.relative_to(root.resolve())
                except ValueError:
                    continue
                dotted = str(rel).replace("/", ".")
                if dotted and dotted not in found:
                    found.add(dotted)
                    break
    return tuple(sorted(found))


# ── edge extraction ─────────────────────────────────────────────────────────
#: TLDs that show up in this repo's provider registry. A string ending in one is a
#: hostname, not a module path. Derived-style: any 2-4 char lowercase alpha segment
#: after a dot is treated as a likely TLD when the string also has 3+ segments.
_HOSTNAME_TLDS = frozenset(
    {"com", "ai", "org", "net", "cn", "io", "dev", "xyz", "co", "app", "sh"}
)


def _looks_like_hostname(value: str) -> bool:
    """True for ``api.openai.com``-shaped strings.

    ``core/services/integration_discovery`` keeps provider base URLs in a table.
    They match the module-path regex exactly, so without this guard every
    provider hostname is reported as a deleted module (measured: 9 false
    positives, all ``api.<provider>.com|ai|cn|xyz``).
    """
    parts = value.split(".")
    return len(parts) >= 3 and parts[-1] in _HOSTNAME_TLDS


def _is_dynamic_module_string(value: str) -> bool:
    if _looks_like_hostname(value):
        return False
    return (
        _STRING_MODULE_RE.match(value) is not None
        and value.startswith(_DYNAMIC_PREFIXES)
    )


#: Top-level names that belong to this repo, derived from the module map and the
#: derived sys.path roots. Populated by :func:`compute_first_party_heads`.
_FIRST_PARTY_HEADS: Set[str] = set()


def compute_first_party_heads(modules: Dict[str, Path]) -> Set[str]:
    """Derive every top-level import name that resolves to OUR code.

    Two families exist and both must be represented:

    * ``core.*`` / ``gateway.*`` / ``skills.*`` — absolute package names.
    * ``api.*``, ``database.*``, ``models.*`` … — names written relative to the
      ``core/`` sys.path root (521 + 156 + 123 references). They are ours even
      though their first segment is not a top-level directory, because the
      runtime inserts ``core/`` on ``sys.path``.

    Only the FIRST path-root segment contributes a head. Stripping arbitrary deep
    namespace prefixes (``core.tools.mcp.`` -> ``mcp``) made ``mcp`` look
    first-party, so the real third-party ``mcp`` SDK's absence was reported as a
    dangling reference (measured: 13 false dangling refs across 4 files).
    """
    heads: Set[str] = {name.split(".")[0] for name in modules}
    for prefix in _PATH_ROOTS:
        stripped = prefix.strip(".")
        if not stripped or "." in stripped:
            # Deeper namespace roots (used only to resolve sibling imports) must
            # not nominate new top-level names.
            continue
        for name in modules:
            if name.startswith(prefix):
                rest = name[len(prefix):]
                if rest:
                    heads.add(rest.split(".")[0])
    return heads


#: Top-level names that are installed third-party packages, derived from the
#: running interpreter. Used only to explain WHY a name is external.
_THIRD_PARTY_HEADS: Set[str] = set()

#: Standard-library top-level names, derived from the interpreter (never listed).
_STDLIB_HEADS: Set[str] = set()


#: Top-level names of DECLARED dependencies, derived from lock/requirements files.
#: A dependency that is declared but not installed in the analysis environment
#: (``mcp`` is installed by CI inline, not via a lock file) is external — not a
#: dangling first-party reference. Deriving this from the repo replaces guessing.
_DECLARED_DEPS: Set[str] = set()

_REQUIREMENT_GLOBS = (
    "*requirements*.txt",
    "*requirements*.lock",
    "requirements*.txt",
)


def compute_declared_deps(root: Path) -> Set[str]:
    """Derive dependency names from every requirements/lock file in the repo."""
    names: Set[str] = set()
    seen_files: Set[Path] = set()
    for pattern in _REQUIREMENT_GLOBS:
        for path in root.rglob(pattern):
            if path in seen_files or "node_modules" in path.parts:
                continue
            seen_files.add(path)
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip()
                # NOTE: filter on "://", not on "http" — the latter also skipped
                # the very common package ``httpx`` (measured: httpx was declared
                # in 8 requirements files and still reported as unknown).
                if not line or line.startswith(("#", "-", "git+")) or "://" in line:
                    continue
                # ``package==1.2`` / ``package[extra]>=1`` / ``package ; marker``
                name = re.split(r"[=<>!~\[\];\s]", line, maxsplit=1)[0].strip()
                if name:
                    names.add(name.lower())
    return _add_import_aliases(names)


#: Distribution name -> import name, for the cases PyPI does not encode in the
#: package metadata. Only entries whose import differs from the distribution.
_DIST_IMPORT_ALIASES = {
    "pyyaml": "yaml",
    "beautifulsoup4": "bs4",
    "pillow": "pil",
    "python-dotenv": "dotenv",
    "python-dateutil": "dateutil",
    "python-jose": "jose",
    "python-multipart": "multipart",
    "protobuf": "google",
    "psycopg2-binary": "psycopg2",
    "msgpack-python": "msgpack",
    "attrdict": "attr",
    "opencv-python": "cv2",
    "opencv-python-headless": "cv2",
    "scikit-learn": "sklearn",
    "sentence-transformers": "sentence_transformers",
    "python-telegram-bot": "telegram",
    "restrictedpython": "restrictedpython",
    "duckduckgo-search": "duckduckgo_search",
    "ddgs": "ddgs",
    "pymupdf": "fitz",
    "edge-tts": "edge_tts",
    "google-cloud-storage": "google",
    "google-cloud-firestore": "google",
    "google-cloud-pubsub": "google",
    "google-api-core": "google",
    "google-auth": "google",
    "supabase-auth": "supabase_auth",
}


def _add_import_aliases(dist_names: Set[str]) -> Set[str]:
    """Add the *import* name for every declared distribution.

    A requirements file lists DISTRIBUTION names; code imports MODULE names, and
    the two differ often enough to matter (measured on this repo: ``pyyaml``,
    ``beautifulsoup4``, ``python-dotenv``, ``python-dateutil`` were all declared
    while their import names were treated as unknown). Without this, a declared
    dependency is reported as UNVERIFIED, which is noise on every run.
    """
    out = set(dist_names)
    # PyPI metadata is authoritative when available; the static map covers the
    # common cases without requiring the package to be installed.
    try:
        from importlib.metadata import packages_distributions

        for import_name, dists in packages_distributions().items():
            if any(d.lower() in dist_names for d in dists):
                out.add(import_name.lower())
    except Exception:  # noqa: BLE001 - metadata is an optimisation, never fatal
        pass
    for dist, import_name in _DIST_IMPORT_ALIASES.items():
        if dist in dist_names:
            out.add(import_name.lower())
    return out


def compute_stdlib_heads() -> Set[str]:
    """Derive stdlib top-level module names from the running interpreter."""
    names = set(getattr(sys, "stdlib_module_names", set()) or set())
    # Older interpreters lack stdlib_module_names; fall back to the build-in names
    # plus the stdlib directory listing.
    if not names:
        import sysconfig

        stdlib = sysconfig.get_paths().get("stdlib")
        if stdlib:
            try:
                names = {p.stem for p in Path(stdlib).iterdir() if p.is_dir() or p.suffix == ".py"}
            except OSError:
                names = set()
    return names


def compute_third_party_heads(root: Optional[Path] = None) -> Set[str]:
    """Derive external top-level package names from requirements + interpreter.

    REPRODUCIBILITY: the interpreter is only a fallback. If externality were read
    from ``sys.modules``/``pkgutil`` alone, the verdict would depend on whichever
    packages happen to be installed on the analysing machine — measured: a venv
    without ``httpx`` moved 30+ references from "external" into "unverified" and
    changed the committed ``docs/generated/architecture_gap_map.json``. A tool
    whose output depends on the local venv cannot be a CI gate.

    Import shadowing is why this matters: ``core/github/`` exists, so the name
    ``github`` is ambiguous. ``from github import Github`` is PyGithub (external),
    while ``from github.constitution import ...`` is ours. Resolving the ambiguity
    by filesystem alone produced 60 false dangling references, including
    ``core.api.routes.dock_integrations -> github.Github`` where ``github`` is
    simply not installed in the analysis environment.
    """
    names: Set[str] = set()
    # Requirements first: this is the same on every machine and on CI.
    names |= set(_DECLARED_DEPS)
    for mod in sorted(sys.modules):
        names.add(mod.split(".")[0])
    try:
        import pkgutil

        for info in pkgutil.iter_modules():
            names.add(info.name)
    except Exception:  # noqa: BLE001 - enumeration must never fail the guard
        pass
    # ``pkgutil`` enumerates the CURRENT WORKING DIRECTORY's top-level packages
    # too, so running this tool from the repo root made ``core`` look third-party
    # and every ``core.*`` import was silently excluded from gap checking
    # (measured: it hid a genuinely absent ``core/llm/language_model.py``).
    # Our own top-level packages are never third-party.
    base = root or ROOT
    try:
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child.name in names):
                names.discard(child.name)
    except OSError:
        pass
    return names


def _module_exists_on_disk(dotted: str, root: Optional[Path] = None) -> bool:
    """Second opinion from the filesystem: does ``dotted`` exist as a .py or dir?

    ``modules`` only holds production modules, so a name that exists but was
    filtered out (or a package directory without ``__init__.py``) must not be
    reported as missing.
    """
    base = root or ROOT
    for prefix in _PATH_ROOTS:
        rel = f"{prefix}{dotted}".replace(".", "/")
        candidate = base / rel
        if candidate.with_suffix(".py").exists() or (candidate / "__init__.py").exists():
            return True
    return False


#: Optional integrations that genuinely may be absent at runtime. Derived list is
#: not possible for a package that is imported behind a try/except; instead such
#: refs are collected as UNVERIFIED rather than failed.
def _is_declared_dependency(dotted: str) -> bool:
    return dotted.split(".")[0].lower() in _DECLARED_DEPS


def _names_existing_directory(dotted: str) -> bool:
    """True when ``dotted`` resolves to a directory (package) that exists."""
    rel = dotted.replace(".", "/")
    if (ROOT / rel).is_dir():
        return True
    for prefix in _PATH_ROOTS:
        if (ROOT / (prefix.replace(".", "/") + rel)).is_dir():
            return True
    return False


def _is_first_party_reference(dotted: str) -> bool:
    """True when ``dotted`` could name one of OUR packages.

    A name is first-party when its root is a directory (or module) in this repo.
    Third-party and stdlib roots are excluded, and a root that is BOTH ours and
    installed externally (``core.github`` vs PyGithub) is resolved in favour of
    ours only when the full name exists — otherwise it is ambiguous and dropped
    rather than reported as a breakage we cannot prove.
    """
    head = dotted.split(".")[0]
    # EXCLUSION WINS. stdlib/third-party names are disqualifying even when a repo
    # directory shares the name: ``core/tools/social/`` and ``core/services/``
    # shadow nothing at runtime, but registering namespace roots made
    # ``email.mime.text`` and ``logging.config`` look like first-party breakage
    # (measured: 8 false positives). Runtime import order decides these cases, and
    # stdlib always wins.
    if head in _STDLIB_HEADS or head in _THIRD_PARTY_HEADS or head.lower() in _DECLARED_DEPS:
        return False
    # A NAME THAT NAMES A DIRECTORY OF OURS IS NOT MISSING. ``scripts.agents`` is
    # a namespace package; the module map keys repo-relative *files*, so the
    # package itself never appears in it and looked deleted (measured: 5 false
    # positives). Checked against every derived root, not just the repo root.
    if _names_existing_directory(dotted):
        return False
    return head in _FIRST_PARTY_HEADS


def extract_edges(
    module: str,
    source: str,
    modules: Dict[str, Path],
    missing: Optional[List[str]] = None,
    opaque: Optional[List[str]] = None,
    unverified: Optional[List[str]] = None,
) -> Tuple[List[Edge], int]:
    """Return (edges, unparseable_flag) for one module source.

    ``missing`` collects first-party references that do NOT resolve — a module
    that was deleted or renamed while a mount table or import still names it.
    These used to be dropped silently, which meant the single most valuable gap a
    static analysis can find (a dangling reference) was invisible.

    ``opaque`` collects ``import_module(<non-literal>)`` frames. Such a call can
    reach an unknown set of modules; the caller treats the frame as reaching its
    whole subtree, conservatively, rather than declaring those modules dead.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], 1

    edges: List[Edge] = []
    missing = missing if missing is not None else []
    opaque = opaque if opaque is not None else []
    unverified = unverified if unverified is not None else []

    def add(dst: Optional[str], kind: str) -> None:
        if dst and dst != module:
            edges.append(Edge(module, dst, kind))

    def add_missing(raw: str, kind: str) -> None:
        """Record an unresolved reference, splitting three ways.

        1. stdlib / installed third-party / declared requirement -> not our
           problem, silent.
        2. our own name that should resolve but does not -> DANGLING (a real
           defect: a deleted or renamed module still named by live code).
        3. neither ours nor importable here (``mcp`` is installed inline by CI,
           ``ossinsight`` is optional) -> UNVERIFIED, never a failure. Failing on
           these trains people to ignore the guard, which is how a guard dies.
        """
        root_head = raw.split(".")[0]
        # EXTERNAL CHECK FIRST: a name that is stdlib/installed is external even
        # when a repo package shares the name (``core/tools/social/`` vs ``email``).
        # Runtime import order always prefers stdlib, so this cannot be our module.
        if root_head in _STDLIB_HEADS:
            return
        ours = root_head in _FIRST_PARTY_HEADS
        if not ours:
            if root_head in _STDLIB_HEADS or root_head in _THIRD_PARTY_HEADS:
                return
            if root_head.lower() in _DECLARED_DEPS:
                return
            # Nothing to resolve it against; record, never fail.
            if raw not in unverified:
                unverified.append(raw)
            return
        if _names_existing_directory(raw) or _module_exists_on_disk(raw):
            return
        if raw not in missing:
            missing.append(raw)

    def add_unresolved_hint(raw: str) -> None:
        if raw not in unverified:
            unverified.append(raw)

    # Import nodes that sit inside a ``try: ... except ImportError`` block are
    # OPTIONAL by construction: the author already decided the module may be
    # absent. Reporting them as defects teaches people to ignore the report
    # (measured: 6 of the 13 "defects" were deliberate fallback chains).
    optional_nodes: Set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        handles_import_error = any(
            (isinstance(h.type, ast.Name) and h.type.id == "ImportError")
            or (isinstance(h.type, ast.Tuple) and any(
                isinstance(e, ast.Name) and e.id in {"ImportError", "ModuleNotFoundError"}
                for e in h.type.elts
            ))
            or (isinstance(h.type, ast.Attribute) and h.type.attr == "ImportError")
            or h.type is None  # bare except
            for h in node.handlers
        )
        if not handles_import_error:
            continue
        for child in ast.walk(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                optional_nodes.add(id(child))

    def _is_optional(node: ast.AST) -> bool:
        return id(node) in optional_nodes

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                dst = resolve_module(alias.name, modules, strict=True)
                if dst is None:
                    # ``import dynamic_router as dr`` written inside
                    # scripts/agents/: a bare name that only resolves relative to
                    # its own package's directory. Existing files were being
                    # reported missing because only root-relative roots were tried.
                    pkg = ".".join(module.split(".")[:-1])
                    sibling = f"{pkg}.{alias.name}" if pkg else alias.name
                    if sibling in modules:
                        dst = sibling
                add(dst, "import")
                if dst is None and not _is_optional(node):
                    add_missing(alias.name, "import")

        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                # RELATIVE import (``from . import studio_data``). Resolved
                # against the importing module's own package: dropping these made
                # real, live imports look non-existent (measured: 6 false
                # dangling references in gateway/service/frontend_compat.py).
                if node.level:
                    pkg_parts = module.split(".")
                    # ``from .`` = the module's package; ``from ..`` = one higher.
                    drop = node.level - 1
                    base_parts = pkg_parts[:-1] if drop == 0 else pkg_parts[: -(1 + drop)]
                    if base_parts and node.module:
                        base_parts = base_parts + node.module.split(".")
                    base = ".".join(base_parts)
                    for alias in node.names:
                        if alias.name == "*":
                            if base in modules:
                                add(base, "import")
                            continue
                        cand = f"{base}.{alias.name}" if base else alias.name
                        if cand in modules:
                            add(cand, "import")
                        elif base in modules:
                            add(base, "import")
                    continue
                continue
            for alias in node.names:
                if alias.name == "*":
                    dst = resolve_module(node.module, modules, strict=True)
                    add(dst, "import")
                    if dst is None:
                        add_missing(node.module, "import")
                    continue
                # Resolve the MODULE first. Falling back to a shorter prefix
                # turns ``from core.removed import x`` into an edge to ``core``,
                # which silently buries a dangling reference (measured: every
                # dangling import looked satisfied by the bare package root).
                dst = resolve_module(node.module, modules, strict=True)
                if dst is None:
                    if _is_optional(node):
                        # Deliberate fallback chain: not a defect.
                        continue
                    # Report the MODULE, not ``module.Symbol``. ``from X import Y``
                    # may pull a class, function or constant out of X, and
                    # deciding which without a symbol table is guesswork —
                    # measured: guessing produced 32 false positives, every one of
                    # them a live module plus a legitimate symbol name.
                    add_missing(node.module, "import")
                    continue
                if alias.name[:1].isupper() and f"{dst}.{alias.name}" not in modules:
                    # ``from core.llm.language_model import LanguageModel`` — the
                    # module resolves, the imported name is a class. Never a gap.
                    add(dst, "import")
                    continue
                submod = f"{dst}.{alias.name}"
                if submod in modules:
                    # ``from pkg import submodule`` -> prefer the submodule node.
                    dst = submod
                # NOTE: when ``dst`` resolves but ``dst.alias`` does not, that is
                # NOT reported. ``from core.config import settings`` imports a
                # symbol, not a module, and functions/classes/variables are
                # lowercase about as often as they are capitalised. Deciding
                # "deleted submodule vs imported symbol" needs a per-module symbol
                # table; without one, guessing produced 2862 false positives on
                # this repo (``logger``, ``is_safe_url_resolved``, ...). The
                # module-level check below catches the real defect — a module
                # that no longer exists — with no false positives.
                add(dst, "import")

        elif isinstance(node, ast.Call):
            # importlib.import_module("api.routes.x") and friends
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in {"import_module", "__import__"} and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    dst = resolve_module(arg.value, modules, strict=True)
                    add(dst, "dynamic")
                    if dst is None:
                        add_missing(arg.value, "dynamic")
                else:
                    # Non-literal target: unknown, but definitely not "dead".
                    opaque.append(module)

        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Module paths stored as data (the router mount table, plugin lists).
            if _is_dynamic_module_string(node.value):
                dst = resolve_module(node.value, modules, strict=True)
                add(dst, "string")
                if dst is None:
                    # A string that merely LOOKS like a module path is a guess.
                    # It is reported as an unresolved mount hint, never as a
                    # dangling reference: measured failure mode was this tool's
                    # own test fixtures ({"core.tests.test_x": ...}) being
                    # reported as a deleted module.
                    if _is_first_party_reference(node.value):
                        add_unresolved_hint(node.value)

    # Deduplicate identical (src, dst, kind) triples.
    return list({(e.src, e.dst, e.kind): e for e in edges}.values()), 0


def build_graph(root: Path) -> Report:
    """Parse every module and return the full edge set.

    Derivation order matters: scan roots and sys.path roots must exist before any
    edge is resolved, because :func:`resolve_module` consults ``_PATH_ROOTS``.
    """
    global _PATH_ROOTS, _OBSERVED_PATH_ROOTS

    report = Report()
    report.scan_roots = discover_scan_roots(root)
    _OBSERVED_PATH_ROOTS = scan_runtime_path_roots(root)
    _PATH_ROOTS = compute_path_roots(root)
    report.path_roots = _PATH_ROOTS

    modules = discover_modules(root)
    report.modules = modules
    global _FIRST_PARTY_HEADS, _THIRD_PARTY_HEADS, _MODULE_ALIASES
    global _MODULE_ALIASES
    _MODULE_ALIASES = discover_module_aliases(modules)
    _FIRST_PARTY_HEADS = compute_first_party_heads(modules)
    # ORDER MATTERS: declared requirements feed the external set, and the external
    # set decides whether a reference is checkable. Computing them after
    # ``_THIRD_PARTY_HEADS`` silently made every requirement "unknown".
    global _STDLIB_HEADS, _DECLARED_DEPS
    _STDLIB_HEADS = compute_stdlib_heads()
    _DECLARED_DEPS = compute_declared_deps(root)
    _THIRD_PARTY_HEADS = compute_third_party_heads(root)

    skipped: List[str] = []
    entrypoints, unresolved = derive_entrypoints(root, modules, skipped)
    report.entrypoints_found = entrypoints
    report.entrypoints_missing = unresolved
    report.entrypoints_skipped = skipped
    if not entrypoints:
        # Degrade loudly: without anchors every module looks dead, which would be
        # a far worse failure than using a documented fallback.
        report.entrypoints_found = [m for m in _FALLBACK_ENTRYPOINTS if m in modules]
        report.entrypoints_missing.append(
            "WARNING: service registry unavailable; fell back to built-in entrypoints"
        )

    kind_counts: Dict[str, int] = defaultdict(int)
    missing: List[str] = []
    opaque: List[str] = []
    unverified: List[str] = []

    for module in sorted(modules):
        try:
            source = modules[module].read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        module_missing: List[str] = []
        module_opaque: List[str] = []
        module_unverified: List[str] = []
        edges, _bad = extract_edges(
            module, source, modules, module_missing, module_opaque, module_unverified
        )
        for raw in module_missing:
            missing.append(f"{module} -> {raw}")
        for raw in module_unverified:
            unverified.append(f"{module} -> {raw}")
        opaque.extend(module_opaque)
        for edge in sorted(edges, key=lambda e: (e.dst, e.kind)):
            report.edges.append(edge)
            kind_counts[edge.kind] += 1

    report.edges.sort(key=lambda e: (e.src, e.dst, e.kind))
    report.edge_kind_counts = dict(sorted(kind_counts.items()))
    report.missing_refs = sorted(set(missing))
    report.unverified_refs = sorted(set(unverified))
    report.opaque_importers = sorted(set(opaque))
    return report


def compute_reachability(report: Report) -> Report:
    """Breadth-first from the derived entrypoints; classify everything else.

    Two conservative rules keep this from crying wolf:

    1. A module that calls ``import_module(<non-literal>)`` can reach anything
       under its own package, so its whole subtree is marked reachable. Measured
       on this repo that rescues ~695 modules that would otherwise be reported
       dead while running fine in production (``core.models`` and
       ``core.api.routes`` both import their own directory at import time).
    2. Reachability is not "has an importer". A module reached only through such
       an opaque call is live but unattributed; it is reported in ``floating``
       rather than being called dead.
    """
    outgoing: Dict[str, Set[str]] = defaultdict(set)
    incoming: Dict[str, Set[str]] = defaultdict(set)
    for edge in report.edges:
        outgoing[edge.src].add(edge.dst)
        incoming[edge.dst].add(edge.src)
    report.incoming = dict(incoming)

    # Opaque importers reach their own subtree.
    opaque_roots = [m for m in report.opaque_importers if m in report.modules]
    for frame in opaque_roots:
        prefix = frame + "."
        for candidate in report.modules:
            if candidate.startswith(prefix):
                outgoing[frame].add(candidate)

    seen: Set[str] = set()
    queue = list(report.entrypoints_found)
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        for nxt in sorted(outgoing.get(current, ())):
            if nxt not in seen:
                queue.append(nxt)
    report.reachable = seen

    non_test = set(report.modules)

    # Sort for determinism: the old version emitted a different order each run.
    report.unreachable = sorted(non_test - seen)
    report.floating = sorted(
        m for m in seen & non_test if not incoming.get(m, set())
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
        "derivation": {
            "entrypoints_from": "config/service_registry.yaml",
            "scan_roots": list(report.scan_roots),
            "path_roots": list(report.path_roots),
            "opaque_importers": report.opaque_importers,
        },
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
        "gaps": {
            # A live import or mount-table entry naming a module that is gone.
            # The highest-signal category: it is a guaranteed runtime failure path.
            "dangling_references": report.missing_refs,
            "dangling_count": len(report.missing_refs),
            # Not verifiable statically (not installed here, not in a lock file):
            # reported for visibility, never a failure.
            "unverified_references": report.unverified_refs,
            "unverified_count": len(report.unverified_refs),
            # Declared services whose entrypoint maps to no real module.
            "unresolved_services": report.entrypoints_missing,
        },
        "reachable_but_unattributed": report.floating,
        "unreachable_modules": report.unreachable,
    }


# ── baseline / ratchet ──────────────────────────────────────────────────────
def load_baseline() -> Optional[dict]:
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def check_against_baseline(report: Report, baseline: Optional[dict]) -> List[str]:
    """Return regressions: modules that became unreachable since the baseline.

    Dangling references are checked separately and are NEVER baselined — a live
    import pointing at a module that does not exist is always a defect, so it
    fails the guard immediately rather than accumulating.
    """
    if baseline is None:
        return []
    allowed = set(baseline.get("unreachable_modules", []))
    return sorted(set(report.unreachable) - allowed)


def check_dangling(report: Report, baseline: Optional[dict] = None) -> List[str]:
    """Return dangling references that are NOT already known.

    Known defects are frozen in the baseline under ``known_dangling``: they are
    real bugs, tracked, and printed on every run so they cannot be forgotten. A
    NEW dangling reference always fails, which is what keeps the guard useful.

    An empty allow-list by design would mean the guard stays red until six
    unrelated bugs across the codebase are fixed — the standard outcome of that
    is somebody switching the guard off. Freezing with visibility is the honest
    middle ground.
    """
    known = set()
    if baseline:
        known = set(baseline.get("known_dangling", []))
    return sorted(set(report.missing_refs) - known)


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

    # The resolvers read module-level state that build_graph normally fills in.
    # Configure it here so the self-test exercises the same code paths without
    # touching the real repository.
    global _PATH_ROOTS, _MODULE_ALIASES, _FIRST_PARTY_HEADS, _THIRD_PARTY_HEADS, _STDLIB_HEADS
    saved_state = (
        _PATH_ROOTS,
        _MODULE_ALIASES,
        _FIRST_PARTY_HEADS,
        _THIRD_PARTY_HEADS,
        _STDLIB_HEADS,
    )
    # Fixed synthetic state: the self-test must not depend on what happens to be
    # installed in the interpreter running it.
    _PATH_ROOTS = ("", "core.")
    _MODULE_ALIASES = {}
    _FIRST_PARTY_HEADS = {"core", "gateway", "browser"}
    _THIRD_PARTY_HEADS = {"fastapi", "pydantic", "httpx"}
    _STDLIB_HEADS = {"json", "typing", "re", "ast", "os", "sys", "pathlib", "logging", "email"}


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
    rep.entrypoints_found = ["gateway.main"]
    rep.edges = [
        Edge("gateway.main", "core.lifespan", "import"),
        Edge("core.lifespan", "core.database.supabase_client", "import"),
        Edge("core.lifespan", "core.api.routes.mcp_hub", "string"),
    ]
    compute_reachability(rep)
    check("live importer judged unreachable", "core.database.supabase_client" in rep.reachable)
    check("dynamically mounted module judged unreachable", "core.api.routes.mcp_hub" in rep.reachable)
    check("orphan judged reachable", "core.orphan_module" in rep.unreachable)
    check(
        "test module counted as production dead code",
        "core.tests.test_x" not in rep.unreachable or _is_test_path(Path("core/tests/test_x.py")),
    )
    check("reachable module reported floating", "core.database.supabase_client" not in rep.floating)

    # 5b. Dangling-reference detection: a missing MODULE is reported, a missing
    # SYMBOL is not, and a hostname is never a module path.
    modules2 = {"core.lifespan": Path("core/lifespan.py"), "core": Path("core/__init__.py")}
    miss: List[str] = []
    extract_edges("core.lifespan", "from core.gone_module import Thing\n", modules2, miss, [])
    check("missing module not reported", "core.gone_module" in miss)

    miss2: List[str] = []
    extract_edges("core.lifespan", "from core import helper_symbol\n", modules2, miss2, [])
    check("imported symbol wrongly reported as missing module", miss2 == [])

    miss3: List[str] = []
    extract_edges("core.lifespan", "import json\nimport fastapi\n", modules2, miss3, [])
    check("stdlib/third-party import reported as missing", miss3 == [])

    check("hostname treated as a module path", not _is_dynamic_module_string("api.openai.com"))

    # 6. Determinism: same input, same bytes.
    first = build_json(rep)
    second = build_json(rep)
    check("output is not deterministic", json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True))

    # Always restore: callers (tests, guards, a shell script) may have their own
    # derived state in place, and this function must leave no trace.
    (
        _PATH_ROOTS,
        _MODULE_ALIASES,
        _FIRST_PARTY_HEADS,
        _THIRD_PARTY_HEADS,
        _STDLIB_HEADS,
    ) = saved_state

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
        print(f"scan roots (derived): {', '.join(report.scan_roots)}")
        print(f"path roots (derived): {len(report.path_roots)} prefix(es)")

        gaps = payload["gaps"]
        if gaps["dangling_references"]:
            print(f"\nDANGLING REFERENCES ({gaps['dangling_count']}) — module named but gone:")
            for ref in gaps["dangling_references"][:20]:
                print(f"  • {ref}")
        if gaps["unverified_references"]:
            print(
                f"\nUNVERIFIED references ({gaps['unverified_count']}) — dependency not "
                "installed here; cannot be checked statically, NOT a failure:"
            )
            for ref in gaps["unverified_references"][:5]:
                print(f"  • {ref}")
        if gaps["unresolved_services"]:
            print(f"\nUNRESOLVED SERVICES ({len(gaps['unresolved_services'])}):")
            for ref in gaps["unresolved_services"]:
                print(f"  • {ref}")
        if report.opaque_importers:
            print(
                f"\nopaque dynamic importers ({len(report.opaque_importers)}) "
                "— subtree treated as reachable, not dead:"
            )
            for name in report.opaque_importers[:8]:
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
        baseline = load_baseline()
        dangling = check_dangling(report, baseline)
        known = set((baseline or {}).get("known_dangling", []))
        still_broken = sorted(set(report.missing_refs) & known)
        if still_broken:
            print(f"\nKNOWN DEFECTS still present ({len(still_broken)}) — tracked, not new:")
            for ref in still_broken:
                print(f"  • {ref}")
        regressions = check_against_baseline(report, baseline)
        failed = False

        if dangling:
            failed = True
            print(f"\nFAIL: {len(dangling)} dangling reference(s) — a live import or")
            print("mount-table entry names a module that no longer exists:")
            for ref in dangling[:25]:
                print(f"  • {ref}")
            if len(dangling) > 25:
                print(f"  … and {len(dangling) - 25} more")

        if regressions:
            failed = True
            print(f"\nFAIL: {len(regressions)} module(s) became unreachable:")
            for name in regressions[:25]:
                print(f"  • {name}")

        if report.entrypoints_missing and not report.entrypoints_missing[0].startswith("WARNING"):
            failed = True
            print(f"\nFAIL: {len(report.entrypoints_missing)} declared service(s) whose")
            print("entrypoint maps to no real module:")
            for name in report.entrypoints_missing:
                print(f"  • {name}")

        if failed:
            return 1
        if still_broken:
            print(
                f"\nOK: no NEW dangling references and no new unreachable modules "
                f"({len(still_broken)} known defect(s) tracked above)"
            )
        else:
            print("\nOK: no dangling references, no new unreachable modules")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
