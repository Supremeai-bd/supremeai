#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

FAILED_JOBS_RAW = os.environ.get("FAILED_JOBS", "[]")
BRANCH = os.environ.get("BRANCH", "main")

try:
    FAILED_JOBS = json.loads(FAILED_JOBS_RAW)
except json.JSONDecodeError:
    FAILED_JOBS = []

FIXES_APPLIED = []


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


def commit_changes():
    run_cmd(["git", "config", "user.name", "SupremeAI CI Bot"], check=True)
    run_cmd(["git", "config", "user.email", "ci-bot@supremeai.dev"], check=True)
    run_cmd(["git", "add", "-A"], check=True)
    commit_msg = (
        "ci(auto-fix): apply automated fixes for failed jobs\n\n"
        f"Failed jobs: {', '.join(FAILED_JOBS)}\n"
        "Fixes applied:\n"
        + "\n".join(f"- {item}" for item in FIXES_APPLIED)
    )
    run_cmd(["git", "commit", "-m", commit_msg], check=True)
    push_result = run_cmd(["git", "push", "origin", BRANCH], check=False)
    return push_result.returncode == 0


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
        committed = commit_changes()
        if committed:
            print("FIXES_COMMITTED=true")
            return 0
        print("FIXES_COMMITTED=false")
        return 0

    print("No changes were made.")
    print("FIXES_COMMITTED=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
