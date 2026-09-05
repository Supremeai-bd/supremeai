#!/usr/bin/env python3
"""Fetch Infisical secrets into GitHub Actions without logging values."""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

API = "https://app.infisical.com"

def call(url: str, *, method: str = "GET", payload: dict | None = None, token: str | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

def main() -> int:
    required = ["INFISICAL_CLIENT_ID", "INFISICAL_CLIENT_SECRET", "INFISICAL_PROJECT_ID"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        print(f"::error::Missing Infisical bootstrap variables: {', '.join(missing)}")
        return 2
    env = os.environ.get("INFISICAL_ENV", "prod")
    if env != "prod":
        print("::error::CI secret loader only permits INFISICAL_ENV=prod")
        return 2
    try:
        token = call(f"{API}/api/v1/auth/universal-auth/login", method="POST", payload={"clientId": os.environ["INFISICAL_CLIENT_ID"], "clientSecret": os.environ["INFISICAL_CLIENT_SECRET"]}).get("accessToken")
        if not token:
            raise RuntimeError("authentication returned no token")
        query = urllib.parse.urlencode({"workspaceId": os.environ["INFISICAL_PROJECT_ID"], "environment": env, "secretPath": os.environ.get("INFISICAL_SECRET_PATH", "/")})
        items = call(f"{API}/api/v3/secrets/raw?{query}", token=token).get("secrets", [])
        values = {item.get("secretKey"): item.get("secretValue") for item in items if item.get("secretKey") and item.get("secretValue")}
        if not values:
            raise RuntimeError("secret fetch returned no values")
        target = os.environ.get("GITHUB_ENV")
        if not target:
            print(f"Loaded {len(values)} Infisical keys (GITHUB_ENV unavailable; validation only)")
            return 0
        with open(target, "a", encoding="utf-8") as output:
            for key, value in values.items():
                if "\n" in value or "\r" in value:
                    raise RuntimeError(f"secret {key} contains an unsupported newline")
                output.write(f"{key}={value}\n")
        print(f"Loaded {len(values)} Infisical keys into GitHub Actions environment")
        return 0
    except Exception as exc:
        print(f"::error::Infisical secret loading failed: {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
