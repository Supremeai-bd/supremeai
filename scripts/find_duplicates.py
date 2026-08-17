#!/usr/bin/env python3
"""
Duplicate Code Detection Script for SupremeAI 2.0

Scans the backend codebase for duplicate code patterns using AST analysis
and structural similarity. Helps identify areas where code can be consolidated.

Usage:
    python scripts/find_duplicates.py
    python scripts/find_duplicates.py --min-lines 10
    python scripts/find_duplicates.py --output reports/duplicates.json
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
class CodeBlock:
    """Represents a code block for duplicate detection."""
    file_path: str
    start_line: int
    end_line: int
    function_name: str
    code: str
    ast_dump: str
    complexity: int = 0


@dataclass
class DuplicateGroup:
    """Represents a group of duplicate code blocks."""
    blocks: list[CodeBlock] = field(default_factory=list)
    similarity_score: float = 0.0


def get_ast_complexity(node: ast.AST) -> int:
    """Calculate cyclomatic complexity of an AST node."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def extract_functions(file_path: str) -> list[CodeBlock]:
    """Extract all function/method definitions from a Python file."""
    blocks = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=file_path)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only consider functions with enough lines
                start_line = node.lineno
                end_line = node.end_lineno or start_line
                line_count = end_line - start_line + 1

                if line_count < 5:
                    continue

                # Get the code for this function
                lines = source.splitlines()
                func_code = "\n".join(
                    lines[start_line - 1:end_line]
                )

                # Create AST dump for comparison
                ast_dump = ast.dump(node)

                # Calculate complexity
                complexity = get_ast_complexity(node)

                blocks.append(CodeBlock(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    function_name=node.name,
                    code=func_code,
                    ast_dump=ast_dump,
                    complexity=complexity,
                ))

    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"  ⚠️  Skipping {file_path}: {e}", file=sys.stderr)

    return blocks


def normalize_code(code: str) -> str:
    """Normalize code by removing variable names and whitespace."""
    # Remove comments
    lines = []
    for line in code.splitlines():
        stripped = line.split("#")[0].rstrip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def calculate_similarity(block1: CodeBlock, block2: CodeBlock) -> float:
    """Calculate similarity between two code blocks using AST structure."""
    # Compare AST dumps for structural similarity
    dump1 = block1.ast_dump
    dump2 = block2.ast_dump

    if dump1 == dump2:
        return 1.0

    # Simple token-based similarity
    tokens1 = set(dump1.split())
    tokens2 = set(dump2.split())

    if not tokens1 and not tokens2:
        return 1.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0


def find_duplicates(
    directory: str,
    min_lines: int = 5,
    min_similarity: float = 0.7,
    ignore_dirs: list[str] | None = None,
) -> list[DuplicateGroup]:
    """Find duplicate code blocks in a directory."""
    if ignore_dirs is None:
        ignore_dirs = ["tests", "migrations", "__pycache__", ".venv", "node_modules"]

    all_blocks: list[CodeBlock] = []

    # Collect all Python files
    py_files = []
    for root, dirs, files in os.walk(directory):
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]

        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))

    print(f"🔍 Scanning {len(py_files)} Python files in {directory}...")

    # Extract functions from all files
    for py_file in py_files:
        blocks = extract_functions(py_file)
        all_blocks.extend(blocks)

    print(f"📊 Extracted {len(all_blocks)} function blocks")

    # Find duplicates
    duplicates: list[DuplicateGroup] = []
    visited = set()

    for i, block1 in enumerate(all_blocks):
        if i in visited:
            continue

        group = DuplicateGroup()
        group.blocks.append(block1)
        visited.add(i)

        for j, block2 in enumerate(all_blocks):
            if j in visited or i == j:
                continue

            # Skip if from the same file
            if block1.file_path == block2.file_path:
                continue

            # Skip if function names are different but similarity is high
            # (this catches copy-paste with minor changes)
            similarity = calculate_similarity(block1, block2)

            if similarity >= min_similarity:
                group.blocks.append(block2)
                group.similarity_score = max(group.similarity_score, similarity)
                visited.add(j)

        if len(group.blocks) > 1:
            duplicates.append(group)

    # Sort by similarity score (highest first)
    duplicates.sort(key=lambda g: g.similarity_score, reverse=True)

    return duplicates


def generate_report(
    duplicates: list[DuplicateGroup],
    output_file: str | None = None,
) -> dict[str, Any]:
    """Generate a JSON report of duplicate code findings."""
    report = {
        "total_duplicate_groups": len(duplicates),
        "total_duplicate_blocks": sum(len(g.blocks) for g in duplicates),
        "duplicates": [],
    }

    for group in duplicates:
        dup_entry = {
            "similarity_score": round(group.similarity_score, 4),
            "block_count": len(group.blocks),
            "blocks": [],
        }

        for block in group.blocks:
            rel_path = os.path.relpath(block.file_path)
            dup_entry["blocks"].append({
                "file": rel_path,
                "function": block.function_name,
                "start_line": block.start_line,
                "end_line": block.end_line,
                "line_count": block.end_line - block.start_line + 1,
                "complexity": block.complexity,
            })

        report["duplicates"].append(dup_entry)

    if output_file:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"📄 Report saved to {output_file}")

    return report


def print_summary(duplicates: list[DuplicateGroup]) -> None:
    """Print a human-readable summary of duplicate findings."""
    print("\n" + "=" * 70)
    print("🔍 DUPLICATE CODE DETECTION REPORT")
    print("=" * 70)

    if not duplicates:
        print("✅ No duplicate code found!")
        return

    print(f"\n📊 Found {len(duplicates)} duplicate groups")
    print(f"   Total duplicate blocks: {sum(len(g.blocks) for g in duplicates)}")
    print()

    for i, group in enumerate(duplicates[:20], 1):  # Show top 20
        print(f"\n  Group {i}: Similarity = {group.similarity_score:.1%}")
        for block in group.blocks:
            rel_path = os.path.relpath(block.file_path)
            print(f"    • {rel_path}:{block.start_line}-{block.end_line} "
                  f"({block.function_name}, {block.end_line - block.start_line + 1} lines)")

    if len(duplicates) > 20:
        print(f"\n  ... and {len(duplicates) - 20} more groups")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Find duplicate code in the SupremeAI 2.0 codebase"
    )
    parser.add_argument(
        "--directory", "-d",
        default="backend",
        help="Directory to scan (default: backend)",
    )
    parser.add_argument(
        "--min-lines", "-m",
        type=int,
        default=5,
        help="Minimum lines for a block to be considered (default: 5)",
    )
    parser.add_argument(
        "--min-similarity", "-s",
        type=float,
        default=0.7,
        help="Minimum similarity score (default: 0.7)",
    )
    parser.add_argument(
        "--output", "-o",
        default="reports/duplicates.json",
        help="Output file for JSON report (default: reports/duplicates.json)",
    )
    parser.add_argument(
        "--ignore", "-i",
        nargs="+",
        default=["tests", "migrations", "__pycache__", ".venv", "node_modules"],
        help="Directories to ignore",
    )

    args = parser.parse_args()

    # Find duplicates
    duplicates = find_duplicates(
        directory=args.directory,
        min_lines=args.min_lines,
        min_similarity=args.min_similarity,
        ignore_dirs=args.ignore,
    )

    # Generate report
    report = generate_report(duplicates, args.output)

    # Print summary
    print_summary(duplicates)

    # Exit with non-zero if duplicates found (for CI)
    if duplicates:
        print(f"\n⚠️  Found {len(duplicates)} duplicate groups. Consider refactoring.")
        sys.exit(1)
    else:
        print("\n✅ No duplicates found!")
        sys.exit(0)


if __name__ == "__main__":
    main()
