#!/usr/bin/env python3
"""
check_hardcoded_deployment_config.py
Scans the codebase for hardcoded production hostnames (e.g. .onrender.com).
Enforces zero-hardcode configuration policy.
"""

import os
import re
import sys
from pathlib import Path

# Directories/files to skip
IGNORE_PATHS = {
    "node_modules",
    "dist",
    "dist-admin",
    "dist-user",
    ".playwright-mcp",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "tests",
    "docs",
    "scripts/ci",
    "scripts/docs",
    "scripts/patches",
    "scripts/advanced_analysis",
    ".env.example",
    ".env",
    ".kilo",
    "secrets_registry.yaml",
    "README.md",
    "AGENTS.md",
    "STATUS.md",
    "CHECKPOINT.md",
    "REAL_TESTING_LOG.md",
    "ERROR_AUDIT.md",
    "reports",
    "specs",
    "audit_reports",
    ".agents",
    "_archive",
    ".github/workflows",
    "firebase.json",
    "htmlcov",
    "scripts/archive",
    "out"
}

# File suffixes that are test fixtures — these intentionally reference
# deployment hostnames to simulate different environments and are not
# themselves hardcoded production configuration.
IGNORE_SUFFIXES = (
    ".test.ts",
    ".test.tsx",
    ".spec.ts",
    ".spec.tsx",
)

# The patterns we want to catch
BANNED_PATTERNS = [
    r"\.onrender\.com",
    r"\.web\.app",
    r"\.firebaseapp\.com",
    r"\.vercel\.app",
    r"supreme-admin-\d+-prod" # hardcoded passwords
]

BANNED_REGEX = re.compile("|".join(BANNED_PATTERNS), re.IGNORECASE)

# Allowed exceptions (File path, Line matching regex)
EXCEPTIONS = [
    # Example: ("frontend/src/api.ts", r"// Legacy endpoint: .*\.onrender\.com")
    (".github/scripts/ci_summary_v2.py", r"\.onrender\.com"),
    # Pydantic Field() docstring examples — illustrative only, not a runtime default.
    ("backend/core/config_validator.py", r"examples="),
    # CSP allow-list uses wildcard host patterns (e.g. https://*.web.app), not a
    # specific deployment hostname, and must stay inline in the HTML head.
    ("frontend/index.html", r"Content-Security-Policy"),
]

def should_ignore(path: Path, root: Path) -> bool:
    try:
        rel_path = path.relative_to(root).as_posix()
    except ValueError:
        return True
    
    # We also ignore artifacts/logs
    if ".system_generated" in rel_path or ".gemini" in rel_path:
        return True

    if rel_path.endswith(IGNORE_SUFFIXES):
        return True

    path_parts = Path(rel_path).parts
    for ignore in IGNORE_PATHS:
        if rel_path.startswith(ignore) or rel_path == ignore:
            return True
        # Match a whole path segment (e.g. "tests" matches "backend/tests/x.py")
        if ignore in path_parts:
            return True
        # Match by filename anywhere in the tree (e.g. "REAL_TESTING_LOG.md")
        if path.name == ignore:
            return True
    return False

def scan_file(filepath: Path, root: Path) -> list[str]:
    violations = []
    try:
        rel_path = filepath.relative_to(root).as_posix()
        content = filepath.read_text(encoding="utf-8")
        
        for line_num, line in enumerate(content.splitlines(), 1):
            if BANNED_REGEX.search(line):
                # Check exceptions
                is_exception = False
                for ex_file, ex_pattern in EXCEPTIONS:
                    if ex_file == rel_path and re.search(ex_pattern, line):
                        is_exception = True
                        break
                
                if not is_exception:
                    violations.append(f"  ❌ Line {line_num}: {line.strip()}")
                    
    except Exception as e:
        # Ignore binary files or unreadable files
        _ = e
    return violations

def main():
    import sys
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    root = Path(__file__).resolve().parent.parent.parent
    has_errors = False
    
    print("🔍 Scanning codebase for hardcoded deployment configuration...")
    
    for root_dir, dirs, files in os.walk(root):
        # Filter directories in-place to avoid traversing ignored paths
        dirs[:] = [d for d in dirs if not should_ignore(Path(root_dir) / d, root)]
        
        for file in files:
            filepath = Path(root_dir) / file
            if should_ignore(filepath, root):
                continue
                
            # Only check likely source files
            if filepath.suffix not in {'.py', '.ts', '.tsx', '.js', '.jsx', '.json', '.yml', '.yaml', '.html', '.sh', '.md', ''}:
                continue
                
            violations = scan_file(filepath, root)
            if violations:
                has_errors = True
                print(f"\n📄 {filepath.relative_to(root)}:")
                for v in violations:
                    print(v)
                    
    if has_errors:
        print("\n🚨 Hardcoded deployment configuration detected! CI failed.")
        print("Please move these values to environment variables/Settings.")
        sys.exit(1)
    else:
        print("\n✅ PASS: No hardcoded deployment configuration found.")
        sys.exit(0)

if __name__ == "__main__":
    main()
