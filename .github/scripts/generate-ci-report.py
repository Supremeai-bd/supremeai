import os
import json
import requests
import argparse
from datetime import datetime

def get_env(key, default=""):
    return os.environ.get(key, default)

# --- Configuration & Environment Variables ---
GITHUB_TOKEN = get_env("GITHUB_TOKEN")
GITHUB_REPOSITORY = get_env("GITHUB_REPOSITORY")
GITHUB_RUN_ID = get_env("GITHUB_RUN_ID")
GITHUB_REF_NAME = get_env("GITHUB_REF_NAME")
GITHUB_ACTOR = get_env("GITHUB_ACTOR")
GITHUB_SERVER_URL = get_env("GITHUB_SERVER_URL", "https://github.com")
DISCORD_WEBHOOK_URL = get_env("DISCORD_WEBHOOK_URL")

API_BASE = f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def fetch_jobs():
    """Fetch all jobs for the current workflow run."""
    url = f"{API_BASE}/actions/runs/{GITHUB_RUN_ID}/jobs"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("jobs", [])
    return []

def extract_error_logs(job_id):
    """Fetch and extract the last 20 lines of logs for a failed job."""
    url = f"{API_BASE}/actions/jobs/{job_id}/logs"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        lines = response.text.splitlines()
        # Extract the last 20 lines for context
        return "\n".join(lines[-20:])
    return "Could not extract logs automatically."

def send_discord_alert(status, report_type, passed_count, failed_count, failed_jobs_details):
    """Send a rich embed alert to Discord."""
    if not DISCORD_WEBHOOK_URL:
        return

    color = 0x00FF00 if status == "SUCCESS" else 0xFF0000
    title = f"{'✅' if status == 'SUCCESS' else '❌'} SupremeAI {report_type.upper()} Build: {status}"
    
    embed = {
        "title": title,
        "url": f"{GITHUB_SERVER_URL}/{GITHUB_REPOSITORY}/actions/runs/{GITHUB_RUN_ID}",
        "color": color,
        "fields": [
            {"name": "Branch", "value": GITHUB_REF_NAME, "inline": True},
            {"name": "Triggered By", "value": GITHUB_ACTOR, "inline": True},
            {"name": "Status", "value": f"{passed_count} Passed | {failed_count} Failed", "inline": False}
        ],
        "footer": {"text": "SupremeAI CI/CD System"}
    }

    if failed_count > 0:
        error_text = ""
        for job in failed_jobs_details:
            error_text += f"**{job['name']}**\n```\n{job.get('error_log', '')[:500]}...\n```\n"
        embed["fields"].append({"name": "Critical Errors", "value": error_text[:1024], "inline": False})

    payload = {"username": "SupremeAI DevOps", "embeds": [embed]}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=['core', 'release', 'maintenance'], default='core')
    args = parser.parse_args()

    jobs = fetch_jobs()
    
    passed_jobs = []
    failed_jobs = []
    skipped_jobs = []

    # Categorize jobs
    for job in jobs:
        # Skip the report generation job itself
        if "Report" in job["name"]:
            continue
        
        if job["conclusion"] == "success":
            passed_jobs.append(job)
        elif job["conclusion"] == "failure":
            log_snippet = extract_error_logs(job["id"])
            job["error_log"] = log_snippet
            failed_jobs.append(job)
        elif job["conclusion"] == "skipped":
            skipped_jobs.append(job)

    status_overall = "FAILED" if failed_jobs else "SUCCESS"
    emoji = "🔴" if status_overall == "FAILED" else "🟢"

    # --- 1. Markdown Generation ---
    md_content = f"# {emoji} SupremeAI {args.type.upper()} Pipeline: {status_overall}\n\n"
    md_content += f"**Branch:** `{GITHUB_REF_NAME}` | **Actor:** `{GITHUB_ACTOR}` | **Run ID:** `{GITHUB_RUN_ID}`\n\n"

    if args.type == 'core' and status_overall == "SUCCESS":
        md_content += "## 🚀 Live Deployments\n"
        md_content += "* **API (Cloud Run):** [https://supremeai-api-565236080752.us-central1.run.app](https://supremeai-api-565236080752.us-central1.run.app)\n"
        md_content += f"* **Studio (Firebase):** [https://{get_env('GCP_PROJECT_ID')}.web.app](https://{get_env('GCP_PROJECT_ID')}.web.app)\n\n"

    if failed_jobs:
        md_content += "## 🔴 Failed Jobs (Action Required!)\n"
        for job in failed_jobs:
            md_content += f"### ❌ {job['name']}\n"
            md_content += f"```text\n{job['error_log']}\n```\n"

    if passed_jobs:
        md_content += f"<details><summary>✅ Passed Jobs ({len(passed_jobs)})</summary>\n\n"
        for job in passed_jobs:
            md_content += f"* {job['name']}\n"
        md_content += "</details>\n\n"

    if skipped_jobs:
        md_content += f"<details><summary>⏭️ Skipped Jobs ({len(skipped_jobs)})</summary>\n\n"
        for job in skipped_jobs:
            md_content += f"* {job['name']}\n"
        md_content += "</details>\n\n"

    # --- 2. Write to GitHub Step Summary ---
    step_summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_file:
        with open(step_summary_file, "a", encoding="utf-8") as f:
            f.write(md_content)

    # --- 3. Save to specific log folders ---
    log_dir = f"logs/{args.type}"
    os.makedirs(log_dir, exist_ok=True)
    
    # Save markdown report
    file_path = os.path.join(log_dir, f"report-{GITHUB_RUN_ID}.md")
    latest_path = os.path.join(log_dir, "latest.md")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Committing logs to repository
    os.system('git config user.name "SupremeAI CI Bot"')
    os.system('git config user.email "ci-bot@supremeai.dev"')
    os.system(f'git add {log_dir}/*')
    os.system(f'git commit -m "ci: update {args.type} logs [skip ci]" || true')
    os.system('git push || true')

    # --- 4. Send Alert ---
    send_discord_alert(status_overall, args.type, len(passed_jobs), len(failed_jobs), failed_jobs)

if __name__ == "__main__":
    main()
