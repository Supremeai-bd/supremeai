#!/usr/bin/env python3
"""TODO Management System - Automated Technical Debt Tracking

This module provides comprehensive TODO/FIXME/HACK tracking with GitHub issue
integration, CI checks, and code linking capabilities.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
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

TODO_PATTERN = re.compile(
    r"#\s*(TODO|FIXME|HACK|OPTIMIZE|DOCUMENT|TEST)\s*:\s*(.*)",
    re.IGNORECASE
)


@dataclass
class TodoItem:
    """Represents a TODO item found in the codebase."""

    tag: str
    message: str
    file_path: str
    line_number: int
    line_content: str
    detected_at: str
    github_issue_id: int | None = None
    status: str = "open"
    priority: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @property
    def github_title(self) -> str:
        """Generate GitHub issue title."""
        return f"[{self.tag}] {self.message} ({Path(self.file_path).name})"

    @property
    def github_body(self) -> str:
        """Generate GitHub issue body."""
        return (
            f"**File:** [{self.file_path}](file://{os.path.abspath(self.file_path)}#L{self.line_number})\n"
            f"**Line:** {self.line_number}\n"
            f"**Tag:** `{self.tag}`\n"
            f"**Priority:** {self.priority}\n\n"
            f"**Context:**\n```\n{self.line_content.strip()}\n```\n\n"
            f"Detected: {self.detected_at}\n\n"
            f"Please address this technical debt item."
        )


class TodoScanner:
    """Scans codebase for TODO/FIXME/HACK comments."""

    def __init__(self, scan_dirs: list[str] | None = None):
        """Initialize scanner.

        Args:
            scan_dirs: Directories to scan
        """
        self.scan_dirs = scan_dirs or SCAN_DIRS
        self.ignore_patterns = [re.compile(pat) for pat in IGNORE_PATTERNS]

    def should_ignore(self, path: str) -> bool:
        """Check if path should be ignored.

        Args:
            path: File or directory path

        Returns:
            True if should be ignored
        """
        return any(pattern.search(path) for pattern in self.ignore_patterns)

    def scan_file(self, file_path: str) -> list[TodoItem]:
        """Scan a single file for TODO comments.

        Args:
            file_path: Path to file

        Returns:
            List of TODO items found
        """
        todos = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                match = TODO_PATTERN.search(line)
                if match:
                    tag = match.group(1).upper()
                    message = match.group(2).strip()

                    # Determine priority based on tag
                    priority = "medium"
                    if tag in {"FIXME", "HACK"}:
                        priority = "high"
                    elif tag == "TODO":
                        priority = "medium"
                    elif tag in {"OPTIMIZE", "DOCUMENT", "TEST"}:
                        priority = "low"

                    todos.append(TodoItem(
                        tag=tag,
                        message=message,
                        file_path=file_path,
                        line_number=line_num,
                        line_content=line,
                        detected_at=datetime.utcnow().isoformat() + "Z",
                        priority=priority,
                    ))
        except Exception as exc:
            print(f"⚠️  Failed to scan {file_path}: {exc}", file=sys.stderr)

        return todos

    def scan_directory(self, directory: str) -> list[TodoItem]:
        """Scan directory recursively for TODO comments.

        Args:
            directory: Directory path

        Returns:
            All TODO items found
        """
        all_todos = []

        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                return []

            for file_path in dir_path.rglob("*"):
                if not file_path.is_file():
                    continue

                file_str = str(file_path)
                if self.should_ignore(file_str):
                    continue

                # Only scan code files
                if file_path.suffix not in {".py", ".ts", ".js", ".tsx", ".jsx", ".yml", ".yaml", ".md"}:
                    continue

                todos = self.scan_file(file_str)
                all_todos.extend(todos)
        except Exception as exc:
            print(f"❌ Error scanning {directory}: {exc}", file=sys.stderr)

        return all_todos

    def scan_all(self) -> list[TodoItem]:
        """Scan all configured directories.

        Returns:
            All TODO items from all directories
        """
        all_todos = []

        for scan_dir in self.scan_dirs:
            if not os.path.exists(scan_dir):
                continue

            todos = self.scan_directory(scan_dir)
            all_todos.extend(todos)

        return all_todos


class TodoManager:
    """Manages TODO items with GitHub integration."""

    def __init__(self, github_token: str | None = None, repo: str | None = None):
        """Initialize manager.

        Args:
            github_token: GitHub API token
            repo: Repository in format "owner/repo"
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.repo = repo or os.getenv("GITHUB_REPOSITORY")
        self.scanner = TodoScanner()

    def get_existing_issues(self) -> set[str]:
        """Fetch existing GitHub issues to avoid duplicates.

        Returns:
            Set of existing issue titles
        """
        if not self.github_token or not self.repo:
            return set()

        import requests

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        existing_titles = set()
        url = f"https://api.github.com/repos/{self.repo}/issues"

        try:
            # Fetch open tech-debt issues
            params = {"labels": "tech-debt", "state": "open", "per_page": 100}
            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                existing_titles = {issue["title"] for issue in response.json()}
        except Exception as exc:
            print(f"⚠️  Failed to fetch GitHub issues: {exc}", file=sys.stderr)

        return existing_titles

    def create_github_issue(self, todo: TodoItem, dry_run: bool = False) -> bool:
        """Create GitHub issue for TODO item.

        Args:
            todo: TODO item
            dry_run: If True, don't actually create issue

        Returns:
            True if successful
        """
        if not self.github_token or not self.repo:
            print("⚠️  GitHub token or repo not configured, skipping issue creation")
            return False

        import requests

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        url = f"https://api.github.com/repos/{self.repo}/issues"
        data = {
            "title": todo.github_title,
            "body": todo.github_body,
            "labels": ["tech-debt", "automated", todo.priority],
        }

        if dry_run:
            print(f"[DRY RUN] Would create issue: {todo.github_title}")
            return True

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)

            if response.status_code == 201:
                todo.github_issue_id = response.json()["id"]
                print(f"✅ Created issue #{response.json()['number']}: {todo.github_title}")
                return True
            else:
                print(f"❌ Failed to create issue: {todo.github_title} (status: {response.status_code})")
                return False
        except Exception as exc:
            print(f"❌ Error creating GitHub issue: {exc}", file=sys.stderr)
            return False

    def create_issues(self, todos: list[TodoItem], limit: int = 10, dry_run: bool = False) -> dict[str, Any]:
        """Create GitHub issues for TODO items.

        Args:
            todos: List of TODO items
            limit: Max issues to create per run
            dry_run: If True, don't actually create issues

        Returns:
            Statistics dictionary
        """
        existing_titles = self.get_existing_issues() if not dry_run else set()

        stats = {
            "total": len(todos),
            "created": 0,
            "skipped": 0,
            "failed": 0,
        }

        for todo in todos[:limit]:
            # Skip if already exists
            if todo.github_title in existing_titles:
                print(f"🔄 Skipping duplicate: {todo.github_title}")
                stats["skipped"] += 1
                continue

            # Create issue
            if self.create_github_issue(todo, dry_run=dry_run):
                stats["created"] += 1
            else:
                stats["failed"] += 1

        return stats

    def export_to_json(self, todos: list[TodoItem], output_path: str) -> None:
        """Export TODO items to JSON file.

        Args:
            todos: List of TODO items
            output_path: Output file path
        """
        data = {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "total_todos": len(todos),
            "by_tag": {},
            "by_priority": {},
            "items": [todo.to_dict() for todo in todos],
        }

        # Count by tag
        for todo in todos:
            data["by_tag"][todo.tag] = data["by_tag"].get(todo.tag, 0) + 1

        # Count by priority
        for todo in todos:
            data["by_priority"][todo.priority] = data["by_priority"].get(todo.priority, 0) + 1

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"📝 Exported {len(todos)} TODOs to {output_path}")


def main() -> None:
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TODO Management System")
    parser.add_argument("--scan", action="store_true", help="Scan codebase for TODOs")
    parser.add_argument("--create-issues", action="store_true", help="Create GitHub issues for TODOs")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no actual changes)")
    parser.add_argument("--limit", type=int, default=10, help="Max issues to create")
    parser.add_argument("--export", type=str, help="Export TODOs to JSON file")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")

    args = parser.parse_args()

    manager = TodoManager()

    # Scan for TODOs
    if args.scan or args.create_issues or args.export or args.stats:
        print("🔍 Scanning codebase for TODOs...")
        todos = manager.scanner.scan_all()
        print(f"📝 Found {len(todos)} TODO items\n")

        # Show breakdown
        by_tag: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for todo in todos:
            by_tag[todo.tag] = by_tag.get(todo.tag, 0) + 1
            by_priority[todo.priority] = by_priority.get(todo.priority, 0) + 1

        print("By Tag:")
        for tag, count in sorted(by_tag.items()):
            print(f"  {tag}: {count}")

        print("\nBy Priority:")
        for priority, count in sorted(by_priority.items(), key=lambda x: x[1], reverse=True):
            print(f"  {priority}: {count}")

        # Export if requested
        if args.export:
            manager.export_to_json(todos, args.export)

        # Show details if stats only
        if args.stats:
            print("\nHigh Priority Items:")
            for todo in sorted(todos, key=lambda t: t.priority == "high", reverse=True)[:20]:
                print(f"  [{todo.priority}] {todo.tag}: {todo.message}")
                print(f"    → {todo.file_path}:{todo.line_number}")
            sys.exit(0)

        # Create GitHub issues if requested
        if args.create_issues:
            print(f"\n🚀 Creating GitHub issues (limit: {args.limit}, dry_run: {args.dry_run})...")
            stats = manager.create_issues(todos, limit=args.limit, dry_run=args.dry_run)

            print(f"\nResults:")
            print(f"  Total TODOs: {stats['total']}")
            print(f"  Created: {stats['created']}")
            print(f"  Skipped: {stats['skipped']}")
            print(f"  Failed: {stats['failed']}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
