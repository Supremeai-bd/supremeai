#!/usr/bin/env python3
"""
SupremeAI - Push Summary Generator
Generates a markdown summary of git differences from the latest push using LLM.
Saves the summary as a Markdown file and maintains a rolling window of the last 20 pushes.
"""

import subprocess
import os
import glob
from litellm import completion

SUMMARY_DIR = "docs/autogen/summaries"
LATEST_SUMMARY = "docs/autogen/LATEST-PUSH-SUMMARY.md"
MAX_FILES = 20

def get_git_diff():
    try:
        # Get diff of the most recent commit
        diff = subprocess.check_output(
            ['git', 'diff', 'HEAD~1', 'HEAD'],
            text=True,
            errors='replace'
        )
        return diff
    except subprocess.CalledProcessError as e:
        print(f"Error generating git diff: {e}")
        return ""

def get_latest_commit_hash():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip().decode('utf-8')
    except Exception:
        return "unknown"

def generate_summary(diff_content):
    if not diff_content.strip():
        return "No significant changes found in this push."

    # Cap the diff size to avoid hitting LLM token limits (e.g. max 50KB string)
    max_diff_size = 50 * 1024
    if len(diff_content) > max_diff_size:
        diff_content = diff_content[:max_diff_size] + "\n...[DIFF TRUNCATED]..."

    prompt = f"""
You are an expert Enterprise Software Architect.
Review the following git diff and provide a concise, high-level technical summary of the changes.
List the files changed and summarize the key updates in bullet points.
Highlight any major architectural shifts, security implications, or critical logic updates.
Keep it strictly under 300 words. Format the output in Markdown.

### Git Diff:
```diff
{diff_content}
```
"""

    try:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if "," in api_key:
            os.environ["GEMINI_API_KEY"] = api_key.split(",")[0]

        print("Calling LLM via litellm...")
        response = completion(
            model="gemini/gemini-2.5-pro",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM Generation Error: {e}")
        return f"### Push Summary\nFailed to generate summary via LLM: {str(e)}"

def manage_history():
    files = sorted(glob.glob(os.path.join(SUMMARY_DIR, "PUSH-SUMMARY-*.md")), key=os.path.getmtime)

    if len(files) > MAX_FILES:
        files_to_remove = files[:len(files) - MAX_FILES]
        for f in files_to_remove:
            print(f"Removing old summary: {f}")
            os.remove(f)

def main():
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LATEST_SUMMARY), exist_ok=True)

    print("Generating summary for the latest push...")
    diff = get_git_diff()
    summary = generate_summary(diff)

    commit_hash = get_latest_commit_hash()
    summary_filename = os.path.join(SUMMARY_DIR, f"PUSH-SUMMARY-{commit_hash}.md")

    # Prefix the output
    final_output = f"# SupremeAI Push Summary ({commit_hash})\n\n{summary}"

    with open(summary_filename, "w", encoding="utf-8") as f:
        f.write(final_output)
    print(f"Saved summary to {summary_filename}")

    # Update the LATEST symlink / copy
    with open(LATEST_SUMMARY, "w", encoding="utf-8") as f:
        f.write(final_output)
    print(f"Updated {LATEST_SUMMARY}")

    manage_history()

if __name__ == "__main__":
    main()
