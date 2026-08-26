#!/usr/bin/env python3
"""
SupremeAI টেস্ট কভারেজ গ্যাপ ম্যাপার
===================================
ব্যাকএন্ডের প্রতিটি পাইথন মডিউলের টেস্ট কভারেজ ম্যাপ করে,
ঝুঁকি ওজন নির্ধারণ করে, এবং স্প্রিন্ট সুপারিশ দেয়।

শুধুমাত্র stdlib ব্যবহার করে তৈরি।
"""

import ast
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# ============================================================
# ধ্রুবক ও কনফিগারেশন
# ============================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
TESTS_DIR = BACKEND_DIR / "tests"

# ঝুঁকি ওজন কনফিগারেশন — প্রতিটি কীওয়ার্ড প্যাটার্ন ম্যাচ করবে মডিউল পাথের সাথে
RISK_CONFIG = {
    "CRITICAL": {
        "weight": 5,
        "emoji": "🔴",
        "keywords": [
            "auth", "security", "payment", "billing", "wallet",
            "api_key", "config", "middleware", "rbac", "secret_vault",
            "secure_credential", "sso", "otp", "autonoguard",
            "cryptographic_ledger", "governance_policy", "audit",
            "billing_api", "payments", "admin_auth",
        ],
    },
    "HIGH": {
        "weight": 4,
        "emoji": "🟠",
        "keywords": [
            "api/routes", "api/routers", "core", "database", "models",
            "agents", "brain", "engine", "api_server", "deps",
            "api_key_middleware", "rate_limiter", "api_gateway",
        ],
    },
    "MEDIUM": {
        "weight": 3,
        "emoji": "🟡",
        "keywords": [
            "services", "integrations", "tools", "brain",
            "memory", "evolution", "learning", "adaptive_engine",
            "browser", "byoc", "p2p", "runtime", "scout",
        ],
    },
    "LOW": {
        "weight": 1,
        "emoji": "🟢",
        "keywords": [
            "utils", "monitoring", "scripts", "docs", "reports",
            "schemas", "storage", "sandbox", "adapters", "middleware",
            "workers", "scaling", "baselines", "docker",
            "alembic_migrations", "examples", "pyerrorfix",
        ],
    },
}

# টেস্ট ফাইলের প্যাটার্ন
TEST_FILE_PATTERNS = ["test_*.py", "*_test.py"]

# বাদ দেওয়ার ডিরেক্টরি
EXCLUDE_DIRS = {"tests", "__pycache__", ".git", "node_modules", ".venv", "venv", "env"}

# বাদ দেওয়ার ফাইল (অ-মডিউল ফাইল)
EXCLUDE_FILES = {"conftest.py", "__init__.py"}


# ============================================================
# হেল্পার ফাংশন
# ============================================================

def is_test_file(filename: str) -> bool:
    """ফাইলটি টেস্ট ফাইল কিনা চেক করে"""
    return any(
        re.match(p.replace("*", ".*"), filename) for p in TEST_FILE_PATTERNS
    )


def get_risk_level(module_rel_path: str) -> tuple:
    """
    মডিউলের আপেক্ষিক পাথ থেকে ঝুঁকি স্তর ও ওজন নির্ধারণ করে।
    সর্বোচ্চ ঝুঁকি ম্যাচ প্রাধান্য পায়।
    রিটার্ন: (level_name, weight, emoji)
    """
    path_lower = module_rel_path.lower().replace(os.sep, "/")
    best = ("LOW", 1, "🟢")  # ডিফল্ট
    for level, cfg in RISK_CONFIG.items():
        for kw in cfg["keywords"]:
            if kw in path_lower:
                if cfg["weight"] > best[1]:
                    best = (level, cfg["weight"], cfg["emoji"])
    return best


def collect_all_modules(backend: Path) -> list:
    """
    backend/ এর নিচে সব .py ফাইল সংগ্রহ করে (tests/ ও __pycache__ বাদ দিয়ে)।
    রিটার্ন: [(relative_path_str, absolute_path)]
    """
    modules = []
    for root, dirs, files in os.walk(backend):
        # বাদ দেওয়ার ডিরেক্টরি ফিল্টার করা
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        # tests/ ডিরেক্টরি সম্পূর্ণ বাদ
        if "tests" in Path(root).relative_to(backend).parts:
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            if f in EXCLUDE_FILES:
                continue
            abs_path = Path(root) / f
            rel_path = str(abs_path.relative_to(backend))
            modules.append((rel_path, abs_path))
    return modules


def collect_all_test_files(tests_dir: Path) -> set:
    """
    tests/ ডিরেক্টরি থেকে সব টেস্ট ফাইলের আপেক্ষিক পাথ সংগ্রহ করে।
    রিটার্ন: {relative_to_tests_dir_str}
    """
    test_files = set()
    if not tests_dir.exists():
        return test_files
    for root, dirs, files in os.walk(tests_dir):
        dirs[:] = [d for d in dirs if d not in {"__pycache__"}]
        for f in files:
            if not f.endswith(".py"):
                continue
            rel = str((Path(root) / f).relative_to(tests_dir))
            test_files.add(rel)
    return test_files


def find_direct_test(module_rel: str, test_files: set) -> str | None:
    """
    মডিউলের জন্য সরাসরি টেস্ট ফাইল খোঁজে:
    - module.py → tests/test_module.py বা tests/module/test_*.py
    - package/module.py → tests/test_module.py বা tests/package/test_module.py
    """
    # মডিউলের নাম বের করা (extension ছাড়া)
    mod_name = Path(module_rel).stem
    # প্যারেন্ট ডিরেক্টরি
    parent = str(Path(module_rel).parent)
    if parent == ".":
        parent = ""

    # প্যাটার্ন ১: tests/test_module.py
    candidate = f"test_{mod_name}.py"
    if candidate in test_files:
        return candidate

    # প্যাটার্ন ২: tests/module_test.py
    candidate = f"{mod_name}_test.py"
    if candidate in test_files:
        return candidate

    # প্যাটার্ন ৩: tests/package/test_module.py
    if parent:
        candidate = f"{parent}/test_{mod_name}.py"
        if candidate in test_files:
            return candidate
        candidate = f"{parent}/{mod_name}_test.py"
        if candidate in test_files:
            return candidate

    # প্যাটার্ন ৪: tests/package/module/test_*.py (যেকোনো)
    if parent:
        prefix = f"{parent}/{mod_name}/"
        for tf in test_files:
            if tf.startswith(prefix) and is_test_file(Path(tf).name):
                return tf

    # প্যাটার্ন ৫: tests/subdir/test_* যেখানে subdir মডিউল নামের সাথে মিলে
    # যেমন: api/routes/auth.py → tests/api/test_auth_routes.py
    parts = Path(module_rel).parts
    if len(parts) >= 2:
        # শেষ দুইটি অংশ নিয়ে চেষ্টা
        for i in range(len(parts) - 1, 0, -1):
            dir_part = "/".join(parts[:i])
            candidate = f"{dir_part}/test_{mod_name}.py"
            if candidate in test_files:
                return candidate

    return None


def build_import_to_test_map(tests_dir: Path, test_files: set) -> dict:
    """
    প্রতিটি টেস্ট ফাইল পার্স করে দেখে কোন মডিউল import করছে।
    রিটার্ন: {imported_module_name: [test_file_rel, ...]}
    """
    import_map = defaultdict(list)
    for tf_rel in test_files:
        tf_path = tests_dir / tf_rel
        if not tf_path.exists():
            continue
        try:
            with open(tf_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
            tree = ast.parse(source, filename=str(tf_path))
        except (SyntaxError, ValueError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_map[alias.name.split(".")[0]].append(tf_rel)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    parts = node.module.split(".")
                    # প্রথম অংশ যদি backend এর সাব-মডিউল হয়
                    for p in parts:
                        if p and not p.startswith("_"):
                            import_map[p].append(tf_rel)
                            break
    return dict(import_map)


def check_indirect_coverage(module_rel: str, import_map: dict) -> str | None:
    """
    মডিউলটি কোনো টেস্ট ফাইলে indirect ভাবে import হয় কিনা চেক করে।
    """
    # মডিউলের নামের অংশগুলো
    parts = Path(module_rel).parts
    stem = Path(module_rel).stem

    # সরাসরি stem দিয়ে চেক
    if stem in import_map and stem not in ("os", "sys", "json", "re", "ast", "pathlib", "collections", "time", "datetime", "typing", "functools", "itertools", "copy", "math", "io", "logging", "unittest", "pytest", "httpx", "asyncio", "hashlib", "secrets", "uuid", "base64", "struct", "enum", "dataclasses", "contextlib", "abc", "importlib"):
        return import_map[stem][0]

    # প্যারেন্ট প্যাকেজ নাম দিয়ে চেক
    for p in parts:
        if p and len(p) > 2 and p in import_map and p not in ("api", "core", "test", "tests"):
            return import_map[p][0]

    return None


def extract_classes_and_functions(filepath: Path) -> dict:
    """
    একটি পাইথন ফাইল থেকে ক্লাস ও ফাংশনের নাম বের করে।
    রিটার্ন: {"classes": [...], "functions": [...]}
    """
    result = {"classes": [], "functions": []}
    if not filepath.exists():
        return result
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, ValueError, OSError):
        return result
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            result["classes"].append(node.name)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if not node.name.startswith("_"):
                result["functions"].append(node.name)
    return result


def get_package(rel_path: str) -> str:
    """মডিউলের টপ-লেভেল প্যাকেজ নাম বের করে"""
    parts = Path(rel_path).parts
    if len(parts) <= 1:
        return "(root)"
    return parts[0]


def count_lines(filepath: Path) -> int:
    """ফাইলের লাইন সংখ্যা গণনা করে"""
    if not filepath.exists():
        return 0
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


# ============================================================
# মূল বিশ্লেষণ ফাংশন
# ============================================================

def analyze_coverage(
    backend: Path,
    tests_dir: Path,
    filter_package: str | None = None,
    risk_only: bool = False,
) -> dict:
    """
    সম্পূর্ণ কভারেজ বিশ্লেষণ করে একটি কাঠামোবদ্ধ ডিকশনারি রিটার্ন করে।
    """
    # ধাপ ১: সব মডিউল ও টেস্ট ফাইল সংগ্রহ
    modules = collect_all_modules(backend)
    test_files = collect_all_test_files(tests_dir)
    import_map = build_import_to_test_map(tests_dir, test_files)

    # ধাপ ২: প্রতিটি মডিউলের জন্য কভারেজ তথ্য তৈরি
    module_data = []
    for rel_path, abs_path in modules:
        pkg = get_package(rel_path)

        # প্যাকেজ ফিল্টার
        if filter_package and pkg != filter_package and not rel_path.startswith(filter_package):
            continue

        risk_level, risk_weight, risk_emoji = get_risk_level(rel_path)
        direct_test = find_direct_test(rel_path, test_files)
        indirect_test = check_indirect_coverage(rel_path, import_map) if not direct_test else None
        has_coverage = direct_test is not None or indirect_test is not None
        coverage_type = "direct" if direct_test else ("indirect" if indirect_test else "none")
        symbols = extract_classes_and_functions(abs_path)
        line_count = count_lines(abs_path)

        module_data.append({
            "path": rel_path,
            "package": pkg,
            "risk_level": risk_level,
            "risk_weight": risk_weight,
            "risk_emoji": risk_emoji,
            "has_coverage": has_coverage,
            "coverage_type": coverage_type,
            "direct_test": direct_test,
            "indirect_test": indirect_test,
            "classes": symbols["classes"],
            "functions": symbols["functions"],
            "line_count": line_count,
        })

    # ধাপ ৩: ফিল্টার (যদি --risk-only হয়)
    if risk_only:
        module_data = [m for m in module_data if m["risk_level"] in ("CRITICAL", "HIGH")]

    # ধাপ ৪: প্যাকেজ-লেভেল সারসংক্ষেপ
    package_summary = defaultdict(lambda: {
        "total_files": 0,
        "covered_files": 0,
        "directly_tested": 0,
        "indirectly_tested": 0,
        "total_risk_weight": 0,
        "covered_risk_weight": 0,
        "untested_critical": 0,
        "untested_high": 0,
    })
    for m in module_data:
        pkg = m["package"]
        ps = package_summary[pkg]
        ps["total_files"] += 1
        ps["total_risk_weight"] += m["risk_weight"]
        if m["has_coverage"]:
            ps["covered_files"] += 1
            ps["covered_risk_weight"] += m["risk_weight"]
            if m["coverage_type"] == "direct":
                ps["directly_tested"] += 1
            else:
                ps["indirectly_tested"] += 1
        else:
            if m["risk_level"] == "CRITICAL":
                ps["untested_critical"] += 1
            elif m["risk_level"] == "HIGH":
                ps["untested_high"] += 1

    # প্যাকেজ সারসংক্ষেপে শতাংশ যোগ
    for pkg, ps in package_summary.items():
        if ps["total_files"] > 0:
            ps["coverage_pct"] = round(ps["covered_files"] / ps["total_files"] * 100, 1)
        else:
            ps["coverage_pct"] = 0.0
        if ps["total_risk_weight"] > 0:
            ps["risk_weighted_coverage_pct"] = round(
                ps["covered_risk_weight"] / ps["total_risk_weight"] * 100, 1
            )
        else:
            ps["risk_weighted_coverage_pct"] = 0.0

    # ধাপ ৫: আনটেস্টেড মডিউল — ঝুঁকি স্কোর অনুযায়ী সাজানো
    untested = [m for m in module_data if not m["has_coverage"]]
    untested.sort(key=lambda x: (-x["risk_weight"], -x["line_count"]))

    # ধাপ ৬: স্প্রিন্ট সুপারিশ — ঝুঁকি × প্রভাব অনুযায়ী শীর্ষ ১০
    for m in untested:
        # প্রভাব স্কোর: ক্লাস+ফাংশন সংখ্যা ও লাইন কাউন্ট
        symbol_count = len(m["classes"]) + len(m["functions"])
        m["impact_score"] = round(
            m["risk_weight"] * (1 + symbol_count * 0.5 + m["line_count"] * 0.001),
            2,
        )
    sprint_top10 = sorted(untested, key=lambda x: -x["impact_score"])[:10]

    # ধাপ ৭: সামগ্রিক পরিসংখ্যান
    total_modules = len(module_data)
    total_covered = sum(1 for m in module_data if m["has_coverage"])
    total_untested = total_modules - total_covered
    critical_untested = sum(1 for m in module_data if not m["has_coverage"] and m["risk_level"] == "CRITICAL")
    high_untested = sum(1 for m in module_data if not m["has_coverage"] and m["risk_level"] == "HIGH")

    overall_coverage_pct = round(total_covered / total_modules * 100, 1) if total_modules > 0 else 0.0
    total_risk_weight = sum(m["risk_weight"] for m in module_data)
    covered_risk_weight = sum(m["risk_weight"] for m in module_data if m["has_coverage"])
    risk_weighted_pct = round(covered_risk_weight / total_risk_weight * 100, 1) if total_risk_weight > 0 else 0.0

    return {
        "summary": {
            "total_modules": total_modules,
            "total_test_files": len(test_files),
            "total_covered": total_covered,
            "total_untested": total_untested,
            "coverage_pct": overall_coverage_pct,
            "risk_weighted_coverage_pct": risk_weighted_pct,
            "critical_untested": critical_untested,
            "high_untested": high_untested,
        },
        "package_summary": dict(sorted(package_summary.items(), key=lambda x: -x[1]["total_files"])),
        "untested_gaps": untested,
        "sprint_recommendation": sprint_top10,
        "all_modules": module_data,
    }


# ============================================================
# আউটপুট ফরম্যাটার
# ============================================================

def format_human_readable(result: dict, risk_only: bool) -> str:
    """মানুষের পড়তে সুবিধাজনক ফরম্যাটে আউটপুট তৈরি করে"""
    lines = []
    s = result["summary"]

    # হেডার
    lines.append("=" * 72)
    lines.append("  SupremeAI টেস্ট কভারেজ গ্যাপ বিশ্লেষণ")
    lines.append("=" * 72)
    lines.append("")

    # সামগ্রিক পরিসংখ্যান
    lines.append(f"  মোট মডিউল:          {s['total_modules']}")
    lines.append(f"  মোট টেস্ট ফাইল:      {s['total_test_files']}")
    lines.append(f"  কভারেজ আছে:          {s['total_covered']} ({s['coverage_pct']}%)")
    lines.append(f"  কভারেজ নেই:          {s['total_untested']}")
    lines.append(f"  ঝুঁকি-ওজনযুক্ত কভারেজ: {s['risk_weighted_coverage_pct']}%")
    lines.append(f"  🔴 CRITICAL আনটেস্টেড: {s['critical_untested']}")
    lines.append(f"  🟠 HIGH আনটেস্টেড:     {s['high_untested']}")
    lines.append("")

    # প্যাকেজ-লেভেল সারসংক্ষেপ
    lines.append("-" * 72)
    lines.append("  প্যাকেজ অনুযায়ী কভারেজ সারসংক্ষেপ")
    lines.append("-" * 72)
    lines.append(f"  {'প্যাকেজ':<22} {'ফাইল':>6} {'কভারেজ':>8} {'ওজনযুক্ত':>10} {'🔴':>4} {'🟠':>4}")
    lines.append(f"  {'─'*22} {'─'*6} {'─'*8} {'─'*10} {'─'*4} {'─'*4}")
    for pkg, ps in result["package_summary"].items():
        cov_emoji = "✅" if ps["coverage_pct"] >= 70 else ("⚠️" if ps["coverage_pct"] >= 40 else "❌")
        lines.append(
            f"  {pkg:<22} {ps['total_files']:>6} "
            f"{ps['coverage_pct']:>6.1f}% {cov_emoji} "
            f"{ps['risk_weighted_coverage_pct']:>6.1f}%   "
            f"{ps['untested_critical']:>3} {ps['untested_high']:>3}"
        )
    lines.append("")

    # গ্যাপ বিশ্লেষণ
    untested = result["untested_gaps"]
    if untested:
        lines.append("-" * 72)
        lines.append("  আনটেস্টেড মডিউল (ঝুঁকি অনুযায়ী সাজানো)")
        lines.append("-" * 72)
        for i, m in enumerate(untested, 1):
            symbols = []
            if m["classes"]:
                symbols.append(f"cls:{','.join(m['classes'][:3])}")
            if m["functions"]:
                symbols.append(f"fn:{','.join(m['functions'][:3])}")
            sym_str = " | ".join(symbols) if symbols else "(শুধুমাত্র import/কনফিগ)"
            if len(sym_str) > 60:
                sym_str = sym_str[:57] + "..."

            # অগ্রাধিকার সুপারিশ
            if m["risk_level"] == "CRITICAL":
                priority = "⚠️  অবিলম্বে লাগাতার"
            elif m["risk_level"] == "HIGH":
                priority = "🔸  এই স্প্রিন্টে"
            elif m["risk_level"] == "MEDIUM":
                priority = "🔹  পরবর্তী স্প্রিন্টে"
            else:
                priority = "    নিম্ন অগ্রাধিকার"

            lines.append(f"")
            lines.append(f"  {i:>3}. {m['risk_emoji']} [{m['risk_level']:<8}] (ওজন:{m['risk_weight']}) {m['path']}")
            lines.append(f"       লাইন: {m['line_count']} | {sym_str}")
            lines.append(f"       অগ্রাধিকার: {priority}")
    else:
        lines.append("  ✅ সব মডিউলে কভারেজ আছে!")
    lines.append("")

    # স্প্রিন্ট সুপারিশ
    sprint = result["sprint_recommendation"]
    if sprint:
        lines.append("=" * 72)
        lines.append("  🎯 স্প্রিন্ট সুপারিশ: শীর্ষ ১০ অগ্রাধিকার মডিউল")
        lines.append("=" * 72)
        lines.append(f"  {'#':<4} {'প্রভাব':>6} {'ঝুঁকি':<10} {'মডিউল'}")
        lines.append(f"  {'─'*4} {'─'*6} {'─'*10} {'─'*40}")
        for i, m in enumerate(sprint, 1):
            lines.append(
                f"  {i:<4} {m['impact_score']:>6.1f} {m['risk_emoji']} {m['risk_level']:<8} {m['path']}"
            )
        lines.append("")

    # এক্সিট কোড নির্দেশিকা
    lines.append("-" * 72)
    lines.append("  এক্সিট কোড: ০ = সব CRITICAL পরীক্ষিত | ১ = CRITICAL গ্যাপ | ২ = ত্রুটি")
    lines.append("-" * 72)

    return "\n".join(lines)


def format_json_output(result: dict) -> str:
    """JSON ফরম্যাটে আউটপুট তৈরি করে"""
    # সিরিয়ালাইজেশনের জন্য ক্লিন কপি
    output = {
        "summary": result["summary"],
        "package_summary": result["package_summary"],
        "sprint_recommendation": [
            {
                "path": m["path"],
                "risk_level": m["risk_level"],
                "risk_weight": m["risk_weight"],
                "impact_score": m.get("impact_score", 0),
                "line_count": m["line_count"],
                "classes": m["classes"],
                "functions": m["functions"],
                "suggested_priority": (
                    "immediate" if m["risk_level"] == "CRITICAL"
                    else "this_sprint" if m["risk_level"] == "HIGH"
                    else "next_sprint" if m["risk_level"] == "MEDIUM"
                    else "low"
                ),
            }
            for m in result["sprint_recommendation"]
        ],
        "untested_gaps": [
            {
                "path": m["path"],
                "package": m["package"],
                "risk_level": m["risk_level"],
                "risk_weight": m["risk_weight"],
                "line_count": m["line_count"],
                "classes": m["classes"],
                "functions": m["functions"],
                "coverage_type": m["coverage_type"],
                "suggested_priority": (
                    "immediate" if m["risk_level"] == "CRITICAL"
                    else "this_sprint" if m["risk_level"] == "HIGH"
                    else "next_sprint" if m["risk_level"] == "MEDIUM"
                    else "low"
                ),
            }
            for m in result["untested_gaps"]
        ],
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


# ============================================================
# মূল এন্ট্রি পয়েন্ট
# ============================================================

def main() -> int:
    """
    স্ক্রিপ্টের মূল ফাংশন।
    এক্সিট কোড:
      ০ = সব CRITICAL মডিউল পরীক্ষিত
      ১ = CRITICAL মডিউলে গ্যাপ আছে
      ২ = রান-টাইম ত্রুটি
    """
    # CLI আর্গুমেন্ট পার্স করা
    parser = argparse.ArgumentParser(
        description="SupremeAI টেস্ট কভারেজ গ্যাপ ম্যাপার — প্রতিটি মডিউলের কভারেজ বিশ্লেষণ করে",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
উদাহরণ:
  python test_coverage_gap_mapper.py                  # সম্পূর্ণ বিশ্লেষণ
  python test_coverage_gap_mapper.py --json            # JSON আউটপুট
  python test_coverage_gap_mapper.py --package api      # শুধু api প্যাকেজ
  python test_coverage_gap_mapper.py --risk-only       # CRITICAL ও HIGH গ্যাপ
        """,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="JSON ফরম্যাটে আউটপুট দেখাও",
    )
    parser.add_argument(
        "--package",
        type=str,
        default=None,
        metavar="PKG",
        help="নির্দিষ্ট প্যাকেজ ফিল্টার করো (যেমন: api, core, models)",
    )
    parser.add_argument(
        "--risk-only",
        action="store_true",
        default=False,
        help="শুধুমাত্র CRITICAL ও HIGH ঝুঁকির গ্যাপ দেখাও",
    )

    args = parser.parse_args()

    # ব্যাকএন্ড ডিরেক্টরি যাচাই
    if not BACKEND_DIR.exists():
        print(f"ত্রুটি: ব্যাকএন্ড ডিরেক্টরি পাওয়া যায়নি: {BACKEND_DIR}", file=sys.stderr)
        return 2

    if not TESTS_DIR.exists():
        print(f"ত্রুটি: টেস্ট ডিরেক্টরি পাওয়া যায়নি: {TESTS_DIR}", file=sys.stderr)
        return 2

    try:
        # বিশ্লেষণ চালানো
        result = analyze_coverage(
            backend=BACKEND_DIR,
            tests_dir=TESTS_DIR,
            filter_package=args.package,
            risk_only=args.risk_only,
        )

        # আউটপুট প্রিন্ট করা
        if args.json:
            print(format_json_output(result))
        else:
            print(format_human_readable(result, args.risk_only))

        # এক্সিট কোড নির্ধারণ
        critical_untested = result["summary"]["critical_untested"]
        if critical_untested > 0:
            return 1
        return 0

    except Exception as e:
        print(f"ত্রুটি: বিশ্লেষণ চলাকালীন সমস্যা হয়েছে: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
