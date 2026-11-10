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


def _get_candidate_tokens() -> list[str]:
    tokens: list[str] = []
    # Collect candidate tokens from environment (PATs take precedence over default GITHUB_TOKEN)
    env_keys = [
        "OPEN_SYNC_PAT",
        "SELF_HEAL_PAT",
        "SYNC_PAT",
        "OPEN_DISPATCH_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
    ]
    for key in env_keys:
        val = (os.environ.get(key) or "").strip()
        if val and val not in tokens:
            tokens.append(val)

    # Local development fallback via GitHub CLI if available
    if not tokens:
        try:
            import subprocess
            out = subprocess.check_output(["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL).strip()
            if out:
                tokens.append(out)
        except Exception:
            pass

    return tokens


def is_local_runner_online(timeout: float = 4.0) -> bool:
    tokens = _get_candidate_tokens()
    repo = os.environ.get("GITHUB_REPOSITORY", "Supremeai-bd/supremeai")
    if not tokens:
        print("DEBUG: no token available", file=sys.stderr)
        return False

    url = f"https://api.github.com/repos/{repo}/actions/runners"

    for token in tokens:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "SupremeAI-Audit-Dispatcher",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            for runner in data.get("runners", []):
                labels = [lbl.get("name") for lbl in runner.get("labels", [])]
                name = runner.get("name", "")
                is_online = runner.get("status") == "online"
                if is_online and ("local-pc" in labels or "self-hosted" in labels or "supremeai-local-pc" in name):
                    return True
            # Successfully queried API but runner was not found or offline
            return False
        except urllib.error.HTTPError as http_err:
            # 401/403: token lacks runner read permissions; try next candidate token
            if http_err.code in (401, 403):
                continue
            print(f"::warning::GitHub runners API HTTP {http_err.code}: {http_err.reason}", file=sys.stderr)
        except Exception as exc:
            print(f"::warning::Failed to query GitHub runners API: {exc}", file=sys.stderr)

    return False
