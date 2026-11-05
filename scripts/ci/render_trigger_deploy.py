#!/usr/bin/env python3
"""
Shared Render deploy trigger script used by all CI deploy jobs
(Core / Worker / Scraper / MCP Control Tower).

Reads configuration from environment variables so no secret interpolation
or f-string quoting inside a `python -c "..."` YAML block is ever needed:

    RENDER_API_KEY   - Render API key (required to actually trigger a deploy)
    RENDER_SVC_ID    - Render service ID to deploy (if unset, the job is skipped)

Note: For the Service Modularization/OOM Mitigation feature, ensure that the
Render Dashboard is configured with the `SUPREMEAI_SERVICE_ROLE` environment
variable for each respective service (`core`, `worker`, `scraper`).

Exits 0 when a deploy is skipped (missing service id) or successfully
triggered. Exits non-zero after exhausting retries on failure.

DRY Phase 2-C3: transport migrated onto scripts/lib/render_client.py —
the retry policy (5 attempts / 10 s) stays here because it is this job's
own concern; auth/URL/error normalization is the client's.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from render_client import RenderApiError, RenderClient  # noqa: E402

MAX_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 10

# Epic #1850 Phase C / issue #1855: opt-in wait-to-terminal-state mode. The old
# behavior (POST and exit — fire-and-forget) is why the */5 deploy-doctor poller
# existed; in-run terminal-state detection replaces it. Enabled by the
# render-deploy-status composite via RENDER_WAIT=1.
RENDER_WAIT = os.environ.get("RENDER_WAIT", "").strip().lower() in ("1", "true", "yes")
POLL_INTERVAL_SECONDS = 15
POLL_TIMEOUT_SECONDS = int(os.environ.get("RENDER_WAIT_TIMEOUT_SECONDS", "660"))
FAIL_STATES = {"build_failed", "update_failed", "deactivated", "canceled"}
OK_STATES = {"live"}

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

BOOTSTRAP_ENV_SYNC_KEYS = (
    "INFISICAL_CLIENT_ID",
    "INFISICAL_CLIENT_SECRET",
    "INFISICAL_PROJECT_ID",
    "INFISICAL_PROJECT_SLUG",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_KEY",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "VERCEL_TOKEN",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "RENDER_API_KEY_1",
    "RENDER_API_KEY_2",
    "RENDER_API_KEY_3",
    "RENDER_API_KEY_4",
    "RENDER_API_KEY_5",
    "RENDER_API_KEY_6",
    "RENDER_API_KEY_PAYKARI",
)


def _collect_candidate_keys(preferred_env: str) -> list[tuple[str, str]]:
    """Return deduplicated (env_name, key_value) pairs starting with preferred_env."""
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


def _resolve_owning_client(
    svc_id: str, candidate_keys: list[tuple[str, str]]
) -> tuple[str, RenderClient]:
    """Probe candidate API keys via get_service(svc_id) to find the owning workspace key."""
    for env_name, api_key in candidate_keys:
        probe = RenderClient(api_key=api_key, service_id=svc_id)
        try:
            probe.get_service(svc_id)
            return env_name, probe
        except RenderApiError as exc:
            if exc.status in (401, 403, 404):
                continue
            return env_name, probe
        except Exception:  # noqa: BLE001
            continue
    first_env, first_key = candidate_keys[0]
    return first_env, RenderClient(api_key=first_key, service_id=svc_id)


def _sync_bootstrap_env_vars(client: RenderClient, svc_id: str) -> None:
    """Merge non-empty CI bootstrap env vars into the Render service before deploy (zero secret logging)."""
    desired: dict[str, str] = {}
    for key in BOOTSTRAP_ENV_SYNC_KEYS:
        val = os.environ.get(key, "").strip()
        if val:
            desired[key] = val
    # Ensure generic RENDER_API_KEY and GITHUB_TOKEN are also populated if fallback keys exist
    if not desired.get("RENDER_API_KEY") and client.api_key:
        desired["RENDER_API_KEY"] = client.api_key
    gh_pat = (
        os.environ.get("OPEN_SYNC_PAT", "").strip()
        or os.environ.get("SYNC_PAT", "").strip()
        or os.environ.get("SELF_HEAL_PAT", "").strip()
    )
    if gh_pat:
        desired["GITHUB_PAT_PAYKARIBAZARONLINE"] = gh_pat
        desired["GITHUB_TOKEN"] = gh_pat

    if not desired:
        return

    try:
        current_items = client.get_env_vars(svc_id, limit=100)
        merged: dict[str, str] = {}
        for item in current_items:
            ev = item.get("envVar", item) if isinstance(item, dict) else {}
            k = ev.get("key")
            v = ev.get("value")
            if k and v is not None:
                merged[str(k)] = str(v)

        added_or_updated: list[str] = []
        for k, v in desired.items():
            if merged.get(k) != v:
                merged[k] = v
                added_or_updated.append(k)

        if added_or_updated:
            payload = [{"key": k, "value": v} for k, v in merged.items()]
            client.update_env_vars(svc_id, payload)
            print(
                f"Synced {len(added_or_updated)} bootstrap env var key(s) on {svc_id}: "
                f"{', '.join(sorted(added_or_updated))}"
            )
        else:
            print(f"Bootstrap env vars on {svc_id} already up-to-date ({len(desired)} checked).")
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::Bootstrap env var sync skipped on {svc_id}: {exc}")


def main() -> int:
    svc_id = (os.environ.get("RENDER_SERVICE_ID", "") or os.environ.get("RENDER_SVC_ID", "")).strip()
    key_env = os.environ.get("RENDER_API_KEY_ENV", "").strip() or "RENDER_API_KEY"
    candidate_keys = _collect_candidate_keys(key_env)

    if not svc_id:
        print("Skipping Render deploy - service ID not set")
        return 0

    if not candidate_keys:
        print("Skipping Render deploy - RENDER_API_KEY not set")
        return 0

    active_env, client = _resolve_owning_client(svc_id, candidate_keys)
    _sync_bootstrap_env_vars(client, svc_id)
    key_idx = next(
        (idx for idx, (env_name, _) in enumerate(candidate_keys) if env_name == active_env),
        0,
    )
    commit_id = (
        os.environ.get("PR_HEAD_SHA", "").strip()
        or os.environ.get("EXPECTED_SHA", "").strip()
        or os.environ.get("GITHUB_SHA", "").strip()
    ) or None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            body = client.trigger_deploy(svc_id, commit_id=commit_id)
            print(f"Deploy triggered via {active_env}:", body)
            if not RENDER_WAIT:
                return 0
            return wait_for_terminal_state(client, svc_id, body)
        except RenderApiError as exc:
            err_body = (exc.body or "").lower()
            if exc.status == 404 and "does not have a commit" in err_body and commit_id is not None:
                print(
                    f"::warning::Service {svc_id} does not index commit {commit_id}; "
                    f"retrying deploy trigger at branch HEAD (commit_id=None)."
                )
                commit_id = None
                try:
                    body = client.trigger_deploy(svc_id, commit_id=None)
                    print(f"Deploy triggered (branch HEAD) via {active_env}:", body)
                    if not RENDER_WAIT:
                        return 0
                    return wait_for_terminal_state(client, svc_id, body)
                except RenderApiError as inner_exc:
                    exc = inner_exc
                    err_body = (exc.body or "").lower()

            if exc.status == 404 and "not found: service" in err_body:
                matched_client = None
                while key_idx + 1 < len(candidate_keys):
                    key_idx += 1
                    next_env, next_key = candidate_keys[key_idx]
                    probe_client = RenderClient(api_key=next_key, service_id=svc_id)
                    try:
                        body = probe_client.trigger_deploy(svc_id, commit_id=commit_id)
                        active_env = next_env
                        client = probe_client
                        matched_client = probe_client
                        print(f"Deploy triggered after key discovery via {active_env}:", body)
                        break
                    except RenderApiError as probe_exc:
                        probe_body = (probe_exc.body or "").lower()
                        if probe_exc.status == 404 and "does not have a commit" in probe_body:
                            body = probe_client.trigger_deploy(svc_id, commit_id=None)
                            active_env = next_env
                            client = probe_client
                            matched_client = probe_client
                            commit_id = None
                            print(f"Deploy triggered (branch HEAD) after key discovery via {active_env}:", body)
                            break
                        continue
                if matched_client is not None:
                    if not RENDER_WAIT:
                        return 0
                    return wait_for_terminal_state(matched_client, svc_id, body)

            print(f"Attempt {attempt}/{MAX_ATTEMPTS} failed with HTTP {exc.status}: {exc.body or exc}")
            if attempt == MAX_ATTEMPTS:
                return 1
            time.sleep(RETRY_DELAY_SECONDS)
        except Exception as exc:  # noqa: BLE001 - intentional retry-all policy
            print(f"Attempt {attempt}/{MAX_ATTEMPTS} unexpected transport error: {exc}")
            if attempt == MAX_ATTEMPTS:
                return 1
            time.sleep(RETRY_DELAY_SECONDS)

    return 1


def wait_for_terminal_state(client: "RenderClient", svc_id: str, trigger_body: dict) -> int:
    """Poll the triggered deploy to a terminal state (issue #1855).

    live -> 0. build_failed/update_failed/deactivated/canceled -> 1 (the enclosing
    job fails -> the event-driven deploy-doctor arm + notify-failure fire IN-RUN).
    Timeout: exit 1 unless the deploy already reached pre_live (deploy essentially
    complete; loud warning instead of a false failure).
    """
    deploy_id = (trigger_body or {}).get("id")
    if not deploy_id:
        print("Deploy trigger response carried no id — cannot poll; treating as triggered (legacy behavior)")
        return 0

    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    last = None
    while time.monotonic() < deadline:
        try:
            deploy = client.get_deploy(deploy_id, svc_id)
        except Exception as exc:  # noqa: BLE001 - transient poll errors are retried
            print(f"poll error (will retry): {exc}")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        last = deploy.get("status") or deploy.get("deploy", {}).get("status") if isinstance(deploy, dict) else None
        if last in OK_STATES:
            print(f"Deploy {deploy_id} reached terminal state: live ✓")
            return 0
        if last in FAIL_STATES:
            print(f"Deploy {deploy_id} reached terminal FAILURE state: {last}")
            return 1
        print(f"Deploy {deploy_id} status: {last} (polling every {POLL_INTERVAL_SECONDS}s)...")
        time.sleep(POLL_INTERVAL_SECONDS)

    if last == "pre_live":
        print(f"::warning::Deploy {deploy_id} still pre_live after {POLL_TIMEOUT_SECONDS}s — build finished, traffic promotion pending; treating as success.")
        return 0
    print(f"::error::Deploy {deploy_id} did not reach a terminal state within {POLL_TIMEOUT_SECONDS}s (last: {last}).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
