import os
import sys
import json
import subprocess
import urllib.request
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPICallError
import importlib.util

# Dynamically import the CodeSmellDetector from the backend tools
spec = importlib.util.spec_from_file_location("code_smell_detector", "backend/tools/code_smell_detector.py")
code_smell_detector_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(code_smell_detector_module)
CodeSmellDetector = code_smell_detector_module.CodeSmellDetector

def call_gemini_with_fallback(api_keys, prompt):
    fallback_models = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.0-pro']
    for i, key in enumerate(api_keys):
        for model_name in fallback_models:
            try:
                print(f"Attempting review with Key {i+1} using {model_name}...", file=sys.stderr)
                genai.configure(api_key=key)
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                print(f"Success with Key {i+1} using {model_name}!", file=sys.stderr)
                return response.text
            except ResourceExhausted:
                print(f"Key {i+1} rate limit exhausted for {model_name}. Trying next...", file=sys.stderr)
            except GoogleAPICallError as e:
                if "not found" in str(e).lower() or "not supported" in str(e).lower():
                    print(f"Model {model_name} not supported by Key {i+1}. Trying next model...", file=sys.stderr)
                    continue
                print(f"Key {i+1} failed with API error for {model_name}: {e}. Trying next...", file=sys.stderr)
            except Exception as e:
                print(f"Key {i+1} failed for {model_name}: {e}. Trying next...", file=sys.stderr)
    return None

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
        "User-Agent": "SupremeAI-Review-Script"
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
                
                # Keep last 150 lines of logs to stay within token limits
                log_lines = log_text.splitlines()
                truncated_log = "\n".join(log_lines[-150:])
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

def get_code_smell_suggestions(file_path, api_keys):
    """Runs code smell analysis and generates suggestions for fixes."""
    if not file_path.endswith('.py'):
        return ""

    print(f"Analyzing for code smells: {file_path}", file=sys.stderr)
    try:
        detector = CodeSmellDetector()
        smells = detector.analyze_python_file(file_path, thresholds={"complexity": 10, "lines": 75})
        if not smells:
            return ""

        suggestions_report = "#### 👃 Code Smell Suggestions\n\n"
        for smell in smells:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()

                prompt = f"""
                A code smell was detected in the file `{file_path}`.
                **Smell Type:** {smell.get('type')}
                **Location:** Line {smell.get('line')}
                **Details:** {smell.get('message')}

                Based on this, suggest a concise, corrected code snippet to fix the issue. Provide only the corrected code block in Python, without any explanation.

                Original file content for context:
                ```python
                {file_content}
                ```
                """
                suggestion = call_gemini_with_fallback(api_keys, prompt)
                if suggestion:
                    suggestions_report += f"**- {smell.get('type')} at line {smell.get('line')}:** {smell.get('message')}\n**Suggested Fix:**\n```python\n{suggestion}\n```\n"
            except Exception as e:
                print(f"Error generating suggestion for a smell in {file_path}: {e}", file=sys.stderr)
        return suggestions_report + "\n"
    except Exception as e:
        print(f"Could not run code smell analysis on {file_path}: {e}", file=sys.stderr)
        return ""

def main():
    # Collect API keys
    api_keys = []
    
    if "GEMINI_API_KEYS" in os.environ:
        api_keys.extend([k.strip() for k in os.environ["GEMINI_API_KEYS"].split(",") if k.strip()])
    
    for k, v in os.environ.items():
        if k.startswith("GEMINI_API_KEY") and k != "GEMINI_API_KEYS" and v.strip():
            api_keys.append(v.strip())
            
    if "GEMINI_FREE_API_KEY" in os.environ and os.environ["GEMINI_FREE_API_KEY"].strip():
        api_keys.append(os.environ["GEMINI_FREE_API_KEY"].strip())
        
    if "GEMINI_API_KEY" in os.environ and os.environ["GEMINI_API_KEY"].strip():
        api_keys.append(os.environ["GEMINI_API_KEY"].strip())
        
    api_keys = list(dict.fromkeys(api_keys))
    
    if not api_keys:
        print("Error: No Gemini API Key found. Please set GEMINI_API_KEY, GEMINI_FREE_API_KEY or GEMINI_API_KEYS in secrets.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Found {len(api_keys)} Gemini API Key(s) to use.", file=sys.stderr)

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

    full_report = "## 🤖 Gemini AI Code Review Report\n\n"
    has_changes = False

    if relevant_files:
        print(f"Found {len(relevant_files)} relevant files to review.", file=sys.stderr)
        for file_path in relevant_files:
            print(f"Reviewing: {file_path}", file=sys.stderr)
            
            try:
                file_diff = subprocess.check_output(["git", "diff", "HEAD~1", "HEAD", "--", file_path]).decode("utf-8")
            except Exception:
                try:
                    file_diff = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--cc", "HEAD", "--", file_path]).decode("utf-8")
                except Exception as ex:
                    print(f"Error getting diff for {file_path}: {ex}", file=sys.stderr)
                    continue

            if not file_diff.strip():
                continue

            has_changes = True

            if len(file_diff.splitlines()) > 3000:
                full_report += f"### 📄 File: `{file_path}`\n*⚠️ Skipped: File diff is too large (>3000 lines) for automated review.*\n\n---\n\n"
                continue

            prompt = f"""
            You are an expert Senior Software Engineer specializing in Python/Java backends, Flutter mobile/web applications, and cloud deployments (Google Cloud Run, Firebase). Your task is to perform a strict, highly actionable code review on the provided git diff.

            ### 🛠️ Tech Stack Context
            - Backend: Python / Java
            - Frontend/Admin: Flutter
            - Infrastructure: Firebase, Google Cloud Run

            ### ⚠️ Review Guidelines & Anti-Hallucination Rules
            1. ONLY analyze the exact code provided in the diff below. Do not guess or assume the existence of code outside this diff.
            2. If the diff lacks sufficient context to make a definitive judgment, explicitly state: "Need more context to verify."
            3. Ignore minor stylistic formatting (like tabs vs spaces). Focus purely on bugs, performance, security, and architectural flaws.

            ### 🔍 Focus Areas
            - Python/Java: Look for memory leaks, unhandled exceptions, thread safety issues, and REST API best practices.
            - Flutter: Evaluate state management efficiency, widget tree optimization (avoiding unnecessary rebuilds), and proper disposal of controllers.
            - Infrastructure: Flag any changes that might negatively impact Firebase connections, break Cloud Run deployments, or compromise CI/CD pipelines.

            ### 📝 Output Format
            Use clear Markdown. Group your feedback into the following categories if applicable:
            - 🛑 **Bugs / Errors**
            - 🔒 **Security Vulnerabilities**
            - ⚡ **Performance Improvements**
            - 💡 **Best Practices / Code Smells**
            Provide short, correct code snippets for any fixes you suggest. Keep explanations concise.
            **CRITICAL**: You MUST write the entire review in Bengali (বাংলা).

            Here are the code changes to review in file `{file_path}`:
            {file_diff}
            """

            response_text = call_gemini_with_fallback(api_keys, prompt)
            if response_text:
                full_report += f"### 📄 File: `{file_path}`\n{response_text}\n\n---\n\n"

                # Add code smell analysis for Python files
                smell_suggestions = get_code_smell_suggestions(file_path, api_keys)
                if smell_suggestions:
                    full_report += smell_suggestions
            else:
                full_report += f"### 📄 File: `{file_path}`\n*⚠️ Review skipped or rate-limited for this file.*\n\n---\n\n"
            
            # Rate limit protection for free API keys (15 RPM limit)
            print("Waiting 5 seconds to prevent rate limits...", file=sys.stderr)
            time.sleep(5)
    else:
        print("No relevant files changed to review.", file=sys.stderr)

    if not has_changes:
        full_report += "No relevant code changes found to review.\n\n---\n\n"

    # Fetch and diagnose failed jobs
    failed_logs = get_failed_jobs_logs()
    if failed_logs:
        full_report += "## 🛑 CI/CD Workflow Failure Diagnosis\n\n"
        for item in failed_logs:
            job_name = item["job_name"]
            logs = item["logs"]
            
            prompt = f"""
            You are an expert CI/CD and DevOps engineer. One of the workflow jobs named "{job_name}" failed.
            Here is the end of the execution log:
            
            ```
            {logs}
            ```
            
            Diagnose the failure. Explain what caused the error and suggest a precise solution to fix it. Keep it concise.
            **CRITICAL**: You MUST write the entire diagnosis and solution in Bengali (বাংলা).
            """
            
            print(f"Diagnosing failure in job: {job_name}...", file=sys.stderr)
            diagnosis_text = call_gemini_with_fallback(api_keys, prompt)
            if diagnosis_text:
                full_report += f"### ❌ Failed Job: `{job_name}`\n{diagnosis_text}\n\n---\n\n"

    # Write report to markdown file
    with open("gemini_report.md", "w", encoding="utf-8") as f:
        f.write(full_report)

    # Also output to stdout
    print(full_report)

if __name__ == "__main__":
    main()
