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
    repo = os.environ.get("GITHUB_REPOSITORY", "Supremeai-bd/supremeai")
    if not token:
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
    except Exception:
        pass
    return False


def main() -> int:
    last_ts = get_last_audit_timestamp()
    now = time.time()
    elapsed_hours = (now - last_ts) / 3600.0

    print(f"Hours elapsed since last audit: {elapsed_hours:.2f}h")

    should_run = False
    target = "skip"

    if elapsed_hours < 24.0 and last_ts > 0:
        print("Audit status: WITHIN_24H_CYCLE (Skipped)")
        target = "skip"
    elif is_local_runner_online():
        print("Audit status: DUE_AND_LOCAL_ONLINE (Target: local-pc)")
        should_run = True
        target = "local-self-hosted"
    elif elapsed_hours >= 48.0:
        print("Audit status: GRACE_EXPIRED_EMERGENCY_CLOUD (Target: cloud-fallback)")
        should_run = True
        target = "cloud-fallback"
    else:
        print("Audit status: DUE_WAITING_FOR_LOCAL_WAKE (Grace window active)")
        target = "wait-local-wake"

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"should_run={'true' if should_run else 'false'}\n")
            f.write(f"audit_target={target}\n")

    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--record":
        save_audit_timestamp()
        print("Saved current timestamp as last audit marker.")
        sys.exit(0)
    sys.exit(main())
