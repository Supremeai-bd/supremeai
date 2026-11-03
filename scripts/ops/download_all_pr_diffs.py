#!/usr/bin/env python3
"""Robust binary-mode downloader for remaining PR diffs.

Fixes Windows CP1252 charmap decode issues by reading subprocess streams
as raw bytes and decoding safely as UTF-8 with replacement.
"""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = "Supremeai-bd/supremeai-open"
TARGET_DIR = Path(r"C:\Users\N\.gemini\antigravity\brain\44c47523-286f-4e09-ab34-a3964341cc01\pr_diffs")
REPO_DIR = Path(r"F:\supremeai-open")
MAX_WORKERS = 8


def fetch_merged_prs() -> list[int]:
    cmd = ["gh", "pr", "list", "--repo", REPO, "--state", "merged", "--limit", "5000", "--json", "number"]
    res = subprocess.run(cmd, capture_output=True, cwd=str(REPO_DIR))
    if res.returncode != 0:
        print(f"Error fetching PR list: {res.stderr.decode('utf-8', errors='ignore')}")
        sys.exit(1)
    data = json.loads(res.stdout.decode("utf-8", errors="ignore"))
    return [item["number"] for item in data]


def get_missing_prs(all_prs: list[int]) -> list[int]:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    missing = []
    for pr in all_prs:
        file_path = TARGET_DIR / f"pr_{pr}.diff"
        if not file_path.exists() or file_path.stat().st_size == 0:
            missing.append(pr)
    return missing


def download_single_pr(pr: int) -> tuple[int, bool, str]:
    out_file = TARGET_DIR / f"pr_{pr}.diff"
    
    # Attempt 1: Raw binary gh pr diff
    cmd = ["gh", "pr", "diff", str(pr), "--repo", REPO]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(REPO_DIR))
    
    if res.returncode == 0 and len(res.stdout) > 0:
        with open(out_file, "wb") as f:
            f.write(res.stdout)
        return pr, True, "gh pr diff"
    
    # Attempt 2: Fallback for 300+ files limit or API blocks
    view_cmd = ["gh", "pr", "view", str(pr), "--repo", REPO, "--json", "mergeCommit", "--jq", ".mergeCommit.oid"]
    view_res = subprocess.run(view_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(REPO_DIR))
    commit_sha = view_res.stdout.decode("utf-8", errors="ignore").strip()
    
    if commit_sha:
        git_show_cmd = ["git", "show", commit_sha]
        git_res = subprocess.run(git_show_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(REPO_DIR))
        if git_res.returncode == 0 and len(git_res.stdout) > 0:
            with open(out_file, "wb") as f:
                f.write(git_res.stdout)
            return pr, True, f"git show {commit_sha[:8]}"

    err_msg = res.stderr.decode("utf-8", errors="ignore").strip()[:80]
    return pr, False, err_msg if err_msg else "empty diff"


def main():
    print("[1/3] Checking PR status...")
    all_prs = fetch_merged_prs()
    missing_prs = get_missing_prs(all_prs)
    total_missing = len(missing_prs)
    
    print(f"Total Merged PRs: {len(all_prs)}")
    print(f"Already Downloaded: {len(all_prs) - total_missing}")
    print(f"Remaining Missing: {total_missing}")

    if not missing_prs:
        print("✅ 100% of all merged PR diffs are downloaded and ready!")
        return

    print(f"[2/3] Downloading remaining {total_missing} diffs (raw binary mode)...")
    success = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_single_pr, pr): pr for pr in missing_prs}
        for future in as_completed(futures):
            pr = futures[future]
            try:
                pr_num, ok, info = future.result()
                if ok:
                    success += 1
                    print(f"[{success + failed}/{total_missing}] PR #{pr_num} -> OK ({info})")
                else:
                    failed += 1
                    print(f"[{success + failed}/{total_missing}] PR #{pr_num} -> FAILED ({info})")
            except Exception as e:
                failed += 1
                print(f"[{success + failed}/{total_missing}] PR #{pr} -> Exception: {e}")

    print("\n" + "=" * 60)
    print(f"Batch completed: {success} newly downloaded, {failed} failed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
