#!/usr/bin/env python3
"""Evaluate whether the 24h+ opportunistic audit is due and whether local runner is available.

Rules:
  - If <24h since last audit: skip.
  - If >=24h and local runner is online: trigger audit on local runner.
  - If >=48h (grace window expired): trigger emergency audit on cloud.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AUDIT_MARKER_FILE = Path("config/ci/last_nightly_audit.json")


def get_last_audit_timestamp() -> float:
    if AUDIT_MARKER_FILE.exists():
        try:
            with open(AUDIT_MARKER_FILE, "r") as f:
                data = json.load(f)
            return float(data.get("timestamp", 0))
        except Exception:
            pass
    return 0.0


def save_audit_timestamp(ts: float | None = None) -> None:
    AUDIT_MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    current = ts or time.time()
    with open(AUDIT_MARKER_FILE, "w") as f:
        json.dump(
            {
                "timestamp": current,
                "iso": datetime.fromtimestamp(current, tz=timezone.utc).isoformat(),
            },
            f,
            indent=2,
        )


def is_local_runner_online() -> bool:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    print(f"DEBUG: GH_TOKEN set={bool(os.environ.get('GH_TOKEN'))} GITHUB_TOKEN set={bool(os.environ.get('GITHUB_TOKEN'))}", file=sys.stderr)
    repo = os.environ.get("GITHUB_REPOSITORY", "Supremeai-bd/supremeai")
    if not token:
        print("DEBUG: no token available", file=sys.stderr)
        return False

    url = f"https://api.github.com/repos/{repo}/actions/runners"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "SupremeAI-Audit-Dispatcher",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        print(f"DEBUG: runner count={len(data.get('runners', []))}", file=sys.stderr)
        for r in data.get("runners", []):
            print(f"DEBUG: name={r.get('name')} status={r.get('status')} labels={[l.get('name') for l in r.get('labels', [])]}", file=sys.stderr)
        for runner in data.get("runners", []):
            labels = [lbl.get("name") for lbl in runner.get("labels", [])]
            if "local-pc" in labels and runner.get("status") == "online":
                return True
    except Exception as exc:
        print(f"::warning::Failed to query GitHub runners API: {exc}", file=sys.stderr)
    return False
