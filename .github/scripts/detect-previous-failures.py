#!/usr/bin/env python3
import json
import os
import sys
import urllib.parse
import urllib.request
import ssl
from typing import Dict, List


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
    "backend": ["Backend (Test)", "Backend Tests", "Deploy Backend (Render)", "Deploy Backend (Cloud Run)", "Canary Deploy Backend (Cloud Run)"],
    "frontend": ["Frontend Monorepo (Turbo)", "Deploy Admin Portal (Firebase)", "Deploy User Portal (Vercel)"],
    "docker_build": ["Build Base Image"],
    "dependencies": []
}

FAILED_CONCLUSIONS = {"failure", "cancelled", "timed_out"}
SUCCESS_CONCLUSIONS = {"success"}
SKIPPED_CONCLUSIONS = {"skipped", "neutral"}


def _get_ssl_contexts() -> List[ssl.SSLContext]:
    # বাংলা মন্তব্য: SSL সার্টিফিকেট ভ্যালিডেশনের জন্য ক্রমান্বয়ে SSL Context তালিকা তৈরি।
    # ১. সিস্টেমের ডিফল্ট CA বান্ডল।
    # ২. certifi প্যাকেজের CA বান্ডল (যদি লোকাল/রানার স্টোর পুরনো হয়)।
    # ৩. আনভেরিফাইড ফলব্যাক কনটেক্সট (যাতে নেটওয়ার্ক ব্লকেজের কারণে CI পাইপলাইন কখনো হার্ড-ফেইল না করে)।
    contexts = []
    try:
        contexts.append(ssl.create_default_context())
    except Exception:
        pass

    try:
        import certifi
        contexts.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        pass

    try:
        contexts.append(ssl._create_unverified_context())
    except Exception:
        pass

    return contexts


def api_get(path: str, params: Dict = None) -> Dict:
    # বাংলা মন্তব্য: GitHub API থেকে নিরাপদে JSON ডেটা ফেচ করা। Multiple SSL context ব্যবহার করা হয়
    # এবং API Error (HTTP 403 / 429 / Rate Limit) এলে SystemExit না করে খালি dict রিটার্ন করা হয়।
    url = f"https://api.github.com/repos/{REPO}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS, method="GET")

    ssl_contexts = _get_ssl_contexts()
    last_error = None

    for ctx in ssl_contexts:
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                body = resp.read().decode("utf-8")
                if resp.status == 200:
                    return json.loads(body)
                else:
                    print(f"[WARN] GitHub API status {resp.status} for {path}: {body[:150]}")
                    return {}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"[WARN] GitHub API HTTP error {e.code} for {path}: {body[:150]}")
            return {}
        except (urllib.error.URLError, OSError, Exception) as e:
            last_error = e
            continue

    if last_error:
        print(f"[WARN] GitHub API fetch failed for {path}: {last_error}")
    return {}


def get_recent_workflow_runs() -> List[Dict]:
    # বাংলা মন্তব্য: সর্বোচ্চ ১৫টি রান ফেচ করা হয় API rate limit এড়াতে
    params = {
        "branch": BRANCH,
        "per_page": 15,
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
    # বাংলা মন্তব্য: গত সর্বোচ্চ ৫টি সক্রিয় রান প্রসেস করা হবে যাতে অযথা ডজন ডজন API কল না হয়
    runs = get_recent_workflow_runs()[:5]
    force_flags = {pkg: "false" for pkg in PACKAGE_MAP}

    # Fetch job statuses for recent runs to reduce API calls
    run_jobs_cache = {}
    for run in runs:
        run_id = run.get("id")
        if not run_id:
            continue
        # Skip dependabot runs so they don't reset failure history
        actor_login = run.get("actor", {}).get("login", "").lower()
        if "dependabot" in actor_login or "[bot]" in actor_login:
            continue
        jobs = get_job_statuses(run_id)
        if jobs:
            run_jobs_cache[run_id] = jobs

    if not run_jobs_cache:
        print("No processable previous workflow runs found.")
        return force_flags

    for pkg, patterns in PACKAGE_MAP.items():
        has_recent_failure = False
        # Iterate from most recent to oldest run
        for run_id in sorted(run_jobs_cache.keys(), reverse=True):
            jobs = run_jobs_cache[run_id]
            matching_jobs = [job for job in jobs if match_job(job.get("name", ""), patterns)]

            if not matching_jobs:
                continue

            job = matching_jobs[0]
            conclusion = (job.get("conclusion") or "").lower()

            if conclusion in FAILED_CONCLUSIONS:
                # Found a failure, so we must force a retry for this package.
                has_recent_failure = True
                break
            elif conclusion in SUCCESS_CONCLUSIONS:
                # Found a success, so the failure chain is broken. No need to force.
                has_recent_failure = False
                break
            # If skipped, just continue to the next older run to find a conclusive result.

        if has_recent_failure:
            print(f"{pkg}: A recent failure was detected. Forcing retry.")
            force_flags[pkg] = "true"
        else:
            print(f"{pkg}: no recent failures found.")
            force_flags[pkg] = "false"

    return force_flags


import base64
def main() -> int:
    force_flags = determine_force_flags()
    json_str = json.dumps(force_flags)
    encoded = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    print(f"force_flags (encoded)={encoded}")
    # Write to GITHUB_OUTPUT file instead of using deprecated ::set-output
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"force_flags_b64={encoded}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
