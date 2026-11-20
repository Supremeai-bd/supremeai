"""SupremeAI Browser - Lightweight Gemini Cookie Relay Engine (~20MB RAM, $0 Cost).

Connects directly to gemini.google.com session over HTTP using stored session cookies,
with fast-fail $0 pure-HTTP fallback cascades (Duck.ai + Zero-Auth Pollinations OpenAI).
Zero Headless Browser overhead, zero Playwright memory bloat on the chat path.
Runs seamlessly on Render 512MB Free Tier or local machine (port 8788). Refs #756.

`/v1/chat/completions` answers both ways: one JSON body, or — when the caller
sends `stream: true` — server-sent events. The SSE path exists because the
gateway reads every provider as SSE; before it, a streamed request to a web
engine burned the full engine latency and then failed with "stream ended before
completion" on an answer that had already been produced. The frames are honest
about what they are: Duck.ai is read incrementally, the cookie engine answers
whole, and the final chunk carries `delivery: incremental|buffered` so nobody has
to guess which one they got.
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import hmac
import json
import logging
import os
import pathlib
import random
import re
import sys
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx

try:
    from browser.surface_controls import (
        EngineConcurrencyLimiter,
        TenantSemanticCache,
        TenantSessionAffinity,
        score_response_quality,
    )
except ImportError:
    from surface_controls import (  # type: ignore[no-redef]
        EngineConcurrencyLimiter,
        TenantSemanticCache,
        TenantSessionAffinity,
        score_response_quality,
    )
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, field_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("supremeai-cookie-relay")

app = FastAPI(title="SupremeAI Gemini Web Cookie Relay", version="2.0.0")

_DEFAULT_BROWSER_ORIGINS = [
    "https://supremeai.live",
    "https://www.supremeai.live",
    "https://app.supremeai.live",
    "https://supremeai-studio.pages.dev",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
_env_browser_origins = [
    o.strip()
    for o in os.environ.get("BROWSER_CORS_ORIGINS", os.environ.get("CORS_ORIGINS", "")).split(",")
    if o.strip() and o.strip() != "*"
]
_ALLOWED_BROWSER_ORIGINS = list(dict.fromkeys(_env_browser_origins + _DEFAULT_BROWSER_ORIGINS))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_BROWSER_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Stealth-Secret", "Accept", "Origin", "Referer"],
)


class ChatMessage(BaseModel):
    role: str
    content: Any = ""

    @field_validator("content", mode="before")
    @classmethod
    def _coerce_content(cls, v: Any) -> str:
        if isinstance(v, list):
            return "\n".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in v
                if (isinstance(part, dict) and part.get("text")) or not isinstance(part, dict)
            )
        return str(v or "")


class ChatRequest(BaseModel):
    model: Optional[str] = "gemini-web-relay"
    messages: List[ChatMessage] = []
    stream: Optional[bool] = False


class GeminiCookieEngine:
    def __init__(self) -> None:
        self._snl: Optional[str] = None
        self._bl: str = "boq_gemini-web-uiserver_20261022.00_p0"
        self._token_expiry: float = 0
        self._cookies: Dict[str, str] = {}
        self._infisical_cookies: Dict[str, str] = {}
        self._infisical_expiry: float = 0
        self._infisical_ttl: float = 3600.0
        self._proxy_list: List[str] = []
        self._proxy_idx: int = 0
        self._proxy_expiry: float = 0

    async def get_proxy(self) -> Optional[str]:
        direct_proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("ROTATING_PROXY_URL")
        if direct_proxy:
            return direct_proxy

        webshare_key = os.getenv("WEBSHARE_API_KEY")
        if not webshare_key:
            return None

        now = time.time()
        if not self._proxy_list or now > self._proxy_expiry:
            try:
                async with httpx.AsyncClient(timeout=10.0) as pc:
                    res = await pc.get(
                        "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=25",
                        headers={"Authorization": f"Token {webshare_key}"},
                    )
                    if res.status_code == 200:
                        data = res.json()
                        results = data.get("results", [])
                        proxies = []
                        for p in results:
                            u, pw, ip, port = p.get("username"), p.get("password"), p.get("proxy_address"), p.get("port")
                            if u and pw and ip and port:
                                proxies.append(f"http://{u}:{pw}@{ip}:{port}")
                        if proxies:
                            self._proxy_list = proxies
                            self._proxy_expiry = now + 3600.0
                            logger.info(f"Loaded {len(proxies)} Webshare rotating proxies")
            except Exception as e:
                logger.warning(f"Failed to fetch Webshare proxy list: {e}")

        if not self._proxy_list:
            return None

        proxy = self._proxy_list[self._proxy_idx % len(self._proxy_list)]
        self._proxy_idx += 1
        return proxy

    def get_cookies(self) -> Dict[str, str]:
        # Prefer Infisical cached cookies if fresh (TTL 1h)
        if self._infisical_cookies and time.time() < self._infisical_expiry:
            self._cookies = self._infisical_cookies
            return self._cookies

        if self._cookies:
            return self._cookies

        # 1. Environment variables
        c: Dict[str, str] = {}
        for key in ("1PSID", "3PSID", "SID", "1PSIDTS", "3PSIDTS", "1PSIDCC", "3PSIDCC"):
            val = os.environ.get(f"SUPREMEAI_GEMINI_{key}", "")
            if val:
                c[f"__Secure-{key}" if "PSID" in key else key] = val
        if c:
            self._cookies = c
            return self._cookies

        # 2. Local encrypted vault fallback (~/.supremeai_vault)
        try:
            vault_path = pathlib.Path.home() / ".supremeai_vault" / "ai_fleet_cookies.enc.json"
            if vault_path.exists():
                ghost_tower_dir = str(pathlib.Path(__file__).resolve().parent / "ghost_tower")
                if ghost_tower_dir not in sys.path:
                    sys.path.insert(0, ghost_tower_dir)
                from credential_vault import CredentialVault

                vault = CredentialVault()
                cookie_list = json.loads(vault.decrypt(vault_path.read_text("utf-8")))
                for cookie in cookie_list:
                    if "google" in cookie.get("domain", ""):
                        name = cookie.get("name")
                        if name in (
                            "__Secure-1PSID",
                            "__Secure-3PSID",
                            "SID",
                            "__Secure-1PSIDTS",
                            "__Secure-3PSIDTS",
                            "__Secure-1PSIDCC",
                            "__Secure-3PSIDCC",
                        ):
                            c[name] = cookie.get("value")
                self._cookies = c
        except Exception as exc:
            logger.warning(f"Could not read cookies from local vault: {exc}")

        return self._cookies

    async def fetch_cookies_from_infisical(self) -> Dict[str, str]:
        """Dynamically fetch Gemini cookies from Infisical Vault (in-memory, TTL 1h)."""
        now = time.time()
        if self._infisical_cookies and now < self._infisical_expiry:
            self._cookies = self._infisical_cookies
            return self._infisical_cookies

        client_id = os.getenv("INFISICAL_CLIENT_ID")
        client_secret = os.getenv("INFISICAL_CLIENT_SECRET")
        workspace_id = os.getenv("INFISICAL_WORKSPACE_ID") or os.getenv("INFISICAL_PROJECT_ID")
        if not client_id or not client_secret or not workspace_id:
            return self.get_cookies()

        environment = os.getenv("INFISICAL_ENV", "prod").strip() or "prod"
        base_url = os.getenv("INFISICAL_API_URL", "https://app.infisical.com").rstrip("/")
        secret_name = os.getenv("INFISICAL_GEMINI_COOKIES_SECRET", "SUPREMEAI_GEMINI_COOKIES").strip() or "SUPREMEAI_GEMINI_COOKIES"

        old_cookies = dict(self._infisical_cookies)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                login_resp = await client.post(
                    f"{base_url}/api/v1/auth/universal-auth/login",
                    json={"clientId": client_id, "clientSecret": client_secret},
                )
                login_resp.raise_for_status()
                token = login_resp.json().get("accessToken")
                if not token:
                    raise ValueError("Infisical auth did not return accessToken")

                url = f"{base_url}/api/v3/secrets/raw/{secret_name}"
                params = {"workspaceId": workspace_id, "environment": environment, "secretPath": "/"}
                resp = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
                resp.raise_for_status()
                data = resp.json()

                raw_value = None
                if isinstance(data, dict):
                    if isinstance(data.get("secret"), dict):
                        raw_value = data["secret"].get("secretValue")
                    elif isinstance(data.get("secrets"), list) and data["secrets"]:
                        raw_value = data["secrets"][0].get("secretValue")
                    else:
                        raw_value = data.get("secretValue")
                if not raw_value:
                    raise ValueError("Infisical secret value is empty")

                cookies = self._parse_infisical_cookie_value(str(raw_value))
                if not cookies:
                    raise ValueError("No Gemini cookies parsed from Infisical secret")

                # Reset token cache if cookies changed
                if cookies != old_cookies:
                    self._snl = None
                    self._token_expiry = 0

                self._infisical_cookies = cookies
                self._infisical_expiry = time.time() + self._infisical_ttl
                self._cookies = cookies
                logger.info(f"Fetched {len(cookies)} Gemini cookies from Infisical (TTL {int(self._infisical_ttl)}s)")
                return cookies
        except Exception as exc:
            logger.warning(f"Could not fetch cookies from Infisical: {exc}")
            return self.get_cookies()

    def _parse_infisical_cookie_value(self, raw: str) -> Dict[str, str]:
        text = raw.strip()
        # Try gzip/base64 compressed payload
        try:
            decoded = base64.b64decode(text, validate=True)
            try:
                text = gzip.decompress(decoded).decode("utf-8")
            except Exception:
                try:
                    text = decoded.decode("utf-8")
                except Exception:
                    pass
        except Exception:
            pass

        # Try JSON
        try:
            data = json.loads(text)
        except Exception:
            cookies: Dict[str, str] = {}
            for part in text.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    cookies[k.strip()] = v.strip()
            known = {"__Secure-1PSID", "__Secure-3PSID", "SID", "__Secure-1PSIDTS", "__Secure-3PSIDTS", "__Secure-1PSIDCC", "__Secure-3PSIDCC"}
            filtered = {k: v for k, v in cookies.items() if k in known}
            return filtered if filtered else cookies

        cookies = {}
        if isinstance(data, dict):
            if isinstance(data.get("cookies"), list):
                data = data["cookies"]
            else:
                mapping: Dict[str, str] = {}
                for k, v in data.items():
                    if isinstance(v, str):
                        mapping[k] = v
                if mapping:
                    normalized: Dict[str, str] = {}
                    for k, v in mapping.items():
                        name = k
                        if k in ("1PSID", "3PSID", "SID", "1PSIDTS", "3PSIDTS", "1PSIDCC", "3PSIDCC"):
                            name = f"__Secure-{k}" if "PSID" in k else k
                        normalized[name] = v
                    return normalized
        if isinstance(data, list):
            for cookie in data:
                if not isinstance(cookie, dict):
                    continue
                name = cookie.get("name")
                value = cookie.get("value")
                domain = str(cookie.get("domain", ""))
                if name and value and ("google" in domain.lower() or str(name).startswith("__Secure-") or name == "SID"):
                    cookies[str(name)] = str(value)

        known = {"__Secure-1PSID", "__Secure-3PSID", "SID", "__Secure-1PSIDTS", "__Secure-3PSIDTS", "__Secure-1PSIDCC", "__Secure-3PSIDCC"}
        filtered = {k: v for k, v in cookies.items() if k in known}
        return filtered if filtered else cookies

    async def _ensure_tokens(self, client: httpx.AsyncClient) -> tuple[str, str]:
        now = time.time()
        if self._snl and now < self._token_expiry:
            return self._snl, self._bl

        if os.getenv("INFISICAL_CLIENT_ID") and os.getenv("INFISICAL_CLIENT_SECRET"):
            cookies = await self.fetch_cookies_from_infisical()
        else:
            cookies = self.get_cookies()
        if not cookies:
            raise ValueError("No Gemini cookies configured (missing env vars and local vault)")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = await client.get(
            "https://gemini.google.com/app", headers=headers, cookies=cookies, follow_redirects=True
        )
        if "accounts.google.com" in str(resp.url):
            raise PermissionError("Gemini cookies expired or redirected to Google Login")

        snl_match = re.search(r'"SNlM0e":"([^"]+)"', resp.text)
        if not snl_match:
            raise RuntimeError("Could not find SNlM0e session token on gemini.google.com/app")

        self._snl = snl_match.group(1)
        bl_match = re.search(r'"cfb2h":"([^"]+)"', resp.text)
        if bl_match:
            self._bl = bl_match.group(1)
        self._token_expiry = now + 3600  # Cache token for 1 hour
        logger.info(f"Refreshed Gemini SNlM0e session token (bl={self._bl})")
        return self._snl, self._bl

    def _extract_reply_text(self, raw_text: str) -> str:
        best_text = ""
        lines = raw_text.splitlines()
        for line in lines:
            line_s = line.strip()
            if not line_s or line_s == ")]}'" or line_s.isdigit():
                continue
            try:
                data = json.loads(line_s)
                for item in data:
                    if isinstance(item, list) and len(item) > 2 and item[0] == "wrb.fr":
                        payload = json.loads(item[2])
                        if len(payload) > 4 and payload[4]:
                            cand0 = payload[4][0]
                            if len(cand0) > 1 and cand0[1]:
                                part0 = cand0[1][0]
                                if isinstance(part0, str) and len(part0) > len(best_text):
                                    best_text = part0
            except Exception:
                continue
        return best_text.strip()

    async def ask(self, prompt: str) -> str:
        if os.getenv("INFISICAL_CLIENT_ID") and os.getenv("INFISICAL_CLIENT_SECRET"):
            cookies = await self.fetch_cookies_from_infisical()
        else:
            cookies = self.get_cookies()
        if not cookies:
            raise HTTPException(status_code=503, detail="No Gemini cookies configured")

        proxy = await self.get_proxy()
        client_kwargs = {"timeout": 10.0}
        if proxy:
            client_kwargs["proxy"] = proxy

        async with httpx.AsyncClient(**client_kwargs) as client:
            try:
                snl, bl = await self._ensure_tokens(client)
            except PermissionError as exc:
                self._infisical_cookies = {}
                self._infisical_expiry = 0
                self._cookies = {}
                fallback_reply = await self._try_api_fallback(prompt)
                if fallback_reply:
                    return fallback_reply
                raise HTTPException(status_code=502, detail=str(exc))
            except Exception as exc:
                fallback_reply = await self._try_api_fallback(prompt)
                if fallback_reply:
                    return fallback_reply
                raise HTTPException(status_code=502, detail=f"Token initialization error: {exc}")

            reqid = int(time.time() * 1000) % 1000000
            post_url = (
                f"https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
                f"?bl={bl}&_reqid={reqid}&rt=c"
            )

            message_struct = [
                [prompt, 0, None, None, None, None, 0],
                ["en"],
                ["", "", ""],
                None,
                None,
                None,
                [1],
                0,
                [],
                [],
                1,
                0,
            ]
            req_payload = [None, json.dumps(message_struct)]
            post_headers = {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": "https://gemini.google.com",
                "Referer": "https://gemini.google.com/app",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            }
            post_data = {
                "f.req": json.dumps(req_payload),
                "at": snl,
            }

            try:
                resp = await client.post(post_url, headers=post_headers, cookies=cookies, data=post_data)
            except httpx.HTTPError as exc:
                fallback_reply = await self._try_api_fallback(prompt)
                if fallback_reply:
                    return fallback_reply
                raise HTTPException(status_code=502, detail=f"Gemini upstream error: {exc}")

            if resp.status_code != 200:
                fallback_reply = await self._try_api_fallback(prompt)
                if fallback_reply:
                    return fallback_reply
                raise HTTPException(status_code=502, detail=f"Gemini returned HTTP {resp.status_code}")

            reply = self._extract_reply_text(resp.text)
            if not reply:
                fallback_reply = await self._try_api_fallback(prompt)
                if fallback_reply:
                    return fallback_reply
                raise HTTPException(status_code=502, detail="Failed to extract chat text from Gemini stream")
            return reply

    async def _try_api_fallback(self, prompt: str) -> Optional[str]:
        if os.getenv("ALLOW_EXTERNAL_FALLBACK", "").strip().lower() in ("0", "false", "no"):
            return None
        api_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
        if not api_key:
            return None
        logger.info("Attempting Gemini API Key fallback response...")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                r = await client.post(url, json=payload)
                if r.status_code == 200:
                    data = r.json()
                    cands = data.get("candidates", [])
                    if cands and "content" in cands[0]:
                        parts = cands[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            text = parts[0]["text"].strip()
                            logger.info(f"Gemini API fallback succeeded ({len(text)} chars)")
                            return text
        except Exception as exc:
            logger.warning(f"Gemini API fallback error: {exc}")
        return None


relay_engine = GeminiCookieEngine()
_engine_latency: dict[str, float] = {"duck": 500.0, "gemini": 1500.0}

# ── Session evidence ────────────────────────────────────────────────────────
# Whether a stored cookie still works can only be learned by using it, so this
# records the outcome of real requests instead of inventing a probe that burns
# quota. `/health` publishes the snapshot and the gateway turns EXPIRED /
# CHALLENGED into a cooldown, so a dead session stops taking traffic instead of
# failing one user at a time. Values never leave this process — only the state,
# a short reason, and an age.
SESSION_STATES = frozenset({"OK", "UNKNOWN", "EXPIRED", "CHALLENGED"})
_session_state: dict[str, dict] = {}


def note_session(engine: str, state: str, detail: str = "") -> None:
    """Record the outcome of one engine attempt (never raises, never logs secrets)."""
    if state not in SESSION_STATES:
        state = "UNKNOWN"
    entry = _session_state.setdefault(engine, {"consecutive_failures": 0})
    if state == "OK":
        entry["consecutive_failures"] = 0
    else:
        entry["consecutive_failures"] = int(entry.get("consecutive_failures", 0)) + 1
    entry.update(state=state, detail=(detail or "")[:200], updated_at=time.time())


def classify_failure(exc: BaseException) -> tuple[str, str]:
    """Map an engine failure onto a session state an operator can act on.

    Conservative by construction: only an explicit auth status (401/403) claims
    EXPIRED, and only an explicit challenge/429 claims CHALLENGED. Everything
    else is UNKNOWN, which the gateway does not act on — a guess must not cool a
    healthy surface.
    """
    detail = str(getattr(exc, "detail", exc) or "")
    # An HTTPException carries its status explicitly, so reading it is not a
    # guess. Engines that raise `HTTPException(403, "...")` with a generic detail
    # used to classify as UNKNOWN and keep a dead cookie in rotation; a genuine
    # auth code is exactly what this function exists to catch.
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return "EXPIRED", detail or f"HTTP {status}"
    if status == 429:
        return "CHALLENGED", detail or "HTTP 429"
    lowered = detail.lower()
    if "challenge" in lowered:
        return "CHALLENGED", detail
    for marker, state in (("HTTP 429", "CHALLENGED"), ("HTTP 401", "EXPIRED"), ("HTTP 403", "EXPIRED")):
        if marker in detail:
            return state, detail
    return "UNKNOWN", detail


# Internal engine name → the id `/models` already publishes. The gateway joins
# latency and session evidence on the same key, so publishing `gemini` here and
# `gemini-web` there would silently match nothing.
PUBLISHED_ENGINE_IDS: dict[str, str] = {"duck": "duck", "gemini": "gemini-web"}


def loaded_cookies() -> Dict[str, str]:
    """Cookies already in memory — attribute reads only, never the vault.

    `/health` is polled continuously by the platform, so it must not block on
    Infisical or the on-disk vault. A health endpoint reports what is loaded, not
    what could be loaded; `get_cookies()` performs I/O and belongs on the request
    path, not here.
    """
    return (
        getattr(relay_engine, "_infisical_cookies", None)
        or getattr(relay_engine, "_cookies", None)
        or {}
    )


def session_snapshot() -> dict[str, dict]:
    """Per-engine session state for `/health` (attribute reads only — no vault I/O)."""
    now = time.time()
    snapshot: dict[str, dict] = {}
    for engine in ("duck", "gemini"):
        entry = dict(
            _session_state.get(engine)
            or {
                "state": "UNKNOWN",
                "detail": "no request yet",
                "updated_at": 0.0,
                "consecutive_failures": 0,
            }
        )
        updated = float(entry.get("updated_at") or 0.0)
        entry["age_s"] = round(now - updated, 1) if updated else None
        entry["disabled"] = engine_disabled(engine)
        if entry["disabled"]:
            entry["disabled_reason"] = _engine_disabled[engine]["reason"]
        if engine == "gemini":
            cookies = loaded_cookies()
            entry["cookie_present"] = bool(cookies)
            entry["cookie_count"] = len(cookies)
        snapshot[PUBLISHED_ENGINE_IDS[engine]] = entry
    return snapshot


async def iter_duck_deltas(lines: Any) -> AsyncIterator[str]:
    """Duck.ai SSE lines → text deltas.

    Kept pure and module-level so the frame format can be tested without a
    socket, a token, or an upstream. `data: [DONE]` ends the stream; anything
    that is not a `message` frame (vqd metadata, action frames, keep-alive
    comments) is skipped, exactly as the old whole-body parser skipped it.
    """
    async for raw in lines:
        line = str(raw).strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        try:
            parsed = json.loads(data)
        except ValueError:
            continue
        message = parsed.get("message") if isinstance(parsed, dict) else None
        if message:
            yield str(message)


class DuckAiEngine:
    """Lightweight Pure-HTTP $0 Web AI Relay (Duck.ai + Zero-Auth Pollinations OpenAI fallback).

    Designed strictly for Render 512MB Free Tier (~25MB total RAM):
    - NEVER spawns Playwright or headless Chromium on the chat path.
    - Tier 1 ($0): Duck.ai HTTP SSE stream with fast 6s timeout.
    - Tier 2 ($0): Zero-auth OpenAI-compatible HTTP relay (text.pollinations.ai/openai)
      when datacenter IPs are rate-limited by Duck.ai (~1.5-3s response).
    """

    MODEL_ALIASES: Dict[str, str] = {
        "duck": "gpt-4o-mini",
        "duck-ai": "gpt-4o-mini",
        "duck-gpt": "gpt-4o-mini",
        "duck-gpt-4o-mini": "gpt-4o-mini",
        "duck-claude": "claude-3-haiku-20240307",
        "duck-claude-haiku": "claude-3-haiku-20240307",
        "duck-llama": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "duck-llama-70b": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "duck-mixtral": "mistralai/Mixtral-8x7B-Instruct-v0.1",
    }

    def __init__(self) -> None:
        self._vqd_token: Optional[str] = None
        self._vqd_expiry: float = 0.0

    def resolve_model(self, model_name: Optional[str]) -> str:
        if not model_name:
            return "gpt-4o-mini"
        cleaned = model_name.strip().lower()
        return self.MODEL_ALIASES.get(
            cleaned,
            cleaned
            if "gpt-" in cleaned or "claude-" in cleaned or "llama" in cleaned or "mixtral" in cleaned
            else "gpt-4o-mini",
        )

    async def _fetch_vqd_token(self, client: httpx.AsyncClient) -> Optional[str]:
        """Fetch fresh vqd session token from duckduckgo status endpoint (fast 4s timeout)."""
        now = time.time()
        if self._vqd_token and now < self._vqd_expiry:
            return self._vqd_token

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "x-vqd-accept": "1",
            "Referer": "https://duck.ai/",
            "Origin": "https://duck.ai",
        }
        try:
            resp = await client.get("https://duckduckgo.com/duckchat/v1/status", headers=headers, timeout=4.0)
            token = resp.headers.get("x-vqd-4")
            if token:
                self._vqd_token = token
                self._vqd_expiry = now + 600.0  # 10 min cache
                return token
        except Exception as exc:
            logger.warning(f"[DuckAI] Failed to fetch vqd token via HTTP: {exc}")

        return None

    async def _ask_zero_auth_http_relay(self, client: httpx.AsyncClient, prompt: str) -> Optional[str]:
        """Zero-credential, pure-HTTP OpenAI-compatible $0 relay fallback (~1-2s latency, 0 extra RAM)."""
        relay_url = os.getenv("FREE_HTTP_AI_RELAY_URL", "https://text.pollinations.ai/openai").strip()
        if not relay_url:
            return None
        stealth_headers = {
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/event-stream, */*",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
        }
        try:
            resp = await client.post(
                relay_url,
                json={
                    "model": "openai",
                    "messages": [{"role": "user", "content": prompt}],
                },
                headers=stealth_headers,
                timeout=6.0,
            )
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    choices = data.get("choices") or []
                    if choices and isinstance(choices[0], dict):
                        msg = choices[0].get("message") or {}
                        content = str(msg.get("content") or "").strip()
                        if content:
                            return content
                except Exception:
                    text = resp.text.strip()
                    if text:
                        return text
        except Exception as exc:
            logger.warning(f"[FreeHTTPRelay] Zero-auth HTTP relay failed: {exc}")
        return None

    def _duck_headers(self, token: str) -> Dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Referer": "https://duck.ai/",
            "Origin": "https://duck.ai",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "x-vqd-4": token,
        }

    async def ask(self, prompt: str, model: Optional[str] = None) -> str:
        """Whole answer (the non-streaming contract)."""
        parts = [delta async for delta in self.ask_stream(prompt, model=model)]
        if not parts:
            raise HTTPException(
                status_code=502, detail="Stealth HTTP relay encountered upstream challenge or timeout"
            )
        return "".join(parts)

    async def ask_stream(self, prompt: str, model: Optional[str] = None) -> AsyncIterator[str]:
        """The answer in the order it arrives, tier by tier.

        Tier 1 (zero-auth HTTP relay) answers whole, so it yields once. Tier 2
        (Duck.ai) is an SSE upstream and yields per frame — that is the only tier
        where anything is genuinely incremental, so the caller labels each answer
        with what it actually got instead of advertising token streaming for a
        single-shot body.

        Nothing about the upstream request changed: same jitter, same headers,
        same payload, same 10s timeout. Only the *reading* of the response is
        incremental, which is why the ban-risk posture is untouched.
        """
        await asyncio.sleep(random.uniform(0.05, 0.15))

        async with httpx.AsyncClient(timeout=25.0) as client:
            free_reply = await self._ask_zero_auth_http_relay(client, prompt)
            if free_reply:
                yield free_reply
                return

            token = await self._fetch_vqd_token(client)
            if not token:
                raise HTTPException(
                    status_code=502, detail="Stealth HTTP relay encountered upstream challenge or timeout"
                )

            target_model = self.resolve_model(model)
            payload = {"model": target_model, "messages": [{"role": "user", "content": prompt}]}
            emitted = 0
            try:
                async with client.stream(
                    "POST",
                    "https://duckduckgo.com/duckchat/v1/chat",
                    headers=self._duck_headers(token),
                    json=payload,
                    timeout=10.0,
                ) as resp:
                    if resp.status_code != 200:
                        logger.warning(f"[DuckAI] HTTP chat returned status {resp.status_code}")
                        raise HTTPException(
                            status_code=502,
                            detail=f"Duck.ai chat returned status {resp.status_code}",
                        )
                    new_token = resp.headers.get("x-vqd-4")
                    if new_token:
                        self._vqd_token = new_token
                        self._vqd_expiry = time.time() + 600.0
                    async for delta in iter_duck_deltas(resp.aiter_lines()):
                        emitted += 1
                        yield delta
            except HTTPException:
                raise
            except Exception as exc:
                logger.warning(f"[DuckAI] HTTP chat request failed: {exc}")
                raise HTTPException(
                    status_code=502, detail="Duck.ai chat stream failed before completion"
                ) from exc

            if not emitted:
                raise HTTPException(
                    status_code=502, detail="Stealth HTTP relay encountered upstream challenge or timeout"
                )


duck_engine = DuckAiEngine()


@app.on_event("startup")
async def on_startup():
    logger.info("Initializing Infisical cookie prefetch on startup...")
    try:
        await relay_engine.fetch_cookies_from_infisical()
    except Exception as exc:
        logger.warning(f"Startup Infisical prefetch notice: {exc}")


@app.get("/health")
async def health() -> Dict[str, Any]:
    cookies = loaded_cookies()  # attribute reads only: /health must not hit the vault
    service_name = os.getenv("SERVICE_NAME", "supremeai-scraper")
    max_concurrency = int(os.getenv("SCRAPER_MAX_CONCURRENCY", "3"))
    return {
        "status": "healthy",
        "service": service_name,
        "browser_service": "supremeai-browser-cookie-relay",
        "playwright_available": False,
        "lightweight_http_mode": True,
        "memory_budget_mb": 512,
        "max_concurrency": max_concurrency,
        "cookies_loaded": bool(cookies),
        "total_cookies": len(cookies),
        "infisical_configured": bool(os.getenv("INFISICAL_CLIENT_ID") and os.getenv("INFISICAL_CLIENT_SECRET")),
        # Additive: per-engine session evidence. A cookie that is present is not
        # a session that works, so `cookie_present` and `state` are separate
        # fields and neither is upgraded from the other.
        "sessions": session_snapshot(),
        "timestamp": time.time(),
    }


# --- operator kill switch ---------------------------------------------------
# The only ways to take a web engine out of rotation used to be "wait for a
# cooldown the gateway inferred" or "change an env var and redeploy". Neither is
# a switch an operator can throw at 3am when one engine starts answering with
# garbage, and the relay is the only place that actually decides which engine a
# request goes to — so the switch lives here and is enforced at dispatch.
#
# It is deliberately not magic: an engine is either enabled or it is not, the
# reason and the moment are recorded, and /health publishes the same truth the
# gateway reads. Nothing is silently re-enabled by a success.
DISABLED_ENGINES_ENV = "SUPREMEAI_RELAY_DISABLED_ENGINES"

# Engine name → {"reason": str, "since": epoch seconds}. Empty means "nothing is
# switched off", which is the state every deploy starts in.
_engine_disabled: Dict[str, Dict[str, Any]] = {}


def _seed_disabled_engines(raw: str) -> Dict[str, Dict[str, Any]]:
    """Parse `duck,gemini` / `gemini-web` / `duck:reason,gemini` into the table.

    Accepts both the relay's internal name and the id `/models` publishes,
    because an operator reading a dashboard should not have to know which one
    they are looking at.
    """
    published_to_internal = {published: internal for internal, published in PUBLISHED_ENGINE_IDS.items()}
    seeded: Dict[str, Dict[str, Any]] = {}
    for chunk in (raw or "").split(","):
        token = chunk.strip()
        if not token:
            continue
        name, _, reason = token.partition(":")
        engine = name.strip()
        engine = published_to_internal.get(engine, engine)
        if engine not in PUBLISHED_ENGINE_IDS:
            logger.warning(f"[kill-switch] ignoring unknown engine `{token}` in {DISABLED_ENGINES_ENV}")
            continue
        seeded[engine] = {"reason": reason.strip() or f"disabled by {DISABLED_ENGINES_ENV}", "since": time.time()}
    return seeded


_engine_disabled.update(_seed_disabled_engines(os.getenv(DISABLED_ENGINES_ENV, "")))


def engine_disabled(engine_name: str) -> bool:
    return engine_name in _engine_disabled


def disabled_engines() -> Dict[str, Dict[str, Any]]:
    """Copy of the switch table, for publishing — never a live reference."""
    return {engine: dict(entry) for engine, entry in _engine_disabled.items()}


def set_engine_disabled(engine_name: str, disabled: bool, reason: str = "") -> Dict[str, Any]:
    """Throw the switch. Returns the engine's new state; raises on a bad name."""
    if engine_name not in PUBLISHED_ENGINE_IDS:
        raise HTTPException(status_code=404, detail=f"unknown relay engine `{engine_name}`")
    if disabled:
        _engine_disabled[engine_name] = {
            "reason": (reason or "disabled by operator").strip()[:200],
            "since": time.time(),
        }
        logger.warning(f"[kill-switch] {engine_name} DISABLED ({_engine_disabled[engine_name]['reason']})")
    else:
        _engine_disabled.pop(engine_name, None)
        logger.info(f"[kill-switch] {engine_name} enabled")
    return {"engine": engine_name, "disabled": engine_name in _engine_disabled, **_engine_disabled.get(engine_name, {})}


def available_engines() -> List[str]:
    """Engines that may serve right now, fastest first. Empty means "none"."""
    candidates = [name for name in ("duck", "gemini") if not engine_disabled(name)]
    return sorted(candidates, key=lambda name: _engine_latency.get(name, 9999.0))


@app.get("/admin/engines")
async def admin_engines(request: Request) -> Dict[str, Any]:
    """Current switch state. Operator-authenticated: engine posture is not public."""
    _verify_stealth_secret(request)
    return {
        "engines": [
            {
                "engine": internal,
                "published_id": published,
                "disabled": engine_disabled(internal),
                "latency_ms": _engine_latency.get(internal, 0.0),
                **_engine_disabled.get(internal, {}),
            }
            for internal, published in PUBLISHED_ENGINE_IDS.items()
        ]
    }


@app.post("/admin/engines")
async def admin_set_engine(request: Request) -> Dict[str, Any]:
    """Disable or re-enable one engine without a deploy.

    Body: `{"engine": "duck", "disabled": true, "reason": "returning garbage"}`.
    The published id (`duck`, `gemini-web`) is accepted as well as the internal
    name, so the value an operator copies out of `/health` is always usable.
    """
    _verify_stealth_secret(request)
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - a malformed body is a client error, not a crash
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")
    published_to_internal = {published: internal for internal, published in PUBLISHED_ENGINE_IDS.items()}
    engine = str(payload.get("engine") or "").strip()
    engine = published_to_internal.get(engine, engine)
    disabled = payload.get("disabled")
    if not isinstance(disabled, bool):
        raise HTTPException(status_code=400, detail="`disabled` must be true or false")
    return set_engine_disabled(engine, disabled, str(payload.get("reason") or ""))


@app.get("/models")
async def models() -> Dict[str, Any]:
    # Rows come from PUBLISHED_ENGINE_IDS, the same table /health uses: a second
    # hand-written list is exactly how the two endpoints drifted before (#695).
    # A disabled engine keeps its row (the gateway joins on that id) and says so.
    return {
        "data": [
            {
                "id": published,
                "latency_ms": _engine_latency.get(internal, 0.0),
                "disabled": engine_disabled(internal),
            }
            for internal, published in PUBLISHED_ENGINE_IDS.items()
        ]
    }


@app.get("/release")
async def release() -> Dict[str, Any]:
    commit = (
        os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("GIT_COMMIT")
        or os.getenv("GITHUB_SHA")
        or os.getenv("COMMIT_SHA")
        or ""
    ).strip()
    return {
        "service": os.getenv("RENDER_SERVICE_NAME") or os.getenv("SERVICE_NAME", "supremeai-scraper"),
        "environment": os.getenv("RENDER_ENV") or os.getenv("ENV", "production"),
        "commit": commit,
        "build_id": os.getenv("RENDER_DEPLOY_ID") or os.getenv("RENDER_INSTANCE_ID") or "",
        "capabilities": {
            "browser": "registered",
            "lightweight_http_mode": True,
        },
    }


def _verify_stealth_secret(request: Request) -> None:
    expected = os.getenv("STEALTH_WEBHOOK_SECRET", "").strip()
    if not expected:
        # Fail-closed in production (Render) when the secret is unset; keep
        # dev/test bypass so local runs and unit tests are not blocked.
        is_prod = bool(
            os.getenv("RENDER_SERVICE_NAME")
            or os.getenv("RENDER")
            or os.getenv("RENDER_ENV", "").strip().lower() in ("production", "prod")
            or os.getenv("ENV", "").strip().lower() in ("production", "prod")
        )
        if is_prod:
            raise HTTPException(
                status_code=500, detail="STEALTH_WEBHOOK_SECRET is required in production"
            )
        return
    incoming = (
        request.headers.get("X-Stealth-Secret")
        or request.headers.get("X-Webhook-Secret")
        or request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    )
    if not hmac.compare_digest(incoming, expected):
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing stealth secret")


@app.post("/api/chat")
async def api_chat(request: Request) -> Dict[str, Any]:
    _verify_stealth_secret(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    prompt = body.get("message") or body.get("prompt") or ""
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Empty prompt or message")

    model = str(body.get("model") or "").strip().lower()
    source = "gemini.google.com (Cookie Relay)"

    if "duck" in model:
        reply = await duck_engine.ask(prompt.strip(), model=model)
        source = f"duck.ai ({duck_engine.resolve_model(model)})"
    else:
        try:
            reply = await relay_engine.ask(prompt.strip())
        except Exception as exc:
            logger.warning(f"Gemini relay failed ({exc}); attempting lightweight $0 HTTP fallback...")
            try:
                reply = await duck_engine.ask(prompt.strip(), model="gpt-4o-mini")
                source = "duck.ai (gpt-4o-mini fallback)"
            except Exception:
                raise exc

    return {
        "reply": reply,
        "source": source,
        "cost": "$0.00",
    }


def _format_stealth_chat_prompt(messages: list[ChatMessage]) -> str:
    """Natural dialogue formatter with conversational deduplication and sliding window."""
    if not messages:
        return ""

    cleaned: list[tuple[str, str]] = []
    for m in messages:
        c = (m.content or "").strip()
        if not c:
            continue
        # Strip noisy IDE headers if present in historical context
        if "<environment_details>" in c and len(messages) > 1:
            c = re.sub(r"<environment_details>[\s\S]*?</environment_details>", "", c).strip()
        if not c:
            continue
        role = (m.role or "user").strip().lower()
        if cleaned and cleaned[-1][0] == role and cleaned[-1][1] == c:
            continue
        cleaned.append((role, c))

    if not cleaned:
        return ""

    # If single turn, return directly
    if len(cleaned) == 1 and cleaned[0][0] == "user":
        return cleaned[0][1]

    # Sliding window: keep up to last 6 turns to avoid bloated token context
    window = cleaned[-6:]
    dialogue: list[str] = []
    for r, c in window:
        prefix = "User" if r == "user" else "Assistant"
        dialogue.append(f"{prefix}: {c}")

    return "\n\n".join(dialogue)


# --- streaming pass-through ------------------------------------------------
# The gateway asks for `stream: true` and reads SSE. Until now the relay accepted
# the flag, ignored it, and answered with one JSON body — so every streamed
# request to a web engine burned the full engine latency and then failed with
# "Upstream stream ended before completion". These frames fix that without
# pretending the engines got faster: Duck.ai is read incrementally, the cookie
# engine is not, and each answer says which one it was.
STREAM_HEARTBEAT_S = float(os.getenv("SUPREMEAI_RELAY_HEARTBEAT_S", "4"))


def sse_frame(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_comment(text: str) -> str:
    return f": {text}\n\n"


def completion_chunk(
    chunk_id: str,
    *,
    model: str,
    content: Optional[str] = None,
    finish_reason: Optional[str] = None,
    role: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """One OpenAI `chat.completion.chunk`; `meta` is the part our clients read."""
    delta: Dict[str, Any] = {}
    if role:
        delta["role"] = role
    if content is not None:
        delta["content"] = content
    body: Dict[str, Any] = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    if meta:
        body["supremeai"] = meta
    return body


def engine_brand(engine_name: str) -> Tuple[str, str, str]:
    """`(served_model, engine_code, label)` — one table for both response shapes."""
    if engine_name == "duck":
        return "supremeai-fast", "dk", "SupremeAI w.dk Turbo"
    return "gemini-web", "ge", "SupremeAI w.ge Turbo"


class EngineStream:
    """Run one engine's delta iterator in a task and hand out deltas via a queue.

    The queue is not decoration. Waiting on an async generator's `__anext__` with
    `asyncio.wait_for` *cancels the generator* when the timeout fires, so a
    keep-alive implemented that way would kill the very request it was trying to
    keep alive. Here the engine runs independently and the writer only ever waits
    on the queue, so a silent engine costs a comment frame and nothing else.
    """

    def __init__(self, deltas: AsyncIterator[str]) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task = asyncio.create_task(self._pump(deltas))

    async def _pump(self, deltas: AsyncIterator[str]) -> None:
        try:
            async for delta in deltas:
                await self._queue.put(("delta", delta))
            await self._queue.put(("done", None))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as an SSE error frame
            await self._queue.put(("error", exc))

    async def next(self, timeout: float) -> Tuple[str, Any]:
        return await asyncio.wait_for(self._queue.get(), timeout=timeout)

    async def aclose(self) -> None:
        if not self._task.done():
            self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):  # noqa: B014 - CancelledError is BaseException
            pass


async def engine_deltas(engine_name: str, prompt: str, req_model: str) -> AsyncIterator[str]:
    """One engine's text, with its session outcome recorded exactly once.

    The outcome is recorded on the *whole* answer, not on the first byte: a
    stream the client abandoned must never count as a success (that is how a dead
    cookie used to keep looking healthy), and a mid-stream failure is classified
    the same way a request-level one is.
    """
    start = time.time()
    try:
        if engine_name == "duck":
            async for delta in duck_engine.ask_stream(prompt, model=req_model):
                yield delta
        else:
            yield await relay_engine.ask(prompt)
    except Exception as exc:
        state, detail = classify_failure(exc)
        note_session(engine_name, state, detail)
        logger.warning(f"{engine_name} relay stream failed ({state}: {exc})")
        raise
    else:
        latency = (time.time() - start) * 1000.0
        _engine_latency[engine_name] = (_engine_latency.get(engine_name, latency) * 0.7) + (
            latency * 0.3
        )
        note_session(engine_name, "OK")


async def sse_completion(prompt: str, req_model: str) -> AsyncIterator[str]:
    """Relay one completion as SSE frames, fastest engine first, commit at byte one.

    Fallback stays where it was: only *before* the first delta. Once a byte has
    been sent, switching engines would splice two answers together, so a
    mid-stream failure is reported as an error frame instead.
    """
    chunk_id = "chatcmpl-stealth-relay-" + os.urandom(6).hex()
    order = available_engines()
    if not order:
        yield sse_frame(
            {
                "error": {
                    "message": "every relay engine is switched off by the operator",
                    "type": "operator_disabled",
                }
            }
        )
        yield "data: [DONE]\n\n"
        return
    last_exc: Optional[Exception] = None

    for engine_name in order:
        served_model, engine_code, engine_label = engine_brand(engine_name)
        pump = EngineStream(engine_deltas(engine_name, prompt, req_model))
        committed = False
        deltas = 0
        try:
            while True:
                try:
                    kind, value = await pump.next(STREAM_HEARTBEAT_S)
                except asyncio.TimeoutError:
                    yield sse_comment("waiting")
                    continue
                if kind == "delta":
                    committed = True
                    deltas += 1
                    meta = None
                    if deltas == 1:
                        meta = {
                            "channel": "w",
                            "engine": engine_code,
                            "tier": "Turbo",
                            "label": engine_label,
                            "stream": "sse",
                        }
                    yield sse_frame(
                        completion_chunk(
                            chunk_id,
                            model=served_model,
                            content=value,
                            role="assistant" if deltas == 1 else None,
                            meta=meta,
                        )
                    )
                elif kind == "done":
                    yield sse_frame(
                        completion_chunk(
                            chunk_id,
                            model=served_model,
                            finish_reason="stop",
                            meta={
                                "channel": "w",
                                "engine": engine_code,
                                "tier": "Turbo",
                                "label": engine_label,
                                "delivery": "incremental" if deltas > 1 else "buffered",
                                "deltas": deltas,
                            },
                        )
                    )
                    yield "data: [DONE]\n\n"
                    return
                else:  # error
                    last_exc = value
                    if committed:
                        logger.warning(f"{engine_name} failed mid-stream: {value}")
                        yield sse_frame(
                            {
                                "error": {
                                    "message": "relay engine failed mid-stream",
                                    "type": "upstream_error",
                                }
                            }
                        )
                        yield "data: [DONE]\n\n"
                        return
                    logger.warning(f"{engine_name} produced no first delta ({value}); trying next")
                    break
        finally:
            await pump.aclose()

    yield sse_frame(
        {
            "error": {
                "message": f"relay engines unavailable: {last_exc}",
                "type": "upstream_error",
            }
        }
    )
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest, request: Request) -> Response:
    _verify_stealth_secret(request)
    prompt = _format_stealth_chat_prompt(req.messages)
    if not prompt.strip():
        prompt = "\n".join(m.content for m in req.messages if m.role == "user" and m.content and m.content.strip())
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Missing user message in payload")

    req_model = str(req.model or "auto").strip().lower()

    if req.stream:
        # Headers now, body as it arrives. `X-Accel-Buffering: no` stops a proxy
        # from collecting the whole stream and handing it over at the end, which
        # would silently undo the point of this branch.
        return StreamingResponse(
            sse_completion(prompt.strip(), req_model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    served_model = "supremeai-fast"
    engine_code = "dk"
    engine_label = "SupremeAI w.dk Turbo"

    # Latency-aware engine selection (fastest first), switch-aware, with fallback.
    engine_order = available_engines()
    if not engine_order:
        # 503, not 502: nothing upstream failed, the operator turned everything
        # off. The gateway must not treat that as an engine injury.
        raise HTTPException(
            status_code=503, detail="every relay engine is switched off by the operator"
        )
    last_exc = None
    for engine_name in engine_order:
        try:
            start = time.time()
            if engine_name == "duck":
                reply = await duck_engine.ask(prompt.strip(), model=req_model)
            else:
                reply = await relay_engine.ask(prompt.strip())
            served_model, engine_code, engine_label = engine_brand(engine_name)
            latency = (time.time() - start) * 1000.0
            _engine_latency[engine_name] = (_engine_latency.get(engine_name, latency) * 0.7) + (latency * 0.3)
            note_session(engine_name, "OK")
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            state, detail = classify_failure(exc)
            note_session(engine_name, state, detail)
            logger.warning(f"{engine_name} relay failed ({state}: {exc}); trying next engine...")
            continue
    if last_exc is not None:
        raise HTTPException(status_code=502, detail=f"Stealth relay fallback failed: {last_exc}")

    return JSONResponse(
        {
            "id": "chatcmpl-stealth-relay-" + os.urandom(6).hex(),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": served_model,
            "supremeai_engine": engine_code,
            "supremeai": {
                "channel": "w",
                "engine": engine_code,
                "tier": "Turbo",
                "label": engine_label,
            },
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": reply,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8788"))
    logger.info(f"Starting SupremeAI Gemini Cookie Relay on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
