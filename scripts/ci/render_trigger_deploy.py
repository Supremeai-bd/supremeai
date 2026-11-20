#!/usr/bin/env python3
"""Trigger and optionally wait for a Render deploy using only the assigned service key.

Runtime credentials are provisioned on the service, never read or written by CI.
When RENDER_HEALTH_PATH is set, resolve release and canary URLs from the exact
service ID in Render's metadata. No hardcoded host or other account is tried.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from render_client import RenderApiError, RenderClient

MAX_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 10

# Epic #1850 Phase C / issue #1855: opt-in wait-to-terminal-state mode. The old
# behavior (POST and exit — fire-and-forget) is why the */5 deploy-doctor poller
# existed; in-run terminal-state detection replaces it. Enabled by the
# render-deploy-status composite via RENDER_WAIT=1.
RENDER_WAIT = os.environ.get("RENDER_WAIT", "").strip().lower() in ("1", "true", "yes")
REQUIRE_EXPECTED_SHA = os.environ.get("REQUIRE_EXPECTED_SHA", "").strip().lower() in ("1", "true", "yes")
POLL_INTERVAL_SECONDS = 15
POLL_TIMEOUT_SECONDS = int(os.environ.get("RENDER_WAIT_TIMEOUT_SECONDS", "660"))
FAIL_STATES = {"build_failed", "update_failed", "deactivated", "canceled"}
OK_STATES = {"live"}

def _write_output(**fields: str) -> None:
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            for name, value in fields.items():
                stream.write(f"{name}={value}\n")


def _allow_ci_fallback() -> None:
    """Mark only strict CI attempts without a valid result as eligible for fallback."""
    if REQUIRE_EXPECTED_SHA:
        _write_output(fallback_allowed="true")


def _unavailable(reason: str) -> int:
    print(f"::error::{reason}")
    _allow_ci_fallback()
    return 2 if REQUIRE_EXPECTED_SHA else 1


def _suspended(svc_id: str) -> int:
    _write_output(deploy_status="not_run")
    if REQUIRE_EXPECTED_SHA and os.environ.get("RENDER_AUXILIARY") != "1":
        return _unavailable(f"Render service {svc_id} is suspended; no verified result.")
    print(f"::warning::Render service {svc_id} is suspended; deployment not run.")
    if gh_env := os.environ.get("GITHUB_ENV"):
        with open(gh_env, "a", encoding="utf-8") as stream:
            stream.write("RENDER_SERVICE_SUSPENDED=1\n")
    return 0


def _service_origin(service: object, svc_id: str) -> str:
    record = service.get("service", service) if isinstance(service, dict) else None
    if not isinstance(record, dict) or record.get("id") != svc_id:
        raise ValueError("Render returned a different service ID")
    details = record.get("serviceDetails")
    origin = details.get("url") if isinstance(details, dict) else None
    if not isinstance(origin, str) or not re.fullmatch(r"https://[a-z0-9-]+\.onrender\.com/?", origin):
        raise ValueError("Render service has no direct HTTPS onrender.com URL")
    return origin.rstrip("/")


def main() -> int:
    svc_id = (os.environ.get("RENDER_SERVICE_ID") or os.environ.get("RENDER_SVC_ID", "")).strip()
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    if not re.fullmatch(r"srv-[a-z0-9]+", svc_id):
        return _unavailable("A valid Render service ID is required.")
    if not api_key:
        return _unavailable("No Render credential configured for this service.")

    expected_sha = os.environ.get("EXPECTED_SHA", "").strip().lower()
    if REQUIRE_EXPECTED_SHA and not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        return _unavailable("Strict deploy requires a full EXPECTED_SHA.")
    strict_sha = expected_sha if REQUIRE_EXPECTED_SHA else None
    commit_id = expected_sha or os.environ.get("GITHUB_SHA", "").strip() or None
    client = RenderClient(api_key=api_key, service_id=svc_id)

    if health_path := os.environ.get("RENDER_HEALTH_PATH", ""):
        if not re.fullmatch(r"/[A-Za-z0-9_/-]+", health_path) or health_path.startswith("//"):
            return _unavailable("Invalid Render canary path.")
        try:
            origin = _service_origin(client.get_service(svc_id), svc_id)
        except (RenderApiError, OSError, ValueError):
            return _unavailable(f"Cannot resolve release target for {svc_id} with its assigned Render credential.")
        _write_output(release_url=f"{origin}/release", health_url=f"{origin}{health_path}")

    #: Why the last attempt failed. Without this the loop's terminal message was
    #: "Render did not return a deploy" for every cause alike — the job failed
    #: with a bare exit code and nothing to act on (brain, 2026-11-20 19:20).
    last_reason = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            body = client.trigger_deploy(svc_id, commit_id=commit_id)
            break
        except TypeError:
            # A TypeError here is a CODE defect (e.g. trigger_deploy losing its
            # `commit_id` parameter in commit e24921b92d36), not a transient API
            # error. Retrying it 5x turned a one-line signature break into a
            # 10-second failed deploy job per service, reported only as
            # "Process completed with exit code 1". Fail immediately and say why.
            raise SystemExit(
                "::error::render_trigger_deploy/client signature mismatch — "
                "RenderClient.trigger_deploy must accept commit_id"
            )
        except RenderApiError as exc:
            err_body = (exc.body or "").lower()
            if exc.status == 400 and "cannot deploy suspended service" in err_body:
                return _suspended(svc_id)
            if exc.status == 404 and "does not have a commit" in err_body:
                return _unavailable(f"Render service cannot build {commit_id}; refusing branch-HEAD fallback.")
            # No credential discovery or retries on permanent client errors.
            if exc.status not in (0, 408, 429) and exc.status < 500:
                return _unavailable(f"Render rejected the deploy for {svc_id} (HTTP {exc.status}).")
            last_reason = f"HTTP {exc.status}: {(exc.body or str(exc))[:200]}"
            print(f"Render trigger attempt {attempt}/{MAX_ATTEMPTS} failed (status {exc.status}).")
        except (OSError, ValueError) as exc:
            last_reason = f"{type(exc).__name__}: {exc}"[:200]
            print(f"Render trigger attempt {attempt}/{MAX_ATTEMPTS} did not return a valid response: {exc}")
        if attempt == MAX_ATTEMPTS:
            return _unavailable(
                f"Render did not return a deploy for {svc_id} after {MAX_ATTEMPTS} attempts"
                + (f" — last error: {last_reason}" if last_reason else "")
            )
        time.sleep(RETRY_DELAY_SECONDS)
    else:
        return 1

    if not (RENDER_WAIT or REQUIRE_EXPECTED_SHA):
        print(f"Deploy triggered for {svc_id} (not verified).")
        return 0
    return wait_for_terminal_state(client, svc_id, body, expected_sha=strict_sha)


def deploy_record(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {}
    record = payload.get("deploy", payload)
    return record if isinstance(record, dict) else {}


def deploy_commit(record: dict) -> str | None:
    commit = record.get("commit")
    sha = (commit.get("id") or commit.get("sha")) if isinstance(commit, dict) else None
    sha = sha or record.get("commitId") or record.get("commitSha")
    return sha if isinstance(sha, str) else None


def _brief(payload: object, limit: int = 240) -> str:
    """Truncated repr of an API payload, for a useful error line."""
    text = repr(payload)
    return text if len(text) <= limit else text[:limit] + "…"


def _same_sha(a: str | None, b: str | None) -> bool:
    """Compare SHAs tolerantly: Render may echo a short form of the commit."""
    if not a or not b:
        return False
    a, b = a.strip().lower(), b.strip().lower()
    return a == b or a.startswith(b) or b.startswith(a)


def recover_deploy_id(
    client: "RenderClient", svc_id: str, trigger_body: object, expected_sha: str | None
) -> str | None:
    """Recover a deploy id when the trigger response omitted it.

    Render accepted the trigger but sometimes answers POST /deploys with a body
    that carries no `id` — on 2026-11-21 that failed the `mcp` deploy job with
    rc 2 ("strict CI cannot verify this deploy") even though the deploy had
    been created. The id is one GET away, so fetch the service's latest deploy
    instead of giving up.

    Recovery is only accepted when the recovered deploy's commit matches the
    expected SHA: otherwise an older deploy could be polled and reported as
    this one, which is the false-green this strict mode exists to prevent.
    """
    try:
        latest = client.get_latest_deploy(svc_id)
    except Exception as exc:  # noqa: BLE001 - any transport failure means "no recovery"
        print(f"Deploy id recovery failed for {svc_id}: {type(exc).__name__}: {exc}")
        return None

    record = deploy_record(latest)
    candidate = record.get("id")
    if not isinstance(candidate, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", candidate):
        print(f"Deploy id recovery found no usable id for {svc_id}: {_brief(latest)}")
        return None

    if expected_sha:
        built = deploy_commit(record)
        if not _same_sha(built, expected_sha):
            print(
                f"Recovered deploy {candidate} for {svc_id} builds {built!r}, "
                f"not the expected {expected_sha!r} — refusing to poll it."
            )
            return None

    print(f"Recovered deploy id {candidate} for {svc_id} from the deploy list (trigger body carried none).")
    return candidate


def wait_for_terminal_state(
    client: RenderClient, svc_id: str, trigger_body: dict, *, expected_sha: str | None = None
) -> int:
    """Poll the triggered deploy to a terminal state (issue #1855).

    A completed build failure is never eligible for fallback. In strict mode,
    success also requires the full expected SHA; missing evidence returns 2.
    Non-strict deployments retain the legacy pre_live timeout tolerance.
    """
    deploy_id = deploy_record(trigger_body).get("id")
    if not isinstance(deploy_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", deploy_id):
        deploy_id = recover_deploy_id(client, svc_id, trigger_body, expected_sha)
    if not isinstance(deploy_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", deploy_id):
        if expected_sha:
            print(
                "::error::Deploy trigger response carried no id and none could be "
                f"recovered; strict CI cannot verify this deploy. trigger body={_brief(trigger_body)}"
            )
            _allow_ci_fallback()
            return 2
        print("Deploy trigger response carried no id — cannot poll; treating as triggered (legacy behavior)")
        return 0

    _write_output(deploy_id=deploy_id)
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    last = None
    while time.monotonic() < deadline:
        try:
            deploy = client.get_deploy(deploy_id, svc_id)
        except (RenderApiError, OSError, ValueError):
            print("Render deploy poll failed; will retry.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        deploy = deploy_record(deploy)
        last = deploy.get("status")
        if last in OK_STATES:
            if expected_sha:
                if deploy.get("id") != deploy_id or deploy_commit(deploy) != expected_sha:
                    print("::error::Live Render deploy did not match the triggered ID and commit.")
                    _allow_ci_fallback()
                    return 2
                _write_output(verified_sha=expected_sha)
            print(f"Deploy {deploy_id} reached terminal state: live ✓")
            return 0
        if last in FAIL_STATES:
            print(f"Deploy {deploy_id} reached terminal FAILURE state: {last}")
            return 1
        print(f"Deploy {deploy_id} status: {last} (polling every {POLL_INTERVAL_SECONDS}s)...")
        time.sleep(POLL_INTERVAL_SECONDS)

    if last == "pre_live":
        if expected_sha:
            print("::error::Strict CI deploy did not reach live; allow GitHub fallback.")
            _allow_ci_fallback()
            return 2
        print(f"::warning::Deploy {deploy_id} still pre_live after {POLL_TIMEOUT_SECONDS}s — build finished, traffic promotion pending; treating as success.")
        return 0
    print(f"::error::Deploy {deploy_id} did not reach a terminal state within {POLL_TIMEOUT_SECONDS}s (last: {last}).")
    _allow_ci_fallback()
    return 2 if expected_sha else 1


if __name__ == "__main__":
    sys.exit(main())
