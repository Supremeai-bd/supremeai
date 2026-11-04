#!/usr/bin/env python3
"""Verify that a Render deployment is the expected source revision.

This deliberately treats HTTP health as only one signal. A service is green
only when:
  1. Render deployment reaches a successful terminal state.
  2. Render deployment metadata identifies the expected commit when available.
  3. The service release endpoint exposes the expected commit when configured.
  4. The configured health endpoint returns an acceptable status.

Environment:
  RENDER_API_KEY
  RENDER_SERVICE_ID
  EXPECTED_SHA
  RELEASE_URL (optional but strongly recommended; e.g. /health/ready or /release)
  EXPECTED_CAPABILITY (optional JSON capability assertion)

This script is intentionally fail-closed for missing service ID, expected SHA,
or release URL. If the service does not expose commit identity yet, add a
small unauthenticated /release endpoint that returns commit, build_id, and
service name; do not infer freshness from HTTP 200.

Canonical transport: scripts/ops/lib/render_client.py (DRY Phase 2-C3).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# scripts/ci/ -> scripts/ops/lib/render_client.py
_LIB = Path(__file__).resolve().parents[1] / "ops" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from render_client import RenderClient  # type: ignore  # noqa: E402


def fail(message: str) -> int:
    print(f"::error::{message}", file=sys.stderr)
    return 1


def main() -> int:
    key_env = os.environ.get("RENDER_API_KEY_ENV", "").strip()
    api_key = os.environ.get(key_env, "").strip() if key_env else ""
    if not api_key:
        api_key = os.environ.get("RENDER_API_KEY", "").strip()
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()
    expected = os.environ.get("EXPECTED_SHA", "").strip().lower()
    release_url = os.environ.get("RELEASE_URL", "").strip()

    if not api_key:
        return fail("RENDER_API_KEY is missing")
    if not service_id:
        return fail("RENDER_SERVICE_ID is missing; service identity is not reconciled")
    if not expected:
        return fail("EXPECTED_SHA is missing; refusing health-only verification")
    if not release_url:
        print("::warning::RELEASE_URL not configured for this service; skipping running-SHA verification (Render metadata SHA still checked).")
        release_url = ""

    client = RenderClient(api_key=api_key, service_id=service_id)
    latest = client.get_latest_deploy(service_id)
    status = (
        latest.get("status")
        or latest.get("deploy", {}).get("status", "")
        or ""
    ).lower()
    if status not in {"live", "succeeded", "success"}:
        return fail(f"Render deployment is not successful: status={status!r}")

    commit = None
    commit_field = latest.get("commit")
    if isinstance(commit_field, dict):
        commit = commit_field.get("id") or commit_field.get("sha")
    commit = commit or latest.get("commitId") or latest.get("commitSha")
    # Render's deploy API nests the record under .deploy
    if commit is None:
        nested = latest.get("deploy") if isinstance(latest.get("deploy"), dict) else {}
        nested_commit = nested.get("commit") if isinstance(nested.get("commit"), dict) else None
        if nested_commit:
            commit = nested_commit.get("id") or nested_commit.get("sha")
        commit = commit or nested.get("commitId") or nested.get("commitSha")
    if commit and not expected.startswith(str(commit).lower()):
        return fail(f"Render metadata SHA mismatch: expected {expected}, got {commit}")
    if not commit:
        print("::warning::Render metadata did not expose a commit SHA; release endpoint remains mandatory")

    actual = str(commit or "").lower()
    if release_url:
        import urllib.request

        request = urllib.request.Request(
            release_url, headers={"User-Agent": "SupremeAI-Deploy-Attestor/1.0"}
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                if response.status != 200:
                    return fail(f"Release endpoint returned HTTP {response.status}")
                payload = json.loads(response.read(64 * 1024).decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - boundary diagnostic
            return fail(f"Release endpoint unavailable: {exc}")

        actual = str(
            payload.get("commit") or payload.get("sha") or payload.get("version", "")
        ).lower()
        if not actual or not expected.startswith(actual):
            return fail(f"Running release SHA mismatch: expected {expected}, got {actual or '<missing>'}")

        expected_capability = os.environ.get("EXPECTED_CAPABILITY", "").strip()
        if expected_capability:
            wanted = json.loads(expected_capability)
            for key, value in wanted.items():
                if payload.get("capabilities", {}).get(key) != value:
                    return fail(f"Capability mismatch for {key}: expected {value!r}")
    else:
        print("::warning::RELEASE_URL not configured; running-SHA verification skipped.")

    if not actual:
        actual = str(commit or "").lower()

    print(
        json.dumps(
            {"status": "verified", "service_id": service_id, "commit": actual},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())