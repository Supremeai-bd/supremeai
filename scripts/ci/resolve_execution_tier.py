#!/usr/bin/env python3
"""Evaluate runner availability and compute the execution target for CI/CD and Audits.

Evaluation logic:
  - Check GitHub API for active self-hosted runners tagged 'local-pc'.
  - If online: return 'local-self-hosted'.
  - If offline: check Render quota via render_quota_preflight logic.
  - If Render quota >= 50: return 'render-source-build'.
  - Otherwise: return 'render-ci-runner' (emergency fallback).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request


def is_local_runner_online() -> bool:
    """Check GitHub repository runner status via GitHub CLI or API."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "Supremeai-bd/supremeai")

    if not token:
        # If running inside GitHub Actions without token, assume false or check local runner
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
        # Default safe assumption
        return 500.0


def resolve_tier() -> str:
    # Priority 1: Local PC Online
    if is_local_runner_online():
        return "local-self-hosted"

    # Priority 2: Render Free Quota Available
    remaining = get_render_quota_remaining()
    if remaining >= 50.0:
        return "render-cloud-free"

    # Priority 3: Emergency Fallback
    return "render-ci-runner-paykari"


def main() -> int:
    tier = resolve_tier()
    print(f"SELECTED_EXECUTION_TIER={tier}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"execution_tier={tier}\n")
            f.write(f"is_local_online={'true' if tier == 'local-self-hosted' else 'false'}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
