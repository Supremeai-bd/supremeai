#!/usr/bin/env python3
"""Single Source of Truth (SSOT) Infisical runtime bootstrap for SupremeAI.

Loads production secrets from Infisical REST API via stdlib urllib (zero external
dependencies), injects them into os.environ, then executes the target command.
Designed to run in any container (core, gateway, mcp-tower) without module imports.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API = "https://app.infisical.com"
DEFAULT_TIMEOUT = 15


def _send_http_request(
    target_url: str,
    http_method: str = "GET",
    json_body: dict | None = None,
    auth_bearer: str | None = None,
) -> dict:
    encoded = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    hdrs = {"Content-Type": "application/json"}
    if auth_bearer:
        hdrs["Authorization"] = f"Bearer {auth_bearer}"
    req = urllib.request.Request(target_url, data=encoded, headers=hdrs, method=http_method)
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_secrets() -> dict[str, str]:
    project = os.environ.get("INFISICAL_PROJECT_ID")
    environment = os.environ.get("INFISICAL_ENV", "prod")
    path = os.environ.get("INFISICAL_SECRET_PATH", "/")
    if not project or environment != "prod":
        return {}

    token = os.environ.get("INFISICAL_TOKEN")
    if not token:
        client_id = os.environ.get("INFISICAL_CLIENT_ID")
        client_secret = os.environ.get("INFISICAL_CLIENT_SECRET")
        if not client_id or not client_secret:
            return {}
        try:
            auth_res = _send_http_request(
                f"{DEFAULT_API}/api/v1/auth/universal-auth/login",
                http_method="POST",
                json_body={"clientId": client_id, "clientSecret": client_secret},
            )
            token = auth_res.get("accessToken")
        except Exception as exc:
            print(f"Infisical auth failed: {exc}", file=sys.stderr)
            # Fail-closed hardening (audit 2026-11-11): a configured-but-broken
            # vault must surface as a boot failure, not as a silent empty env.
            raise

    if not token:
        return {}

    workspace_id = project
    try:
        ws_res = _send_http_request(f"{DEFAULT_API}/api/v1/workspace", auth_bearer=token)
        for ws in ws_res.get("workspaces", []):
            if ws.get("id") == workspace_id or ws.get("slug") == workspace_id:
                workspace_id = ws.get("id")
                break
    except Exception:
        pass

    query = urllib.parse.urlencode(
        {"workspaceId": workspace_id, "environment": environment, "secretPath": path}
    )
    try:
        response = _send_http_request(f"{DEFAULT_API}/api/v3/secrets/raw?{query}", auth_bearer=token)
        secrets: dict[str, str] = {}
        for item in response.get("secrets", []):
            k = item.get("secretKey")
            v = item.get("secretValue")
            if k and v:
                secrets[k] = v
        return secrets
    except Exception as exc:
        print(f"Infisical secret fetch error: {exc}", file=sys.stderr)
        # Fail-closed hardening (audit 2026-11-11): propagate to main().
        raise


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: infisical_bootstrap.py <command> [args...]", file=sys.stderr)
        return 2

    project_configured = bool(os.environ.get("INFISICAL_PROJECT_ID"))
    try:
        secrets = load_secrets()
    except Exception as exc:
        if project_configured and os.environ.get("INFISICAL_ALLOW_EMPTY") != "1":
            print(
                f"Infisical bootstrap FAILED while INFISICAL_PROJECT_ID is configured: {exc}; "
                "refusing to start a hollow service (set INFISICAL_ALLOW_EMPTY=1 to override)",
                file=sys.stderr,
            )
            return 1
        print(f"Infisical bootstrap bypassed (using container env): {exc}", file=sys.stderr)
        secrets = {}

    if secrets:
        os.environ.update(secrets)
        print(f"Infisical bootstrap: loaded {len(secrets)} secrets successfully", file=sys.stderr)
    elif project_configured and os.environ.get("INFISICAL_ALLOW_EMPTY") != "1":
        print(
            "Infisical bootstrap: project configured but no secrets returned; "
            "failing closed (set INFISICAL_ALLOW_EMPTY=1 to override)",
            file=sys.stderr,
        )
        return 1

    os.execvp(sys.argv[1], sys.argv[1:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
