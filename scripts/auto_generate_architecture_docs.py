#!/usr/bin/env python3
"""
SupremeAI - Auto Generate Architecture Docs
Analyzes recent git changes and generates/updates:
- Architecture Decision Records (ADR)
- Data Flow Diagrams (DFD - Mermaid.js)
- Sequence Diagrams (Mermaid.js)
- Security Threat Models
"""

import subprocess
from pathlib import Path
from litellm import completion

def get_recent_diff():
    try:
        # Get diff of the most recent push (or just HEAD~1 if not available)
        diff = subprocess.check_output(['git', 'diff', 'HEAD~1', 'HEAD'], text=True, errors='replace')
        return diff
    except subprocess.CalledProcessError:
        return ""

def call_llm(prompt):
    try:
        import os
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if "," in api_key:
            os.environ["GEMINI_API_KEY"] = api_key.split(",")[0]

        print("Calling LLM via litellm...")
        response = completion(
            model="gemini/gemini-2.5-pro",
            messages=[{"role": "user", "content": prompt}],
            timeout=60
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM Generation Error: {e}")
        return ""

def generate_adr(diff):
    print("Generating ADR...")
    prompt = f"""
You are an expert Enterprise Software Architect. Review this git diff and determine if a new Architecture Decision Record (ADR) is needed.
If yes, write a concise ADR in Markdown format. If no architectural changes are present, output EXACTLY "NO_ADR_NEEDED".
Git Diff:
```diff
{diff[:20000]}
```
"""
    result = call_llm(prompt)
    if "NO_ADR_NEEDED" not in result and result.strip():
        # Find a suitable filename
        adr_count = len(list(Path('.').glob('ADR-*.md'))) + 1
        filename = f"ADR-{adr_count:03d}-auto-generated.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Created {filename}")

def generate_diagrams(diff):
    print("Generating Mermaid Diagrams (DFD & Sequence)...")
    prompt = f"""
You are an expert Systems Architect. Analyze this git diff and generate:
1. A Data Flow Diagram (DFD) using Mermaid.js syntax.
2. A Sequence Diagram using Mermaid.js syntax.

Important: ONLY output valid Mermaid code blocks (```mermaid ... ```).
Do not output anything else. Include both diagrams in your response.

Git Diff:
```diff
{diff[:20000]}
```
"""
    result = call_llm(prompt)
    if "```mermaid" in result:
        diagram_count = len(list(Path('.').glob('DIAGRAM-*.md'))) + 1
        filename = f"DIAGRAM-{diagram_count:03d}-auto-generated.md"
        content = f"# Auto-Generated Architecture Diagrams\n\n{result}"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created {filename}")

def update_threat_model(diff):
    print("Updating Threat Model...")
    prompt = f"""
You are an Elite Cyber Security Auditor. Analyze this git diff for new API routes, external calls, or data access.
Mandate: Check for Auth, SSRF, and Injection vulnerabilities for any new routes.
If you find new security implications, write an update for the Threat Model in Markdown.
If no security changes are present, output EXACTLY "NO_THREAT_UPDATES".

Git Diff:
```diff
{diff[:20000]}
```
"""
    result = call_llm(prompt)
    if "NO_THREAT_UPDATES" not in result and result.strip():
        tm_file = Path("THREAT-MODEL-001-authentication.md")
        if tm_file.exists():
            with open(tm_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n## Auto-Generated Security Audit Update\n\n{result}")
            print(f"Updated {tm_file}")
        else:
            with open("THREAT-MODEL-auto-generated.md", "w", encoding="utf-8") as f:
                f.write(result)
            print("Created THREAT-MODEL-auto-generated.md")

def main():
    diff = get_recent_diff()
    if not diff.strip():
        print("No diff found. Exiting.")
        return

    generate_adr(diff)
    generate_diagrams(diff)
    update_threat_model(diff)

if __name__ == "__main__":
    main()
