#!/usr/bin/env python3
"""Check CI failures on main branch — create issues for red workflows.

# বাংলা মন্তব্য: main branch-এর সর্বশেষ CI runs চেক করে।
# কোনো workflow fail হলে P1-high issue তৈরি করে।
# Smart Continuous Loop (#2908) এর অংশ — "CI fixer" কম্পোনেন্ট।
"""
from __future__ import annotations
import json, os, sys, subprocess, hashlib
import urllib.request, urllib.error
from typing import Any

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")

def get_recent_failed_runs(limit: int = 10) -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["gh", "run", "list", "--repo", REPO, "--branch", "main",
             "--status", "failure", "--limit", str(limit), "--json",
             "databaseId,name,conclusion,event,createdAt,headSha,url"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode != 0:
            return []
        return json.loads(result.stdout) if result.stdout.strip() else []
    except Exception:
        return []

def get_existing_ci_issues() -> set[str]:
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", REPO, "--state", "open",
             "--label", "ci-failure", "--json", "number,title", "--limit", "50"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if result.returncode != 0:
            return set()
        issues = json.loads(result.stdout) if result.stdout.strip() else []
        fingerprints = set()
        for issue in issues:
            title = issue.get("title", "")
            if "[ci-fail:" in title:
                fp = title.split("[ci-fail:")[1].split("]")[0]
                fingerprints.add(fp)
        return fingerprints
    except Exception:
        return set()

def create_ci_failure_issue(run: dict[str, Any]) -> int | None:
    run_id = run.get("databaseId", "?")
    name = run.get("name", "unknown")
    event = run.get("event", "unknown")
    sha = run.get("headSha", "")[:12]
    url = run.get("url", "")
    created = run.get("createdAt", "")
    fingerprint = f"{name}:{sha}"
    fp_hash = hashlib.md5(fingerprint.encode()).hexdigest()[:12]
    existing = get_existing_ci_issues()
    if fp_hash in existing:
        print(f"  Skip duplicate: {name} @ {sha}")
        return None
    title = f"fix(ci): [ci-fail:{fp_hash}] {name} RED on main ({sha})"
    body = f"## CI Failure on Main\n\n| Field | Value |\n|---|---|\n| Workflow | `{name}` |\n| Event | `{event}` |\n| Commit | `{sha}` |\n| Run ID | `{run_id}` |\n| URL | {url} |\n\n### Reproduction\n```bash\ngh run view {run_id} --repo {REPO} --log-failed\n```\n\n*Auto-filed by check_ci_failures.py (#2908)*"
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    try:
        payload = json.dumps({"title": title, "body": body, "labels": ["P1-high", "area:ci", "type:bug", "ci-failure"]}).encode()
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/issues",
            data=payload, method="POST",
            headers={"Authorization": f"token {gh_token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            issue = json.load(r)
            print(f"  Created issue #{issue['number']}: {title[:60]}")
            return issue["number"]
    except Exception as e:
        print(f"  Could not create issue: {e}", file=sys.stderr)
        return None

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Check CI failures on main")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", type=str)
    args = parser.parse_args()
    print(f"Checking CI failures on {REPO} main branch...")
    failed_runs = get_recent_failed_runs()
    if not failed_runs:
        print("No CI failures found on main. All green!")
        return 0
    print(f"Found {len(failed_runs)} failed run(s):")
    issues_created = []
    for run in failed_runs:
        name = run.get("name", "?")
        sha = run.get("headSha", "")[:12]
        print(f"  {name} @ {sha}")
        if args.dry_run:
            continue
        issue_num = create_ci_failure_issue(run)
        if issue_num:
            issues_created.append(issue_num)
    return 1 if issues_created else 0

if __name__ == "__main__":
    sys.exit(main())
