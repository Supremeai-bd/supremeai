#!/usr/bin/env python3
"""
SupremeAI Smart CI — Enhanced Previous Failure & Skip Detector
Replaces the fragile bash/jq logic with robust Python.
Detects:
  - Jobs that failed in previous run(s)
  - Jobs that were skipped but had failed before (unverified fixes)
  - Consecutive failure chains
"""
import json
import os
import subprocess
import sys
from typing import Dict, List, Set, Tuple

REPO = os.environ["GITHUB_REPOSITORY"]
BRANCH = os.environ["GITHUB_REF_NAME"]
CURRENT_RUN_ID = os.environ["GITHUB_RUN_ID"]
WORKFLOW_NAME = os.environ.get("WORKFLOW_NAME", "SupremeAI Smart CI")
GH_TOKEN = os.environ["GH_TOKEN"]

# Map internal package names to workflow job name patterns
PACKAGE_PATTERNS = {
    "backend": ["Backend Tests", "Code Smell Analysis"],
    "studio": ["Studio Client Build", "Studio Build"],
    "mobile": ["Mobile App Analysis", "Mobile Analyze"],
    "webchat": ["Web Chat Build", "WebChat Build", "Webchat Build"],
    "vscode": ["VS Code Extension Build", "VS Code Build"],
    "prompt": ["LLM Prompt Evaluation", "Prompt Eval"],
}


def gh_api(args: List[str]) -> dict:
    """Run gh CLI and return JSON."""
    cmd = ["gh", "run", *args, "--repo", REPO]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={**os.environ, "GH_TOKEN": GH_TOKEN},
    )
    if result.returncode != 0:
        print(f"⚠️ gh command failed: {result.stderr}", file=sys.stderr)
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def get_recent_runs(limit: int = 6) -> List[dict]:
    """Get recent workflow runs for this branch, excluding current."""
    # Use gh API instead of run list for better control
    cmd = [
        "gh", "api",
        f"/repos/{REPO}/actions/workflows/supreme-ci.yml/runs",
        "--jq", f".workflow_runs[:{limit}]",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ)
    if result.returncode != 0:
        # Fallback to run list
        raw = subprocess.run(
            ["gh", "run", "list", "--workflow", WORKFLOW_NAME, "--branch", BRANCH, "--limit", str(limit), "--json", "databaseId,conclusion,status,headBranch,event,headSha"],
            capture_output=True, text=True, env=os.environ,
        )
        try:
            runs = json.loads(raw.stdout)
        except Exception:
            runs = []
    else:
        try:
            runs = json.loads(result.stdout)
        except Exception:
            runs = []

    # Filter out current run and other branches
    return [
        r for r in runs
        if str(r.get("databaseId") or r.get("id")) != CURRENT_RUN_ID
        and (r.get("headBranch") or r.get("head_branch")) == BRANCH
    ][:5]


def get_jobs_for_run(run_id: str) -> List[dict]:
    """Get all jobs for a specific run."""
    cmd = [
        "gh", "api",
        f"/repos/{REPO}/actions/runs/{run_id}/jobs",
        "--jq", ".jobs",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ)
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except Exception:
            pass
    # Fallback
    raw = subprocess.run(
        ["gh", "run", "view", str(run_id), "--json", "jobs"],
        capture_output=True, text=True, env=os.environ,
    )
    try:
        return json.loads(raw.stdout).get("jobs", [])
    except Exception:
        return []


def match_job(name: str, patterns: List[str]) -> bool:
    """Check if job name matches any pattern (case-insensitive substring)."""
    name_lower = name.lower()
    for p in patterns:
        if p.lower() in name_lower:
            return True
    return False


def analyze_package(pkg: str, patterns: List[str], runs: List[dict]) -> Tuple[str, int, str]:
    """
    Analyze a package across recent runs.
    Returns: (force_flag, consecutive_count, reason)
    """
    consecutive_failures = 0
    chain_broken = False
    last_was_skipped_after_failure = False

    for run in runs:
        if chain_broken:
            break

        run_id = str(run.get("databaseId") or run.get("id"))
        jobs = get_jobs_for_run(run_id)

        # Find matching job in this run
        matched_job = None
        for job in jobs:
            if match_job(job.get("name", ""), patterns):
                matched_job = job
                break

        if not matched_job:
            # Job not found in this run — maybe workflow was cancelled early
            # Treat as chain broken to be safe
            chain_broken = True
            continue

        conclusion = (matched_job.get("conclusion") or "").lower()
        status = (matched_job.get("status") or "").lower()

        if conclusion in ("failure", "cancelled", "timed_out"):
            consecutive_failures += 1
            last_was_skipped_after_failure = False
        elif conclusion == "skipped":
            # If skipped, check if it was skipped due to path detection or dependency failure
            # We can't easily tell, but if we had failures before, this skip means
            # the fix was never verified. Count it as a "soft failure" for forcing.
            if consecutive_failures > 0:
                last_was_skipped_after_failure = True
            # Don't break chain — a skip after failure keeps the suspicion alive
            # But don't increment consecutive_failures either
            pass
        elif conclusion == "success":
            chain_broken = True
            consecutive_failures = 0
        else:
            # Neutral / unknown — break chain to be safe
            chain_broken = True

    # Decision logic
    if consecutive_failures >= 2:
        return ("false", consecutive_failures, f"{consecutive_failures} consecutive failures — disabling auto-retry, creating issue")
    elif consecutive_failures == 1 or last_was_skipped_after_failure:
        return ("true", consecutive_failures, f"Previously failed (or skipped after failure) — forcing retry")
    else:
        return ("false", 0, "No recent failures")


def main():
    print(f"🔍 Checking previous failures for {REPO}@{BRANCH} (excluding run {CURRENT_RUN_ID})")
    runs = get_recent_runs(limit=6)
    print(f"Found {len(runs)} previous runs on this branch")

    results = {}
    for pkg, patterns in PACKAGE_PATTERNS.items():
        force, count, reason = analyze_package(pkg, patterns, runs)
        results[pkg] = force
        emoji = "✅" if force == "false" and count == 0 else "⚠️" if force == "true" else "🚨"
        print(f"  {emoji} {pkg}: {reason}")

    # Output JSON for GitHub Actions
    json_out = json.dumps(results)
    print(f"::set-output name=force_flags::{json_out}")
    # Also write to GITHUB_OUTPUT
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
        f.write(f"force_flags={json_out}\n")

    print(f"\n📊 Final force_flags: {json_out}")


if __name__ == "__main__":
    main()
