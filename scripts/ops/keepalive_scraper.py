"""Keep-alive heartbeat for the scraper node.

Pings the scraper's health path every 10 minutes to prevent the free-tier
container from idling/sleeping. The host is resolved from
config/service_registry.yaml (env SCRAPER_HEALTH_URL wins), so this docstring
deliberately names no deployment URL.
"""

from __future__ import annotations

import os
import time
import urllib.request


def main() -> None:
    try:
        from repo_paths import service_endpoint as _service_endpoint
        _default = _service_endpoint("scraper") or ""
    except Exception:  # pragma: no cover
        _default = ""
    url = os.getenv("SCRAPER_HEALTH_URL", _default)
    interval = int(os.getenv("KEEPALIVE_INTERVAL_SECONDS", "600"))
    while True:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                print(f"[keepalive] {url} -> {resp.status}")
        except Exception as exc:  # noqa: BLE001
            print(f"[keepalive] {url} failed: {exc}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
