#!/usr/bin/env python3
"""Evaluate runner availability and compute the execution target for CI/CD and Audits.

Evaluation logic (4-Tier SSOT per docs/PR_TO_PRODUCTION_LIFECYCLE.md):
  - Priority 1: Local PC online -> 'local-self-hosted' (0 cloud/render mins)
  - Priority 2: Local offline + Render quota > 50m remaining -> 'render-ci-runner'
  - Priority 3: Local offline + Render CI worker busy but quota < 450m used -> 'github-ubuntu-render-backend'
  - Priority 4: Local offline + Render quota exhausted (>= 450m used) -> 'github-ubuntu-emergency'

Pull requests are not eligible for the persistent personal runner. Render
quota is unknown without an authoritative source, so the active cloud path
is Priority 3. Do not probe the dormant CI runner when quota is unknown.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from http.client import HTTPException
from pathlib import Path

# Reuse the canonical local-runner probe to avoid code duplication (Zero-Recurrence Invariant).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_opportunistic_audit import is_local_runner_online

PROBE_TIMEOUT_S = 4.0
QUOTA_UNKNOWN_REMAINING = 0.0  # sentinel only; never compare when known=False
RENDER_FREE_MONTHLY_LIMIT_MINS = 500.0  # Render free tier monthly build minutes
RENDER_QUOTA_REMAINING_P2_MINS = 50.0  # min remaining minutes required to select Priority 2 (render-ci-runner)
RENDER_QUOTA_MAX_USED_P3_MINS = 450.0  # max used minutes to still allow Priority 3 (github-ubuntu-render-backend)


def get_render_quota_remaining() -> tuple[float, bool]:
    """Return (remaining_minutes, known). known=False always — Render has no public billing/usage API."""
    return QUOTA_UNKNOWN_REMAINING, False


def is_render_ci_worker_available() -> bool:
    """Check if the Render CI runner service is reachable with valid credentials."""
    api_key = (os.environ.get("RENDER_API_KEY_PAYKARI") or "").strip()
    svc_id = (os.environ.get("RENDER_CI_RUNNER_SERVICE_ID") or "").strip()
    if not api_key or not svc_id:
        return False
    try:
        req = urllib.request.Request(
            f"https://api.render.com/v1/services/{svc_id}",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT_S) as resp:
            if resp.status >= 400:
                return False
            data = json.loads(resp.read().decode())
        obj = data.get("service", data) if isinstance(data, dict) else {}
        if isinstance(obj, dict):
            suspended = str(obj.get("suspended") or "").lower() in ("suspended", "true", "1")
            if suspended:
                return False
        return True
    except (OSError, HTTPException, ValueError) as exc:
        print(f"::warning::Render CI worker probe failed ({exc}); not selecting Priority 2", file=sys.stderr)
        return False


def resolve_tier() -> str:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    if event not in {"pull_request", "pull_request_target"} and os.environ.get("ALLOW_LOCAL_CI", "true") == "true":
        try:
            if is_local_runner_online():
                return "local-self-hosted"
        except Exception as exc:  # noqa: BLE001 — probe ব্যর্থ হলেও cloud fallback চালাতে হবে
            print(f"::warning::Local runner probe error ({exc}); continuing to cloud tiers", file=sys.stderr)

    remaining, quota_known = get_render_quota_remaining()
    if not quota_known:
        return "github-ubuntu-render-backend"
    if remaining >= RENDER_QUOTA_REMAINING_P2_MINS and is_render_ci_worker_available():
        return "render-ci-runner"
    if RENDER_FREE_MONTHLY_LIMIT_MINS - remaining < RENDER_QUOTA_MAX_USED_P3_MINS:
        return "github-ubuntu-render-backend"
    return "github-ubuntu-emergency"


def main() -> int:
    tier = resolve_tier()
    print(f"SELECTED_EXECUTION_TIER={tier}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"execution_tier={tier}\n")
            f.write(f"is_local_online={'true' if tier == 'local-self-hosted' else 'false'}\n")
            f.write(f"render_quota_exhausted={'true' if tier == 'github-ubuntu-emergency' else 'false'}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
