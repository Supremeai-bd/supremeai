"""SupremeAI Standalone Scraper & Gemini Cookie Relay Entrypoint.

Provides the FastAPI application entrypoint for Render (uvicorn main:app)
and local deployments. Seamlessly integrates the lightweight Gemini Cookie
Relay engine (server.py) with optional scraping routes.
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("supremeai.scraper")

# Ensure local directory is in path
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

# Import primary application from server.py (Cookie Relay Engine) or create standalone app
try:
    from server import ChatRequest, app, duck_engine, relay_engine
except ImportError:
    try:
        from browser.server import (  # type: ignore
            ChatRequest,
            app,
            duck_engine,
            relay_engine,
        )
    except ImportError:
        from fastapi import FastAPI
        app = FastAPI(title="SupremeAI Browser & Scraper Service", version="2.0.0")
        relay_engine = None
        duck_engine = None
        ChatRequest = None

# ---------------------------------------------------------------------------
# Optional scraper routes.
#
# 2026-11-17: dependency setup AND route registration used to share one
# `try/except Exception`. A single bug anywhere in the ~105 lines of route code
# therefore disabled /scrape, /browse and /recipe and reported it as
# "dependencies unavailable" at INFO level — the failure was invisible. Setup is
# now isolated: once the engine is constructed, the routes register
# unconditionally, so a registration error can never masquerade as a missing
# optional dependency.
# ---------------------------------------------------------------------------
_scraper = None
_agent = None
_scraper_unavailable_reason: str | None = None

try:
    try:
        from browser_agent import BrowserAgent, BrowseRequest
        from security import is_safe_url
        from web_scraper import WebScraper
    except ImportError:
        from services.scraper.browser_agent import BrowserAgent, BrowseRequest
        from services.scraper.security import is_safe_url
        from services.scraper.web_scraper import WebScraper

    _scraper = WebScraper()
    _agent = BrowserAgent(headless=True)
except Exception as _scraper_err:  # noqa: BLE001 — optional engine, must not block boot
    _scraper_unavailable_reason = f"{type(_scraper_err).__name__}: {_scraper_err}"
    logger.exception(
        "Scraper engine could not be constructed (%s). /scrape, /browse and /recipe "
        "will NOT be registered; the service continues in Gemini Cookie Relay mode.",
        _scraper_unavailable_reason,
    )

if _scraper is not None and _agent is not None:
    from fastapi import HTTPException, Request
    from pydantic import BaseModel

    def _verify_scraper_secret(request: Request) -> None:
        """Audit P1-13 fix: scraper routes are unauthenticated by design today.

        Every scraper route now requires the shared webhook secret (same
        credential as the stealth relay) — failing closed on any production
        host and allowing a local dev/test bypass only. This prevents an
        anonymous caller from driving the headless browser once the
        Dockerfile copy step ships these modules publicly.
        """
        try:  # reuse the relay engine's shared check when available
            from server import _verify_stealth_secret  # type: ignore

            _verify_stealth_secret(request)
            return
        except ImportError:
            pass
        expected = os.getenv("STEALTH_WEBHOOK_SECRET", "").strip()
        is_prod = bool(
            os.getenv("RENDER_SERVICE_NAME")
            or os.getenv("RENDER")
            or os.getenv("RENDER_ENV", "").strip().lower() in ("production", "prod")
            or os.getenv("ENV", "").strip().lower() in ("production", "prod")
        )
        if not expected:
            if is_prod:
                raise HTTPException(status_code=500, detail="STEALTH_WEBHOOK_SECRET is required in production")
            return
        import hmac as _hmac

        incoming = (
            request.headers.get("X-Stealth-Secret")
            or request.headers.get("X-Webhook-Secret")
            or request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        )
        if not _hmac.compare_digest(incoming, expected):
            raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing stealth secret")

    MAX_CONCURRENCY = int(os.getenv("SCRAPER_MAX_CONCURRENCY", "3"))
    TIMEOUT_SECONDS = int(os.getenv("SCRAPER_TIMEOUT_SECONDS", "45"))

    class ScrapeRequest(BaseModel):
        url: str
        extraction_prompt: str | None = None

    class RecipeRequest(BaseModel):
        steps: list = []
        initial_url: str | None = None

    @app.post("/scrape", tags=["scraper"])
    async def scrape(request: ScrapeRequest, raw_request: Request):
        _verify_scraper_secret(raw_request)
        if not request.url:
            raise HTTPException(status_code=400, detail="URL is required")
        if not is_safe_url(request.url):
            raise HTTPException(
                status_code=400, detail="SSRF check failed: Unauthorized internal access"
            )
        import asyncio
        return await asyncio.to_thread(_scraper.fetch_page, request.url)

    @app.post("/browse", tags=["scraper"])
    async def browse(request: BrowseRequest, raw_request: Request):
        _verify_scraper_secret(raw_request)
        if not request.url:
            raise HTTPException(status_code=400, detail="URL is required")
        if not is_safe_url(request.url):
            raise HTTPException(
                status_code=400, detail="SSRF check failed: Unauthorized internal access"
            )
        return await _agent.navigate_and_interact(
            url=request.url,
            action=request.action or "fetch",
            selector=request.selector,
            text=request.text,
            wait_for=request.wait_for,
        )

    @app.post("/recipe", tags=["scraper"])
    async def recipe(request: RecipeRequest, raw_request: Request):
        _verify_scraper_secret(raw_request)
        if request.initial_url and not is_safe_url(request.initial_url):
            raise HTTPException(
                status_code=400, detail="SSRF check failed: Unauthorized internal access"
            )
        return await _agent.execute_recipe(steps=request.steps, initial_url=request.initial_url)

    logger.info("Scraper browser routes registered successfully")

