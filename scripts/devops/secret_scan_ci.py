#!/usr/bin/env python3
"""
Secret Scanning CI Pipeline Script
====================================

CI/CD pipeline script for automated secret scanning using SecretHunter.
Integrates with GitHub Actions for pre-commit and PR checks.

বাংলা: সিক্রেট স্ক্যানিং-এর জন্য CI/CD পাইপলাইন স্ক্রিপ্ট — SecretHunter ব্যবহার করে
প্রি-কমিট এবং PR চেকের জন্য GitHub Actions-এর সাথে ইন্টিগ্রেটেড।

Usage:
    # Scan staged files (pre-commit hook)
    python scripts/devops/secret_scan_ci.py --staged

    # Scan entire codebase (CI pipeline)
    python scripts/devops/secret_scan_ci.py --full

    # Scan specific directory
    python scripts/devops/secret_scan_ci.py --path backend/core

    # Generate pre-commit hook config
    python scripts/devops/secret_scan_ci.py --install-hook
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Ensure we can import core modules from backend directory
project_root = Path(__file__).resolve().parent.parent.parent
backend_dir = project_root / "backend"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    from core.security.secret_hunter import SecretHunter
except ImportError:
    try:
        from backend.core.security.secret_hunter import SecretHunter
    except ImportError:
        print("⚠️  Could not import SecretHunter. Ensure dependencies are installed.")
        SecretHunter = None


# ── Constants ──────────────────────────────────────────────────────────────────

# GitHub Actions output file
GITHUB_OUTPUT = os.environ.get("GITHUB_OUTPUT", "")

# Exit codes
EXIT_SUCCESS = 0
EXIT_SECRETS_FOUND = 1

# Minimum severity to fail CI
CI_FAIL_SEVERITY = "high"  # Fail on critical and high findings

# File patterns to scan
SCAN_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
    ".toml", ".env", ".sh", ".dart", ".go", ".rs", ".java", ".rb",
    ".php", ".swift", ".kt", ".cs", ".ini", ".cfg", ".conf",
}


def _is_excluded(path: Path) -> bool:
    """Mirror SecretHunter's own directory/file exclusions for staged-file scans.

    বাংলা মন্তব্য: full-codebase স্ক্যানে tests/ ও test_* ফাইল বাদ পড়ে, কিন্তু staged
    স্ক্যানে পড়ত না — ফলে স্ক্যানারের নিজের ডকুমেন্টেড fixture কী কমিট ব্লক করত।
    """
    parts = set(path.parts)
    return bool(parts & {"node_modules", "__pycache__", "tests"}) or path.name.startswith("test_")


def get_staged_files() -> list[Path]:
    """Get list of staged files from git.

    Returns:
        List of staged file paths
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parent.parent.parent,
        )
        files = [Path(f.strip()) for f in result.stdout.split("\n") if f.strip()]
        return [
            f
            for f in files
            if f.suffix in SCAN_EXTENSIONS and not _is_excluded(f)
        ]
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"⚠️  Git not available or not a git repository: {e}")
        return []


def scan_staged_files(hunter: SecretHunter) -> bool:
    """Scan only staged files for secrets.

    Args:
        hunter: SecretHunter instance

    Returns:
        True if no secrets found, False otherwise
    """
    staged_files = get_staged_files()
    if not staged_files:
        print("✅ No staged files to scan.")
        return True

    # Filter out deleted files
    existing_files = [f for f in staged_files if f.exists()]
    if not existing_files:
        return True

    print(f"🔍 Scanning {len(existing_files)} staged files for secrets...")
    findings = []

    for file_path in existing_files:
        file_findings = hunter.gitleaks.scan_file(file_path)
        findings.extend(file_findings)

    if findings:
        critical = [f for f in findings if f.severity == "critical"]
        high = [f for f in findings if f.severity == "high"]

        print(f"\n❌ SECRETS DETECTED IN STAGED FILES!")
        print(f"   Critical: {len(critical)}, High: {len(high)}")

        for f in findings:
            if f.severity in ("critical", "high"):
                print(f"\n   📁 {f.file_path}:{f.line_number}")
                print(f"   🔑 Type: {f.secret_type} (Severity: {f.severity})")
                print(f"   🔧 Fix: {f.remediation}")
                print(f"   📝 Matched: {f.matched_text[:60]}...")

        return False

    print("✅ No secrets found in staged files.")
    return True


def scan_codebase(hunter: SecretHunter, path: str | None = None) -> bool:
    """Scan the entire codebase or a specific path for secrets.

    Args:
        hunter: SecretHunter instance
        path: Specific path to scan (None = whole codebase)

    Returns:
        True if no critical/high secrets found, False otherwise
    """
    target = path or str(Path(__file__).resolve().parent.parent.parent / "backend")

    print(f"🔍 Scanning codebase: {target}")
    print("   This may take a while...")

    # Run the scan
    import asyncio

    report = asyncio.run(hunter.scan_codebase(target, use_ai=False, min_severity=CI_FAIL_SEVERITY))

    # Print summary
    findings = report.findings
    critical_count = report.summary.get("critical_count", 0)
    high_count = report.summary.get("high_count", 0)

    print(f"\n📊 Scan Report: {report.scan_id}")
    print(f"   Files scanned: {report.total_files}")
    print(f"   Total findings: {len(findings)}")
    print(f"   Critical: {critical_count}")
    print(f"   High: {high_count}")

    if findings:
        # Print top findings
        print("\n📋 Top Findings:")
        for f in findings[:10]:  # Show first 10
            severity_icon = {"critical": "🚨", "high": "⚠️", "medium": "⚡", "low": "ℹ️"}
            icon = severity_icon.get(f.severity, "❓")
            print(f"   {icon} [{f.severity.upper()}] {f.file_path}:{f.line_number}")
            print(f"      Type: {f.secret_type}")
            if f.ai_confidence > 0:
                print(f"      AI Confidence: {f.ai_confidence:.0%}")

        if findings:
            print(f"\n   ... and {len(findings) - min(10, len(findings))} more findings")

    # Set GitHub Actions output
    if GITHUB_OUTPUT:
        _set_github_output("findings_count", str(len(findings)))
        _set_github_output("critical_count", str(critical_count))
        _set_github_output("high_count", str(high_count))

    if critical_count > 0 or high_count > 0:
        print(f"\n❌ FAILED: {critical_count + high_count} critical/high secrets detected!")
        return False

    print("\n✅ PASSED: No critical or high severity secrets detected.")
    return True


def install_pre_commit_hook() -> None:
    """Install SecretHunter pre-commit hook."""
    hook_dir = Path(".git/hooks")
    hook_path = hook_dir / "pre-commit"

    if not hook_dir.exists():
        print("❌ Not a git repository. Cannot install pre-commit hook.")
        sys.exit(1)

    # Generate hook script using SecretHunter
    if SecretHunter:
        hunter = SecretHunter()
        hook_content = hunter.generate_pre_commit_hook()
    else:
        # Fallback hook content
        hook_content = """#!/bin/bash
echo "🔍 Running SecretHunter pre-commit scan..."
python scripts/devops/secret_scan_ci.py --staged
if [ $? -ne 0 ]; then
    echo "❌ Secret scan failed! Fix issues before committing."
    exit 1
fi
echo "✅ No secrets detected."
exit 0
"""

    with open(hook_path, "w", encoding="utf-8") as f:
        f.write(hook_content)

    # Make executable on Unix
    if sys.platform != "win32":
        hook_path.chmod(0o755)

    print(f"✅ Pre-commit hook installed at {hook_path}")


def _set_github_output(name: str, value: str) -> None:
    """Set GitHub Actions output variable.

    Args:
        name: Output variable name
        value: Output value
    """
    if GITHUB_OUTPUT:
        try:
            with open(GITHUB_OUTPUT, "a") as f:
                f.write(f"{name}={value}\n")
        except (OSError, IOError) as e:
            print(f"⚠️  Failed to write GitHub output: {e}")


def main() -> int:
    """Main entry point for CI secret scanning.

    Returns:
        Exit code (0 = success, 1 = secrets found)
    """
    parser = argparse.ArgumentParser(
        description="SecretHunter CI — Automated Secret Scanning Pipeline",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Scan only staged files (pre-commit use case)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Scan entire codebase (CI pipeline use case)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Scan specific path",
    )
    parser.add_argument(
        "--install-hook",
        action="store_true",
        help="Install pre-commit hook",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    # Handle hook installation
    if args.install_hook:
        install_pre_commit_hook()
        return EXIT_SUCCESS

    # Ensure SecretHunter is available
    if SecretHunter is None:
        print("❌ SecretHunter not available. Install dependencies first.")
        return EXIT_SECRETS_FOUND

    hunter = SecretHunter()

    # Handle staged file scan
    if args.staged:
        success = scan_staged_files(hunter)
        return EXIT_SUCCESS if success else EXIT_SECRETS_FOUND

    # Handle full/partial scan
    if args.full or args.path:
        success = scan_codebase(hunter, args.path)
        return EXIT_SUCCESS if success else EXIT_SECRETS_FOUND

    # No mode selected — show help
    parser.print_help()
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
