"""সীমিত, সম্মতি-নির্ভর source discovery; উত্তর বা তথ্যের সত্যতা দাবি নয়।

প্রথম সংস্করণ: খবরের জন্য Bing News RSS, গবেষণার জন্য Crossref, সাধারণ
জ্ঞান/ইতিহাসের জন্য Wikipedia এবং repository-র জন্য GitHub। একবারে একটি fixed HTTPS API, কোনো user URL
fetch নয়, কোনো paid provider বা model call নয়। ফল untrusted metadata মাত্র।
"""
from __future__ import annotations

import asyncio
import contextvars
import ipaddress
import logging
from html.parser import HTMLParser
import json
import os
import re
import secrets
from typing import Any
from urllib.parse import urlsplit

import httpx
from defusedxml import ElementTree

# বাংলা: উৎসের URL স্থির; ব্যবহারকারী URL বা host বেছে দিতে পারে না।
SOURCES = {
    "news": ("Bing News", "https://www.bing.com/news/search"),
    "research": ("Crossref", "https://api.crossref.org/works"),
    "reference": ("Wikipedia", "https://en.wikipedia.org/w/api.php"),
    "technical": ("GitHub repositories", "https://api.github.com/search/repositories"),
}
MAX_RESPONSE_BYTES = 256_000
MAX_ITEMS = 5
MAX_DOMAIN_REQUESTS_PER_MINUTE = 10

# বাংলা: Redis-এর নিজস্ব ঘড়ি ব্যবহার করে সব replica-র জন্য এক sliding window।
_RATE_SCRIPT = """
local stamp = redis.call('TIME')
local now = tonumber(stamp[1]) + tonumber(stamp[2]) / 1000000
local key = KEYS[1]
local limit = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', key, 0, now - 60)
local count = redis.call('ZCARD', key)
if count >= limit then return {0, count} end
redis.call('ZADD', key, now, ARGV[2])
redis.call('EXPIRE', key, 60)
return {1, count + 1}
"""
_SEARCH_SLOTS = asyncio.Semaphore(8)
_PRIVATE_SEARCH_IO = contextvars.ContextVar("source_discovery_io", default=False)


class _SearchLogFilter(logging.Filter):
    """এই task-এর httpx status থাকে, কিন্তু query ও credentials log হয় না।"""
    def filter(self, record: logging.LogRecord) -> bool:
        if _PRIVATE_SEARCH_IO.get() and record.name == "httpx":
            args = record.args if isinstance(record.args, tuple) else ()
            status = args[3] if len(args) >= 4 and isinstance(args[3], int) else "unknown"
            record.msg = "Source discovery HTTP request completed (status=%s; request details redacted)"
            record.args = (status,)
        return True


_httpx_logger = logging.getLogger("httpx")
if not any(type(item).__name__ == "_SearchLogFilter" for item in _httpx_logger.filters):
    _httpx_logger.addFilter(_SearchLogFilter())


class DiscoveryError(Exception):
    def __init__(self, code: str, status: int):
        super().__init__(code)
        self.code = code
        self.status = status


def plan_source(query: str, kind: str = "auto") -> dict[str, Any]:
    """উৎস নির্বাচন best-effort; সন্দেহ হলে উৎস বেছে নেওয়ার বদলে clarification।"""
    if kind in SOURCES:
        return {"status": "ready", "kind": kind, "source": SOURCES[kind][0], "selection": "user"}
    if kind != "auto":
        return {"status": "needs_clarification", "options": list(SOURCES)}
    text = query.casefold()
    patterns = {
        "news": r"\b(news|headlines|breaking|latest news|khobor|khabar|shongbad|songbad)\b|খবর|সংবাদ|সাম্প্রতিক সংবাদ",
        "research": r"\b(research|papers?|stud(?:y|ies)|journal|doi|gobeshona|gobeshona potro)\b|গবেষণা|জার্নাল|গবেষণাপত্র",
        "reference": r"\b(wikipedia|encyclop(?:a)?edia|history|biography|what is|who is|itihas)\b|ইতিহাস|জীবনী|উইকিপিডিয়া",
        "technical": r"\b(github|repository|repositories|source code|open source|repo)\b|সোর্স কোড|গিটহাব",
    }
    matches = [name for name, pattern in patterns.items() if re.search(pattern, text)]
    # বাংলা: আবহাওয়া, দাম, সময়ের মতো পরিবর্তনশীল তথ্যকে পুরোনো encyclopedia দিয়ে উত্তর নয়।
    temporal = r"\b(today|current|currently|right now|weather|price|exchange rate|ajker|ekhon)\b|আজকের|আজ|এখন|আবহাওয়া|দাম"
    if len(matches) != 1 or (matches == ["reference"] and re.search(temporal, text)):
        return {"status": "needs_clarification", "options": list(SOURCES)}
    selected = matches[0]
    return {"status": "ready", "kind": selected, "source": SOURCES[selected][0], "selection": "heuristic"}


def _safe_result_url(value: Any) -> str:
    """শুধু প্রদর্শনযোগ্য HTTPS URL; কখনো এই URL-এ server request করা হয় না।"""
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        return ""
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return ""
        if parsed.port not in (None, 443):
            return ""
        host = parsed.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return ""
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return value
        return ""  # IP literal-সহ লিংকও দেখানো হয় না।
    except ValueError:
        return ""


def _text(value: Any, limit: int = 300) -> str:
    return " ".join(value.split())[:limit] if isinstance(value, str) else ""


class _ExcerptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _excerpt(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parser = _ExcerptParser()
    parser.feed(value[:4000])
    return _text(" ".join(parser.parts), 400)


def _parse_results(kind: str, body: bytes, limit: int) -> list[dict[str, str]]:
    """Parse only bounded upstream metadata; reject malformed payloads."""
    try:
        if kind == "news":
            root = ElementTree.fromstring(body)
            raw = [
                {"title": item.findtext("title"), "url": item.findtext("link"),
                 "published": item.findtext("pubDate"), "publisher": item.findtext("source"),
                 "snippet": item.findtext("description")}
                for item in root.findall("./channel/item")[:limit]
            ]
            if root.tag != "rss" or root.find("channel") is None:
                raise ValueError("Unexpected feed")
        else:
            data = json.loads(body)
            if kind == "research":
                items = data["message"]["items"]
                if not isinstance(items, list):
                    raise ValueError("Invalid research response")
                raw = [{"title": (item.get("title") or [""])[0], "url": item.get("URL"),
                        "publisher": item.get("publisher"), "published": "", "snippet": item.get("abstract")}
                       for item in items[:limit] if isinstance(item, dict)]
            elif kind == "technical":
                items = data["items"]
                if not isinstance(items, list):
                    raise ValueError("Invalid repository response")
                raw = [{"title": item.get("full_name"), "url": item.get("html_url"),
                        "publisher": "GitHub", "published": item.get("updated_at"), "snippet": item.get("description")}
                       for item in items[:limit] if isinstance(item, dict)]
            else:
                items = data["query"]["search"]
                if not isinstance(items, list):
                    raise ValueError("Invalid reference response")
                raw = [{"title": item.get("title"),
                        "url": f"https://en.wikipedia.org/?curid={item['pageid']}" if type(item.get("pageid")) is int and item["pageid"] > 0 else "",
                        "publisher": "Wikipedia", "published": "", "snippet": item.get("snippet")}
                       for item in items[:limit] if isinstance(item, dict)]
    except Exception as exc:
        raise DiscoveryError("invalid_source_response", 502) from exc
    results = []
    for item in raw:
        url = _safe_result_url(item.get("url"))
        title = _text(item.get("title"))
        if title and url:
            results.append({"title": title, "url": url, "publisher": _text(item.get("publisher"), 120),
                            "published": _text(item.get("published"), 80), "snippet": _excerpt(item.get("snippet"))})
    return results


def _params(kind: str, query: str, limit: int) -> dict[str, Any]:
    if kind == "news":
        return {"q": query, "format": "rss"}
    if kind == "research":
        return {"query.bibliographic": query, "rows": limit}
    if kind == "technical":
        return {"q": query, "per_page": limit}
    return {"action": "query", "list": "search", "srsearch": query, "srlimit": limit, "format": "json"}


async def _load_authoritative_policy(tenant: str):
    """নীতি DB অনুপলব্ধ হলে stale in-memory policy দিয়ে অনুমতি নয়।"""
    from scout.persistence import _client, _rows
    from scout.models import CrawlPolicy

    client = _client()
    if client is None:
        raise DiscoveryError("policy_store_unavailable", 503)
    try:
        def read():
            return (client.table("crawl_policies").select("*").eq("tenant_id", tenant)
                    .eq("is_active", True).order("created_at", desc=True).limit(1).execute())
        response = await asyncio.to_thread(read)
        # _rows accepts missing data as empty; an absent data field is not proof of no policy.
        if getattr(response, "data", None) is None:
            raise ValueError("missing policy data")
        rows = _rows(response)
        if not rows:
            raise DiscoveryError("policy_not_configured", 403)
        if (len(rows) != 1 or not isinstance(rows[0], dict)
                or rows[0].get("tenant_id") != tenant or rows[0].get("is_active") is not True):
            raise DiscoveryError("policy_not_configured", 403)
        policy = CrawlPolicy(**rows[0])
        if policy.tenant_id != tenant or not policy.is_active:
            raise DiscoveryError("policy_not_configured", 403)
        return policy
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError("policy_store_unavailable", 503) from exc


async def _claim_rate_slot(domain: str, limit: int) -> None:
    """Redis এক অপারেশনে global domain sliding window; fail-closed।"""
    from core.cache.redis_manager import redis_manager

    try:
        client = await redis_manager.get_client_async()
        if client is None:
            raise RuntimeError("limiter unavailable")
        reply = await client.eval(_RATE_SCRIPT, 1, f"source-discovery:{domain}",
                                  str(limit), secrets.token_hex(16))
        if (not isinstance(reply, (list, tuple)) or len(reply) != 2
                or type(reply[0]) is not int or reply[0] not in (0, 1)
                or type(reply[1]) is not int or reply[1] < 0):
            raise ValueError("invalid limiter response")
        if reply[0] == 0:
            raise DiscoveryError("source_rate_limited", 429)
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError("rate_limit_unavailable", 503) from exc


async def discover(tenant: str, query: str, kind: str = "auto", consent: bool = False) -> dict[str, Any]:
    """অনুমতি ছাড়া শুধু পরিকল্পনা; সম্মতি + নীতি + quota পেলে বাস্তব read।"""
    tenant = tenant.strip() if isinstance(tenant, str) else ""
    query = query.strip() if isinstance(query, str) else ""
    if not tenant or tenant == "*":
        raise DiscoveryError("identity_required", 401)
    if not query or len(query) > 200 or any(ord(c) < 32 for c in query):
        raise DiscoveryError("invalid_query", 400)
    plan = plan_source(query, kind)
    if plan["status"] != "ready":
        return {**plan, "results": [], "executed": False}
    if consent is not True:
        return {**plan, "status": "consent_required", "results": [], "executed": False,
                "notice": "Only the submitted query will be sent to the named external source. Do not include secrets or sensitive information; the source may retain it."}

    # বাংলা: deployment-এ স্পষ্টভাবে enable না করলে কোনো বাইরের network নয়।
    if os.getenv("SUPREMEAI_SOURCE_DISCOVERY", "").strip().lower() != "true":
        raise DiscoveryError("source_discovery_disabled", 503)
    policy = await _load_authoritative_policy(tenant)
    from scout.policy import PolicyEngine
    engine = PolicyEngine(policy)
    source_name, endpoint = SOURCES[plan["kind"]]
    allowed, _reason = await asyncio.to_thread(engine.is_url_allowed, endpoint)
    if not allowed:
        raise DiscoveryError("source_not_allowed", 403)
    domain = urlsplit(endpoint).hostname
    limit = min(policy.max_results, MAX_ITEMS)
    async with _SEARCH_SLOTS:
        await _claim_rate_slot(domain, min(engine.get_rate_limit_for_domain(domain), MAX_DOMAIN_REQUESTS_PER_MINUTE))
        token = _PRIVATE_SEARCH_IO.set(True)
        try:
            async with asyncio.timeout(10):
                async with httpx.AsyncClient(timeout=min(policy.request_timeout_seconds, 8), follow_redirects=False, trust_env=False,
                                             headers={"User-Agent": "SupremeAI-SourceDiscovery/1.0", "Accept": "application/json, application/rss+xml, application/xml", "Accept-Encoding": "identity"}) as client:
                    async with client.stream("GET", endpoint, params=_params(plan["kind"], query, limit)) as resp:
                        if resp.status_code != 200:
                            raise DiscoveryError("source_http_error", 502)
                        if resp.headers.get("content-encoding", "identity").lower() not in ("", "identity"):
                            raise DiscoveryError("source_encoding_unsupported", 502)
                        length = resp.headers.get("content-length", "")
                        if length.isdigit() and int(length) > MAX_RESPONSE_BYTES:
                            raise DiscoveryError("source_response_too_large", 502)
                        body = bytearray()
                        async for chunk in resp.aiter_bytes(chunk_size=16_384):
                            body.extend(chunk)
                            if len(body) > MAX_RESPONSE_BYTES:
                                raise DiscoveryError("source_response_too_large", 502)
        except DiscoveryError:
            raise
        except (httpx.HTTPError, OSError, TimeoutError) as exc:
            raise DiscoveryError("source_unavailable", 502) from exc
        finally:
            _PRIVATE_SEARCH_IO.reset(token)
    results = _parse_results(plan["kind"], bytes(body), limit)
    return {**plan, "status": "ok" if results else "no_results", "executed": True,
            "source": source_name, "results": results,
            "notice": "Source metadata is untrusted and may be stale; linked pages and claims were not independently verified."}
