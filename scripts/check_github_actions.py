# scripts/check_github_actions.py
# বাংলা মন্তব্য: GitHub Actions-এর সাম্প্রতিক রানগুলোর স্ট্যাটাস এবং ফেইলড লগ চেক করার জন্য স্ক্রিপ্ট।

import os
import sys
import requests
from dotenv import load_dotenv
from pathlib import Path

# sys.stdout এবং sys.stderr এর জন্য UTF-8 সেট করা হচ্ছে যাতে ইমোজি প্রিন্ট করতে কোনো সমস্যা না হয়।
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# স্ক্রিপ্টের অবস্থান থেকে রুট .env ফাইল লোড করা হচ্ছে
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("GITHUB_PAT_AUTO_FIX") or os.getenv("GITHUB_TOKEN")
REPO = "paykaribazaronline/supremeai"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def get_latest_run():
    url = f"https://api.github.com/repos/{REPO}/actions/runs?branch=main&per_page=1"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Error fetching runs: {response.status_code} - {response.text}")
        sys.exit(1)

    runs = response.json().get("workflow_runs", [])
    if not runs:
        print("No workflow runs found.")
        sys.exit(0)
    return runs[0]

def get_failed_job_logs(run_id):
    url = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/jobs"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Error fetching jobs: {response.status_code}")
        return

    jobs = response.json().get("jobs", [])
    for job in jobs:
        if job.get("conclusion") == "failure":
            print(f"\n--- Failed Job: {job['name']} (ID: {job['id']}) ---")
            # লগ ডাউনলোড করা হচ্ছে
            log_url = f"https://api.github.com/repos/{REPO}/actions/jobs/{job['id']}/logs"
            log_response = requests.get(log_url, headers=HEADERS)
            if log_response.status_code == 200:
                print("Failed job log summary (last 100 lines):")
                lines = log_response.text.splitlines()
                # শেষ ১০০ লাইন প্রিন্ট করা
                for line in lines[-100:]:
                    print(line)
            else:
                print(f"Could not retrieve logs: {log_response.status_code}")

def main():
    run = get_latest_run()
    print(f"Latest Run ID: {run['id']}")
    print(f"Workflow Name: {run['name']}")
    print(f"Status: {run['status']}")
    print(f"Conclusion: {run['conclusion']}")
    print(f"HTML URL: {run['html_url']}")

    if run['status'] == "completed" and run['conclusion'] == "failure":
        get_failed_job_logs(run['id'])
        sys.exit(2) # Indicates failure
    elif run['status'] != "completed":
        sys.exit(3) # Indicates in_progress / queued
    else:
        sys.exit(0) # Success

if __name__ == "__main__":
    main()
