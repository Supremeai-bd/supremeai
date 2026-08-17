#!/usr/bin/env python3
"""
GitHub Actions Failed Job Detector & Log Extractor for SupremeAI Agents.
বাংলা মন্তব্য: গিটহাব অ্যাকশনসের যেকোনো জব ব্যর্থ হলে তা চিহ্নিত করে পুরো লগ স্ট্রিম মার্কডাউন ফাইলে সেভ করবে।
"""

import os
import sys
import json
import zipfile
import io
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GitHubFailureDetector:
    """
    গিটহাব অ্যাকশনস ওয়ার্কফ্লো রান স্ক্যানার এবং ফেইলড জব লগ এক্সট্রাক্টর।
    """

    def __init__(self, repo: str = "paykaribazaronline/supremeai", token: Optional[str] = None):
        self.repo = repo
        self.token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_API_TOKEN")
        self.base_url = f"https://api.github.com/repos/{self.repo}"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SupremeAI-Agent-Detector"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def get_recent_failed_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        সাম্প্রতিক ব্যর্থ হওয়া গিটহাব অ্যাকশনস ওয়ার্কফ্লো রানগুলো খুঁজে বের করা।
        """
        url = f"{self.base_url}/actions/runs?status=failure&per_page={limit}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            print(f"❌ Error fetching workflow runs (HTTP {response.status_code}): {response.text}")
            return []

        runs = response.json().get("workflow_runs", [])
        print(f"🔍 Found {len(runs)} failed workflow runs in repository '{self.repo}'.")
        return runs

    def get_run_failed_jobs(self, run_id: int) -> List[Dict[str, Any]]:
        """
        একটি সুনির্দিষ্ট ওয়ার্কফ্লো রানের ভেতরের ব্যর্থ হওয়া জবসমূহ তালিকাভুক্ত করা।
        """
        url = f"{self.base_url}/actions/runs/{run_id}/jobs"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            print(f"❌ Error fetching jobs for run #{run_id}: {response.text}")
            return []

        jobs = response.json().get("jobs", [])
        failed_jobs = [job for job in jobs if job.get("conclusion") == "failure"]
        return failed_jobs

    def download_job_logs_markdown(self, run_id: int, output_dir: str = "docs/04-ci-logs") -> Optional[str]:
        """
        ফেইলড জবের সম্পূর্ণ লগ ডাউনলোড করে একটি মার্কডাউন (.md) ফাইলে সংরক্ষণ করা।
        """
        failed_jobs = self.get_run_failed_jobs(run_id)
        if not failed_jobs:
            print(f"⚠️ No failed jobs found for run #{run_id}.")
            return None

        os.makedirs(output_dir, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_filename = os.path.join(output_dir, f"ci_failure_run_{run_id}_{timestamp_str}.md")

        # Download ZIP archive of logs for the run
        logs_url = f"{self.base_url}/actions/runs/{run_id}/logs"
        response = requests.get(logs_url, headers=self.headers, stream=True)

        log_contents: Dict[str, str] = {}
        if response.status_code == 200:
            try:
                z = zipfile.ZipFile(io.BytesIO(response.content))
                for file_info in z.infolist():
                    if file_info.filename.endswith(".txt"):
                        with z.open(file_info) as f:
                            log_contents[file_info.filename] = f.read().decode('utf-8', errors='ignore')
            except Exception as e:
                print(f"⚠️ Could not parse ZIP logs: {e}")

        # Build Markdown File Content
        md_content = []
        md_content.append(f"# 🚨 CI/CD Failure Log Report — Run #{run_id}")
        md_content.append(f"**Repository:** `{self.repo}`  ")
        md_content.append(f"**Run ID:** `{run_id}`  ")
        md_content.append(f"**Generated At:** `{datetime.now().isoformat()}`  ")
        md_content.append(f"**Total Failed Jobs:** {len(failed_jobs)}\n")

        md_content.append("---")
        md_content.append("## 📋 Failed Jobs Overview\n")

        for job in failed_jobs:
            job_name = job.get("name", "Unknown Job")
            job_url = job.get("html_url", "#")
            md_content.append(f"### ❌ Job: [{job_name}]({job_url})")
            md_content.append(f"- **Status:** `{job.get('status')}`")
            md_content.append(f"- **Conclusion:** `{job.get('conclusion')}`")
            md_content.append(f"- **Started At:** `{job.get('started_at')}`")
            md_content.append(f"- **Completed At:** `{job.get('completed_at')}`\n")

            md_content.append("#### 🔍 Failed Steps:")
            for step in job.get("steps", []):
                if step.get("conclusion") == "failure":
                    md_content.append(f"- 💥 **{step.get('name')}** (Number: {step.get('number')})")

            md_content.append("\n#### 📜 Log Output:")
            # Match job log file from extracted zip contents
            matching_logs = [text for name, text in log_contents.items() if job_name.replace(" ", "_") in name or str(job.get("id")) in name]
            if matching_logs:
                raw_log = matching_logs[0]
                # Truncate if ultra long to avoid huge files
                if len(raw_log) > 50000:
                    raw_log = raw_log[-50000:] + "\n...[Truncated Lead Log Output]..."
                md_content.append("```bash")
                md_content.append(raw_log.strip())
                md_content.append("```\n")
            else:
                # Fallback step API message
                md_content.append("```text")
                md_content.append("Detailed ZIP log file not found or direct log download restricted. Check failed steps above.")
                md_content.append("```\n")

            md_content.append("---\n")

        with open(md_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))

        print(f"✅ Full failure log saved to markdown: file:///{os.path.abspath(md_filename)}")
        return md_filename

def main():
    parser = argparse.ArgumentParser(description="SupremeAI GitHub Actions Failure Detector & Log Downloader")
    parser.add_argument("--repo", default="paykaribazaronline/supremeai", help="GitHub Repository (owner/repo)")
    parser.add_argument("--run-id", type=int, help="Specific Workflow Run ID to process")
    parser.add_argument("--output-dir", default="docs/04-ci-logs", help="Directory to save markdown reports")
    args = parser.parse_args()

    detector = GitHubFailureDetector(repo=args.repo)

    if args.run_id:
        detector.download_job_logs_markdown(args.run_id, output_dir=args.output_dir)
    else:
        failed_runs = detector.get_recent_failed_runs(limit=5)
        if not failed_runs:
            print("🎉 No failed workflow runs found!")
            return

        latest_failed_run = failed_runs[0]
        run_id = latest_failed_run["id"]
        print(f"🚀 Processing latest failed run #{run_id} ({latest_failed_run.get('name')})...")
        detector.download_job_logs_markdown(run_id, output_dir=args.output_dir)

if __name__ == "__main__":
    main()
