#!/usr/bin/env python3
"""High-speed indexer for downloaded PR diffs.

Parses all merged PR diff files in docs/archive/merged_pr_diffs/ to extract:
- PR number
- List of files modified/added/deleted
- Insertions and deletions count
- Summary & metadata
Outputs a unified JSON index (docs/archive/pr_diff_index.json) that agents
and the MCP Control Tower can query with sub-millisecond latency.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# Windows console encoding safety
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DIFF_DIR = Path(os.environ.get("PR_DIFF_DIR") or REPO_ROOT / "docs" / "archive" / "merged_pr_diffs")
OUTPUT_INDEX = Path(os.environ.get("PR_DIFF_INDEX") or REPO_ROOT / "docs" / "archive" / "pr_diff_index.json")


def parse_diff_file(file_path: Path) -> dict:
    pr_num = int(file_path.stem.replace("pr_", ""))
    files = []
    additions = 0
    deletions = 0
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("diff --git a/"):
                    parts = line.strip().split(" ")
                    if len(parts) >= 4:
                        f_name = parts[2][2:] # strip a/
                        if f_name not in files:
                            files.append(f_name)
                elif line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1
    except Exception:
        pass
        
    return {
        "pr": pr_num,
        "files": files,
        "additions": additions,
        "deletions": deletions,
        "diff_path": f"docs/archive/merged_pr_diffs/{file_path.name}"
    }


def main():
    print("[1/3] Scanning diff files on disk...")
    diff_files = sorted(list(DIFF_DIR.glob("pr_*.diff")), key=lambda p: int(p.stem.replace("pr_", "")))
    print(f"   Found {len(diff_files)} diff files to index.")
    
    start_time = time.time()
    records = []
    file_to_prs = {}
    
    print("\n[2/3] Extracting file changes, additions, and deletions...")
    for i, df in enumerate(diff_files):
        rec = parse_diff_file(df)
        records.append(rec)
        for f in rec["files"]:
            file_to_prs.setdefault(f, []).append(rec["pr"])
            
        if (i + 1) % 500 == 0 or (i + 1) == len(diff_files):
            print(f"   Indexed {i + 1}/{len(diff_files)} PRs...")

    index_data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_prs": len(records),
        "total_unique_files_tracked": len(file_to_prs),
        "prs": records,
        "file_index": file_to_prs
    }

    print("\n[3/3] Saving pr_diff_index.json...")
    with open(OUTPUT_INDEX, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)
        
    elapsed = time.time() - start_time
    file_mb = OUTPUT_INDEX.stat().st_size / (1024 * 1024)
    print(f"\n[DONE] Built PR Intelligence Index in {elapsed:.2f}s!")
    print(f"   Saved to: {OUTPUT_INDEX}")
    print(f"   Index Size: {file_mb:.2f} MB")
    print(f"   Unique files indexed: {len(file_to_prs)}")


if __name__ == "__main__":
    main()

