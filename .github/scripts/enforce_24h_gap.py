#!/usr/bin/env python3
import os
import sys
import requests
from datetime import datetime, timezone, timedelta
import time

def main():
    if os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        print("Not a scheduled run. Skipping 12-hour gap check.")
        return 0

    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    workflow_name = os.environ.get("GITHUB_WORKFLOW")
    current_run_id = os.environ.get("GITHUB_RUN_ID")

    if not all([repo, token, workflow_name, current_run_id]):
        print("Missing required GitHub environment variables.")
        return 0

    url = f"https://api.github.com/repos/{repo}/actions/runs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    resp = requests.get(url, headers=headers, params={"per_page": 20})
    if not resp.ok:
        print(f"Failed to fetch runs: {resp.text}")
        return 0
        
    runs = resp.json().get("workflow_runs", [])
    now = datetime.now(timezone.utc)

    for run in runs:
        if str(run["id"]) == current_run_id:
            continue
            
        if run["name"] != workflow_name:
            continue
            
        conclusion = run.get("conclusion")
        if conclusion in ["cancelled", "skipped"]:
            continue
            
        if conclusion == "failure":
            print(f"Previous run ({run['id']}) failed. Allowing this scheduled run as a retry.")
            return 0
            
        created_at_str = run["created_at"]
        created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        
        # রুল ১৬ (Zero Cost) অনুযায়ী আমরা শিডিউল রানগুলো দিনে ১ বার (প্রতি ২৪ ঘণ্টায়) রান করব
        # যাতে গিটহাব অ্যাকশনস এর ফ্রি মিনিটগুলো অযথাই নষ্ট না হয়।
        diff = now - created_at
        
        if diff < timedelta(hours=24):
            print(f"Previous run ({run['id']}) started at {created_at_str}, which is {diff} ago (less than 24 hours).")
            print("Cancelling this scheduled run to save resources.")
            os.system(f"gh run cancel {current_run_id}")
            time.sleep(15)
            sys.exit(1)
            
        else:
            print(f"Previous run was {diff} ago. Minimum 24-hour gap met. Proceeding.")
            return 0
            
    print("No valid previous runs found. Proceeding.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
