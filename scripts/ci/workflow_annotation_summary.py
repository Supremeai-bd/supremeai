#!/usr/bin/env python3
"""Summarize completed-run GitHub annotations without copying untrusted messages.

Run only from the trusted default branch on workflow_run, with read-only token.
This reports Actions job annotations plus the same-commit CodeQL check, not
arbitrary log warnings, Dependabot, or alerts that GitHub does not expose here.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from collections import Counter

API = "https://api.github.com"


def pages(path: str, token: str):
    """Fetch a paginated GitHub list; failure must never masquerade as zero."""
    for page in range(1, 101):
        separator = "&" if "?" in path else "?"
        req = urllib.request.Request(
            f"{API}{path}{separator}per_page=100&page={page}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            body = json.load(response)
        yield body
        # Github endpoints may wrap arrays in named objects.
        items = body.get("jobs", body.get("check_runs")) if isinstance(body, dict) else body
        if not isinstance(items, list):
            raise ValueError("Invalid GitHub response")
        if len(items) < 100:
            return
    raise RuntimeError("Pagination limit reached")


def report(repo: str, run: str, attempt: str, sha: str, token: str, fetch=pages) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository")
    if not re.fullmatch(r"[1-9][0-9]*", run) or not re.fullmatch(r"[1-9][0-9]*", attempt):
        raise ValueError("Invalid source run")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha) or not token:
        raise ValueError("Missing source SHA or token")
    root = f"/repos/{repo}"
    jobs = []
    for page in fetch(f"{root}/actions/runs/{run}/attempts/{attempt}/jobs", token):
        jobs.extend(page["jobs"])
    # Treat an empty jobs response as unavailable, never as a clean run.
    if not jobs:
        raise ValueError("No source jobs returned")

    checks = []
    job_statuses = Counter(str(job.get("conclusion") or job.get("status") or "unknown") for job in jobs)
    pending_codeql = 0
    codeql_count = 0
    for job in jobs:
        check_id = job.get("id")
        if not isinstance(check_id, int) or isinstance(check_id, bool) or check_id <= 0:
            raise ValueError("Invalid job id")
        checks.append((check_id, "Actions job"))
    # Security-scanning's CodeQL check is separate from Actions jobs. It is
    # scoped to the same SHA, not necessarily uniquely attributable to this run.
    for page in fetch(f"{root}/commits/{sha}/check-runs", token):
        for check in page["check_runs"]:
            if check.get("name") == "CodeQL" and (check.get("app") or {}).get("slug") == "github-advanced-security":
                cid = check.get("id")
                if isinstance(cid, int) and not isinstance(cid, bool) and cid > 0:
                    checks.append((cid, "Same-SHA CodeQL"))
                    codeql_count += 1
                    if check.get("status") != "completed":
                        pending_codeql += 1

    lines = ["## Warning and failure annotations", "",
             f"Source: [run {run}, attempt {attempt}](https://github.com/{repo}/actions/runs/{run}/attempts/{attempt}) · SHA `{sha[:12]}`", "",
             "| Source | Warning annotations | Failure annotations | Details |", "| --- | ---: | ---: | --- |"]
    totals = Counter()
    seen = set()
    for cid, kind in checks:
        if cid in seen:
            continue
        seen.add(cid)
        counts = Counter()
        for page in fetch(f"{root}/check-runs/{cid}/annotations", token):
            for annotation in page:
                level = annotation.get("annotation_level")
                if level in ("warning", "failure"):
                    counts[level] += 1
        totals.update(counts)
        if counts:
            # Link to the original check; do not copy raw messages, file paths,
            # branch names, or titles into a summary where secrets may be exposed.
            check_url = (f"https://github.com/{repo}/actions/runs/{run}/job/{cid}"
                         if kind == "Actions job" else f"https://github.com/{repo}/runs/{cid}")
            lines.append(f"| {kind} `{cid}` | {counts['warning']} | {counts['failure']} | [Open original check]({check_url}) |")
    lines += ["", f"**Total:** {totals['warning']} warning, {totals['failure']} failure annotations in the sources above.",
              f"Source jobs: {len(jobs)}; skipped: {job_statuses['skipped']}, cancelled: {job_statuses['cancelled']}. "
              f"Same-SHA CodeQL checks found: {codeql_count}; not completed: {pending_codeql}.",
              "Counts are a snapshot; checks still running may add annotations later.", "",
              "Coverage: completed source-run job annotations and same-SHA CodeQL checks only. "
              "Plain log warnings, Dependabot, other commits and inaccessible checks are not included. "
              "Open the original checks for individual messages; this summary does not copy potentially sensitive text."]
    return "\n".join(lines) + "\n"


def main() -> int:
    dest = os.environ.get("GITHUB_STEP_SUMMARY")
    if not dest:
        print("Annotation summary unavailable: no summary path", file=sys.stderr)
        return 1
    try:
        text = report(os.getenv("GITHUB_REPOSITORY", ""), os.getenv("SOURCE_RUN_ID", ""),
                      os.getenv("SOURCE_RUN_ATTEMPT", ""), os.getenv("SOURCE_HEAD_SHA", ""),
                      os.getenv("GH_TOKEN", ""))
    except Exception as exc:
        # No API responses / exception bodies: they could include credentials.
        text = ("## Warning and failure annotations\n\n"
                f"**INCOMPLETE:** could not retrieve all source annotations ({type(exc).__name__}). "
                "Do not interpret this as zero warnings; inspect the source run manually.\n")
        with open(dest, "a", encoding="utf-8") as stream:
            stream.write(text)
        print("::error::Warning summary incomplete; inspect source run manually.", file=sys.stderr)
        return 1
    with open(dest, "a", encoding="utf-8") as stream:
        stream.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
