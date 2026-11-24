# backend/tools/browser/web_scraper.py
# NOTE: path header kept from the original module; the import contract is unchanged.
"""HTTP web scraper with redirect-walking SSRF defense (redirect + DNS-rebinding).

``WebScraper`` is the import surface consumed by
``core.agents.live.browser_agent`` and ``core.tools.browser.ai_web_extractor``.
Historically this module used ``httpx.get(..., follow_redirects=True)`` and a
parse-time-only ``is_safe_url`` check — a redirect (or a DNS record that flips
between validation and the TCP connect) could land the fetch on an internal
address. The canonical implementation lives in ``browser/web_scraper.py``;
this copy mirrors its discipline so the core import surface is at least as
safe as the standalone scraper microservice.

Guarantees:
- the initial URL is validated with ``core.security.is_safe_url`` (which
  resolves DNS via the shared SSRF protection), and
- redirects are followed MANUALLY (max 5 hops), re-validating the target on
  every hop — no silent multi-hop traversal into private space.

Residual risk (mirrors ``browser/security.py``): between the per-hop check and
httpx's own DNS re-resolution there is a TOCTOU window; closing it fully needs
a transport-layer IP pin (httpcore backend) — tracked as a follow-up.
"""

from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from core.monitoring.logging_config import logger
from core.security import is_safe_url

_MAX_REDIRECTS = 5
_TIMEOUT = 15.0
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


class WebScraper:
    def fetch_page(self, url: str) -> dict[str, Any]:
        logger.info(f"Fetching page: {url}")
        return self._fetch_with_redirects(url, hops_left=_MAX_REDIRECTS)

    def _fetch_with_redirects(self, url: str, hops_left: int) -> dict[str, Any]:
        if not is_safe_url(url):
            logger.error(f"SSRF Attempt Blocked: {url}")
            return {
                "success": False,
                "error": "SSRF check failed: Unauthorized internal access or DNS resolution rejected",
                "url": url,
            }
        headers = {"User-Agent": _USER_AGENT}
        try:
            with httpx.Client(headers=headers, timeout=_TIMEOUT, follow_redirects=False) as client:
                current = url
                response = None
                while True:
                    response = client.get(current)
                    if response.is_redirect:
                        location = response.headers.get("location", "").strip()
                        if not location:
                            return {
                                "success": False,
                                "error": "Redirect response without a Location header",
                                "url": current,
                            }
                        next_url = urljoin(current, location)
                        # Never let a redirect walk us into unvalidated space.
                        if not is_safe_url(next_url):
                            logger.error(f"SSRF Attempt Blocked (redirect hop): {next_url}")
                            return {
                                "success": False,
                                "error": "SSRF check failed on redirect target",
                                "url": next_url,
                            }
                        if hops_left <= 1:
                            return {
                                "success": False,
                                "error": f"Too many redirects (>{_MAX_REDIRECTS})",
                                "url": next_url,
                            }
                        current = next_url
                        hops_left -= 1
                        continue
                    break
                response.raise_for_status()
                final_url = str(response.url)
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string.strip() if soup.title else "No Title"
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = " ".join(soup.get_text(separator=" ").split())[:3000]
                links = [a.get("href", "") for a in soup.find_all("a", href=True)][:20]
                return {
                    "success": True,
                    "url": final_url,
                    "title": title,
                    "content": text,
                    "links": links,
                    "status_code": response.status_code,
                }
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return {"success": False, "error": str(e), "url": url}
