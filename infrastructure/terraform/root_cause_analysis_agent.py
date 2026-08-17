# backend/analysis/root_cause_analysis_agent.py

import re
import json
from typing import List, Dict, Any, Optional

# Placeholder for external clients
# from backend.clients.github_client import GitHubClient # এটি একটি বাস্তব ক্লায়েন্ট হবে
# from some_llm_provider import LLMClient
# from some_git_provider import GitClient
# from core.database import get_db_pool  # As per db_context.xml


class RootCauseAnalysisAgent:
    """
    AI-Powered Root Cause Analysis Agent.
    This agent analyzes logs, traces, and git history to identify the root cause of system errors.
    It is designed to evolve from simple error pattern matching to complex, AI-driven diagnostics.
    """

    def __init__(
        self,
        llm_client: Any,
        db_pool: Any,
        git_client: Any,
        github_client: Optional[Any] = None,
    ):
        """
        Initializes the agent with necessary clients.

        Args:
            llm_client: A client to interact with a Large Language Model (e.g., Gemini).
            db_pool: An async database connection pool for accessing the error remediation knowledge base.
            git_client: A client for interacting with Git repositories (e.g., for 'git blame').
            github_client: A client for interacting with the GitHub API (e.g., to create issues).
        """
        self.llm_client = llm_client
        self.db_pool = db_pool
        self.git_client = git_client
        self.github_client = github_client
        # Regex for common error patterns (e.g., NullPointerException, TimeoutException)
        self.common_error_patterns = [
            re.compile(r".*NullPointerException.*"),
            re.compile(r".*TimeoutException.*"),
            re.compile(r"status=5\d{2}"),
        ]

    async def _parse_logs(self, log_files: List[str]) -> List[Dict[str, Any]]:
        """
        Parses log files to extract structured error information.
        This can be expanded to support various log formats (JSON, plain text, etc.).

        Args:
            log_files: A list of paths to log files.

        Returns:
            A list of dictionaries, each representing a structured log entry.
        """
        print("Parsing log files...")
        structured_logs = []
        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        for pattern in self.common_error_patterns:
                            if match := pattern.search(line):
                                structured_logs.append(
                                    {
                                        "file": log_file,
                                        "raw_log": line.strip(),
                                        "error_type": match.group(0),  # উদাহরণস্বরূপ
                                    }
                                )
            except FileNotFoundError:
                print(f"Warning: Log file not found at {log_file}")
        print(f"Found {len(structured_logs)} relevant log entries.")
        return structured_logs

    async def _parse_traces(self, trace_files: List[str]) -> List[Dict[str, Any]]:
        """
        Parses distributed tracing files (e.g., from OpenTelemetry, Jaeger)
        to identify high-latency spans or error-prone services.

        Args:
            trace_files: A list of paths to trace data files.

        Returns:
            A list of dictionaries representing problematic trace spans.
        """
        print("Parsing trace files...")
        # Dummy implementation: In a real system, this would parse formats like JSON from Jaeger/Zipkin.
        problematic_spans = []
        for trace_file in trace_files:
            try:
                with open(trace_file, "r", encoding="utf-8") as f:
                    trace_data = json.load(f)
                    for trace in trace_data.get("data", []):
                        for span in trace.get("spans", []):
                            if span.get("error") or span.get("duration_ms", 0) > 1000:
                                problematic_spans.append(span)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Warning: Could not process trace file {trace_file}. Error: {e}")

        print(f"Found {len(problematic_spans)} problematic trace spans.")
        return problematic_spans

    async def _get_context_from_git(
        self, file_path: str, line_number: int
    ) -> Optional[Dict[str, str]]:
        """
        Uses 'git blame' to find the last commit and author related to a specific line of code.

        Args:
            file_path: The path to the source code file.
            line_number: The line number where the error occurred.

        Returns:
            A dictionary with commit hash, author, and date, or None if not found.
        """
        print(f"Running git blame on {file_path}:{line_number}...")
        try:
            return self.git_client.blame(file_path, line_number)
        except Exception as e:
            print(f"Error running git blame: {e}")
            return None

    async def analyze(
        self, incident_id: str, log_files: List[str], trace_files: List[str]
    ) -> Dict[str, Any]:
        """
        Main analysis pipeline. It orchestrates parsing, context gathering, and AI-driven diagnosis.

        Args:
            incident_id: A unique ID for the incident being analyzed.
            log_files: A list of paths to relevant log files.
            trace_files: A list of paths to relevant trace files.

        Returns:
            A dictionary containing the analysis summary and recommended actions.
        """
        print(f"Starting root cause analysis for incident: {incident_id}")
        logs = await self._parse_logs(log_files)
        traces = await self._parse_traces(trace_files)

        # উদাহরণস্বরূপ, প্রথম লগ থেকে ফাইল পাথ এবং লাইন নম্বর বের করা
        # বাস্তব ক্ষেত্রে এটি আরও জটিল হবে
        git_context = (
            await self._get_context_from_git("src/payment_processor.py", 42)
            if logs
            else None
        )

        # Prepare prompt for the LLM
        prompt = f"""
        Incident ID: {incident_id}
        Error Logs: {json.dumps(logs, indent=2)}
        Problematic Traces: {json.dumps(traces, indent=2)}
        Git Context (from blame): {json.dumps(git_context, indent=2)}

        Based on the data above, what is the most likely root cause of the incident?
        Suggest a code patch and/or an architectural improvement.
        Format the output as a JSON object with keys 'root_cause', 'code_patch_suggestion', and 'architecture_suggestion'.
        """

        print("Sending data to LLM for final diagnosis...")
        try:
            llm_response_str = await self.llm_client.generate(prompt)
            analysis_result = json.loads(llm_response_str)
        except Exception as e:
            print(f"Error during LLM diagnosis: {e}")
            analysis_result = {
                "root_cause": "Failed to get a diagnosis from the LLM.",
                "code_patch_suggestion": "N/A",
                "architecture_suggestion": "N/A",
            }
        print("Analysis complete.")
        return analysis_result

    def create_github_issue(
        self, incident_id: str, analysis_result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Creates a GitHub issue based on the analysis result.

        Args:
            incident_id: The unique ID of the incident.
            analysis_result: The result from the analyze() method.

        Returns:
            A dictionary with the created issue's details, or None if the client is not configured.
        """
        if not self.github_client:
            print("GitHub client is not configured. Skipping issue creation.")
            return None

        title = f"Bug: Automated RCA for Incident {incident_id}"

        body = f"""
### 🚨 Automated Root Cause Analysis Report

**Incident ID:** `{incident_id}`

---

### 🕵️ Root Cause
_{analysis_result.get("root_cause", "Not determined.")}_

---

### 💡 Code Patch Suggestion
```python
{analysis_result.get("code_patch_suggestion", "No suggestion available.")}
```

### 🏛️ Architectural Suggestion
{analysis_result.get("architecture_suggestion", "No suggestion available.")}
"""
        labels = ["bug", "autogenerated", "needs-review"]
        try:
            created_issue = self.github_client.create_issue(
                title=title, body=body.strip(), labels=labels
            )
            print(f"Successfully created GitHub issue: {created_issue.get('html_url')}")
            return created_issue
        except Exception as e:
            print(f"Failed to create GitHub issue: {e}")
            return None
