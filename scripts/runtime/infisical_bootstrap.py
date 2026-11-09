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


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    token: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


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
            auth_res = request_json(
                f"{DEFAULT_API}/api/v1/auth/universal-auth/login",
                method="POST",
                payload={"clientId": client_id, "clientSecret": client_secret},
            )
            token = auth_res.get("accessToken")
        except Exception as exc:
            print(f"Infisical auth failed: {exc}", file=sys.stderr)
            return {}

    if not token:
        return {}

    workspace_id = project
    try:
        ws_res = request_json(f"{DEFAULT_API}/api/v1/workspace", token=token)
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
        response = request_json(f"{DEFAULT_API}/api/v3/secrets/raw?{query}", token=token)
        secrets: dict[str, str] = {}
        for item in response.get("secrets", []):
            k = item.get("secretKey")
            v = item.get("secretValue")
            if k and v:
                secrets[k] = v
        return secrets
    except Exception as exc:
        print(f"Infisical secret fetch error: {exc}", file=sys.stderr)
        return {}


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: infisical_bootstrap.py <command> [args...]", file=sys.stderr)
        return 2

    try:
        secrets = load_secrets()
        if secrets:
            os.environ.update(secrets)
            print(f"Infisical bootstrap: loaded {len(secrets)} secrets successfully", file=sys.stderr)
    except Exception as exc:
        print(f"Infisical bootstrap bypassed (using container env): {exc}", file=sys.stderr)

    os.execvp(sys.argv[1], sys.argv[1:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
