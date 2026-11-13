"""Single Source of Truth (SSOT) Infisical Secret Loader for SupremeAI.

Bypasses vendor blind-index SDK bug (issue #434, #478) using direct REST API (/api/v3/secrets/raw)
with universal-auth token login, workspace slug/id resolution, and fail-closed handling.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_INFISICAL_API = "https://app.infisical.com"
DEFAULT_TIMEOUT = 10


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Perform hermetic HTTP JSON request without third-party dependencies."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def resolve_infisical_token(
    api_base: str = DEFAULT_INFISICAL_API,
    token: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str | None:
    """Resolve an Infisical auth token directly or via Universal Auth login."""
    if token:
        return token
    cid = client_id or os.environ.get("INFISICAL_CLIENT_ID")
    csec = client_secret or os.environ.get("INFISICAL_CLIENT_SECRET")
    if not cid or not csec:
        return None

    try:
        res = request_json(
            f"{api_base}/api/v1/auth/universal-auth/login",
            method="POST",
            payload={"clientId": cid, "clientSecret": csec},
            timeout=timeout,
        )
        return res.get("accessToken")
    except Exception as exc:
        logger.warning(f"Infisical universal-auth login failed: {exc}")
        return None


def resolve_workspace_id(
    workspace_or_slug: str,
    token: str,
    api_base: str = DEFAULT_INFISICAL_API,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Resolve workspace slug or id to canonical workspaceId."""
    try:
        ws_res = request_json(f"{api_base}/api/v1/workspace", token=token, timeout=timeout)
        for ws in ws_res.get("workspaces", []):
            if ws.get("id") == workspace_or_slug or ws.get("slug") == workspace_or_slug:
                return ws.get("id")
    except Exception as exc:
        logger.debug(f"Unable to resolve Infisical workspace '{workspace_or_slug}': {exc}")
    return workspace_or_slug


def fetch_raw_infisical_secrets(
    *,
    project_id: str | None = None,
    environment: str | None = None,
    secret_path: str = "/",
    token: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    api_url: str | None = None,
    timeout: int | None = None,
) -> dict[str, str]:
    """Fetch all secrets via Infisical raw REST API (/api/v3/secrets/raw).

    Single source of truth for both boot-time container execution and runtime vault.
    """
    project = (
        project_id
        or os.environ.get("INFISICAL_PROJECT_ID")
        or (
            "92aa20c4-aef5-4e33-82bd-efb06058aaf0"
            if os.environ.get("INFISICAL_PROJECT_SLUG") == "supreme-ai-p-n-fr"
            else os.environ.get("INFISICAL_PROJECT_SLUG")
        )
        or "92aa20c4-aef5-4e33-82bd-efb06058aaf0"
    )
    if not project:
        return {}

    env = environment or os.environ.get("INFISICAL_ENV") or "prod"
    path = secret_path or os.environ.get("INFISICAL_SECRET_PATH") or "/"
    api_base = (api_url or os.environ.get("INFISICAL_API_URL") or DEFAULT_INFISICAL_API).rstrip("/")
    call_timeout = timeout or int(os.environ.get("INFISICAL_TIMEOUT") or DEFAULT_TIMEOUT)

    auth_token = resolve_infisical_token(
        api_base=api_base,
        token=token or os.environ.get("INFISICAL_TOKEN"),
        client_id=client_id,
        client_secret=client_secret,
        timeout=call_timeout,
    )
    if not auth_token:
        return {}

    workspace_id = resolve_workspace_id(project, auth_token, api_base=api_base, timeout=call_timeout)

    query = urllib.parse.urlencode({"workspaceId": workspace_id, "environment": env, "secretPath": path})
    try:
        response = request_json(
            f"{api_base}/api/v3/secrets/raw?{query}",
            token=auth_token,
            timeout=call_timeout,
        )
    except Exception as exc:
        logger.warning(f"Raw Infisical secrets fetch failed: {exc}")
        return {}

    secrets: dict[str, str] = {}
    for item in response.get("secrets", []):
        key = item.get("secretKey")
        value = item.get("secretValue")
        if key and value is not None:
            secrets[key] = str(value)
    return secrets


__all__ = [
    "DEFAULT_INFISICAL_API",
    "DEFAULT_TIMEOUT",
    "fetch_raw_infisical_secrets",
    "request_json",
    "resolve_infisical_token",
    "resolve_workspace_id",
]
