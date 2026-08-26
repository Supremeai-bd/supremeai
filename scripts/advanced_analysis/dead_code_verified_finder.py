#!/usr/bin/env python3
"""SupremeAI ডেড কোড ভেরিফাইড ফাইন্ডার

বাংলা: এই স্ক্রিপ্ট backend/ এর সব Python ফাইলের import গ্রাফ তৈরি করে,
entry point থেকে BFS দিয়ে রিচেবিলিটি যাচাই করে, এবং
কঠোর বিশ্লেষণের মাধ্যমে ডেড কোড শনাক্ত করে।

Exit codes:
  0 = পরিষ্কার (ডেড কোড নেই)
  1 = ডেড কোড পাওয়া গেছে
  2 = ত্রুটি ঘটেছে

Usage:
  python dead_code_verified_finder.py
  python dead_code_verified_finder.py --json
  python dead_code_verified_finder.py --include-tests
  python dead_code_verified_finder.py --package agents
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
import tomllib
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TextIO


# ============================================================================
# ধ্রুবক এবং কনফিগারেশন
# ============================================================================

# বাংলা: রিপো রুট এবং backend পাথ স্বয়ংক্রিয়ভাবে নির্ধারণ করা হয়
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"

# বাংলা: জানা entry point ফাইলগুলো (রুট মডিউল যেগুলো কেউ import করে না)
KNOWN_ENTRY_POINTS: set[str] = {
    "main.py",
    "core/app.py",
    "core/app_builder.py",
    "api/routers.py",
    "api/server.py",
    "seed_db_configs.py",
    "analyze_coverage.py",
}

# বাংলা: সবসময় entry point হিসেবে বিবেচিত __init__.py ফাইলের প্যাটার্ন
INIT_ENTRY_PATTERNS: list[str] = [
    "api/__init__.py",
    "api/routes/__init__.py",
    "core/__init__.py",
    "models/__init__.py",
    "services/__init__.py",
    "agents/__init__.py",
    "tools/__init__.py",
    "brain/__init__.py",
    "ws/__init__.py",
    "monitoring/__init__.py",
    "adaptive_engine/__init__.py",
    "learning/__init__.py",
    "evolution/__init__.py",
    "p2p/__init__.py",
    "scout/__init__.py",
    "utils/__init__.py",
    "middleware/__init__.py",
    "integrations/__init__.py",
    "scaling/__init__.py",
    "engine/__init__.py",
    "config/__init__.py",
    "workers/__init__.py",
    "pipelines/__init__.py",
    "pyerrorfix/__init__.py",
    "reports/__init__.py",
    "admin/__init__.py",
]

# বাংলা: প্রোডাকশন প্যাকেজের তালিকা (test/ বাদ দেওয়ার জন্য)
PRODUCTION_PACKAGES: set[str] = {
    "api", "core", "models", "services", "agents", "tools", "brain",
    "ws", "monitoring", "adaptive_engine", "learning", "evolution",
    "p2p", "scout", "utils", "middleware", "integrations", "scaling",
    "engine", "config", "workers", "pipelines", "pyerrorfix", "reports",
    "admin", "alembic_migrations",
}

# বাংলা: রাউটার রেজিস্ট্রেশন ফাইল থেকে খুঁজে বের করার জন্য প্যাটার্ন
ROUTER_REGISTRY_FILES: set[str] = {
    "api/routers.py",
    "core/app.py",
    "core/app_builder.py",
}


class ModuleStatus(str, Enum):
    """বাংলা: মডিউলের স্ট্যাটাস ক্লাসিফিকেশন"""
    ALIVE = "ALIVE"                 # 🟢 সঠিকভাবে import করা হয়েছে এবং ব্যবহৃত
    ENTRY_POINT = "ENTRY_POINT"     # 🔵 entry point — কেউ import করে না কিন্তু এটা প্রত্যাশিত
    BARELY_ALIVE = "BARELY_ALIVE"   # 🟡 শুধু টেস্টে ব্যবহৃত, প্রোডাকশনে না
    DEAD = "DEAD"                   # 🔴 কেউ ব্যবহার করে না, কোনো entry point না


@dataclass
class ModuleInfo:
    """বাংলা: প্রতিটি মডিউলের বিশদ তথ্য"""
    rel_path: str                           # backend/ থেকে relative path
    imports: set[str] = field(default_factory=set)  # এই মডিউল যেসব মডিউল import করে
    imported_by: set[str] = field(default_factory=set)  # কারা এই মডিউল import করে
    test_imported_by: set[str] = field(default_factory=set)  # কোন টেস্ট ফাইল import করে
    defines_all: bool = False               # __all__ ডিফাইন করে কিনা
    all_exports: list[str] = field(default_factory=list)  # __all__ এর সদস্য
    classes: list[str] = field(default_factory=list)      # ডিফাইন করা class
    functions: list[str] = field(default_factory=list)    # ডিফাইন করা top-level function
    status: ModuleStatus = ModuleStatus.DEAD
    reachable: bool = False
    is_test_file: bool = False
    is_entry_point: bool = False
    referenced_in_config: bool = False
    referenced_in_routers: bool = False


class ImportVisitor(ast.NodeVisitor):
    """বাংলা: AST visitor যা import স্টেটমেন্ট সংগ্রহ করে"""

    def __init__(self) -> None:
        self.imports: list[tuple[str, str | None]] = []  # (module, name_or_None)
        self.has_all: bool = False
        self.all_names: list[str] = []
        self.classes: list[str] = []
        self.functions: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((alias.name, alias.asname))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            for alias in node.names:
                self.imports.append((node.module, alias.name))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # বাংলা: __all__ ডিফিনিশন খুঁজে বের করা
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                self.has_all = True
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            self.all_names.append(elt.value)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # বাংলা: শুধু top-level function, nested না
        self.functions.append(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.functions.append(node.name)


class DeadCodeFinder:
    """বাংলা: মূল ডেড কোড ফাইন্ডার ক্লাস

    এই ক্লাস পুরো backend/ ডিরেক্টরি স্ক্যান করে import গ্রাফ তৈরি করে,
    entry point থেকে রিচেবিলিটি ট্রেস করে, এবং ক্লাসিফিকেশন করে।
    """

    def __init__(
        self,
        backend_dir: Path = BACKEND_DIR,
        include_tests: bool = False,
        package_filter: str | None = None,
    ) -> None:
        self.backend_dir = backend_dir
        self.include_tests = include_tests
        self.package_filter = package_filter

        # বাংলা: সব মডিউলের তথ্য — key হলো relative path (backend/ থেকে)
        self.modules: dict[str, ModuleInfo] = {}
        # বাংলা: import গ্রাফ — module -> set of imported module dots
        self.import_graph: dict[str, set[str]] = defaultdict(set)
        # বাংলা: reverse import গ্রাফ — module -> set of importers
        self.reverse_graph: dict[str, set[str]] = defaultdict(set)
        # বাংলা: entry points
        self.entry_points: set[str] = set()
        # বাংলা: ফাইল পাথ থেকে মডিউল নামের ম্যাপিং
        self.path_to_module: dict[str, str] = {}
        # বাংলা: মডিউল নাম থেকে ফাইল পাথের ম্যাপিং (একাধিক হতে পারে)
        self.module_to_paths: dict[str, list[str]] = defaultdict(list)

    # ------------------------------------------------------------------
    # পর্যায় ১: সব Python ফাইল খুঁজে বের করা
    # ------------------------------------------------------------------
    def _discover_files(self) -> list[Path]:
        """বাংলা: backend/ এর মধ্যে সব .py ফাইল খুঁজে বের করা"""
        py_files: list[Path] = []
        for root, _dirs, files in os.walk(self.backend_dir):
            root_path = Path(root)
            for f in files:
                if not f.endswith(".py"):
                    continue
                # বাংলা: __pycache__ এবং .venv বাদ দেওয়া
                if "__pycache__" in root_path.parts or ".venv" in root_path.parts:
                    continue
                # বাংলা: প্যাকেজ ফিল্টার থাকলে সেটা প্রয়োগ
                if self.package_filter:
                    rel = root_path.relative_to(self.backend_dir)
                    if rel.parts and rel.parts[0] != self.package_filter:
                        continue
                py_files.append(root_path / f)
        return sorted(py_files)

    # ------------------------------------------------------------------
    # পর্যায় ২: ফাইল পাথ থেকে মডিউল ডট-নোটেশন তৈরি
    # ------------------------------------------------------------------
    def _path_to_module_name(self, filepath: Path) -> str:
        """বাংলা: backend/core/config.py -> core.config"""
        try:
            rel = filepath.relative_to(self.backend_dir)
        except ValueError:
            return filepath.stem
        parts = list(rel.parts)
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        if parts[-1] == "__init__":
            parts = parts[:-1]
            if not parts:
                return ""
        return ".".join(parts)

    # ------------------------------------------------------------------
    # পর্যায় ৩: একটি ফাইল parse করে import ও ডিফিনিশন সংগ্রহ
    # ------------------------------------------------------------------
    def _parse_file(self, filepath: Path) -> ImportVisitor:
        """বাংলা: AST দিয়ে ফাইল parse করে import visitor রিটার্ন করা"""
        visitor = ImportVisitor()
        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(filepath))
            visitor.visit(tree)
        except (SyntaxError, ValueError, OSError) as exc:
            # বাংলা: syntax error থাকলে শুধু আউটপুটে সতর্কতা দেখাবো, থামাবো না
            print(f"  ⚠️  Parse ত্রুটি: {filepath}: {exc}", file=sys.stderr)
        return visitor

    # ------------------------------------------------------------------
    # পর্যায় ৪: import গ্রাফ তৈরি
    # ------------------------------------------------------------------
    def build_import_graph(self) -> None:
        """বাংলা: সব .py ফাইল থেকে import গ্রাফ তৈরি করা"""
        print("📋 ধাপ ১: সব Python ফাইল স্ক্যান করা হচ্ছে...", file=sys.stderr)
        py_files = self._discover_files()
        print(f"   {len(py_files)} টি ফাইল পাওয়া গেছে", file=sys.stderr)

        # বাংলা: প্রথমে সব ফাইলের মডিউল নাম রেজিস্টার করা
        for fp in py_files:
            rel = str(fp.relative_to(self.backend_dir))
            mod_name = self._path_to_module_name(fp)
            is_test = "/tests/" in rel or rel.startswith("tests/")

            info = ModuleInfo(rel_path=rel, is_test_file=is_test)
            self.modules[rel] = info

            if mod_name:
                self.path_to_module[rel] = mod_name
                self.module_to_paths[mod_name].append(rel)

        # বাংলা: এখন প্রতিটি ফাইলের import parse করা
        print("📋 ধাপ ২: import স্টেটমেন্ট parse করা হচ্ছে...", file=sys.stderr)
        parse_errors = 0
        for fp in py_files:
            rel = str(fp.relative_to(self.backend_dir))
            visitor = self._parse_file(fp)
            info = self.modules[rel]

            info.defines_all = visitor.has_all
            info.all_exports = visitor.all_names
            info.classes = visitor.classes
            info.functions = visitor.functions

            for mod_imported, name in visitor.imports:
                # বাংলা: শুধু অভ্যন্তরীণ (backend/) import ট্র্যাক
                resolved = self._resolve_import(mod_imported, name, rel)
                if resolved:
                    info.imports.add(resolved)
                    self.import_graph[rel].add(resolved)

        # বাংলা: reverse graph তৈরি
        for src, targets in self.import_graph.items():
            for tgt in targets:
                self.reverse_graph[tgt].add(src)
                src_info = self.modules.get(src)
                tgt_info = self.modules.get(tgt)
                if src_info and tgt_info:
                    if src_info.is_test_file:
                        tgt_info.test_imported_by.add(src)
                    else:
                        tgt_info.imported_by.add(src)

        print(f"   Import গ্রাফ তৈরি সম্পন্ন ({parse_errors} টি parse ত্রুটি)", file=sys.stderr)

    def _resolve_import(
        self, module: str, name: str | None, source_rel: str
    ) -> str | None:
        """বাংলা: import স্টেটমেন্টকে backend/ relative path-এ রেজোলভ করা

        'from core.config import settings' -> 'core/config.py' বা 'core/config/__init__.py'
        'import api.routes' -> 'api/routes.py' বা 'api/routes/__init__.py'
        """
        # বাংলা: stdlib এবং তৃতীয় পক্ষের প্যাকেজ বাদ দেওয়া
        if module.split(".")[0] in PRODUCTION_PACKAGES or self._is_internal_module(module):
            pass
        else:
            return None

        # বাংলা: সরাসরি মডিউল ম্যাচিং চেষ্টা
        # from core.config import settings -> core.config (মডিউল) + name=settings
        candidate = self._module_to_path(module)
        if candidate:
            return candidate

        # বাংলা: 'from core.config.settings import X' হলে core/config/settings.py খুঁজো
        if name and not module.endswith("."):
            full_mod = f"{module}.{name}" if name else module
            candidate = self._module_to_path(full_mod)
            if candidate:
                return candidate

        # বাংলা: প্যারেন্ট মডিউল চেষ্টা (e.g. core.config.settings -> core.config)
        parts = module.rsplit(".", 1)
        if len(parts) > 1:
            candidate = self._module_to_path(parts[0])
            if candidate:
                return candidate

        return None

    def _is_internal_module(self, module: str) -> bool:
        """বাংলা: মডিউলটি backend/ এর ভিতরের কিনা চেক করা"""
        top = module.split(".")[0]
        # বাংলা: যদি কোনো ফাইলের মডিউল নামের সাথে মেলে
        return any(p.startswith(top + ".") or p == top for p in self.path_to_module.values())

    def _module_to_path(self, module: str) -> str | None:
        """বাংলা: মডিউল ডট-নোটেশনকে ফাইল relative path-এ রূপান্তর"""
        # বাংলা: সরাসরি ম্যাচ
        if module in self.module_to_paths:
            paths = self.module_to_paths[module]
            # বাংলা: __init__.py কে প্রাধান্য দেওয়া
            for p in paths:
                if p.endswith("__init__.py"):
                    return p
            return paths[0]

        # বাংলা: .py এক্সটেনশন সহ চেষ্টা (e.g. core.config -> core/config.py)
        py_path = module.replace(".", "/") + ".py"
        if py_path in self.modules:
            return py_path

        # বাংলা: __init__.py হিসেবে চেষ্টা (e.g. core.config -> core/config/__init__.py)
        init_path = module.replace(".", "/") + "/__init__.py"
        if init_path in self.modules:
            return init_path

        return None

    # ------------------------------------------------------------------
    # পর্যায় ৫: Entry points সনাক্তকরণ
    # ------------------------------------------------------------------
    def find_entry_points(self) -> None:
        """বাংলা: সব entry point সনাক্ত করা — জানা, conftest, config, router registry"""
        print("📋 ধাপ ৩: Entry points সনাক্ত করা হচ্ছে...", file=sys.stderr)

        # ১. বাংলা: পূর্বনির্ধারিত জানা entry points
        for ep in KNOWN_ENTRY_POINTS:
            if ep in self.modules:
                self.entry_points.add(ep)
                self.modules[ep].is_entry_point = True

        # ২. বাংলা: __init__.py entry points (re-export করে এমন)
        for init_pat in INIT_ENTRY_PATTERNS:
            if init_pat in self.modules:
                info = self.modules[init_pat]
                # বাংলা: শুধুমাত্র যেগুলো __all__ বা re-export করে
                if info.defines_all or info.imports:
                    self.entry_points.add(init_pat)
                    info.is_entry_point = True

        # ৩. বাংলা: conftest.py থেকে রেফারেন্স করা মডিউল
        for rel, info in self.modules.items():
            if rel.endswith("conftest.py"):
                self.entry_points.add(rel)
                info.is_entry_point = True
                # বাংলা: conftest যেসব মডিউল import করে সেগুলোও entry point
                for imp in info.imports:
                    if imp in self.modules:
                        self.modules[imp].referenced_in_config = True

        # ৪. বাংলা: pyproject.toml থেকে scripts এবং রেফারেন্স
        self._parse_pyproject_toml()

        # ৫. বাংলা: Router registry থেকে রেফারেন্স করা মডিউল
        self._parse_router_registries()

        # ৬. বাংলা: যেকোনো __init__.py যা re-export করে (top-level import আছে)
        for rel, info in self.modules.items():
            if rel.endswith("__init__.py") and info.imports:
                # বাংলা: __init__.py থেকে করা import মানে re-export
                if not info.is_entry_point:
                    # বাংলা: শুধু যেগুলোতে significant import আছে
                    non_test_imports = {
                        i for i in info.imports
                        if not self.modules.get(i, ModuleInfo("")).is_test_file
                    }
                    if non_test_imports:
                        self.entry_points.add(rel)
                        info.is_entry_point = True

        print(f"   {len(self.entry_points)} টি entry point পাওয়া গেছে", file=sys.stderr)

    def _parse_pyproject_toml(self) -> None:
        """বাংলা: pyproject.toml থেকে স্ক্রিপ্ট ও রেফারেন্স বের করা"""
        toml_path = self.backend_dir / "pyproject.toml"
        if not toml_path.exists():
            return
        try:
            content = toml_path.read_text(encoding="utf-8")
            data = tomllib.loads(content)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            print(f"  ⚠️  pyproject.toml parse ত্রুটি: {exc}", file=sys.stderr)
            return

        # বাংলা: [tool.poetry.scripts] বা [project.scripts] থেকে রেফারেন্স
        scripts = (
            data.get("tool", {}).get("poetry", {}).get("scripts", {})
        )
        scripts.update(data.get("project", {}).get("scripts", {}))

        for _script_name, module_ref in scripts.items():
            # বাংলা: "module:function" ফরম্যাট
            mod_part = module_ref.split(":")[0] if ":" in module_ref else module_ref
            resolved = self._module_to_path(mod_part)
            if resolved and resolved in self.modules:
                self.entry_points.add(resolved)
                self.modules[resolved].is_entry_point = True
                self.modules[resolved].referenced_in_config = True

        # বাংলা: সম্পূর্ণ toml ফাইলে মডিউল রেফারেন্স খোঁজা (স্ট্রিং ম্যাচিং)
        toml_str = content
        for mod_name, paths in self.module_to_paths.items():
            if mod_name in toml_str:
                for p in paths:
                    if p in self.modules:
                        self.modules[p].referenced_in_config = True

    def _parse_router_registries(self) -> None:
        """বাংলা: Router registry ফাইল থেকে রেফারেন্স করা মডিউল বের করা

        api/routers.py-এর ALL_ROUTERS লিস্টে যেসব মডিউলের পথ আছে
        সেগুলো entry point হিসেবে চিহ্নিত করা হয়।
        """
        for registry_rel in ROUTER_REGISTRY_FILES:
            if registry_rel not in self.modules:
                continue
            info = self.modules[registry_rel]
            for imp_rel in info.imports:
                if imp_rel in self.modules:
                    self.modules[imp_rel].referenced_in_routers = True

        # বাংলা: অতিরিক্তভাবে router registry ফাইলে স্ট্রিং লিটারেল হিসেবে
        # থাকা মডিউল পাথ (e.g. "api.routes.chat") খোঁজা
        for registry_rel in ROUTER_REGISTRY_FILES:
            if registry_rel not in self.modules:
                continue
            fp = self.backend_dir / registry_rel
            if not fp.exists():
                continue
            try:
                source = fp.read_text(encoding="utf-8")
            except OSError:
                continue
            for mod_name, paths in self.module_to_paths.items():
                # বাংলা: স্ট্রিং লিটারেলে মডিউল রেফারেন্স আছে কিনা
                pattern = f'"{mod_name}"'
                if pattern in source or f"'{mod_name}'" in source:
                    for p in paths:
                        if p in self.modules:
                            self.modules[p].referenced_in_routers = True

    # ------------------------------------------------------------------
    # পর্যায় ৬: রিচেবিলিটি ট্রেস (BFS)
    # ------------------------------------------------------------------
    def trace_reachability(self) -> None:
        """বাংলা: Entry points থেকে BFS দিয়ে সব পৌঁছানোযোগ্য মডিউল চিহ্নিত করা"""
        print("📋 ধাপ ৪: রিচেবিলিটি ট্রেস (BFS)...", file=sys.stderr)

        visited: set[str] = set()
        queue: deque[str] = deque()

        # বাংলা: শুধু প্রোডাকশন entry points থেকে শুরু (টেস্ট ফাইল বাদ)
        for ep in self.entry_points:
            ep_info = self.modules.get(ep)
            if ep_info and not ep_info.is_test_file:
                if ep not in visited:
                    queue.append(ep)
                    visited.add(ep)

        while queue:
            current = queue.popleft()
            self.modules[current].reachable = True

            for neighbor in self.import_graph.get(current, set()):
                if neighbor not in visited and neighbor in self.modules:
                    # বাংলা: include_tests ফ্ল্যাগ অনুযায়ী টেস্ট মডিউল যোগ
                    neighbor_info = self.modules[neighbor]
                    if self.include_tests or not neighbor_info.is_test_file:
                        visited.add(neighbor)
                        queue.append(neighbor)

        reachable_count = sum(1 for m in self.modules.values() if m.reachable)
        total = len(self.modules)
        print(f"   {reachable_count}/{total} টি মডিউল পৌঁছানোযোগ্য", file=sys.stderr)

    # ------------------------------------------------------------------
    # পর্যায় ৭: ক্লাসিফিকেশন
    # ------------------------------------------------------------------
    def classify_modules(self) -> None:
        """বাংলা: প্রতিটি মডিউল ক্লাসিফাই করা — DEAD/BARELY_ALIVE/ENTRY_POINT/ALIVE"""
        print("📋 ধাপ ৫: মডিউল ক্লাসিফিকেশন...", file=sys.stderr)

        for rel, info in self.modules.items():
            # বাংলা: টেস্ট ফাইল সবসময় ALIVE (এগুলো বিশ্লেষণের বাইরে)
            if info.is_test_file:
                info.status = ModuleStatus.ALIVE
                continue

            # বাংলা: Entry point চেক
            if info.is_entry_point:
                info.status = ModuleStatus.ENTRY_POINT
                continue

            # বাংলা: রিচেবল (প্রোডাকশন কোড থেকে import করা হয়েছে)
            prod_importers = info.imported_by - {
                r for r in info.imported_by if self.modules.get(r, ModuleInfo("")).is_test_file
            }

            if info.reachable and prod_importers:
                info.status = ModuleStatus.ALIVE
                continue

            # বাংলা: শুধু টেস্টে import করা হয়েছে (BARELY_ALIVE)
            if info.test_imported_by and not prod_importers and not info.referenced_in_routers:
                info.status = ModuleStatus.BARELY_ALIVE
                continue

            # বাংলা: config/registry তে রেফারেন্স আছে
            if info.referenced_in_config or info.referenced_in_routers:
                info.status = ModuleStatus.ENTRY_POINT
                continue

            # বাংলা: __all__ দিয়ে re-export হচ্ছে কিনা চেক
            if info.defines_all and self._is_reexported_via_all(rel):
                info.status = ModuleStatus.ALIVE
                continue

            # বাংলা: কেউ কিছুই import করে না — DEAD
            if not info.imported_by and not info.test_imported_by:
                info.status = ModuleStatus.DEAD
                continue

            # বাংলা: reachable কিন্তু শুধু test থেকে
            if info.reachable and info.test_imported_by and not prod_importers:
                if self.include_tests:
                    info.status = ModuleStatus.ALIVE
                else:
                    info.status = ModuleStatus.BARELY_ALIVE
                continue

            # বাংলা: ডিফল্ট — reachable হলে ALIVE, না হলে DEAD
            info.status = ModuleStatus.ALIVE if info.reachable else ModuleStatus.DEAD

    def _is_reexported_via_all(self, rel: str) -> bool:
        """বাংলা: কোনো __init__.py এর __all__-এ এই মডিউলের কিছু আছে কিনা"""
        mod_name = self.path_to_module.get(rel, "")
        if not mod_name:
            return False
        # বাংলা: শেষের অংশ (class/function name)
        last_part = mod_name.rsplit(".", 1)[-1] if "." in mod_name else mod_name

        for other_rel, other_info in self.modules.items():
            if not other_rel.endswith("__init__.py") or not other_info.defines_all:
                continue
            if last_part in other_info.all_exports:
                return True
        return False

    # ------------------------------------------------------------------
    # পর্যায় ৮: রিপোর্ট তৈরি
    # ------------------------------------------------------------------
    def generate_markdown_report(self, out: TextIO = sys.stdout) -> None:
        """বাংলা: কাঠামোবদ্ধ Markdown রিপোর্ট তৈরি করা"""
        dead = [m for m in self.modules.values() if m.status == ModuleStatus.DEAD]
        barely = [m for m in self.modules.values() if m.status == ModuleStatus.BARELY_ALIVE]
        entry = [m for m in self.modules.values() if m.status == ModuleStatus.ENTRY_POINT]
        alive = [m for m in self.modules.values() if m.status == ModuleStatus.ALIVE]

        out.write("# 🔍 SupremeAI ডেড কোড ভেরিফায়েড রিপোর্ট\n\n")
        out.write(f"**স্ক্যান সময়**: {self._now_iso()}\n")
        out.write(f"**মোট মডিউল**: {len(self.modules)}\n")
        out.write(f"**ফিল্টার**: `{self.package_filter or 'সব'}`\n")
        out.write(f"**টেস্ট অন্তর্ভুক্ত**: {'হ্যাঁ' if self.include_tests else 'না'}\n\n")

        # বাংলা: সারসংক্ষেপ টেবিল
        out.write("## 📊 সারসংক্ষেপ\n\n")
        out.write("| স্ট্যাটাস | আইকন | সংখ্যা | শতাংশ |\n")
        out.write("|---------|-------|--------|--------|\n")
        total = len(self.modules)
        for label, icon, count in [
            ("ALIVE", "🟢", len(alive)),
            ("ENTRY_POINT", "🔵", len(entry)),
            ("BARELY_ALIVE", "🟡", len(barely)),
            ("DEAD", "🔴", len(dead)),
        ]:
            pct = f"{count / total * 100:.1f}%" if total else "0%"
            out.write(f"| {label} | {icon} | {count} | {pct} |\n")
        out.write("\n")

        # বাংলা: 🔴 DEAD মডিউল
        if dead:
            out.write(f"## 🔴 DEAD মডিউল ({len(dead)})\n\n")
            out.write("এগুলো কোনো মডিউলে import হয় না, entry point না, টেস্টেও ব্যবহৃত নয়।\n\n")
            for info in sorted(dead, key=lambda m: m.rel_path):
                self._write_module_detail(out, info, "🔴")
            out.write("\n")

        # বাংলা: 🟡 BARELY ALIVE মডিউল
        if barely:
            out.write(f"## 🟡 BARELY ALIVE মডিউল ({len(barely)})\n\n")
            out.write("এগুলো শুধু টেস্টে ব্যবহৃত, প্রোডাকশন কোডে কোথাও import হয় না।\n\n")
            for info in sorted(barely, key=lambda m: m.rel_path):
                self._write_module_detail(out, info, "🟡")
            out.write("\n")

        # বাংলা: 🔵 ENTRY POINT মডিউল (সংক্ষেপে)
        if entry:
            out.write(f"## 🔵 ENTRY POINT মডিউল ({len(entry)})\n\n")
            out.write("এগুলো entry point — কেউ import করে না কিন্তু প্রত্যাশিত।\n\n")
            out.write("| পাথ | ধরন |\n")
            out.write("|------|------|\n")
            for info in sorted(entry, key=lambda m: m.rel_path):
                ep_type = "__init__" if info.rel_path.endswith("__init__.py") else "script"
                if info.rel_path in KNOWN_ENTRY_POINTS:
                    ep_type = "known"
                if info.referenced_in_routers:
                    ep_type = "router-ref"
                if info.referenced_in_config:
                    ep_type = "config-ref"
                out.write(f"| `{info.rel_path}` | {ep_type} |\n")
            out.write("\n")

        # বাংলা: 🟢 ALIVE সংক্ষেপ
        out.write(f"## 🟢 ALIVE মডিউল ({len(alive)})\n\n")
        out.write(f"সঠিকভাবে ব্যবহৃত মডিউল সংখ্যা: **{len(alive)}**\n\n")

    def _write_module_detail(self, out: TextIO, info: ModuleInfo, icon: str) -> None:
        """বাংলা: একটি মডিউলের বিশদ তথ্য লেখা"""
        out.write(f"### {icon} `{info.rel_path}`\n\n")

        # বাংলা: যদি import করে তার তালিকা
        if info.imported_by:
            importers = ", ".join(f"`{i}`" for i in sorted(info.imported_by)[:5])
            out.write(f"- **Import করে**: {importers}\n")

        # বাংলা: টেস্টে import করলে
        if info.test_imported_by:
            testers = ", ".join(f"`{t}`" for t in sorted(info.test_imported_by)[:5])
            out.write(f"- **টেস্টে import**: {testers}\n")

        # বাংলা: __all__ থাকলে
        if info.defines_all:
            out.write(f"- **__all__**: {info.all_exports[:10]}\n")

        # বাংলা: ডিফাইন করা class ও function
        items: list[str] = []
        for cls in info.classes:
            items.append(f"class `{cls}`")
        for func in info.functions:
            if func.startswith("_") and not func.startswith("__"):
                continue  # বাংলা: private helper বাদ
            items.append(f"def `{func}()`")

        if items:
            out.write(f"- **সদস্য**: {', '.join(items[:15])}\n")
        else:
            out.write("- **সদস্য**: (কোনো public class/function নেই)\n")

        out.write("\n")

    def generate_json_report(self, out: TextIO = sys.stdout) -> None:
        """বাংলা: JSON ফরম্যাটে রিপোর্ট তৈরি"""
        result: dict[str, Any] = {
            "timestamp": self._now_iso(),
            "total_modules": len(self.modules),
            "package_filter": self.package_filter,
            "include_tests": self.include_tests,
            "summary": {
                "alive": 0,
                "entry_point": 0,
                "barely_alive": 0,
                "dead": 0,
            },
            "modules": [],
        }

        for rel, info in sorted(self.modules.items()):
            status = info.status.value
            result["summary"][{
                ModuleStatus.ALIVE: "alive",
                ModuleStatus.ENTRY_POINT: "entry_point",
                ModuleStatus.BARELY_ALIVE: "barely_alive",
                ModuleStatus.DEAD: "dead",
            }[info.status]] += 1

            mod_data: dict[str, Any] = {
                "path": rel,
                "status": status,
                "is_test": info.is_test_file,
                "is_entry_point": info.is_entry_point,
                "reachable": info.reachable,
                "imported_by": sorted(info.imported_by),
                "test_imported_by": sorted(info.test_imported_by),
                "classes": info.classes,
                "functions": info.functions,
                "defines_all": info.defines_all,
                "all_exports": info.all_exports,
                "referenced_in_config": info.referenced_in_config,
                "referenced_in_routers": info.referenced_in_routers,
            }
            result["modules"].append(mod_data)

        json.dump(result, out, indent=2, ensure_ascii=False)
        out.write("\n")

    @staticmethod
    def _now_iso() -> str:
        """বাংলা: বর্তমান সময় ISO ফরম্যাটে"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # মূল রান মেথড
    # ------------------------------------------------------------------
    def run(self) -> int:
        """বাংলা: সম্পূর্ণ বিশ্লেষণ চালানো এবং exit code রিটার্ন করা"""
        try:
            self.build_import_graph()
            self.find_entry_points()
            self.trace_reachability()
            self.classify_modules()
        except Exception as exc:
            print(f"\n❌ ত্রুটি ঘটেছে: {exc}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return 2

        # বাংলা: রিপোর্ট আউটপুট
        dead_count = sum(
            1 for m in self.modules.values()
            if m.status == ModuleStatus.DEAD
        )

        if self._json_mode:
            self.generate_json_report()
        else:
            self.generate_markdown_report()

        # বাংলা: exit code
        if dead_count > 0:
            print(
                f"\n⚠️  {dead_count} টি ডেড মডিউল পাওয়া গেছে (exit code=1)",
                file=sys.stderr,
            )
            return 1
        else:
            print("\n✅ কোনো ডেড কোড নেই (exit code=0)", file=sys.stderr)
            return 0

    _json_mode: bool = False


def _print_usage() -> None:
    """বাংলা: ব্যবহার নির্দেশনা প্রিন্ট করা"""
    print(
        """ব্যবহার: dead_code_verified_finder.py [অপশন]

অপশন:
  --json             JSON ফরম্যাটে আউটপুট
  --include-tests    টেস্ট import-কে ALIVE হিসেবে গণনা
  --package PKG      নির্দিষ্ট প্যাকেজ বিশ্লেষণ (যেমন: agents, core)
  --help, -h         এই সাহায্য বার্তা""",
        file=sys.stderr,
    )


def main() -> int:
    """বাংলা: CLI এন্ট্রি পয়েন্ট"""
    include_tests = False
    json_mode = False
    package_filter: str | None = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--json",):
            json_mode = True
        elif arg in ("--include-tests",):
            include_tests = True
        elif arg in ("--package",) and i + 1 < len(args):
            i += 1
            package_filter = args[i]
        elif arg in ("--help", "-h"):
            _print_usage()
            return 0
        elif arg.startswith("-"):
            print(f"❌ অজানা অপশন: {arg}", file=sys.stderr)
            _print_usage()
            return 2
        i += 1

    finder = DeadCodeFinder(
        backend_dir=BACKEND_DIR,
        include_tests=include_tests,
        package_filter=package_filter,
    )
    finder._json_mode = json_mode
    return finder.run()


if __name__ == "__main__":
    sys.exit(main())
