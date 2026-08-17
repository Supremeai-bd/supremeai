"""Production-grade Render service/deploy status checker.
Replaces: check_render.py, check_logs.py (root-level scratch scripts).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter, Retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("render_status")

RENDER_API_BASE = os.getenv("RENDER_API_BASE", "https://api.render.com/v1")
REQUEST_TIMEOUT = float(os.getenv("RENDER_API_TIMEOUT_SECONDS", "10"))


@dataclass(frozen=True)
class RenderAccount:
    label: str
    api_key: str | None


def _build_session() -> requests.Session:
    """Session with bounded retries/backoff — no infinite hangs, no silent failures."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def fetch_services(session: requests.Session, account: RenderAccount) -> list[dict]:
    if not account.api_key:
        logger.warning("No API key set for %s — skipping.", account.label)
        return []
    headers = {"Authorization": f"Bearer {account.api_key}", "Accept": "application/json"}
    try:
        resp = session.get(f"{RENDER_API_BASE}/services?limit=10", headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return [item.get("service", {}) for item in resp.json()]
    except requests.exceptions.Timeout:
        logger.error("[%s] Request timed out after %ss", account.label, REQUEST_TIMEOUT)
    except requests.exceptions.HTTPError as e:
        logger.error("[%s] HTTP %s: %s", account.label, e.response.status_code, e.response.text[:200])
    except requests.exceptions.RequestException as e:
        logger.error("[%s] Network error: %s", account.label, e)
    return []


def fetch_latest_deploy(session: requests.Session, account: RenderAccount, service_id: str) -> dict | None:
    headers = {"Authorization": f"Bearer {account.api_key}", "Accept": "application/json"}
    try:
        resp = session.get(
            f"{RENDER_API_BASE}/services/{service_id}/deploys?limit=1",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        deploys = resp.json()
        return deploys[0].get("deploy", {}) if deploys else None
    except requests.exceptions.RequestException as e:
        logger.error("[%s] Could not fetch deploys for %s: %s", account.label, service_id, e)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Render service/deploy status.")
    parser.add_argument(
        "--service-id",
        default=os.getenv("RENDER_SERVICE_ID"),
        help="Optional: check a single service's deploy history (env: RENDER_SERVICE_ID)",
    )
    args = parser.parse_args()

    accounts = [
        RenderAccount("Primary", os.getenv("RENDER_API_KEY")),
        RenderAccount("Backup", os.getenv("RENDER_API_KEY_BACKUP")),
    ]
    if not any(a.api_key for a in accounts):
        logger.error("No RENDER_API_KEY / RENDER_API_KEY_BACKUP set in environment. Aborting.")
        return 1

    session = _build_session()
    had_failure = False

    for account in accounts:
        logger.info("--- %s ---", account.label)
        services = fetch_services(session, account)
        if not services and account.api_key:
            had_failure = True
        for service in services:
            name, s_type, s_id = service.get("name", "?"), service.get("type", "?"), service.get("id")
            state = "Suspended" if service.get("suspended") == "suspended" else "Active"
            url = service.get("serviceDetails", {}).get("url", "N/A")
            logger.info("%s | %s | %s | %s", name, s_type, state, url)
            if s_id:
                deploy = fetch_latest_deploy(session, account, s_id)
                if deploy:
                    logger.info("  Last deploy: %s", deploy.get("status", "Unknown"))

        if args.service_id:
            deploy = fetch_latest_deploy(session, account, args.service_id)
            if deploy is None:
                had_failure = True

    return 1 if had_failure else 0


if __name__ == "__main__":
    sys.exit(main())
