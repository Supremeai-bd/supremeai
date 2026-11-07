#!/usr/bin/env python3
"""Publish a signed-by-transport CI result to MCP Tower.

The tower endpoint must authenticate with MCP_TOWER_AUTH_TOKEN and persist:
repo, workflow_run_id, expected_sha, result, runner_service_id, timestamp.
The endpoint must be idempotent on (repo, workflow_run_id).

Environment:
  MCP_TOWER_ATTESTATION_URL
  MCP_TOWER_AUTH_TOKEN
  EXPECTED_SHA            (github.sha)
  CI_RESULT               (job status: success/failure/cancelled)
  RENDER_SVC_ID           (optional override for runner_service_id)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request


def fail(message: str) -> int:
    print(f"::error::{message}", file=sys.stderr)
    return 1


def main() -> int:
    url = os.environ.get("MCP_TOWER_ATTESTATION_URL", "").strip()
    token = os.environ.get("MCP_TOWER_AUTH_TOKEN", "").strip()
    if not url:
        print("::warning::MCP_TOWER_ATTESTATION_URL not configured; result not published")
        return 0
    if not token:
        print("::warning::MCP_TOWER_AUTH_TOKEN not configured; result not published")
        return 0

    payload = {
        "repo": os.environ.get("GITHUB_REPOSITORY", "Supremeai-bd/supremeai"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "expected_sha": os.environ.get("EXPECTED_SHA", ""),
        "result": os.environ.get("CI_RESULT", "unknown"),
        "runner_service": os.environ.get(
            "RENDER_SERVICE_ID",
            os.environ.get("RENDER_SVC_ID", os.environ.get("RENDER_CI_RUNNER_SERVICE_ID", os.environ.get("RENDER_CI_RUNNER_SVC_ID", "")))
        ),
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status >= 300:
                return fail(f"MCP Tower returned HTTP {response.status}")
    except Exception as exc:  # noqa: BLE001 - boundary diagnostic, non-blocking
        print(f"::warning::CI attestation not published to MCP Tower: {exc}")
        return 0
    print("CI attestation published to MCP Tower")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())