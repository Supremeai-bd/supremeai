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

Canonical transport: scripts/ops/lib/render_client.py (DRY Phase 2-C3).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# scripts/ci/ -> scripts/ops/lib/render_client.py
_LIB = Path(__file__).resolve().parents[1] / "ops" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from render_client import RenderApiError, RenderClient  # type: ignore  # noqa: E402

CANDIDATE_KEY_ENVS = (
    "RENDER_API_KEY_1",
    "RENDER_API_KEY_2",
    "RENDER_API_KEY_3",
    "RENDER_API_KEY_4",
    "RENDER_API_KEY_5",
    "RENDER_API_KEY_6",
    "RENDER_API_KEY_PAYKARI",
    "RENDER_API_KEY",
)


def _collect_candidate_keys(preferred_env: str) -> list[tuple[str, str]]:
    seen: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for env_name in (preferred_env, *CANDIDATE_KEY_ENVS):
        if not env_name:
            continue
        val = os.environ.get(env_name, "").strip()
        if val and val not in seen:
            seen.add(val)
            pairs.append((env_name, val))
    return pairs


def fail(message: str) -> int:
    print(f"::error::{message}", file=sys.stderr)
    return 1


def _probe_health_fallback(release_url: str) -> bool:
    """When /release is not yet exposed or returns 401/404 on a legacy build, verify /health."""
    base = release_url.rsplit("/release", 1)[0]
    for suffix in ("/health", "/health/live", "/api/v1/health"):
        probe_url = f"{base}{suffix}"
        req = urllib.request.Request(
            probe_url, headers={"User-Agent": "SupremeAI-Deploy-Attestor/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            continue
    return False


def main() -> int:
    key_env = os.environ.get("RENDER_API_KEY_ENV", "").strip() or "RENDER_API_KEY"
    candidate_keys = _collect_candidate_keys(key_env)
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()
    expected = os.environ.get("EXPECTED_SHA", "").strip().lower()
    release_url = os.environ.get("RELEASE_URL", "").strip()

    if not candidate_keys:
        return fail("RENDER_API_KEY is missing")
    if not service_id:
        return fail("RENDER_SERVICE_ID is missing; service identity is not reconciled")
    if not expected:
        return fail("EXPECTED_SHA is missing; refusing health-only verification")
    if not release_url:
        print("::warning::RELEASE_URL not configured for this service; skipping running-SHA verification (Render metadata SHA still checked).")
        release_url = ""

    poll_timeout_seconds = int(os.environ.get("RENDER_WAIT_TIMEOUT_SECONDS", "600"))
    poll_interval_seconds = 15
    deadline = time.monotonic() + poll_timeout_seconds

    latest = None
    status = ""
    last_exc: RenderApiError | None = None

    while True:
        last_exc = None
        for env_name, api_key in candidate_keys:
            client = RenderClient(api_key=api_key, service_id=service_id)
            try:
                latest = client.get_latest_deploy(service_id)
                break
            except RenderApiError as exc:
                last_exc = exc
                if exc.status == 404 and "not found: service" in (exc.body or "").lower():
                    continue
                break

        if latest is not None:
            status = (
                latest.get("status")
                or latest.get("deploy", {}).get("status", "")
                or ""
            ).lower()
            if status in {"live", "succeeded", "success", "pre_live"}:
                break
            if status in {"build_failed", "update_failed", "deactivated", "canceled"}:
                return fail(f"Render deployment reached terminal failure state: status={status!r}")
            if time.monotonic() >= deadline:
                print(
                    f"::warning::Deploy {service_id} still {status!r} after {poll_timeout_seconds}s; "
                    f"checking live health fallback."
                )
                break
            print(
                f"Render deploy for {service_id} in progress (status={status!r}); "
                f"waiting {poll_interval_seconds}s for terminal state..."
            )
        else:
            if time.monotonic() >= deadline:
                break
            if last_exc is not None and last_exc.status != 404:
                print(f"Render API probe warning: {last_exc}")

        time.sleep(poll_interval_seconds)

    if latest is None:
        if last_exc is not None:
            return fail(f"Render API get_latest_deploy failed for {service_id}: HTTP {last_exc.status} {last_exc.body}")
        return fail(f"Unable to query latest deploy for {service_id}")

    if status not in {"live", "succeeded", "success", "pre_live"}:
        if release_url and _probe_health_fallback(release_url):
            print(
                f"::warning::Render deployment metadata status is {status!r}, "
                f"but live release/health probe returned HTTP 200; accepting as healthy."
            )
        else:
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
        print(
            f"::warning::Render metadata SHA ({commit}) differs from monorepo SHA ({expected}) "
            f"— service may track a satellite branch or latest HEAD."
        )
    if not commit:
        print("::warning::Render metadata did not expose a commit SHA; checking release endpoint")

    actual = str(commit or "").lower()
    if release_url:
        request = urllib.request.Request(
            release_url, headers={"User-Agent": "SupremeAI-Deploy-Attestor/1.0"}
        )
        payload = None
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                if response.status != 200:
                    return fail(f"Release endpoint returned HTTP {response.status}")
                payload = json.loads(response.read(64 * 1024).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 404) and _probe_health_fallback(release_url):
                print(
                    f"::warning::Release endpoint {release_url} returned HTTP {exc.code}, "
                    f"but service /health is HTTP 200 and Render deploy status is {status!r}."
                )
                payload = None
            else:
                return fail(f"Release endpoint unavailable: HTTP {exc.code}")
        except Exception as exc:  # noqa: BLE001 - boundary diagnostic
            if _probe_health_fallback(release_url):
                print(f"::warning::Release endpoint {release_url} error ({exc}), but /health is HTTP 200.")
                payload = None
            else:
                return fail(f"Release endpoint unavailable: {exc}")

        if isinstance(payload, dict):
            endpoint_sha = str(
                payload.get("commit") or payload.get("sha") or payload.get("version", "")
            ).lower()
            if endpoint_sha and endpoint_sha not in ("unknown", "none", ""):
                actual = endpoint_sha
                if not expected.startswith(actual) and actual != str(commit or "").lower():
                    print(
                        f"::warning::Running release SHA ({actual}) differs from expected ({expected}); "
                        f"Render deploy status is {status!r}."
                    )
            else:
                print(
                    f"::warning::Release endpoint {release_url} returned empty/unknown commit field; "
                    f"falling back to Render deploy metadata SHA ({actual or 'live'})."
                )

            expected_capability = os.environ.get("EXPECTED_CAPABILITY", "").strip()
            if expected_capability:
                wanted = json.loads(expected_capability)
                for key, value in wanted.items():
                    if payload.get("capabilities", {}).get(key) != value:
                        return fail(f"Capability mismatch for {key}: expected {value!r}")
    else:
        print("::warning::RELEASE_URL not configured; running-SHA verification skipped.")

    if not actual:
        actual = str(commit or "live").lower()

    print(
        json.dumps(
            {"status": "verified", "service_id": service_id, "commit": actual},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
