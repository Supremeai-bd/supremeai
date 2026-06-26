#!/usr/bin/env python3
"""
SupremeAI Smart CI — Auto-Fix Engine
Analyzes failed CI jobs and applies automated fixes.
Supports: backend, studio, webchat, vscode, mobile
"""
import json
import os
import subprocess
import sys
from pathlib import Path

FAILED_JOBS_RAW = os.environ.get("FAILED_JOBS", "[]")
BRANCH = os.environ.get("BRANCH", "main")

try:
    FAILED_JOBS = json.loads(FAILED_JOBS_RAW)
except Exception:
    FAILED_JOBS = []

FIXES_APPLIED = []
CHANGES_MADE = False


def run_cmd(cmd: list, cwd: str = None, check: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command safely."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def fix_backend():
    """Auto-fix backend (Python) issues."""
    global CHANGES_MADE
    backend_dir = Path("backend")
    if not backend_dir.exists():
        print("⚠️ backend/ directory not found")
        return

    # 1. Auto-fix with Ruff
    result = run_cmd(["poetry", "run", "ruff", "check", ".", "--fix"], cwd="backend")
    if result.stdout and ("fixed" in result.stdout.lower() or "Found" in result.stdout):
        FIXES_APPLIED.append("ruff check --fix")
        CHANGES_MADE = True

    # 2. Format with Black
    run_cmd(["poetry", "run", "black", "."], cwd="backend")
    FIXES_APPLIED.append("black .")
    CHANGES_MADE = True

    # 3. Ensure __init__.py files exist in core/, brain/, api/, memory/, tools/
    for subdir in ["core", "brain", "api", "memory", "tools"]:
        d = backend_dir / subdir
        if d.exists():
            init_file = d / "__init__.py"
            if not init_file.exists():
                init_file.touch()
                FIXES_APPLIED.append(f"created {init_file}")
                CHANGES_MADE = True
            # Also check subdirectories
            for sub in d.rglob(""):
                if sub.is_dir() and not (sub / "__init__.py").exists():
                    # Only if there are Python files in this dir
                    if list(sub.glob("*.py")):
                        (sub / "__init__.py").touch()
                        FIXES_APPLIED.append(f"created {sub / '__init__.py'}")
                        CHANGES_MADE = True

    # 4. Sync poetry.lock if pyproject.toml changed
    result = run_cmd(["poetry", "lock", "--no-update"], cwd="backend")
    if result.returncode == 0:
        # Check if lockfile changed
        status = run_cmd(["git", "status", "--porcelain", "backend/poetry.lock"])
        if status.stdout.strip():
            FIXES_APPLIED.append("poetry lock --no-update")
            CHANGES_MADE = True

    # 5. Try to auto-fix missing imports via ruff (if available)
    run_cmd(["poetry", "run", "ruff", "check", ".", "--select", "I", "--fix"], cwd="backend")
    FIXES_APPLIED.append("ruff import sorting")
    CHANGES_MADE = True


def fix_frontend(pkg_dir: str, filter_name: str):
    """Generic frontend fixer for studio/webchat/vscode."""
    global CHANGES_MADE
    if not Path(pkg_dir).exists():
        print(f"⚠️ {pkg_dir}/ not found")
        return

    # 1. ESLint --fix
    result = run_cmd(["pnpm", "exec", "eslint", pkg_dir, "--fix"])
    if result.returncode == 0 or "fixed" in (result.stdout + result.stderr).lower():
        FIXES_APPLIED.append(f"eslint {pkg_dir} --fix")
        CHANGES_MADE = True

    # 2. Prettier write
    run_cmd(["pnpm", "exec", "prettier", "--write", pkg_dir])
    FIXES_APPLIED.append(f"prettier --write {pkg_dir}")
    CHANGES_MADE = True

    # 3. Check for missing dependencies (package.json sync)
    # If pnpm-lock.yaml is out of sync, pnpm install --frozen-lockfile would fail
    result = run_cmd(["pnpm", "install", "--no-frozen-lockfile"])
    if result.returncode == 0:
        status = run_cmd(["git", "status", "--porcelain", "pnpm-lock.yaml"])
        if status.stdout.strip():
            FIXES_APPLIED.append("pnpm install (lockfile sync)")
            CHANGES_MADE = True

    # 4. Turbo build to catch type errors that might be auto-fixable
    result = run_cmd(["pnpm", "turbo", "run", "lint", "--fix", f"--filter={filter_name}"])
    if result.returncode == 0:
        FIXES_APPLIED.append(f"turbo lint --fix --filter={filter_name}")
        CHANGES_MADE = True


def fix_studio():
    fix_frontend("apps/studio-client", "supremeai-studio-client")


def fix_webchat():
    fix_frontend("apps/web-chat", "web-chat")


def fix_vscode():
    fix_frontend("tools/vscode-extension", "supremeai-vscode")


def fix_mobile():
    """Auto-fix Flutter/Dart issues."""
    global CHANGES_MADE
    mobile_dir = Path("apps/mobile")
    if not mobile_dir.exists():
        print("⚠️ apps/mobile/ not found")
        return

    # 1. Dart fix
    result = run_cmd(["dart", "fix", "--apply"], cwd="apps/mobile")
    if result.returncode == 0:
        FIXES_APPLIED.append("dart fix --apply")
        CHANGES_MADE = True

    # 2. Format
    run_cmd(["dart", "format", "."], cwd="apps/mobile")
    FIXES_APPLIED.append("dart format .")
    CHANGES_MADE = True

    # 3. Flutter pub get (if pubspec.lock out of sync)
    result = run_cmd(["flutter", "pub", "get"], cwd="apps/mobile")
    if result.returncode == 0:
        status = run_cmd(["git", "status", "--porcelain", "apps/mobile/pubspec.lock"])
        if status.stdout.strip():
            FIXES_APPLIED.append("flutter pub get (lockfile sync)")
            CHANGES_MADE = True


# Map job names (from CI report) to fixer functions
JOB_FIXERS = {
    "backend-test": fix_backend,
    "backend_test": fix_backend,
    "🐍 Backend Tests": fix_backend,
    "studio-build": fix_studio,
    "studio_build": fix_studio,
    "🎨 Studio Client Build": fix_studio,
    "🎨 Studio Build": fix_studio,
    "mobile-analyze": fix_mobile,
    "mobile_analyze": fix_mobile,
    "📱 Mobile App Analysis": fix_mobile,
    "webchat-build": fix_webchat,
    "webchat_build": fix_webchat,
    "💬 Web Chat Build": fix_webchat,
    "💬 WebChat Build": fix_webchat,
    "vscode-build": fix_vscode,
    "vscode_build": fix_vscode,
    "🧩 VS Code Extension Build": fix_vscode,
    "🧩 VS Code Build": fix_vscode,
}


def main():
    print(f"🔧 SupremeAI CI Auto-Fix Engine")
    print(f"   Failed jobs: {FAILED_JOBS}")
    print(f"   Branch: {BRANCH}")
    print()

    if not FAILED_JOBS:
        print("✅ No failed jobs to fix.")
        print("FIXES_COMMITTED=false")
        return

    # Setup git
    run_cmd(["git", "config", "user.name", "SupremeAI CI Bot"])
    run_cmd(["git", "config", "user.email", "ci-bot@supremeai.dev"])

    for job in FAILED_JOBS:
        fixer = None
        # Try exact match first, then partial
        if job in JOB_FIXERS:
            fixer = JOB_FIXERS[job]
        else:
            for key, fn in JOB_FIXERS.items():
                if key.lower() in job.lower() or job.lower() in key.lower():
                    fixer = fn
                    break

        if fixer:
            print(f"🔧 Running auto-fix for: {job}")
            try:
                fixer()
            except Exception as e:
                print(f"  ⚠️ Fix failed: {e}")
        else:
            print(f"ℹ️ No auto-fix available for: {job}")

    # Check for changes
    status = run_cmd(["git", "status", "--porcelain"])
    if status.stdout.strip():
        print("\n📦 Changes detected. Committing...")
        run_cmd(["git", "add", "-A"])
        commit_msg = f"""ci(auto-fix): apply automated fixes for failed jobs

Failed jobs: {', '.join(FAILED_JOBS)}
Fixes applied:
- {chr(10).join('- ' + f for f in FIXES_APPLIED)}
"""
        run_cmd(["git", "commit", "-m", commit_msg])
        run_cmd(["git", "push", "origin", BRANCH])
        print("FIXES_COMMITTED=true")
        print(f"\n✅ Committed {len(FIXES_APPLIED)} fix(es)")
    else:
        print("\n🤷 No auto-fixes could be applied.")
        print("FIXES_COMMITTED=false")


if __name__ == "__main__":
    main()
