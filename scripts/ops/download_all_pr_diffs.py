#!/usr/bin/env python3
"""Unified Intelligent Merged PR Diff Downloader & Synchronizer.

Features:
1. Fast-Path (Local Git Log): Scans local commit history to extract all merged PRs instantly with zero network cost.
2. Remote API Probe (GitHub REST): Checks GitHub API for newly merged PRs not yet pulled to local git.
3. Smart Skip & Deduplication: Automatically detects already downloaded diffs on disk (files > 0 bytes)
   and skips them, downloading strictly the new/missing merged PRs.
4. Auto-Retry & Safe I/O: Resilient parallel downloads with retry handling and Windows console encoding safety.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Safe Windows stdout wrapper
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = "Supremeai-bd/supremeai-open"
TARGET_DIR = Path(os.environ.get("PR_DIFF_DIR") or Path(__file__).resolve().parent.parent.parent / "docs" / "archive" / "merged_pr_diffs")
MAX_WORKERS = 8

def get_token() -> str:
    umbrella = r"C:\Users\N\AppData\Local\Temp\supremeai-umbrella"
    if os.path.exists(umbrella):
        res = subprocess.run(["git", "remote", "get-url", "origin"], cwd=umbrella, capture_output=True, text=True)
        url = res.stdout.strip()
        if "@" in url:
            return url.split("@")[0].split(":")[-1]
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""

TOKEN = get_token()

def get_prs_from_local_git() -> dict[int, str]:
    """Extract PR numbers and commit SHAs directly from local git log."""
    res = subprocess.run(["git", "log", "--format=%H %s"], capture_output=True, text=True, errors="replace")
    pr_map = {}
    for line in res.stdout.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            sha, msg = parts
            m = re.search(r"\(#(\d+)\)", msg) or re.search(r"Merge pull request #(\d+)", msg)
            if m:
                pr_num = int(m.group(1))
                if pr_num not in pr_map:
                    pr_map[pr_num] = sha
    return pr_map

def get_latest_remote_merged_prs() -> list[int]:
    """Quickly probe GitHub API for the most recent closed/merged PRs (page 1-3)."""
    headers = {"User-Agent": "SupremeAI-Agent", "Accept": "application/vnd.github.v3+json"}
    if TOKEN:
        headers["Authorization"] = "token " + TOKEN
    
    remote_prs = []
    for page in range(1, 4):
        url = f"https://api.github.com/repos/{REPO}/pulls?state=closed&per_page=100&page={page}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if not data:
                    break
                for p in data:
                    if p.get("merged_at"):
                        remote_prs.append(p["number"])
        except Exception:
            break
    return remote_prs

def download_diff_for_pr(pr_num: int, sha: str = "") -> tuple[int, bool, str]:
    out_file = TARGET_DIR / f"pr_{pr_num}.diff"
    
    # 1. Try local git show if commit SHA is known
    if sha:
        git_res = subprocess.run(["git", "show", sha], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if git_res.returncode == 0 and len(git_res.stdout) > 0:
            with open(out_file, "wb") as f:
                f.write(git_res.stdout)
            return pr_num, True, f"git show {sha[:7]}"

    # 2. Fallback to GitHub REST API with vnd.github.v3.diff
    headers = {"User-Agent": "SupremeAI-Agent", "Accept": "application/vnd.github.v3.diff"}
    if TOKEN:
        headers["Authorization"] = "token " + TOKEN
    url = f"https://api.github.com/repos/{REPO}/pulls/{pr_num}"
    
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                content = resp.read()
                if content:
                    with open(out_file, "wb") as f:
                        f.write(content)
                    return pr_num, True, f"api ({len(content)} bytes)"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return pr_num, False, "404 Not Found"
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
            
    return pr_num, False, "failed after 3 retries"

def main():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print("[1/3] Scanning PR sources (Local Git Log + Remote API)...")
    
    local_map = get_prs_from_local_git()
    remote_prs = get_latest_remote_merged_prs()
    
    all_known_prs = dict(local_map)
    for r_num in remote_prs:
        if r_num not in all_known_prs:
            all_known_prs[r_num] = ""
            
    sorted_prs = sorted(list(all_known_prs.keys()))
    print(f"   Found {len(sorted_prs)} total merged PRs (Range: #{sorted_prs[0]} to #{sorted_prs[-1]}).")

    print("\n[2/3] Checking local storage for existing diff files...")
    existing_files = {int(f.stem.replace("pr_", "")) for f in TARGET_DIR.glob("pr_*.diff") if f.stat().st_size > 0}
    
    missing_prs = [p for p in sorted_prs if p not in existing_files]
    
    print(f"   Total Merged PRs : {len(sorted_prs)}")
    print(f"   Already Downloaded (Skipped) : {len(existing_files)}")
    print(f"   Missing to Download          : {len(missing_prs)}")

    if not missing_prs:
        print("\n[PASS] 100% of all merged PR diffs are already downloaded and up to date! Nothing to do.")
        return

    print(f"\n[3/3] Downloading {len(missing_prs)} missing PR diffs...")
    done = 0
    failed = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_diff_for_pr, p, all_known_prs.get(p, "")): p for p in missing_prs}
        for future in as_completed(futures):
            pr_num, ok, info = future.result()
            done += 1
            if not ok:
                failed += 1
                print(f"   [FAIL] PR #{pr_num} -> FAILED ({info})")
            if done % 100 == 0 or done == len(missing_prs):
                print(f"   Progress: {done}/{len(missing_prs)} ({done*100//len(missing_prs)}%) - Failed: {failed}")
                
    elapsed = time.time() - start_time
    total_on_disk = len(list(TARGET_DIR.glob("pr_*.diff")))
    print(f"\nSync completed in {elapsed:.1f}s! Total diffs in storage: {total_on_disk}")

if __name__ == "__main__":
    main()
