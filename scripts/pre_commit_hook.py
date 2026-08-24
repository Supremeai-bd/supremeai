#!/usr/bin/env python3
"""
SupremeAI Git Pre-Commit Hook
==============================
Runs automatically on every `git commit`:
  1. rotate_lessons.py  — Enforces 12KB cap on LESSONS_LEARNED.md (archives if over limit)
  2. checkpoint_update.py — Updates CHECKPOINT.md with current session state

Install:
  python scripts/install_hooks.py
  (or manually: copy this file to .git/hooks/pre-commit)
"""

import subprocess
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
PYTHON = sys.executable


def run_script(script_name: str, args: list[str] = []) -> bool:
    """Run a script and return True if successful."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"[WARN] Script not found, skipping: {script_path}")
        return True  # Non-blocking — don't fail commit if script missing

    try:
        result = subprocess.run(
            [PYTHON, script_path] + args,
            cwd=ROOT_DIR,
            capture_output=False,  # Show output live
            text=True,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[WARN] Failed to run {script_name}: {e}")
        return True  # Non-blocking


def check_github_actions_status():
    import urllib.request
    import json
    
    print("\n[4/4] Checking GitHub Actions status for previous push...")
    try:
        repo_url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"], text=True).strip()
        owner_repo = ""
        if "github.com" in repo_url:
            if repo_url.startswith("http"):
                parts = repo_url.split("/")
                owner_repo = f"{parts[-2]}/{parts[-1].replace('.git', '')}"
            elif repo_url.startswith("git@"):
                parts = repo_url.split(":")[-1].split("/")
                owner_repo = f"{parts[0]}/{parts[1].replace('.git', '')}"
                
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
        
        if owner_repo:
            api_url = f"https://api.github.com/repos/{owner_repo}/actions/runs?branch={branch}&per_page=1"
            req = urllib.request.Request(api_url, headers={"User-Agent": "SupremeAI-PreCommitHook"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get("workflow_runs"):
                    run = data["workflow_runs"][0]
                    status = run.get("status")
                    conclusion = run.get("conclusion")
                    if status == "completed" and conclusion == "failure":
                        print(f"\n[WARN] [ATTENTION] Your last push to GitHub failed! (Branch: {branch})")
                        print(f"Run URL: {run.get('html_url')}")
                        
                        # Fetch failed jobs details
                        try:
                            jobs_url = run.get("jobs_url")
                            if jobs_url:
                                req_jobs = urllib.request.Request(jobs_url, headers={"User-Agent": "SupremeAI-PreCommitHook"})
                                with urllib.request.urlopen(req_jobs, timeout=5) as r2:
                                    jobs_data = json.loads(r2.read().decode())
                                    for job in jobs_data.get("jobs", []):
                                        if job.get("conclusion") == "failure":
                                            job_name = job.get("name", "").encode("ascii", "ignore").decode()
                                            print(f"[FAILED JOB] {job_name}")
                                            for step in job.get("steps", []):
                                                if step.get("conclusion") == "failure":
                                                    step_name = step.get("name", "").encode("ascii", "ignore").decode()
                                                    print(f"  -> Failed Step: {step_name}")
                        except Exception as e:
                            print(f"[DEBUG] Could not fetch job details: {e}")
                            
                        print("\n[SUGGESTION FOR AI AGENT]")
                        print("-> Do NOT ignore these remote CI failures!")
                        print("-> You MUST investigate the root cause and fix the code before pushing.")
                        print("-> If you are an AI, fetch the logs or ask the user for details before proceeding.\n")
                    elif status == "completed" and conclusion == "success":
                        print("[INFO] [OK] Previous GitHub Actions run passed successfully.")
                    else:
                        print(f"[INFO] [PENDING] Previous GitHub Actions run is currently: {status}.")
    except Exception as e:
        import traceback
        print(f"[DEBUG] Could not check GitHub Actions status (this is non-blocking). Exception: {e}")
        traceback.print_exc()


def main():
    print("\n[PRE-COMMIT] SupremeAI hook running...")
    print("-" * 50)

    marker_file = os.path.join(ROOT_DIR, ".git", "pre_commit_failed")
    if os.path.exists(marker_file):
        print("[INFO] ⚠️ Detected previous hook failure. Running strict checks to ensure issues are resolved...")
        print("-" * 50)

    # Step 1: Rotate LESSONS_LEARNED.md if over 12KB cap
    print("[1/2] Checking LESSONS_LEARNED.md size...")
    run_script("rotate_lessons.py")

    # Step 2: Update CHECKPOINT.md
    print("\n[2/2] Updating CHECKPOINT.md...")
    run_script("checkpoint_update.py", ["--message", "Auto-updated via pre-commit hook"])

    # Step 3: Run Ruff Formatter & Linter
    print("\n[3/3] Running Code Formatter & Linter (Ruff)...")
    try:
        backend_dir = os.path.join(ROOT_DIR, "backend")
        if os.path.exists(backend_dir):
            # Run formatter
            subprocess.run(
                ["ruff", "format", "."],
                cwd=backend_dir,
                capture_output=False,
            )
            # Run linter and auto-fix
            subprocess.run(
                ["ruff", "check", "--fix", "."],
                cwd=backend_dir,
                capture_output=False,
            )
            # Stage any formatting changes in backend
            subprocess.run(
                ["git", "add", "."],
                cwd=backend_dir,
                capture_output=True,
            )
            # Final strict lint check (Blocking)
            lint_result = subprocess.run(
                ["ruff", "check", "."],
                cwd=backend_dir,
                capture_output=False,
            )
            if lint_result.returncode != 0:
                print("\n[ERROR] Ruff Linter found errors! Commit blocked. Please fix them before committing.")
                with open(marker_file, 'w') as f:
                    f.write('failed')
                sys.exit(1)
    except Exception as e:
        print(f"[WARN] Failed to run ruff: {e}")

    # Stage any changes made by the scripts above
    try:
        files_to_stage = ["CHECKPOINT.md", "LESSONS_LEARNED.md", "docs/archive/"]
        for f in files_to_stage:
            full_path = os.path.join(ROOT_DIR, f)
            if os.path.exists(full_path):
                subprocess.run(
                    ["git", "add", f],
                    cwd=ROOT_DIR,
                    capture_output=True
                )
    except Exception:
        pass

    # Step 4: Check GitHub Actions remote status
    check_github_actions_status()

    print("-" * 50)
    print("[PRE-COMMIT] Done. Proceeding with commit.\n")
    
    if os.path.exists(marker_file):
        os.remove(marker_file)
        
    sys.exit(0)  # Allow commit if linter passes


if __name__ == "__main__":
    main()
