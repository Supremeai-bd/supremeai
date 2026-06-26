#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

FAILED_JOBS_RAW = os.environ.get("FAILED_JOBS", "[]")
BRANCH = os.environ.get("BRANCH", "main")

try:
    FAILED_JOBS = json.loads(FAILED_JOBS_RAW)
except json.JSONDecodeError:
    FAILED_JOBS = []
FIXES_COMMITTED = False

FIXES_APPLIED = []

# ═══════════════════════════════════════════════════════════════
# DIFF GUARD — Limits on auto-fix scope (Phase 1 Safety Layer)
# ═══════════════════════════════════════════════════════════════
MAX_FILES_CHANGED = int(os.environ.get("MAX_FILES_CHANGED", "10"))
MAX_LINES_CHANGED = int(os.environ.get("MAX_LINES_CHANGED", "300"))

# Structural patterns — block if LOGIC changes in these paths
CRITICAL_FILE_PATTERNS = [
    "alembic/versions/",      # DB migration scripts
    "core/auth/",             # Authentication logic
    "core/security/",         # Security logic
    "core/config.py",         # Core configuration
    ".env",                   # Environment secrets
    "secrets",                # Secret files
]

# These patterns in critical dirs are safe (formatting/init only)
ALLOW_COSMETIC_PATTERNS = [
    "__init__.py",            # Package markers
    ".pyi",                   # Type stubs
]


def run_cmd(cmd, cwd=None, check=False):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            cmd,
            output=result.stdout,
            stderr=result.stderr,
        )

    return result


def ensure_init_files(base_path: Path):
    if not base_path.exists():
        return

    for subdir in base_path.rglob("*"):
        if not subdir.is_dir():
            continue
        python_files = list(subdir.glob("*.py"))
        if not python_files:
            continue
        init_file = subdir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# Auto-generated package marker\n")
            FIXES_APPLIED.append(f"created {init_file}")


def fix_backend():
    backend_dir = Path("backend")
    if not backend_dir.exists():
        print("⚠️ backend/ directory not found")
        return

    ruff_result = run_cmd(["poetry", "run", "ruff", "check", ".", "--fix"], cwd=str(backend_dir))
    if ruff_result.returncode == 0 or "fixed" in (ruff_result.stdout + ruff_result.stderr).lower():
        FIXES_APPLIED.append("ruff check --fix")

    black_result = run_cmd(["poetry", "run", "black", "."], cwd=str(backend_dir))
    if black_result.returncode == 0:
        FIXES_APPLIED.append("black .")

    for sub in ["core", "brain", "api", "memory", "tools"]:
        ensure_init_files(backend_dir / sub)

    lock_result = run_cmd(["poetry", "lock", "--no-update"], cwd=str(backend_dir))
    if lock_result.returncode == 0:
        status = run_cmd(["git", "status", "--porcelain", "backend/poetry.lock"])
        if status.stdout.strip():
            FIXES_APPLIED.append("poetry lock --no-update")

    run_cmd(["poetry", "run", "ruff", "check", ".", "--select", "I", "--fix"], cwd=str(backend_dir))


def fix_frontend(pkg_dir: str):
    path = Path(pkg_dir)
    if not path.exists():
        print(f"⚠️ {pkg_dir}/ not found")
        return

    eslint_result = run_cmd(["pnpm", "exec", "eslint", pkg_dir, "--fix"])
    if eslint_result.returncode == 0 or "fixed" in (eslint_result.stdout + eslint_result.stderr).lower():
        FIXES_APPLIED.append(f"eslint {pkg_dir} --fix")

    prettier_result = run_cmd(["pnpm", "exec", "prettier", "--write", pkg_dir])
    if prettier_result.returncode == 0:
        FIXES_APPLIED.append(f"prettier --write {pkg_dir}")

    pnpm_result = run_cmd(["pnpm", "install", "--no-frozen-lockfile"])
    if pnpm_result.returncode == 0:
        status = run_cmd(["git", "status", "--porcelain", "pnpm-lock.yaml"])
        if status.stdout.strip():
            FIXES_APPLIED.append("pnpm install --no-frozen-lockfile")


def fix_mobile():
    mobile_dir = Path("apps/mobile")
    if not mobile_dir.exists():
        print("⚠️ apps/mobile/ not found")
        return

    dart_result = run_cmd(["dart", "fix", "--apply"], cwd=str(mobile_dir))
    if dart_result.returncode == 0:
        FIXES_APPLIED.append("dart fix --apply")

    format_result = run_cmd(["dart", "format", "."], cwd=str(mobile_dir))
    if format_result.returncode == 0:
        FIXES_APPLIED.append("dart format .")

    pub_result = run_cmd(["flutter", "pub", "get"], cwd=str(mobile_dir))
    if pub_result.returncode == 0:
        status = run_cmd(["git", "status", "--porcelain", "apps/mobile/pubspec.lock"])
        if status.stdout.strip():
            FIXES_APPLIED.append("flutter pub get")


JOB_FIXERS = {
    "backend-test": fix_backend,
    "backend_test": fix_backend,
    "🐍 Backend Tests": fix_backend,
    "studio-build": lambda: fix_frontend("apps/studio-client"),
    "studio_build": lambda: fix_frontend("apps/studio-client"),
    "🎨 Studio Client Build": lambda: fix_frontend("apps/studio-client"),
    "🎨 Studio Build": lambda: fix_frontend("apps/studio-client"),
    "webchat-build": lambda: fix_frontend("apps/web-chat"),
    "webchat_build": lambda: fix_frontend("apps/web-chat"),
    "💬 Web Chat Build": lambda: fix_frontend("apps/web-chat"),
    "💬 WebChat Build": lambda: fix_frontend("apps/web-chat"),
    "vscode-build": lambda: fix_frontend("tools/vscode-extension"),
    "vscode_build": lambda: fix_frontend("tools/vscode-extension"),
    "🧩 VS Code Extension Build": lambda: fix_frontend("tools/vscode-extension"),
    "🧩 VS Code Build": lambda: fix_frontend("tools/vscode-extension"),
    "mobile-analyze": fix_mobile,
    "mobile_analyze": fix_mobile,
    "📱 Mobile Analysis": fix_mobile,
    "prompt-eval": lambda: print("No auto-fix available for prompt evaluation."),
    "prompt_eval": lambda: print("No auto-fix available for prompt evaluation."),
    "🤖 LLM Prompt Evaluation": lambda: print("No auto-fix available for prompt evaluation."),
}


# ═══════════════════════════════════════════════════════════════
# GUARD CHECK — Block oversized or dangerous auto-fixes
# ═══════════════════════════════════════════════════════════════
def get_changed_files() -> list:
    """Return list of files modified in the working tree."""
    result = run_cmd(["git", "diff", "--name-only", "HEAD"])
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def get_diff_line_count() -> int:
    """Return total lines changed (insertions + deletions)."""
    result = run_cmd(["git", "diff", "--shortstat", "HEAD"])
    text = result.stdout.strip()
    if not text:
        return 0
    # Parse: "X files changed, Y insertions(+), Z deletions(-)"
    numbers = re.findall(r"(\d+)", text)
    if len(numbers) >= 3:
        return int(numbers[1]) + int(numbers[2])  # insertions + deletions
    elif len(numbers) >= 2:
        return int(numbers[1])
    return 0


def is_critical_structural_change(filepath: str) -> bool:
    """
    Detect if a change to a critical file is structural (schema/logic)
    vs cosmetic (formatting, imports, __init__.py).

    Returns True → BLOCK this commit.
    Returns False → allow this file.
    """
    # Check if file matches any critical pattern
    is_critical = any(pattern in filepath for pattern in CRITICAL_FILE_PATTERNS)
    if not is_critical:
        return False  # Not a critical file — always allow

    # If it's a cosmetic file (e.g. __init__.py), allow even in critical dirs
    if any(filepath.endswith(pattern) for pattern in ALLOW_COSMETIC_PATTERNS):
        return False

    # It's a critical file that isn't cosmetic → block
    return True


def open_github_issue(title: str, body: str = ""):
    """Create a GitHub Issue when auto-fix is blocked."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        print(f"⚠️  Cannot create issue (missing GITHUB_TOKEN or GITHUB_REPOSITORY): {title}")
        return

    full_body = (
        f"{body}\n\n"
        f"**Branch:** `{BRANCH}`\n"
        f"**Failed jobs:** {', '.join(FAILED_JOBS)}\n"
        f"**Fixes attempted:** {', '.join(FIXES_APPLIED) if FIXES_APPLIED else 'none'}\n\n"
        f"This auto-fix was blocked by the CI safety guard. A human must review and fix manually."
    )
    payload = json.dumps({
        "title": f"🚨 Auto-Fix Blocked: {title}",
        "body": full_body,
        "labels": ["auto-fix-blocked", "needs-human-review"],
    }).encode()

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            issue_url = json.loads(resp.read().decode()).get("html_url", "")
            print(f"📋 Issue created: {issue_url}")
    except Exception as e:
        print(f"⚠️  Failed to create GitHub issue: {e}")


def guard_check() -> bool:
    """
    Pre-commit safety gate. Returns True if safe to commit.

    Checks:
      1. File count <= MAX_FILES_CHANGED
      2. Total line diff <= MAX_LINES_CHANGED
      3. No structural changes in critical files
    """
    print("\n🛡️  Running diff guard check...")

    # 1. File count check
    changed_files = get_changed_files()
    file_count = len(changed_files)
    print(f"   Files changed: {file_count} (limit: {MAX_FILES_CHANGED})")

    if file_count > MAX_FILES_CHANGED:
        msg = f"{file_count} files changed (limit: {MAX_FILES_CHANGED})"
        print(f"   🚫 BLOCKED — {msg}")
        open_github_issue(msg, f"Auto-fix changed {file_count} files, exceeding the safety limit of {MAX_FILES_CHANGED}.\n\nFiles:\n" + "\n".join(f"- `{f}`" for f in changed_files))
        return False

    # 2. Line count check
    line_count = get_diff_line_count()
    print(f"   Lines changed: {line_count} (limit: {MAX_LINES_CHANGED})")

    if line_count > MAX_LINES_CHANGED:
        msg = f"{line_count} lines changed (limit: {MAX_LINES_CHANGED})"
        print(f"   🚫 BLOCKED — {msg}")
        open_github_issue(msg, f"Auto-fix changed {line_count} lines, exceeding the safety limit of {MAX_LINES_CHANGED}.")
        return False

    # 3. Critical file check
    for filepath in changed_files:
        if is_critical_structural_change(filepath):
            msg = f"Structural change in critical file: {filepath}"
            print(f"   🚫 BLOCKED — {msg}")
            open_github_issue(msg, f"Auto-fix attempted a structural change to `{filepath}`, which is a protected critical file.")
            return False

    print("   ✅ Guard check passed")
    return True


def commit_changes():
    global FIXES_COMMITTED
    run_cmd(["git", "config", "user.name", "SupremeAI CI Bot"], check=True)
    run_cmd(["git", "config", "user.email", "ci-bot@supremeai.dev"], check=True)
    run_cmd(["git", "add", "-A"], check=True)
    commit_msg = (
        "ci(auto-fix): apply automated fixes for failed jobs [skip ci]\n\n"
        f"Failed jobs: {', '.join(FAILED_JOBS)}\n"
        f"Files changed: {len(get_changed_files())}\n"
        f"Lines changed: {get_diff_line_count()}\n"
        "Fixes applied:\n"
        + "\n".join(f"- {item}" for item in FIXES_APPLIED)
    )
    run_cmd(["git", "commit", "-m", commit_msg], check=True)
    push_result = run_cmd(["git", "push", "origin", BRANCH], check=False)
    if push_result.returncode == 0:
        FIXES_COMMITTED = True
        return True
    return False


def main():
    print("🔧 SupremeAI CI Auto-Fix Engine")
    print(f"Failed jobs: {FAILED_JOBS}")
    print(f"Branch: {BRANCH}")

    if not FAILED_JOBS:
        print("No failed jobs to fix.")
        print("FIXES_COMMITTED=false")
        return 0

    for job in FAILED_JOBS:
        fixer = JOB_FIXERS.get(job)
        if fixer is None:
            for key, fn in JOB_FIXERS.items():
                if key.lower() in job.lower() or job.lower() in key.lower():
                    fixer = fn
                    break

        if fixer:
            print(f"Applying fixes for {job}...")
            try:
                fixer()
            except Exception as exc:
                print(f"Failed to auto-fix {job}: {exc}")
        else:
            print(f"No auto-fix available for job '{job}'")

    status = run_cmd(["git", "status", "--porcelain"])
    if status.stdout.strip():
        # 🛡️ Run guard check before committing
        if not guard_check():
            print("\n🚫 Auto-fix BLOCKED by diff guard. No commit made.")
            print("FIXES_COMMITTED=false")
            if "GITHUB_OUTPUT" in os.environ:
                with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
                    fh.write("fixes_committed=false\n")
                    fh.write("guard_blocked=true\n")
            return 0

        # Also export diff content for multi-model evaluator (Phase 3)
        diff_result = run_cmd(["git", "diff", "HEAD"])
        if "GITHUB_OUTPUT" in os.environ:
            # Write diff to a file so evaluator can read it
            diff_path = "/tmp/auto-fix-diff.txt"
            with open(diff_path, "w") as df:
                df.write(diff_result.stdout[:16000])  # Cap at 16KB for API limits
            with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
                fh.write(f"diff_file={diff_path}\n")

        committed = commit_changes()
        if committed:
            print("FIXES_COMMITTED=true")
            if "GITHUB_OUTPUT" in os.environ:
                with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
                    fh.write("fixes_committed=true\n")
            return 0
        print("FIXES_COMMITTED=false")
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
                fh.write("fixes_committed=false\n")
        return 0

    print("No changes were made.")
    print("FIXES_COMMITTED=false")
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write("fixes_committed=false\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
