#!/usr/bin/env python3
"""Evaluate runner availability and compute the execution target for CI/CD and Audits.

Evaluation logic (4-Tier SSOT per docs/PR_TO_PRODUCTION_LIFECYCLE.md):
  - Priority 1: Local PC online -> 'local-self-hosted' (0 cloud/render mins)
  - Priority 2: Local offline + Render quota > 50m remaining -> 'render-ci-runner'
  - Priority 3: Local offline + Render CI worker busy but quota < 450m used -> 'github-ubuntu-render-backend'
  - Priority 4: Local offline + Render quota exhausted (>= 450m used) -> 'github-ubuntu-emergency'
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request


def is_local_runner_online() -> bool:
    """Check GitHub repository runner status via GitHub API."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "Supremeai-bd/supremeai")

    if not token:
        return False

    url = f"https://api.github.com/repos/{repo}/actions/runners"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "SupremeAI-Runner-Dispatcher",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        runners = data.get("runners", [])
        for runner in runners:
            labels = [lbl.get("name") for lbl in runner.get("labels", [])]
            if "local-pc" in labels and runner.get("status") == "online":
                return True
    except Exception as exc:
        print(f"::warning::Failed to query GitHub runners API: {exc}")

    return False


def get_render_quota_remaining() -> float:
    """Estimate remaining Render build minutes for primary account."""
    api_key = os.environ.get("RENDER_API_KEY_PAYKARI") or os.environ.get("RENDER_API_KEY")
    if not api_key:
        return 500.0

    try:
        req = urllib.request.Request(
            "https://api.render.com/v1/billing/usage",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        limit = float(data.get("limit") or data.get("monthlyLimit") or 500.0)
        used = float(data.get("used") or data.get("usedMinutes") or 0.0)
        return max(0.0, limit - used)
    except Exception:
        return 500.0


def is_render_ci_worker_available() -> bool:
    """Check if the Render CI runner service is online and not busy."""
    # The Render CI runner (srv-dbl8tbmtlv9c73bbkvqg) is considered available
    # if the Render API key is configured. Actual busy-state is checked at dispatch.
    api_key = os.environ.get("RENDER_API_KEY_PAYKARI") or os.environ.get("RENDER_API_KEY")
    return bool(api_key)


def resolve_tier() -> str:
    # Priority 1: Local PC Online
    if is_local_runner_online():
        return "local-self-hosted"

    remaining = get_render_quota_remaining()
    used = 500.0 - remaining

    # Priority 2: Render CI Runner (quota > 50m remaining)
    if remaining >= 50.0 and is_render_ci_worker_available():
        return "render-ci-runner"

    # Priority 3: GitHub Ubuntu + Render backend free build time (< 450m used)
    if used < 450.0:
        return "github-ubuntu-render-backend"

    # Priority 4: GitHub Ubuntu Emergency (quota exhausted)
    return "github-ubuntu-emergency"


def main() -> int:
    tier = resolve_tier()
    print(f"SELECTED_EXECUTION_TIER={tier}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"execution_tier={tier}\n")
            f.write(f"is_local_online={'true' if tier == 'local-self-hosted' else 'false'}\n")
            f.write(f"render_quota_exhausted={'true' if tier == 'github-ubuntu-emergency' else 'false'}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
