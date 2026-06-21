import os
import sys
import json
import subprocess
import urllib.request

def get_failed_jobs_logs():
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo or not run_id or not token:
        print("Missing GITHUB_REPOSITORY, GITHUB_RUN_ID, or GITHUB_TOKEN. Skipping log diagnosis.", file=sys.stderr)
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "SupremeAI-Prompt-Generator"
    }

    try:
        url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        
        failed_jobs = []
        for job in data.get("jobs", []):
            if job.get("conclusion") == "failure":
                job_id = job.get("id")
                job_name = job.get("name")
                failed_jobs.append((job_id, job_name))
        
        diagnoses = []
        for job_id, job_name in failed_jobs:
            if "AI Code Review" in job_name: # Avoid self-diagnosis loop
                continue
            try:
                log_url = f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}/logs"
                log_req = urllib.request.Request(log_url, headers=headers)
                with urllib.request.urlopen(log_req) as log_response:
                    log_text = log_response.read().decode("utf-8", errors="ignore")
                
                # Keep last 200 lines of logs to stay within token limits
                log_lines = log_text.splitlines()
                truncated_log = "\n".join(log_lines[-200:])
                diagnoses.append({
                    "job_name": job_name,
                    "logs": truncated_log
                })
            except Exception as ex:
                print(f"Error fetching logs for job {job_name} ({job_id}): {ex}", file=sys.stderr)
        return diagnoses
    except Exception as e:
        print(f"Error checking failed jobs: {e}", file=sys.stderr)
        return []

def main():
    # Get modified files list
    try:
        changed_files = subprocess.check_output(["git", "diff", "--name-only", "HEAD~1", "HEAD"]).decode("utf-8").splitlines()
    except Exception:
        try:
            changed_files = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"]).decode("utf-8").splitlines()
        except Exception as ex:
            print(f"Error getting changed files list: {ex}", file=sys.stderr)
            sys.exit(1)

    allowed_extensions = ('.java', '.dart', '.py', '.ts', '.js', '.tsx', '.jsx', '.json', '.yml', '.yaml')
    relevant_files = [f for f in changed_files if f.endswith(allowed_extensions)]

    final_output = """You are an expert Senior Software Engineer and DevOps Architect.
Please review the following codebase changes and CI/CD diagnostic logs.
Provide a comprehensive review including:
- Bugs and logical errors
- Security vulnerabilities
- Performance and scalability bottlenecks
- Code style, smells, and best practices
Provide specific, optimized code fixes and configurations where necessary.
Respond in Bengali (বাংলা).

### 🛠️ Tech Stack Context
- Backend: Python FastAPI / Java Spring Boot
- Frontend & Client: React/Next.js (Studio), Flutter (Mobile)
- Databases & AI: Firebase, Pinecone vector store, Gemini API
- Infrastructure: Google Cloud Run, Docker, GHA

---
## 📄 Code Changes
"""

    has_changes = False
    for file_path in relevant_files:
        try:
            file_diff = subprocess.check_output(["git", "diff", "HEAD~1", "HEAD", "--", file_path]).decode("utf-8")
        except Exception:
            try:
                file_diff = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--cc", "HEAD", "--", file_path]).decode("utf-8")
            except Exception:
                continue

        if not file_diff.strip():
            continue

        has_changes = True
        final_output += f"\n### File: `{file_path}`\n```diff\n{file_diff}\n```\n"

    if not has_changes:
        final_output += "\nNo file changes found in this commit.\n"

    # Get failed jobs logs
    failed_logs = get_failed_jobs_logs()
    if failed_logs:
        final_output += "\n---\n## 🛑 CI/CD Failure Diagnostic Logs\n"
        for item in failed_logs:
            final_output += f"\n### Failed Job: `{item['job_name']}`\n```\n{item['logs']}\n```\n"

    # Save to file
    with open("ai_review_prompt.txt", "w", encoding="utf-8") as f:
        f.write(final_output)

    print("Successfully generated ai_review_prompt.txt")

if __name__ == "__main__":
    main()
