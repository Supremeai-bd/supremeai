#!/usr/bin/env python3
import json
import os
import sys
from typing import Dict, List

import requests


REPO = os.environ.get("GITHUB_REPOSITORY")
BRANCH = os.environ.get("GITHUB_REF_NAME")
CURRENT_RUN_ID = int(os.environ.get("GITHUB_RUN_ID", "0"))
WORKFLOW_NAME = os.environ.get("GITHUB_WORKFLOW")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

if not REPO or not BRANCH or not TOKEN or not WORKFLOW_NAME or not CURRENT_RUN_ID:
    print("Missing required GitHub environment variables.")
    sys.exit(1)

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}

PACKAGE_MAP = {
    "backend": ["Backend Tests", "backend-test", "backend_test", "🐍 Backend Tests"],
    "studio": ["Studio Build", "studio-build", "studio_build", "🎨 Studio Build", "🎨 Studio Client Build"],
    "mobile": ["Mobile Analysis", "mobile-analyze", "mobile_analyze", "📱 Mobile Analysis"],
    "webchat": ["WebChat Build", "webchat-build", "webchat_build", "💬 WebChat Build", "💬 Web Chat Build"],
    "vscode": ["VS Code Build", "vscode-build", "vscode_build", "🧩 VS Code Build", "🧩 VS Code Extension Build"],
    "prompt": ["Prompt Eval", "prompt-eval", "prompt_eval", "🤖 LLM Prompt Evaluation"],
}

FAILED_CONCLUSIONS = {"failure", "cancelled", "timed_out"}
SUCCESS_CONCLUSIONS = {"success"}
SKIPPED_CONCLUSIONS = {"skipped", "neutral"}


def api_get(path: str, params: Dict = None) -> Dict:
    url = f"https://api.github.com/repos/{REPO}{path}"
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code >= 400:
        raise SystemExit(f"GitHub API request failed: {resp.status_code} {resp.text}")
    return resp.json()


def get_recent_workflow_runs() -> List[Dict]:
    params = {
        "branch": BRANCH,
        "per_page": 50,
    }
    runs_data = api_get("/actions/runs", params=params)
    runs = runs_data.get("workflow_runs", [])
    return [run for run in runs if run.get("name") == WORKFLOW_NAME and run.get("id") != CURRENT_RUN_ID]


def get_job_statuses(run_id: int) -> List[Dict]:
    jobs_data = api_get(f"/actions/runs/{run_id}/jobs", params={"per_page": 100})
    return jobs_data.get("jobs", [])


def match_job(job_name: str, patterns: List[str]) -> bool:
    lower_name = job_name.lower()
    for pattern in patterns:
        if pattern.lower() in lower_name or lower_name in pattern.lower():
            return True
    return False


def determine_force_flags() -> Dict[str, str]:
    runs = get_recent_workflow_runs()
    if not runs:
        print("No previous workflow runs found.")

    force_flags = {pkg: "false" for pkg in PACKAGE_MAP}

    for pkg, patterns in PACKAGE_MAP.items():
        consecutive_failures = 0
        chain_broken = False

        for run in runs:
            if chain_broken:
                break

            run_id = run.get("id")
            if not run_id:
                continue

            jobs = get_job_statuses(run_id)
            matching_jobs = [job for job in jobs if match_job(job.get("name", ""), patterns)]
            if not matching_jobs:
                # No matching job in this run; ignore and continue searching.
                continue

            # Prefer the most recent matching job if multiple exist.
            job = matching_jobs[0]
            conclusion = (job.get("conclusion") or "").lower()

            if conclusion in FAILED_CONCLUSIONS:
                consecutive_failures += 1
                continue
            if conclusion in SUCCESS_CONCLUSIONS:
                chain_broken = True
                break
            if conclusion in SKIPPED_CONCLUSIONS:
                # If there was already a previous failure, keep the chain alive.
                if consecutive_failures > 0:
                    continue
                # If we haven't seen a failure yet, this run is not informative.
                continue

            # Any unhandled conclusion breaks the chain.
            chain_broken = True

        if consecutive_failures >= 2:
            print(f"{pkg}: {consecutive_failures} consecutive failures. Disabling auto-retry.")
            force_flags[pkg] = "false"
        elif consecutive_failures == 1:
            print(f"{pkg}: 1 previous failure detected. Forcing retry.")
            force_flags[pkg] = "true"
        else:
            print(f"{pkg}: no recent failures found.")
            force_flags[pkg] = "false"

    return force_flags


def main() -> int:
    force_flags = determine_force_flags()
    print(f"force_flags={json.dumps(force_flags)}")
    print(f"::set-output name=force_flags::{json.dumps(force_flags)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
