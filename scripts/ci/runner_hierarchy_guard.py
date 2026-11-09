#!/usr/bin/env python3
"""Enforce Universal 4-Level Runner Hierarchy guard (constitutional, warn-only default)."""
from __future__ import annotations
import argparse, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"
DEPLOY_NAME_RE = re.compile(r"deploy|release-publish|publish-release|cloudflare|vercel|render.*service|no-render-deploy|verify.*render.*service|attest", re.I)
ALLOW = {"evaluate-audit-timing", "detect-changes", "resolve-execution-tier"}

def split_jobs(text):
    jobs = {}
    for m in re.finditer(r"^  ([a-zA-Z0-9_-]+):\s*$", text, re.M):
        name = m.group(1); start = m.end()
        n = re.search(r"^  [a-zA-Z0-9_-]+:\s*$", text[start:], re.M)
        jobs[name] = text[start:start + n.start() if n else None]
    return jobs

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--strict", action="store_true"); args = ap.parse_args()
    issues = []
    for p in sorted(WF.glob("*.yml")):
        t = p.read_text(encoding="utf-8", errors="ignore")
        has_preflight = ("resolve-execution-tier" in t) or ("resolve_execution_tier" in t)
        for name, block in split_jobs(t).items():
            runs = re.search(r"^\s*runs-on:\s*(.+)$", block, re.M)
            if not runs or "ubuntu" not in runs.group(1): continue
            tm = re.search(r"^\s*timeout-minutes:\s*(\d+)", block, re.M)
            minutes = int(tm.group(1)) if tm else 0
            gated = ("resolve-execution-tier" in block) or ("hierarchy-exception:" in block)
            if minutes >= 15 and not gated and not DEPLOY_NAME_RE.search(name) and name not in ALLOW:
                issues.append(f"{p.name}:{name} ubuntu timeout={minutes}m missing hierarchy gate/exception")
            if has_preflight and minutes >= 30 and "resolve-execution-tier" not in block and "hierarchy-exception:" not in block and not DEPLOY_NAME_RE.search(name):
                issues.append(f"{p.name}:{name} heavy({minutes}m) on ubuntu without resolve-execution-tier dependency")
    for i in issues: print(("ERROR" if args.strict else "WARN") + ": " + i)
    print(f"runner_hierarchy_guard: {len(issues)} issue(s) ({'strict' if args.strict else 'warn-only'})")
    return 1 if (issues and args.strict) else 0

if __name__ == "__main__": raise SystemExit(main())
