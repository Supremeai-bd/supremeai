#!/usr/bin/env python3
"""Broad Exception Refactoring Tool

This script identifies and helps refactor broad 'except Exception:' blocks
to use specific exception types, improving code quality and error handling.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Configuration
SCAN_DIRS = ["backend", "apps", "scripts", "packages", "tools"]
IGNORE_PATTERNS = [
    r"\.venv",
    r"node_modules",
    r"\.git",
    r"__pycache__",
    r"\.pytest_cache",
    r"\.mypy_cache",
    r"\.ruff_cache",
    r"tests",
    r"docs",
]

# Common exception type mappings based on context
EXCEPTION_SUGGESTIONS = {
    # I/O operations
    "open(": ["FileNotFoundError", "PermissionError", "OSError"],
    "read(": ["FileNotFoundError", "PermissionError", "OSError"],
    "write(": ["PermissionError", "OSError"],
    # JSON operations
    "json.load": ["json.JSONDecodeError", "ValueError"],
    "json.dump": ["TypeError", "ValueError"],
    # Database
    "execute(": ["DatabaseError", "SQLAlchemyError"],
    "commit(": ["DatabaseError", "SQLAlchemyError"],
    # HTTP/Network
    "requests.": ["requests.RequestException", "ConnectionError", "Timeout"],
    "fetch(": ["Exception"],  # Generic for now
    # Redis
    "redis.": ["redis.ConnectionError", "redis.TimeoutError"],
    # Time/Date
    "datetime": ["ValueError", "TypeError"],
    # Type conversions
    "int(": ["ValueError", "TypeError"],
    "float(": ["ValueError", "TypeError"],
    # List/Dict operations
    "get(": ["KeyError", "AttributeError"],
    "append(": ["AttributeError"],
}


@dataclass
class BroadException:
    """Represents a broad exception handler found in code."""

    file_path: str
    line_number: int
    line_content: str
    context_lines: list[str]
    suggested_exceptions: list[str]
    confidence: float  # 0.0 to 1.0


class BroadExceptionVisitor(ast.NodeVisitor):
    """AST visitor to find broad exception handlers."""

    def __init__(self):
        """Initialize visitor."""
        self.broad_exceptions: list[BroadException] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Visit exception handlers."""
        if node.type is None or (isinstance(node.type, ast.Name) and node.type.id == "Exception"):
            # Found broad except
            self.broad_exceptions.append(
                BroadException(
                    file_path="",  # Set externally
                    line_number=node.lineno,
                    line_content="",  # Set externally
                    context_lines=[],
                    suggested_exceptions=self._suggest_exceptions(""),
                    confidence=0.5,
                )
            )

        self.generic_visit(node)

    def _suggest_exceptions(self, context: str) -> list[str]:
        """Suggest specific exceptions based on context.

        Args:
            context: Code context

        Returns:
            List of suggested exception types
        """
        suggestions = set()

        # Check context against known patterns
        for pattern, exc_types in EXCEPTION_SUGGESTIONS.items():
            if pattern in context:
                suggestions.update(exc_types)

        # Default suggestions if no matches
        if not suggestions:
            suggestions = {"Exception"}

        return sorted(suggestions)


def find_broad_exceptions(file_path: str) -> list[BroadException]:
    """Find broad exception handlers in a file.

    Args:
        file_path: Path to Python file

    Returns:
        List of broad exception handlers
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")

        tree = ast.parse(content)
        visitor = BroadExceptionVisitor()
        visitor.visit(tree)

        # Enhance with line content and context
        for exc in visitor.broad_exceptions:
            exc.file_path = file_path
            exc.line_content = lines[exc.line_number - 1] if exc.line_number <= len(lines) else ""

            # Get context (3 lines before and after)
            start = max(0, exc.line_number - 4)
            end = min(len(lines), exc.line_number + 3)
            exc.context_lines = lines[start:end]

            # Update suggestions based on actual context
            context = "\n".join(exc.context_lines)
            exc.suggested_exceptions = _suggest_exceptions_from_context(context)

        return visitor.broad_exceptions

    except SyntaxError:
        return []
    except Exception as exc:
        print(f"⚠️  Error parsing {file_path}: {exc}", file=sys.stderr)
        return []


def _suggest_exceptions_from_context(context: str) -> list[str]:
    """Suggest specific exceptions based on code context.

    Args:
        context: Code context

    Returns:
        List of suggested exception types
    """
    suggestions = set()
    context_lower = context.lower()

    # I/O operations
    if any(x in context for x in ["open(", "read(", "write(", "Path("]):
        suggestions.update(["FileNotFoundError", "PermissionError", "OSError"])

    # JSON operations
    if "json.load" in context or "json.dump" in context:
        suggestions.update(["json.JSONDecodeError", "ValueError", "TypeError"])

    # Database
    if "execute" in context or "commit" in context:
        suggestions.update(["DatabaseError", "SQLAlchemyError"])

    # HTTP/Network
    if "requests." in context or "fetch(" in context:
        suggestions.update(["requests.RequestException", "ConnectionError", "TimeoutError"])

    # Type conversions
    if "int(" in context or "float(" in context:
        suggestions.update(["ValueError", "TypeError"])

    # Dictionary/List access
    if ".get(" in context or "[" in context:
        suggestions.update(["KeyError", "IndexError", "AttributeError"])

    # Redis
    if "redis" in context_lower:
        suggestions.update(["redis.ConnectionError", "redis.TimeoutError"])

    # Default to Exception if no specific matches
    if not suggestions:
        suggestions = {"Exception"}

    return sorted(suggestions)


def scan_directory(directory: str) -> list[BroadException]:
    """Scan directory for broad exception handlers.

    Args:
        directory: Directory path

    Returns:
        List of all broad exception handlers
    """
    all_exceptions = []
    dir_path = Path(directory)

    if not dir_path.exists():
        return []

    for file_path in dir_path.rglob("*.py"):
        # Skip ignored directories
        if any(pattern in str(file_path) for pattern in IGNORE_PATTERNS):
            continue

        exceptions = find_broad_exceptions(str(file_path))
        all_exceptions.extend(exceptions)

    return all_exceptions


def generate_refactored_code(broad_exc: BroadException) -> str:
    """Generate refactored exception handler code.

    Args:
        broad_exc: Broad exception to refactor

    Returns:
        Refactored code suggestion
    """
    original = broad_exc.line_content.strip()

    # Detect indentation
    indent = len(original) - len(original.lstrip())
    indent_str = original[:indent]

    # Generate specific exception handling
    suggested = ", ".join(broad_exc.suggested_exceptions[:3])  # Top 3 suggestions

    # Create refactored version
    refactored = f"{indent_str}except ({suggested}) as exc:"

    return refactored


def main() -> None:
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Broad Exception Refactoring Tool")
    parser.add_argument("--scan", type=str, help="Scan specific directory")
    parser.add_argument("--file", type=str, help="Scan specific file")
    parser.add_argument("--output", type=str, help="Output report to JSON file")
    parser.add_argument("--suggest-refactor", action="store_true", help="Suggest refactored code")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Minimum confidence threshold")

    args = parser.parse_args()

    all_exceptions = []

    if args.file:
        all_exceptions = find_broad_exceptions(args.file)
    elif args.scan:
        all_exceptions = scan_directory(args.scan)
    else:
        # Scan all configured directories
        for scan_dir in SCAN_DIRS:
            if Path(scan_dir).exists():
                all_exceptions.extend(scan_directory(scan_dir))

    # Filter by confidence
    all_exceptions = [exc for exc in all_exceptions if exc.confidence >= args.min_confidence]

    print(f"\n🔍 Found {len(all_exceptions)} broad exception handlers\n")

    # Group by file
    by_file: dict[str, list[BroadException]] = {}
    for exc in all_exceptions:
        by_file.setdefault(exc.file_path, []).append(exc)

    # Display results
    for file_path, exceptions in sorted(by_file.items()):
        print(f"\n📄 {file_path}")
        print("=" * 80)

        for exc in sorted(exceptions, key=lambda e: e.line_number):
            print(f"\n  Line {exc.line_number}: {exc.line_content.strip()}")
            print(f"  Suggested exceptions: {', '.join(exc.suggested_exceptions)}")
            print(f"  Confidence: {exc.confidence:.0%}")

            if args.suggest_refactor:
                refactored = generate_refactored_code(exc)
                print(f"\n  Suggested refactor:")
                print(f"    {refactored}")
                print(f"    # TODO: Add specific exception handling")

    # Export if requested
    if args.output:
        import json

        report = {
            "timestamp": "2026-07-27",
            "total_broad_exceptions": len(all_exceptions),
            "by_file": {
                file: [
                    {
                        "line": exc.line_number,
                        "content": exc.line_content.strip(),
                        "suggestions": exc.suggested_exceptions,
                        "confidence": exc.confidence,
                        "refactored_code": generate_refactored_code(exc) if args.suggest_refactor else None,
                    }
                    for exc in exceptions
                ]
                for file, exceptions in by_file.items()
            },
        }

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print(f"\n📝 Report exported to {args.output}")

    # Summary
    print(f"\n📊 Summary:")
    print(f"  Total broad exceptions: {len(all_exceptions)}")
    print(f"  Files affected: {len(by_file)}")


if __name__ == "__main__":
    main()
