#!/usr/bin/env python3
"""
GitHub Actions Failure Analyzer for SupremeAI Agents.
বাংলা মন্তব্য: গিটহাব অ্যাকশনসের ফেইলড জবগুলো বিস্তারিত বিশ্লেষণ করে সমস্যা চিহ্নিত করবে।
"""

import os
import sys
import json
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GitHubFailureAnalyzer:
    """
    GitHub Actions failure analyzer that identifies and diagnoses problems.
    """

    def __init__(self, repo: str = "paykaribazaronline/supremeai", token: Optional[str] = None):
        self.repo = repo
        self.token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_API_TOKEN")
        self.base_url = f"https://api.github.com/repos/{self.repo}"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SupremeAI-Failure-Analyzer"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def get_recent_failed_runs(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recently failed workflow runs.
        """
        url = f"{self.base_url}/actions/runs?status=failure&per_page={limit}"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print(f"❌ Error fetching workflow runs (HTTP {response.status_code}): {response.text}")
            return []

        runs = response.json().get("workflow_runs", [])
        print(f"🔍 Found {len(runs)} failed workflow runs in repository '{self.repo}'.")
        return runs

    def get_run_jobs(self, run_id: int) -> List[Dict[str, Any]]:
        """
        Get all jobs for a specific workflow run.
        """
        url = f"{self.base_url}/actions/runs/{run_id}/jobs"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print(f"❌ Error fetching jobs for run #{run_id}: {response.text}")
            return []

        jobs = response.json().get("jobs", [])
        return jobs

    def get_job_logs(self, job_id: int) -> Optional[str]:
        """
        Get logs for a specific job.
        """
        url = f"{self.base_url}/actions/jobs/{job_id}/logs"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.text
        else:
            print(f"❌ Error fetching logs for job #{job_id}: {response.status_code}")
            return None

    def analyze_failure_patterns(self, run_id: int) -> Dict[str, Any]:
        """
        Analyze failure patterns in a specific run.
        """
        jobs = self.get_run_jobs(run_id)
        failed_jobs = [job for job in jobs if job.get("conclusion") == "failure"]

        analysis = {
            "run_id": run_id,
            "total_jobs": len(jobs),
            "failed_jobs": len(failed_jobs),
            "failed_job_details": [],
            "potential_fixes": []
        }

        for job in failed_jobs:
            job_detail = {
                "job_id": job.get("id"),
                "job_name": job.get("name"),
                "status": job.get("status"),
                "conclusion": job.get("conclusion"),
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "steps": []
            }

            # Get detailed step information
            for step in job.get("steps", []):
                if step.get("conclusion") == "failure":
                    step_detail = {
                        "name": step.get("name"),
                        "number": step.get("number"),
                        "conclusion": step.get("conclusion"),
                        "started_at": step.get("started_at"),
                        "completed_at": step.get("completed_at")
                    }
                    job_detail["steps"].append(step_detail)

                    # Identify potential fixes based on step name
                    potential_fix = self.identify_fix_for_step(step.get("name"))
                    if potential_fix and potential_fix not in analysis["potential_fixes"]:
                        analysis["potential_fixes"].append(potential_fix)

            analysis["failed_job_details"].append(job_detail)

        return analysis

    def identify_fix_for_step(self, step_name: str) -> Optional[str]:
        """
        Identify potential fixes based on failed step names.
        """
        step_lower = step_name.lower()

        if "observability" in step_lower or "audit" in step_lower:
            return "Fix: Check observability configuration and audit scripts in backend/monitoring/"
        elif "test" in step_lower or "pytest" in step_lower:
            return "Fix: Run local tests to identify failing tests, check backend/tests/ for specific failures"
        elif "redis" in step_lower or "database" in step_lower:
            return "Fix: Check Redis connection configuration and database connectivity in backend/config/"
        elif "dependency" in step_lower or "poetry" in step_lower:
            return "Fix: Update poetry.lock file or check dependency conflicts in backend/pyproject.toml"
        elif "lint" in step_lower or "format" in step_lower:
            return "Fix: Run code formatter and linter locally before pushing changes"
        elif "build" in step_lower:
            return "Fix: Check build configuration and dependencies in Dockerfile or build scripts"
        elif "deploy" in step_lower:
            return "Fix: Check deployment configuration and credentials in infrastructure/"

        return None

    def suggest_comprehensive_fix(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Suggest comprehensive fixes based on the analysis.
        """
        fixes = []

        for job_detail in analysis["failed_job_details"]:
            job_name = job_detail["job_name"].lower()

            if "observability" in job_name:
                fixes.append("1. Fix observability audit script - check backend/monitoring/observability_audit.py")
                fixes.append("2. Ensure all monitoring endpoints are properly configured")

            if "backend" in job_name and "test" in job_name:
                fixes.append("3. Investigate failing backend tests - run 'poetry run pytest' locally")
                fixes.append("4. Check test database setup and Redis connection in test environment")

        if not fixes:
            fixes.append("1. Re-run the failed workflow after addressing the identified issues")
            fixes.append("2. Check the complete logs for more detailed error messages")

        return fixes

def main():
    analyzer = GitHubFailureAnalyzer()

    # Get recent failed runs
    failed_runs = analyzer.get_recent_failed_runs(limit=3)

    if not failed_runs:
        print("🎉 No failed workflow runs found!")
        return

    # Analyze the most recent failed run
    latest_failed_run = failed_runs[0]
    run_id = latest_failed_run["id"]
    print(f"🚀 Analyzing latest failed run #{run_id} ({latest_failed_run.get('name')})...")
    print(f"📅 Created at: {latest_failed_run.get('created_at')}")
    print(f"🔗 URL: {latest_failed_run.get('html_url')}")

    # Perform detailed analysis
    analysis = analyzer.analyze_failure_patterns(run_id)

    print(f"\n📋 Analysis Results for Run #{analysis['run_id']}:")
    print(f"   Total Jobs: {analysis['total_jobs']}")
    print(f"   Failed Jobs: {analysis['failed_jobs']}")

    if analysis["failed_job_details"]:
        print(f"\n❌ Failed Job Details:")
        for idx, job_detail in enumerate(analysis["failed_job_details"], 1):
            print(f"   {idx}. Job: {job_detail['job_name']} (ID: {job_detail['job_id']})")
            print(f"      Status: {job_detail['conclusion']}")
            print(f"      Failed Steps: {len(job_detail['steps'])}")

            for step in job_detail["steps"]:
                print(f"         - {step['name']} (Step #{step['number']})")

    if analysis["potential_fixes"]:
        print(f"\n🔧 Identified Potential Fixes:")
        for fix in analysis["potential_fixes"]:
            print(f"   - {fix}")

    # Suggest comprehensive fixes
    comprehensive_fixes = analyzer.suggest_comprehensive_fix(analysis)
    print(f"\n💡 Recommended Actions:")
    for fix in comprehensive_fixes:
        print(f"   {fix}")

    # Save analysis to file
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"docs/04-ci-logs/github_failure_analysis_{run_id}_{timestamp_str}.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Analysis saved to: {output_file}")

if __name__ == "__main__":
    main()
