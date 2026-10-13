"""Core isolation regression guard — issue #126 (Phase-5 repo separation).

বাংলা: Phase0 বাউন্ডারি-ম্যাট্রিক্স (docs/architecture/PHASE0_BOUNDARY_CLASSIFICATION.md)
অনুযায়ী ``backend/core`` কে ``brain``/``adaptive_engine`` ছাড়া স্বয়ংসম্পূর্ণ
library হিসেবে চালানোর যোগ্যতা এই স্যুট মেশিন-প্রয়োগকৃতভাবে ধরে রাখে:

1. AST guard — ``backend/core``-এ কোনো **module-level** (function/if/try বাইরে)
   ``brain``/``adaptive_engine`` import নিষিদ্ধ। ভোগের জায়গায় lazy import
   (established "Domain adapter" idiom) অনুমোদিত।
2. Leaf-ness — ``core/contracts/boundaries.py`` শুধু stdlib/typing import করতে পারে।
3. Boot smoke — ``import backend.core`` রিপো-রুট থেকে সফল।
4. Extraction simulation — brain/adaptive_engine ব্লক করা meta_path finder দিয়ে
   আগে-কাপলড মডিউলগুলো import হয়; ``sys.modules``-এ cross-domain মডিউল আসে না।

Root-cause context (#126): ৯টি hard module-level import + ৩টি module-level
try-guarded import (একই defect-class) lazy-তে রূপান্তরিত — এই টেস্ট পুরো শ্রেণির
পুনরাবৃত্তি আটকায় (P6 poka-yoke)।
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = REPO_ROOT / "backend" / "core"
CONTRACTS_LEAF = CORE_DIR / "contracts" / "boundaries.py"

BANNED_PREFIXES = ("brain", "adaptive_engine")
STDLIB_TOPLEVELS = {
    "__future__", "abc", "annotations", "asyncio", "collections", "contextlib",
    "dataclasses", "datetime", "enum", "functools", "hashlib", "importlib",
    "itertools", "json", "logging", "math", "os", "pathlib", "re", "sqlite3",
    "string", "sys", "threading", "time", "typing", "types", "uuid", "warnings",
    "weakref",
}


def _module_name_of(node: ast.ImportFrom) -> str:
    return node.module or ""


def _is_banned(name: str) -> bool:
    return name == "brain" or name.startswith("brain.") or name == "adaptive_engine" or name.startswith("adaptive_engine.")


def _collect_module_level_violations(tree: ast.Module) -> list[str]:
    """Module-body-র direct children + try/if-wrapped (module-executed) import scan।"""
    found: list[str] = []

    def scan(stmts: list[ast.stmt]) -> None:
        for st in stmts:
            if isinstance(st, ast.Import):
                for alias in st.names:
                    if _is_banned(alias.name):
                        found.append(f"line {st.lineno}: import {alias.name}")
            elif isinstance(st, ast.ImportFrom):
                if _is_banned(_module_name_of(st)):
                    found.append(f"line {st.lineno}: from {st.module} import …")
            elif isinstance(st, (ast.Try, ast.If)):
                # module-level try/except (soft-fail import) ও import-time এ চলে — একই coupling
                scan(st.body)
                scan(st.orelse)
                scan(getattr(st, "finalbody", []))

    scan(tree.body)
    return found


class TestCoreIsolation:
    def test_no_module_level_brain_or_adaptive_engine_imports(self):
        """AST guard — backend/core-এ module-level cross-domain import শূন্য হতে হবে।"""
        violations: list[str] = []
        for py_file in sorted(CORE_DIR.rglob("*.py")):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue  # syntax-অসুস্থ ফাইল boot-smoke/compile গেটে ধরা পড়বে
            for v in _collect_module_level_violations(tree):
                violations.append(f"{py_file.relative_to(REPO_ROOT)}: {v}")
        assert not violations, "module-level brain/adaptive_engine import আছে:\n" + "\n".join(violations)

    def test_contracts_boundaries_is_stdlib_only_leaf(self):
        """contracts.boundaries — শুধু stdlib/typing import (leaf চুক্তি)।"""
        tree = ast.parse(CONTRACTS_LEAF.read_text(encoding="utf-8"))
        bad: list[str] = []
        for st in ast.walk(tree):
            if isinstance(st, ast.Import):
                for alias in st.names:
                    top = alias.name.split(".")[0]
                    if top not in STDLIB_TOPLEVELS:
                        bad.append(f"line {st.lineno}: import {alias.name}")
            elif isinstance(st, ast.ImportFrom):
                top = (st.module or "").split(".")[0]
                if top and top not in STDLIB_TOPLEVELS:
                    bad.append(f"line {st.lineno}: from {st.module} import …")
        assert not bad, "boundaries.py leaf-চুক্তি ভাঙছে:\n" + "\n".join(bad)

    def test_boundaries_protocols_exist(self):
        """চুক্তি-Protocol গুলো সংজ্ঞায়িত ও runtime-checkable।"""
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        try:
            from core.contracts import boundaries as b

            for name in (
                "ModelRoutingContract",
                "ReasoningOrchestrationContract",
                "AutonomousAgentContract",
                "ModelRegistryContract",
            ):
                assert hasattr(b, name), f"contracts.boundaries.{name} নেই"
        finally:
            sys.path.remove(str(REPO_ROOT / "backend"))

    def test_boot_smoke_import_backend_core(self):
        """Boot smoke — রিপো-রুট থেকে ``import backend.core`` সফল (issue চুক্তি §2)।"""
        res = subprocess.run(
            [sys.executable, "-c", "import backend.core; print('Core boot passed')"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert res.returncode == 0, f"boot smoke ব্যর্থ:\n{res.stderr[-2000:]}"
        assert "Core boot passed" in res.stdout

    def test_extraction_simulation_imports_without_brain_or_adaptive(self):
        """Extraction simulation — brain/adaptive_engine ব্লক করা অবস্থায় আগে-কাপলড
        core মডিউলগুলো import হয় এবং cross-domain মডিউল sys.modules-এ ঢোকে না।"""
        script = (
            "import sys, importlib.abc\n"
            "class _Blocker(importlib.abc.MetaPathFinder):\n"
            "    def find_spec(self, fullname, path=None, target=None):\n"
            "        if fullname.split('.')[0] in ('brain', 'adaptive_engine'):\n"
            "            raise ImportError(f'{fullname} blocked (extraction simulation)')\n"
            "        return None\n"
            "sys.meta_path.insert(0, _Blocker())\n"
            "import core.performance_enhancer\n"
            "import core.cache.semantic_cache\n"
            "import core.connection_registry\n"
            "import core.self_evolution.evolution_engine\n"
            "import core.agents.framework.crewai_agents\n"
            "import core.localization.bhasha_bot\n"
            "leaked = [m for m in sys.modules if m.split('.')[0] in ('brain', 'adaptive_engine')]\n"
            "assert not leaked, f'cross-domain modules leaked: {leaked}'\n"
            "print('ISOLATION OK')\n"
        )
        res = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(REPO_ROOT / "backend"),
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert res.returncode == 0, f"isolation simulation ব্যর্থ:\n{res.stderr[-2000:]}"
        assert "ISOLATION OK" in res.stdout
