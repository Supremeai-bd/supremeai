#!/usr/bin/env python3
"""
Fast Secret Scanner for Pre-commit Hook
=======================================
বাংলা: শুধুমাত্র সাধারণ সিক্রেট প্যাটার্ন চেক করে - দ্রুত স্ক্যানের জন্য
"""

import re
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple

def get_staged_files() -> List[str]:
    """Get list of staged files for commit."""
    try:
        result = subprocess.run(['git', 'diff', '--cached', '--name-only'],
                                capture_output=True, text=True, check=True)
        return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except subprocess.CalledProcessError:
        print("⚠️  Not in a git repository or no staged files found.")
        return []

def fast_secret_scan(file_paths: List[str]) -> Tuple[bool, List[Tuple[str, int, str]]]:
    """Fast scan for common secret patterns in staged files."""
    # Common secret patterns that can be detected quickly
    patterns = [
        (r'(?i)(password|secret|key|token|api[_-]?key)\s*[=:]\s*["\'][^"\']{10,}', 'Potential secret/password in plain text'),
        (r'(?i)aws[_-]?(access|secret)[_=][^"\']{10,}', 'AWS credential detected'),
        (r'(?i)github[_-]?(token|key)[_=][^"\']{10,}', 'GitHub token/key detected'),
        (r'(ssh-rsa|ssh-ed25519)\s+[A-Za-z0-9+/]{20,}={0,3}\s+.*', 'SSH key detected'),
        (r'-----BEGIN (RSA|OPENSSH|DSA|EC|PGP) PRIVATE KEY-----', 'Private key detected'),
    ]

    findings = []

    for file_path in file_paths:
        if not file_path or file_path.startswith('.'):
            continue

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                for pattern, description in patterns:
                    if re.search(pattern, line):
                        findings.append((file_path, line_num, description))

        except Exception:
            # Skip binary files or unreadable files
            continue

    return len(findings) == 0, findings

def main():
    """Main function for fast secret scanning."""
    print("🔍 Running fast secret scan...")

    staged_files = get_staged_files()
    if not staged_files:
        print("✅ No staged files to scan.")
        return 0

    # Filter for text-based files
    text_files = [f for f in staged_files if any(f.endswith(ext) for ext in
                                               ['.py', '.js', '.ts', '.tsx', '.jsx', '.json',
                                                '.yaml', '.yml', '.toml', '.txt', '.md', '.env'])]

    if not text_files:
        print("✅ No text files to scan.")
        return 0

    is_clean, findings = fast_secret_scan(text_files)

    if is_clean:
        print("✅ No secrets detected in staged files.")
        return 0
    else:
        print("\n❌ Potential secrets detected:")
        for file_path, line_num, description in findings:
            print(f"  - {file_path}:{line_num}: {description}")

        print("\n⚠️  Commit blocked due to potential secrets detected.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
