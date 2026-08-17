#!/usr/bin/env python3
"""
Import Analysis Script for SupremeAI 2.0

Analyzes Python imports across the codebase to identify:
- Unused imports
- Circular imports
- Import ordering issues
- Duplicate imports across modules

Usage:
    python scripts/analyze_imports.py
    python scripts/analyze_imports.py --directory backend
    python scripts/analyze_imports.py --check-unused
"""

import argparse
import ast
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ImportInfo:
    """Information about a single import statement."""
    file_path: str
    line_number: int
    module: str
    names: list[str]
    import_type: str  # 'import' or 'from'
    is_used: bool = False


@dataclass
class ImportAnalysis:
    """Analysis results for a file's imports."""
    file_path: str
    imports: list[ImportInfo] = field(default_factory=list)
    unused_imports: list[ImportInfo] = field(default_factory=list)
    circular_imports: list[str] = field(default_factory=list)


def extract_imports(file_path: str) -> list[ImportInfo]:
    """Extract all import statements from a Python file."""
    imports = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(
                        file_path=file_path,
                        line_number=node.lineno,
                        module=alias.name,
                        names=[alias.asname or alias.name],
                        import_type="import",
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(ImportInfo(
                        file_path=file_path,
                        line_number=node.lineno,
                        module=module,
                        names=[alias.asname or alias.name],
                        import_type="from",
                    ))

    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"  ⚠️  Skipping {file_path}: {e}", file=sys.stderr)

    return imports


def check_import_usage(file_path: str, imports: list[ImportInfo]) -> list[ImportInfo]:
    """Check which imports are actually used in the file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=file_path)

        # Collect all names used in the code
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Handle attribute access like module.function
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        # Check each import
        unused = []
        for imp in imports:
            # Check if any of the imported names are used
            is_used = False
            for name in imp.names:
                if name in used_names:
                    is_used = True
                    break
                # Check for module-level usage (e.g., import x.y)
                if imp.import_type == "import" and name.split(".")[0] in used_names:
                    is_used = True
                    break

            imp.is_used = is_used
            if not is_used:
                unused.append(imp)

    except (SyntaxError, UnicodeDecodeError):
        pass

    return unused


def detect_circular_imports(
    directory: str,
    ignore_dirs: list[str] | None = None,
) -> dict[str, list[str]]:
    """Detect circular import dependencies."""
    if ignore_dirs is None:
        ignore_dirs = ["tests", "migrations", "__pycache__", ".venv", "node_modules"]

    # Build import graph
    import_graph: dict[str, set[str]] = defaultdict(set)

    py_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))

    for py_file in py_files:
        imports = extract_imports(py_file)
        module_name = py_file.replace("/", ".").replace(".py", "")
        module_name = module_name.replace("\\", ".")

        for imp in imports:
            if imp.module:
                # Normalize module name
                mod = imp.module.replace("/", ".").replace("\\", ".")
                if mod.startswith(directory.replace("/", ".")):
                    import_graph[module_name].add(mod)

    # Detect cycles using DFS
    cycles: dict[str, list[str]] = defaultdict(list)

    def dfs(node: str, visited: set[str], path: list[str]):
        if node in path:
            # Found a cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            cycles[node].append(" -> ".join(cycle))
            return

        if node in visited:
            return

        visited.add(node)
        path.append(node)

        for neighbor in import_graph.get(node, []):
            dfs(neighbor, visited, path)

        path.pop()

    for node in import_graph:
        dfs(node, set(), [])

    return dict(cycles)


def analyze_imports(
    directory: str,
    check_unused: bool = True,
    check_circular: bool = True,
    ignore_dirs: list[str] | None = None,
) -> dict[str, Any]:
    """Analyze imports across the codebase."""
    if ignore_dirs is None:
        ignore_dirs = ["tests", "migrations", "__pycache__", ".venv", "node_modules"]

    py_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))

    print(f"🔍 Analyzing imports in {len(py_files)} Python files...")

    results: dict[str, Any] = {
        "total_files": len(py_files),
        "total_imports": 0,
        "unused_imports": [],
        "circular_imports": {},
        "import_frequency": defaultdict(int),
    }

    all_imports: dict[str, list[ImportInfo]] = {}

    for py_file in py_files:
        imports = extract_imports(py_file)
        results["total_imports"] += len(imports)
        all_imports[py_file] = imports

        # Track import frequency
        for imp in imports:
            results["import_frequency"][imp.module] += 1

        # Check for unused imports
        if check_unused:
            unused = check_import_usage(py_file, imports)
            if unused:
                results["unused_imports"].append({
                    "file": os.path.relpath(py_file),
                    "imports": [
                        {
                            "module": imp.module,
                            "names": imp.names,
                            "line": imp.line_number,
                        }
                        for imp in unused
                    ],
                })

    # Detect circular imports
    if check_circular:
        print("🔄 Detecting circular imports...")
        results["circular_imports"] = detect_circular_imports(directory, ignore_dirs)

    return results


def generate_report(results: dict[str, Any], output_file: str | None = None) -> None:
    """Generate a report of import analysis."""
    # Convert defaultdict to regular dict for JSON serialization
    results["import_frequency"] = dict(results["import_frequency"])

    if output_file:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"📄 Report saved to {output_file}")


def print_summary(results: dict[str, Any]) -> None:
    """Print a human-readable summary of import analysis."""
    print("\n" + "=" * 70)
    print("📊 IMPORT ANALYSIS REPORT")
    print("=" * 70)

    print(f"\n📁 Files analyzed: {results['total_files']}")
    print(f"📦 Total imports: {results['total_imports']}")

    # Unused imports
    unused = results.get("unused_imports", [])
    total_unused = sum(len(u["imports"]) for u in unused)
    print(f"\n⚠️  Unused imports: {total_unused} in {len(unused)} files")

    if unused:
        print("\n  Top files with unused imports:")
        for entry in unused[:10]:
            print(f"    • {entry['file']}: {len(entry['imports'])} unused")
            for imp in entry["imports"][:3]:
                print(f"      - {imp['module']} (line {imp['line']})")

    # Circular imports
    circular = results.get("circular_imports", {})
    if circular:
        print(f"\n🔄 Circular imports detected: {len(circular)}")
        for module, cycles in list(circular.items())[:5]:
            for cycle in cycles[:2]:
                print(f"    • {cycle}")
    else:
        print(f"\n✅ No circular imports detected")

    # Most imported modules
    freq = results.get("import_frequency", {})
    if freq:
        print(f"\n📈 Most imported modules:")
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        for module, count in sorted_freq[:10]:
            print(f"    • {module}: {count} imports")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Python imports in the SupremeAI 2.0 codebase"
    )
    parser.add_argument(
        "--directory", "-d",
        default="backend",
        help="Directory to analyze (default: backend)",
    )
    parser.add_argument(
        "--check-unused",
        action="store_true",
        default=True,
        help="Check for unused imports",
    )
    parser.add_argument(
        "--check-circular",
        action="store_true",
        default=True,
        help="Check for circular imports",
    )
    parser.add_argument(
        "--output", "-o",
        default="reports/import_analysis.json",
        help="Output file for JSON report (default: reports/import_analysis.json)",
    )
    parser.add_argument(
        "--ignore", "-i",
        nargs="+",
        default=["tests", "migrations", "__pycache__", ".venv", "node_modules"],
        help="Directories to ignore",
    )

    args = parser.parse_args()

    # Analyze imports
    results = analyze_imports(
        directory=args.directory,
        check_unused=args.check_unused,
        check_circular=args.check_circular,
        ignore_dirs=args.ignore,
    )

    # Generate report
    generate_report(results, args.output)

    # Print summary
    print_summary(results)

    # Exit with non-zero if issues found
    unused_count = sum(len(u["imports"]) for u in results.get("unused_imports", []))
    circular_count = len(results.get("circular_imports", {}))

    if unused_count > 0 or circular_count > 0:
        print(f"\n⚠️  Found {unused_count} unused imports and {circular_count} circular dependencies.")
        sys.exit(1)
    else:
        print("\n✅ No import issues found!")
        sys.exit(0)


if __name__ == "__main__":
    main()
