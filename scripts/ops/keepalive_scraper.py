"""Keep-alive heartbeat for the Render scraper node.

Pings https://supremeai-scraper-node.onrender.com/health every 10 minutes
to prevent the free-tier container from idling/sleeping.
"""

from __future__ import annotations

import os
import time
import urllib.request


def main() -> None:
    url = os.getenv("SCRAPER_HEALTH_URL", "https://supremeai-scraper-node.onrender.com/health")
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
