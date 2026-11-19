#!/usr/bin/env python3
"""Attest the exact triggered Render deployment and the running release SHA.

Health checks remain a separate canary. Missing, stale or mismatched evidence
must never emit 'verified'. An explicitly optional auxiliary target that was
not deployed may emit 'not_run', which is not release evidence.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

if __package__:
    from .render_trigger_deploy import (
        RenderApiError, RenderClient, _collect_candidate_keys, deploy_commit, deploy_record,
    )
else:
    from render_trigger_deploy import (
        RenderApiError, RenderClient, _collect_candidate_keys, deploy_commit, deploy_record,
    )


def main() -> int:
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()
    deploy_id = os.environ.get("RENDER_DEPLOY_ID", "").strip()
    expected = os.environ.get("EXPECTED_SHA", "").strip().lower()
    release_url = os.environ.get("RELEASE_URL", "").strip()
    optional = os.environ.get("RENDER_AUXILIARY") == "1"

    def report(status: str, reason: str = "") -> int:
        result = {"status": status, "service_id": service_id}
        if status == "verified":
            result.update(commit=expected, deploy_id=deploy_id)
        else:
            result["reason"] = reason
            level = "error" if status == "unverified" else "warning"
            print(f"::{level}::Render release {status}: {reason}", file=sys.stderr)
        print(json.dumps(result, sort_keys=True))
        return 1 if status == "unverified" else 0

    if not service_id or not re.fullmatch(r"[0-9a-f]{40}", expected):
        return report("unverified", "Missing service ID or full EXPECTED_SHA")
    if os.environ.get("RENDER_SERVICE_SUSPENDED") == "1":
        state = "not_run" if optional and not deploy_id else "unverified"
        return report(state, "Render service suspended")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", deploy_id):
        return report("unverified", "Triggered deploy ID is required")
    if not release_url.startswith("https://") and not (optional and not release_url):
        return report("unverified", "HTTPS RELEASE_URL is required")

    key_env = os.environ.get("RENDER_API_KEY_ENV", "").strip() or "RENDER_API_KEY"
    candidate_keys = _collect_candidate_keys(key_env)
    record = None
    for _, key in candidate_keys:
        try:
            client = RenderClient(api_key=key, service_id=service_id)
            record = deploy_record(client.get_deploy(deploy_id, service_id))
            break
        except RenderApiError as exc:
            if exc.status in (401, 403, 404):
                continue
            return report("unverified", "Render deploy metadata unavailable")
        except (OSError, ValueError):
            return report("unverified", "Render deploy metadata unavailable or invalid")
    if not record:
        return report("unverified", "No metadata for the triggered Render deploy")
    if record.get("id") != deploy_id or record.get("status") != "live":
        return report("unverified", "The triggered Render deploy is not live")
    if deploy_commit(record) != expected:
        return report("unverified", "Render deploy commit does not match EXPECTED_SHA")
    if not release_url:
        return report("metadata_only", "CI runner has no runtime release target; not release evidence")

    try:
        request = urllib.request.Request(
            release_url, headers={"User-Agent": "SupremeAI-Deploy-Attestor/1.0"}
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            if response.status != 200 or response.geturl() != release_url:
                return report("unverified", "Configured runtime release endpoint did not answer directly with HTTP 200")
            payload = json.loads(response.read(64 * 1024).decode("utf-8"))
    except (OSError, ValueError):
        return report("unverified", "Runtime release endpoint unavailable or invalid")
    if not isinstance(payload, dict) or (payload.get("commit") or payload.get("sha")) != expected:
        return report("unverified", "Running release commit does not match EXPECTED_SHA")

    if wanted := os.environ.get("EXPECTED_CAPABILITY", "").strip():
        try:
            expected_capabilities = json.loads(wanted)
        except ValueError:
            return report("unverified", "Invalid EXPECTED_CAPABILITY configuration")
        actual = payload.get("capabilities")
        if not isinstance(expected_capabilities, dict) or not isinstance(actual, dict) or any(
            actual.get(key) != value for key, value in expected_capabilities.items()
        ):
            return report("unverified", "Runtime capabilities do not match")
    return report("verified")


if __name__ == "__main__":
    sys.exit(main())
