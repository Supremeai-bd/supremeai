#!/usr/bin/env python3
"""Evaluate whether the 24h+ opportunistic audit is due.

Timing is handled here (24h/48h). Runner selection is delegated to the workflow
SSOT preflight (scripts/ci/resolve_execution_tier.py) when --timing-only is used.
"""

from __future__ import annotations

import argparse
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
            with open(AUDIT_MARKER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return float(data.get("timestamp", 0))
        except Exception:
            pass
    return 0.0


def save_audit_timestamp(ts: float | None = None) -> None:
    AUDIT_MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    current = ts or time.time()
    with open(AUDIT_MARKER_FILE, "w", encoding="utf-8") as f:
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
        for runner in data.get("runners", []):
            labels = [lbl.get("name") for lbl in runner.get("labels", [])]
            if "local-pc" in labels and runner.get("status") == "online":
                return True
    except Exception as exc:
        print(f"::warning::Failed to query GitHub runners API: {exc}", file=sys.stderr)
    return False
