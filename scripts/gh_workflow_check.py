# scripts/gh_workflow_check.py
"""Check a GitHub Actions run for failed jobs/steps."""
import argparse
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()  # loads GITHUB_TOKEN from .env properly, no manual parsing


def check_run(run_id: str, repo: str = "paykaribazaronline/supremeai") -> int:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set in environment.", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch run {run_id}: {e}", file=sys.stderr)
        return 1

    jobs = resp.json().get("jobs", [])
    failed = [j for j in jobs if j.get("conclusion") == "failure"]
    for job in failed:
        print(f"Failed Job: {job['name']}")
        for step in job.get("steps", []):
            if step.get("conclusion") == "failure":
                print(f"  Failed Step: {step['name']}")

    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id", help="GitHub Actions run ID to inspect")
    args = parser.parse_args()
    sys.exit(check_run(args.run_id))
