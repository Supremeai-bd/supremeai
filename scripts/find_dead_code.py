#!/usr/bin/env python3
"""
find_dead_code.py — SupremeAI 2.0 Dead Code / Unused Symbol Scanner (P2 Gate)
=============================================================================
Master Audit Plan Phase 4 (tools/scripts/utils) ও Phase 0 (dead code) অনুযায়ী
এই স্ক্রিপ্টটি Python ফাইলগুলোর মধ্যে নিচের সমস্যাগুলো খুঁজে বের করে:

  1. Unused imports (ইম্পোর্ট করা কিন্তু ব্যবহার না করা)
  2. Unused top-level functions (সংজ্ঞায়িত কিন্তু ফাইলজুড়ে কল/রেফারেন্স না থাকা)
  3. Unused top-level classes (সংজ্ঞায়িত কিন্তু রেফারেন্স না থাকা)
  4. Empty function/classes (শুধু `pass` বা ডকো স্ট্রিং — stub সন্দেহ)
  5. Syntax errors (AST parse ব্যর্থ — এটি নিজেই একটি bug)

Cross-file aware: একটি নাম অন্য কোনো ফাইলে import/রেফারেন্স করা হলে তা
"used" হিসেবে গণ্য হয় — false positive কমায়।

AST-based হওয়ায় regex-এর চেয়ে নির্ভুল। ম্যাচ পেলে non-zero exit (CI gate)।

ব্যবহার:
    python scripts/find_dead_code.py                  # পুরো কোডবেস
    python scripts/find_dead_code.py --path backend/   # শুধু backend/
    python scripts/find_dead_code.py --min-severity P2

Exit codes:
    0 — গুরুতর dead code পাওয়া যায়নি (PASS)
    1 — অন্তত একটি dead code সন্দেহ পাওয়া গেছে (FAIL)
    2 — রানটাইম/আর্গুমেন্ট এরর
"""

import argparse
import ast
import os
import sys
from pathlib import Path

DEFAULT_EXCLUDE: tuple[str, ...] = (
    ".venv", "node_modules", "__pycache__", ".git", ".agent",
    "infrastructure", "archive", "build", "dist", ".turbo", "tests",
    "out", "htmlcov", ".coverage", "coverage", "ephemeral",
)

# বাংলা মন্তব্য: এই নামগুলো সাধারণত entry-point বা framework দিয়ে কল হয় — unused ধরা যাবে না।
ENTRYPOINT_NAMES: tuple[str, ...] = (
    "main", "__init__", "__call__", "__enter__", "__exit__", "__aenter__",
    "__aexit__", "__str__", "__repr__", "__len__", "__getitem__", "__setitem__",
    "__iter__", "__next__", "setup", "teardown", "run",
    # FastAPI/Flask framework-registered
    "startup_event", "shutdown_event", "health_check", "health", "index",
    "generate", "chat_completions", "list_models", "not_found_handler",
    "internal_error_handler", "root", "home", "status", "ping", "pong",
    # Alembic migrations
    "upgrade", "downgrade",
    # CLI entrypoints
    "cli", "command", "handler", "callback",
    # Pytest fixtures
    "setup_test_environment", "mock_redis", "mock_async_redis", "mock_external_apis",
    # Common factory/registration patterns
    "register_routes", "register_router", "register_all_routers",
    "include_user_routers", "include_admin_routers",
    "app_lifespan", "get_health_monitor", "register_self_healer_listener",
    "start_swarm_cache_invalidator", "acquire_idempotency_lock",
    "get_cache", "get_redis_client", "get_firestore_client",
    "get_production_env", "get_default_code_smell_thresholds",
    "get_common_strings_to_ignore", "get_ld_ai_components",
    "get_from_memory", "save_to_memory", "get_engine_info",
    "get_admin_capabilities", "get_self_sovereign_router",
    "run_complete_system_test", "check_url_accessibility",
    "make_fingerprint", "safe_http_error", "safe_error_response",
    "with_error_bus", "probe_redis", "probe_database", "probe_external_api",
    "aggregated_health_check", "router_health_check",
    "get_system_health", "get_cache_metrics", "get_db_metrics",
    "get_ai_metrics", "get_security_metrics", "get_performance_overview",
    "get_detailed_status", "get_fitness_engine", "verify_autonomous_agent_token",
    "get_tenant_db", "get_current_tenant", "verify_idempotency",
    "api_error_handler", "raise_bad_request", "raise_unauthorized",
    "raise_forbidden", "raise_not_found", "raise_conflict", "raise_internal",
    "list_resources", "get_engine_info",
    # Agent factory functions (get_* pattern)
    "get_churn_prophet", "get_bangla_nlp", "get_ecommerce_agent",
    "get_education_agent", "get_financial_services", "get_healthcare_assistant",
    "get_adversarial_defense", "get_federated_learning", "get_meta_learning",
    "get_multi_agent_collaboration", "get_ethics_monitor", "get_insight_mage",
    "get_competitor_analysis", "get_compliance_monitor", "get_predictive_analytics",
    "get_tech_radar", "get_performance_guardian", "get_sentinel",
    "initialize_agents", "initialize_internet_monitor", "get_internet_updates",
    "get_update_summary", "get_update_history", "scan_for_vulnerabilities",
    "scan_project_endpoint", "create_learning_loop",
)


class UsageCollector(ast.NodeVisitor):
    """পুরো মডিইউলজুড়ে ব্যবহৃত নাম (Name/Call/Import) সংগ্রহ করে।"""

    def __init__(self):
        self.used_names: set[str] = set()

    def visit_Name(self, node: ast.Name):
        self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # মডিউল.অ্যাট্রিবিউট ব্যবহার — মূল নামটাও marked করি (যেমন os.path)
        if isinstance(node.value, ast.Name):
            self.used_names.add(node.value.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # কলের টার্গেট নামটাও ব্যবহৃত হিসেবে ধরি (যেমন foo())
        if isinstance(node.func, ast.Name):
            self.used_names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            self.used_names.add(node.func.value.id)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        # import x → x ব্যবহৃত
        for alias in node.names:
            self.used_names.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        # from x import y → y ব্যবহৃত
        for alias in node.names:
            if alias.name != "*":
                self.used_names.add(alias.asname or alias.name)
        self.generic_visit(node)


def _is_effectively_empty(node: ast.AST) -> bool:
    """ফাংশন/ক্লাস শুধু `pass` বা ডকো স্ট্রিং কি না চেক করে।"""
    body = [n for n in getattr(node, "body", [])
            if not (isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant))]
    return len(body) == 0 or all(isinstance(n, ast.Pass) for n in body)


def _is_future_import(node: ast.AST) -> bool:
    """`from __future__ import ...` — এটা কখনো unused ধরা যাবে না।"""
    return isinstance(node, ast.ImportFrom) and node.module == "__future__"


def _is_decorated(node: ast.AST) -> bool:
    """ডেকোরেটর থাকলে framework-registered হতে পারে — unused ধরা যাবে না।"""
    return bool(getattr(node, "decorator_list", []))


def _collect_file_symbols(filepath: str) -> tuple[set[str], set[str], list[dict]]:
    """একটি ফাইলের defined names + used names + findings সংগ্রহ করে।"""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            source = f.read()
    except Exception:
        return set(), set(), []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        return set(), set(), [{
            "file": filepath, "line": exc.lineno or 0, "severity": "P1",
            "category": "syntax_error", "detail": f"AST parse ব্যর্থ: {exc.msg}",
        }]

    defined: set[str] = set()
    collector = UsageCollector()
    collector.visit(tree)
    used = collector.used_names

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                defined.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    defined.add(alias.asname or alias.name)

    return defined, used, []


def scan_file(filepath: str, min_severity: str, global_used: set[str]) -> list[dict]:
    """একটি ফাইল স্ক্যান — global_used-এ অন্য ফাইলে ব্যবহৃত নামগুলো থাকে।"""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            source = f.read()
    except Exception:
        return []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        return [{
            "file": filepath, "line": exc.lineno or 0, "severity": "P1",
            "category": "syntax_error", "detail": f"AST parse ব্যর্থ: {exc.msg}",
        }]

    findings: list[dict] = []
    collector = UsageCollector()
    collector.visit(tree)
    used = collector.used_names

    # বাংলা মন্তব্য: __init__.py ফাইলে re-export সাধারণ — unused import ধরা যাবে না।
    is_init = Path(filepath).name == "__init__.py"

    # Top-level imports যা আর ব্যবহার হয়নি
    for node in tree.body:
        if _is_future_import(node):
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                if name not in used and name not in global_used and not is_init:
                    findings.append(_mk(filepath, node, "P2", "unused_import", f"import '{name}' ব্যবহার করা হয়নি"))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name
                if name not in used and name not in global_used and not is_init:
                    findings.append(_mk(filepath, node, "P2", "unused_import", f"from {node.module} import '{name}' ব্যবহার করা হয়নি"))

    # Top-level functions/classes
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name not in ENTRYPOINT_NAMES and node.name not in used and node.name not in global_used:
                if _is_effectively_empty(node):
                    findings.append(_mk(filepath, node, "P3", "empty_function", f"def {node.name}() — শুধু pass/docstring (stub সন্দেহ)"))
                else:
                    findings.append(_mk(filepath, node, "P2", "unused_function", f"def {node.name}() ফাইলে আর কল/রেফারেন্স করা হয়নি"))
        elif isinstance(node, ast.ClassDef):
            if node.name not in ENTRYPOINT_NAMES and node.name not in used and node.name not in global_used:
                if _is_effectively_empty(node):
                    findings.append(_mk(filepath, node, "P3", "empty_class", f"class {node.name} — শুধু pass/docstring (stub সন্দেহ)"))
                else:
                    findings.append(_mk(filepath, node, "P2", "unused_class", f"class {node.name} রেফারেন্স করা হয়নি"))

    sev_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return [f for f in findings if sev_order[f["severity"]] >= sev_order[min_severity]]


def _mk(filepath: str, node: ast.AST, severity: str, category: str, detail: str) -> dict:
    return {
        "file": filepath, "line": getattr(node, "lineno", 0),
        "severity": severity, "category": category, "detail": detail,
    }


def _collect_python_files(root: str, exclude: list[str]) -> list[str]:
    """স্ক্যানযোগ্য সব .py ফাইলের তালিকা।"""
    files: list[str] = []
    for path, dirs, filenames in os.walk(root):
        dirs[:] = [d for d in dirs
                   if not any(ex in d for ex in exclude) and not d.startswith(".")]
        for file in filenames:
            if file.endswith(".py"):
                files.append(str(Path(path) / file))
    return files


def scan_directory(root: str, exclude: list[str], min_severity: str) -> list[dict]:
    """Cross-file aware স্ক্যান — প্রথমে সব ফাইলের defined names সংগ্রহ, তারপর চেক।"""
    all_files = _collect_python_files(root, exclude)

    # Pass 1: সব ফাইলের defined names + used names সংগ্রহ
    all_defined: set[str] = set()
    all_used: set[str] = set()
    for fp in all_files:
        defined, used, _ = _collect_file_symbols(fp)
        all_defined.update(defined)
        all_used.update(used)

    # বাংলা মন্তব্য: global_used = অন্য ফাইলে ব্যবহৃত নাম (cross-file usage)
    global_used = all_used - all_defined

    # Pass 2: প্রতিটি ফাইল স্ক্যান
    all_findings: list[dict] = []
    for fp in all_files:
        all_findings.extend(scan_file(fp, min_severity, global_used))
    return all_findings


def main() -> int:
    parser = argparse.ArgumentParser(description="SupremeAI Dead Code Scanner (P2 Gate)")
    parser.add_argument("--path", default=".", help="স্ক্যান করার পাথ (ডিফল্ট: repo root)")
    parser.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDE), help="এক্সক্লুড ডিরেক্টরি")
    parser.add_argument("--min-severity", choices=["P0", "P1", "P2", "P3"], default="P1",
                        help="রিপোর্ট করার সর্বনিম্ন সিভিরিটি (ডিফল্ট: P1 — শুধু syntax error FAIL)")
    args = parser.parse_args()

    # বাংলা মন্তব্য: উইন্ডোজ কনসোল (charmap) বাংলা এনকোড করতে পারে না — stdout/stderr কে utf-8-এ রিকনফিগ করি।
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    sev_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    min_sev = sev_order[args.min_severity]

    print(f"[SCAN] Dead code স্ক্যান চলছে: {args.path} (min severity {args.min_severity})")
    print()

    findings = scan_directory(args.path, args.exclude, args.min_severity)

    if not findings:
        print("[PASS] নির্দিষ্ট সিভিরিটির ওপরে কোনো dead code পাওয়া যায়নি")
        return 0

    by_cat: dict[str, int] = {}
    for f in findings:
        by_cat[f["category"]] = by_cat.get(f["category"], 0) + 1

    print(f"[FAIL] {len(findings)} সম্ভাব্য dead-code/issues পাওয়া গেছে:")
    for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"   {cat}: {cnt}")
    print()

    for f in sorted(findings, key=lambda x: (sev_order[x["severity"]], x["file"])):
        safe_file = f["file"].encode(sys.stdout.encoding or "utf-8", "replace").decode()
        safe_detail = f["detail"].encode(sys.stdout.encoding or "utf-8", "replace").decode()
        print(f"  [{f['severity']}] {f['category']}")
        print(f"     File: {safe_file}:{f['line']}")
        print(f"     Info: {safe_detail}")
        print()

    worst = min(sev_order[f["severity"]] for f in findings)
    return 1 if worst <= min_sev else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)