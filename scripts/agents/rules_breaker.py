#!/usr/bin/env python3
"""Rules Breaker Agent — Red Team / Pentest Scanner (#2574).

This agent proactively hunts for vulnerabilities and policy violations
in the SupremeAI codebase and opens GitHub issues for each finding.

Scope (audit-only, no code changes):
  1. Secret hardcoding / credential leaks
  2. Localhost / 127.0.0.1 / Windows-path binding in production code
  3. Unsafe privilege elevation / sudo / admin bypass patterns
  4. Silent exception swallowing (pass-only handlers)
  5. Missing backend authorization (client-side-only guards)
  6. Test manipulation (delete/skip/fake assertions)
  7. Direct main-branch push from bot
  8. Self-approval / self-merge patterns
  9. Missing 3-tier verification hooks
  10. Docs garbage (new .md outside allowlist)

Usage:
    python scripts/agents/rules_breaker.py --agent-name rules-breaker-1
    python scripts/agents/rules_breaker.py --agent-name rules-breaker-1 --limit 20
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        **kwargs,
    )


def gh_issue_create(title: str, body: str, labels: list[str]) -> None:
    cmd = [
        "gh", "issue", "create",
        "--repo", REPO,
        "--title", title,
        "--body", body,
    ]
    for label in labels:
        cmd.extend(["--label", label])
    res = run(cmd)
    if res.returncode == 0:
        print(f"  ✅ Created issue: {title}")
    else:
        print(f"  ❌ Failed to create issue: {res.stderr}")


# ============================================================================
# Scanner modules
# ============================================================================

def scan_secret_hardcoding(limit: int) -> list[dict]:
    """Detect hardcoded API keys, tokens, passwords, private keys."""
    findings = []
    patterns = [
        (r'(?i)(api_key|apikey|api_secret|secret_key|private_key|access_key)\s*[:=]\s*["\']([A-Za-z0-9_\-]{20,})["\']', "Hardcoded API key/secret"),
        (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\'][^"\']{8,}["\']', "Hardcoded password"),
        (r'["\'](sk-[A-Za-z0-9]{20,})["\']', "Potential Stripe/OpenAI secret key"),
        (r'["\'](ghp_[A-Za-z0-9]{36})["\']', "Potential GitHub personal access token"),
        (r'["\'](AKIA[A-Z0-9]{16})["\']', "Potential AWS access key ID"),
        (r'["\']([0-9a-f]{32,})["\']', "Potential hardcoded hex token/secret"),
    ]
    exts = {".py", ".ts", ".js", ".json", ".yml", ".yaml", ".env", ".toml"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git", "backend/.venv"}

    files_scanned = 0
    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            if ".venv" in str(fpath) or "node_modules" in str(fpath):
                continue
            files_scanned += 1
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pattern, desc in patterns:
                for m in re.finditer(pattern, text):
                    line_no = text[:m.start()].count("\n") + 1
                    snippet = text[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
                    findings.append({
                        "file": str(fpath.relative_to(ROOT_DIR)),
                        "line": line_no,
                        "snippet": snippet,
                        "rule": "security.rule_002",
                        "severity": "BLOCK",
                        "description": f"[Secret Hardcoding] {desc} detected",
                    })
                    if len(findings) >= limit:
                        return findings
    return findings


def scan_localhost_binding(limit: int) -> list[dict]:
    """Detect localhost/127.0.0.1/Windows-path binding outside tests."""
    findings = []
    patterns = [
        (r'(?i)(localhost|127\.0\.0\.1|0\.0\.0\.0)', "Localhost/IP binding"),
        (r'(?i)(C:\\\\|D:\\\\|E:\\\\|/mnt/c/)', "Windows path binding"),
    ]
    exts = {".py", ".ts", ".js", ".json"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git", "tests", "test"}

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                if line.strip().startswith("#"):
                    continue
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "architecture.rule_001",
                            "severity": "BLOCK",
                            "description": f"[Localhost/Windows Binding] {desc} in production code",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


def scan_silent_failures(limit: int) -> list[dict]:
    """Detect pass-only exception handlers."""
    findings = []
    exts = {".py"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git"}

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if re.match(r'^\s*except\b.*:\s*$', line):
                    # Check if next non-empty line is just 'pass'
                    j = i
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if next_line and not next_line.startswith("#"):
                            if next_line == "pass":
                                findings.append({
                                    "file": str(fpath.relative_to(ROOT_DIR)),
                                    "line": i,
                                    "snippet": line.strip()[:120],
                                    "rule": "reliability.rule_001",
                                    "severity": "BLOCK",
                                    "description": "Silent failure: bare except with pass-only handler",
                                })
                                if len(findings) >= limit:
                                    return findings
                            break
                        j += 1
    return findings


def scan_test_manipulation(limit: int) -> list[dict]:
    """Detect test delete/skip/fake assertion patterns."""
    findings = []
    patterns = [
        (r'@pytest\.mark\.skip', "pytest skip decorator"),
        (r'@pytest\.mark\.xfail', "pytest xfail decorator"),
        (r'def test_[^()]*\(.*\):\s*pass\s*$', "Empty test body (pass only)"),
        (r'assert\s+False\s*#', "Fake assertion"),
        (r'#\s*TODO.*test', "Skipped test TODO"),
    ]
    exts = {".py"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git"}

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if "test" not in fpath.name.lower() and fpath.suffix.lower() != ".py":
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "gates.test_guard_gate",
                            "severity": "BLOCK",
                            "description": f"[Test Manipulation] {desc}",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


def scan_docs_garbage(limit: int) -> list[dict]:
    """Detect new .md docs outside allowlist."""
    findings = []
    allowed = {
        "docs/master_docs", "docs/agents", "docs/architecture", "docs/archive",
        "docs/governance", "docs/INDEX.md", "docs/ROADMAP.md",
    }
    for fpath in ROOT_DIR.rglob("*.md"):
        rel = str(fpath.relative_to(ROOT_DIR))
        if any(rel.startswith(a) for a in allowed):
            continue
        if ".venv" in rel or "node_modules" in rel or ".git" in rel:
            continue
        # Flag non-canonical docs
        findings.append({
            "file": rel,
            "line": 1,
            "snippet": rel,
            "rule": "gates.docs_garbage",
            "severity": "WARN",
            "description": "Docs garbage: .md file outside canonical allowlist",
        })
        if len(findings) >= limit:
            return findings
    return findings


def scan_privilege_elevation(limit: int) -> list[dict]:
    """Detect sudo/admin privilege elevation patterns."""
    findings = []
    patterns = [
        (r'(?i)(sudo\s+|runas\s+|elevat\w*\s*\(|ShellExecute.*runas|admin.*privilege|setuid|seteuid)', "Privilege elevation"),
    ]
    exts = {".py", ".ts", ".js", ".ps1", ".sh", ".bat", ".cmd"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git"}

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                if line.strip().startswith("#"):
                    continue
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "security.rule_003",
                            "severity": "BLOCK",
                            "description": f"[Privilege Elevation] {desc} pattern detected",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


def scan_client_side_auth(limit: int) -> list[dict]:
    """Detect client-side-only authorization patterns."""
    findings = []
    patterns = [
        (r'(?i)(if\s*\(.*role\s*==|if\s*\(.*isAdmin|if\s*\(.*isLoggedIn|window\.location\.replace.*login)', "Client-side auth check"),
    ]
    exts = {".ts", ".tsx", ".js", ".jsx"}
    exclude_dirs = {"node_modules", "__pycache__", ".git", ".venv"}

    for root, dirs, files in os.walk(ROOT_DIR / "frontend"):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "security.rule_001",
                            "severity": "WARN",
                            "description": f"[Client-Side Auth] {desc} — backend enforcement missing?",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


# ============================================================================
# Attack simulation modules (safe, read-only probes)
# ============================================================================

def probe_sql_injection_patterns(limit: int) -> list[dict]:
    """Look for raw SQL string concatenation or f-string SQL."""
    findings = []
    patterns = [
        (r'(?i)(execute|executemany|cursor\.execute)\s*\(.*f["\']', "f-string SQL execution"),
        (r'(?i)(execute|executemany)\s*\(.*\+.*\+', "String-concatenated SQL"),
        (r'(?i)SELECT.*FROM.*WHERE.*\+', "Concatenated WHERE clause"),
    ]
    exts = {".py"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git"}

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                if line.strip().startswith("#"):
                    continue
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "security.rule_001",
                            "severity": "BLOCK",
                            "description": f"[SQL Injection Risk] {desc} — parameterized queries required",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


def probe_path_traversal_patterns(limit: int) -> list[dict]:
    """Look for unsanitized file path joins with user input."""
    findings = []
    patterns = [
        (r'(?i)(os\.path\.join|Path\().*request\.(args|params|query|body|form)', "User input in path join"),
        (r'(?i)(open|Path)\(.*\+.*request', "User input in file open"),
    ]
    exts = {".py", ".ts", ".js"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git"}

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "security.rule_001",
                            "severity": "BLOCK",
                            "description": f"[Path Traversal Risk] {desc} — sanitize paths before join/open",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


def probe_xss_patterns(limit: int) -> list[dict]:
    """Look for unsafe innerHTML / dangerouslySetInnerHTML without sanitization."""
    findings = []
    patterns = [
        (r'(?i)(innerHTML\s*=|dangerouslySetInnerHTML)', "Unsafe HTML injection"),
        (r'(?i)(\.html\(.*request\.|\.html\(.*user)', "User-controlled HTML rendering"),
    ]
    exts = {".ts", ".tsx", ".js", ".jsx"}
    exclude_dirs = {"node_modules", "__pycache__", ".git", ".venv"}

    for root, dirs, files in os.walk(ROOT_DIR / "frontend"):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "security.rule_001",
                            "severity": "WARN",
                            "description": f"[XSS Risk] {desc} — sanitize before rendering",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


def probe_auth_bypass(limit: int) -> list[dict]:
    """Look for missing auth decorators on sensitive routes."""
    findings = []
    patterns = [
        (r'@app\.(get|post|put|delete|patch)\s*\(.*\)\s*\n\s*def\s+\w+\(', "Missing auth decorator on route"),
    ]
    exts = {".py"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git"}

    for root, dirs, files in os.walk(ROOT_DIR / "backend"):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pattern, desc in patterns:
                for m in re.finditer(pattern, text):
                    line_no = text[:m.start()].count("\n") + 1
                    route_line = text[m.start():m.end()].splitlines()[0]
                    findings.append({
                        "file": str(fpath.relative_to(ROOT_DIR)),
                        "line": line_no,
                        "snippet": route_line.strip()[:120],
                        "rule": "security.rule_001",
                        "severity": "BLOCK",
                        "description": f"[Auth Bypass Risk] {desc} — ensure backend auth enforced",
                    })
                    if len(findings) >= limit:
                        return findings
    return findings


def probe_insecure_deserialization(limit: int) -> list[dict]:
    """Look for pickle.loads / yaml.load / eval on untrusted input."""
    findings = []
    patterns = [
        (r'(?i)(pickle\.loads?|yaml\.load\(.*Loader=None|eval\(|exec\(|compile\(.*input)', "Insecure deserialization/eval"),
    ]
    exts = {".py", ".ts", ".js"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git"}

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                if line.strip().startswith("#"):
                    continue
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "security.rule_003",
                            "severity": "BLOCK",
                            "description": f"[Insecure Deserialization] {desc} — use safe alternatives",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


def probe_cors_misconfiguration(limit: int) -> list[dict]:
    """Look for overly permissive CORS (allow_all origins)."""
    findings = []
    patterns = [
        (r'(?i)(allow_origins\s*=\s*\["\*"\]|allow_all|Access-Control-Allow-Origin.*\*)', "Permissive CORS"),
    ]
    exts = {".py", ".ts", ".js"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git"}

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "security.rule_001",
                            "severity": "WARN",
                            "description": f"[CORS Misconfiguration] {desc} — restrict origins explicitly",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


def probe_log_injection(limit: int) -> list[dict]:
    """Look for unsanitized user input in log/print statements."""
    findings = []
    patterns = [
        (r'(?i)(print\(.*request\.|logger\.(info|debug|warn|error)\(.*request\.|logging\.\w+\(.*request\.)', "User input in log/print"),
    ]
    exts = {".py", ".ts", ".js"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git"}

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "reliability.rule_002",
                            "severity": "WARN",
                            "description": f"[Log Injection] {desc} — sanitize before logging",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


def probe_self_merge_patterns(limit: int) -> list[dict]:
    """Look for self-approval or self-merge in automation scripts."""
    findings = []
    patterns = [
        (r'(?i)(self_merge|self-merge|self_approv|approve.*own|merge.*own)', "Self-merge/approve pattern"),
    ]
    exts = {".py", ".sh", ".yml", ".yaml"}
    exclude_dirs = {".venv", "node_modules", "__pycache__", ".git"}

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in exts:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                if line.strip().startswith("#"):
                    continue
                for pattern, desc in patterns:
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(fpath.relative_to(ROOT_DIR)),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "rule": "gates.self_merge_gate",
                            "severity": "BLOCK",
                            "description": f"[Self-Merge Risk] {desc} — prohibited by constitution",
                        })
                        if len(findings) >= limit:
                            return findings
    return findings


# ============================================================================
# Issue creation
# ============================================================================

def create_issue_for_finding(f: dict, scan_type: str, agent_name: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    severity_icon = {"BLOCK": "🔴", "WARN": "🟡", "INFO": "🔵"}.get(f["severity"], "⚪")
    title = f"[{scan_type}] {severity_icon} {f['severity']} — {f['description']} ({f['file']}:{f['line']})"
    body = f"""## 🔴 Rules Breaker Finding

| Field | Value |
| :--- | :--- |
| **Scan Type** | `{scan_type}` |
| **Severity** | `{f['severity']}` |
| **Rule Violated** | `{f['rule']}` |
| **File** | `{f['file']}` |
| **Line** | `{f['line']}` |
| **Snippet** | `{f['snippet']}` |
| **Agent** | `{agent_name}` |
| **Scan Time** | `{now}` |

### Description
{f['description']}

### Remediation
Please review and fix this vulnerability. Reference the rule ID above for the constitutional requirement.

---
_Auto-generated by `rules_breaker.py` — Red Team Pentest Agent_
"""
    gh_issue_create(title, body, ["vulnerability", "rules-breaker", f"severity:{f['severity'].lower()}"])


def run_scans(limit: int, agent_name: str) -> None:
    scanners = [
        ("secret-hardcoding", scan_secret_hardcoding),
        ("localhost-binding", scan_localhost_binding),
        ("silent-failures", scan_silent_failures),
        ("test-manipulation", scan_test_manipulation),
        ("docs-garbage", scan_docs_garbage),
        ("privilege-elevation", scan_privilege_elevation),
        ("client-side-auth", scan_client_side_auth),
        ("sql-injection", probe_sql_injection_patterns),
        ("path-traversal", probe_path_traversal_patterns),
        ("xss-risk", probe_xss_patterns),
        ("auth-bypass", probe_auth_bypass),
        ("insecure-deserialization", probe_insecure_deserialization),
        ("cors-misconfig", probe_cors_misconfiguration),
        ("log-injection", probe_log_injection),
        ("self-merge", probe_self_merge_patterns),
    ]

    total_findings = 0
    print(f"🔴 Starting Rules Breaker scan: agent={agent_name}, limit={limit}")
    print(f"   Scanners: {len(scanners)}")
    print()

    for scan_name, scanner in scanners:
        findings = scanner(limit)
        if not findings:
            print(f"  ✅ {scan_name}: clean")
            continue
        print(f"  ⚠️  {scan_name}: {len(findings)} finding(s)")
        for f in findings:
            create_issue_for_finding(f, scan_name, agent_name)
            total_findings += 1
            if total_findings >= limit:
                print(f"\n🛑 Reached limit of {limit} issues. Stopping.")
                return

    print(f"\n✅ Scan complete. Total issues created: {total_findings}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rules Breaker Agent — Red Team Pentest Scanner")
    parser.add_argument("--agent-name", required=True, help="Agent identifier (e.g. rules-breaker-1)")
    parser.add_argument("--limit", type=int, default=20, help="Max issues to create per run")
    args = parser.parse_args()

    run_scans(args.limit, args.agent_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
