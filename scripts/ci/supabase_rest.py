#!/usr/bin/env python3
"""Shared Supabase PostgREST upsert for knowledge ingestion and Rule 13 verifier.

Single implementation of the hygiene-guarded insert-or-merge REST call so the
ingestion pipeline and the decision-record verifier cannot drift apart.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from scripts.ci.ai_knowledge_exchange import is_clean_knowledge_payload


def rest_upsert(
    url: str,
    key: str,
    table: str,
    row: dict,
    on_conflict: str,
    action: str = "upsert",
    timeout: int = 12,
) -> bool:
    """Insert-or-merge one row after the hygiene guard; True on 2xx."""
    # বাংলা মন্তব্য: সিক্রেট, `.onion` বা প্রম্পট-ইনজেকশন পেলোড থাকলে ডাটাবেসে ইনসার্ট ব্লক করা হয়।
    if not is_clean_knowledge_payload(json.dumps(row, ensure_ascii=False)):
        print(f"::warning::Blocked unsafe payload for Supabase table {table}", file=sys.stderr)
        return False
    endpoint = f"{url.rstrip('/')}/rest/v1/{urllib.parse.quote(table)}?on_conflict={on_conflict}"
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(row).encode("utf-8"),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 201)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        print(f"::warning::Supabase {action} into {table} failed ({err.code}): {body[:300]}", file=sys.stderr)
        return False
    except Exception as err:
        print(f"::warning::Supabase connection error: {err}", file=sys.stderr)
        return False

def rest_json(
    url: str,
    key: str,
    method: str,
    path: str,
    payload: dict | None = None,
    timeout: int = 10,
) -> list | dict:
    """Generic PostgREST JSON call (GET/POST/PATCH) returning parsed JSON.

    Raises urllib.error.HTTPError / OSError on failure - callers map errors
    to their own context (HTTPException for routes, warnings for CI jobs).
    """
    req = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body) if body.strip() else []
