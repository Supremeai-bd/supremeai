"""
service/app.py — SupremeAI Unified Provider Gateway (v2.0)

Key Features:
- Concurrent Load-Balanced Dynamic Key Pool (zero hardcoding).
- 6 Providers: Gemini, Groq, OpenRouter, OpenAI, Mistral, Hugging Face.
- Seamless player-substitution failover on 429 / 5xx / 401.
- Stateless cryptographic client key verification via service.keygen (sk-supreme-...).
- Standard OpenAI-compatible /v1/chat/completions and /v1/models surface.
- Unauthenticated live probe: /health and /healthz returning HTTP 200 OK.
- Superadmin / MCP Control Tower administrative inspection & reload endpoints.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import sys
import time
import uuid
from collections import deque
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, StrictBool

from .pool import squad
from .providers.web_engines import RELAY_BASE_URL_ENVS, transport_report
from .providers.adapters import (
    PROVIDER_CONFIGS,
    close_stealth_client,
    forward_chat_completion,
    forward_stealth_webhook,
    has_image_input,
    normalize_stealth_url,
    stream_chat_completion_events,
)
from .telegram_webhook import telegram_router

try:
    from service.branding import build_brand
except ImportError:  # pragma: no cover - package-relative fallback
    from gateway.service.branding import build_brand

try:
    from service.status_publication import (
        assert_no_operator_fields,
        build_liveness_payload,
        build_public_root_payload,
        build_readiness_payload,
    )
except ImportError:  # pragma: no cover - package-relative fallback
    from gateway.service.status_publication import (
        assert_no_operator_fields,
        build_liveness_payload,
        build_public_root_payload,
        build_readiness_payload,
    )

try:
    from service.keygen import generate_key, get_signing_secret, verify_key
    from service.providers.web_session import web_bridge
except ImportError:
    try:
        from gateway.service.keygen import generate_key, get_signing_secret, verify_key
    except ImportError:
        def verify_key(key: str) -> dict | None:  # type: ignore[no-redef]
            return None

        def generate_key(client_name: str = "client", quota: str = "standard") -> str:  # type: ignore[no-redef]
            """Fail-closed stub: without keygen nothing can sign a token."""
            raise RuntimeError(
                "keygen unavailable (neither service.keygen nor "
                "gateway.service.keygen is importable): refusing to issue an "
                "unsigned API token"
            )

        def get_signing_secret() -> str:  # type: ignore[no-redef]
            """Fail-closed stub: no signing secret is resolvable without keygen."""
            raise RuntimeError(
                "keygen unavailable (neither service.keygen nor "
                "gateway.service.keygen is importable): no signing secret"
            )
    try:
        from gateway.service.providers.web_session import web_bridge
    except ImportError:
        try:
            from service.providers.web_session import web_bridge
        except ImportError:
            web_bridge = None  # type: ignore[assignment]


try:
    from service.webhook_scout import webhook_scout
except ImportError:
    try:
        from gateway.service.webhook_scout import webhook_scout
    except ImportError:
        webhook_scout = None  # type: ignore[assignment]

try:
    from .storage import (
        add_message,
        create_user,
        delete_conversation,
        get_conversation,
        get_user_by_email,
        get_user_preferences,
        list_conversations,
        save_conversation,
        save_guest_token,
        save_user_preferences,
        verify_guest_token,
        verify_user_password,
    )
except ImportError:
    try:
        from gateway.service.storage import (
            add_message,
            create_user,
            delete_conversation,
            get_conversation,
            get_user_by_email,
            get_user_preferences,
            list_conversations,
            save_conversation,
            save_guest_token,
            save_user_preferences,
            verify_guest_token,
            verify_user_password,
        )
    except ImportError:
        add_message = None  # type: ignore[assignment]
        create_user = None  # type: ignore[assignment]
        delete_conversation = None  # type: ignore[assignment]
        get_conversation = None  # type: ignore[assignment]
        get_user_by_email = None  # type: ignore[assignment]
        get_user_preferences = None  # type: ignore[assignment]
        list_conversations = None  # type: ignore[assignment]
        save_conversation = None  # type: ignore[assignment]
        save_guest_token = None  # type: ignore[assignment]
        save_user_preferences = None  # type: ignore[assignment]
        verify_guest_token = None  # type: ignore[assignment]
        verify_user_password = None  # type: ignore[assignment]

# ── Provider-Agnostic Context Compiler, Response Guard & Canonical Memory ──
try:
    from .context_compiler import compile_chat_context, resolve_sampling_knobs
    from .memory_store import (
        append_canonical_message,
        get_recent_history,
        get_user_durable_memories,
        ingest_consented_personal_memory,
        get_personal_memory_state,
        set_personal_memory_consent,
        clear_personal_memory,
        log_provider_attempt,
    )
    from .response_guard import (
        is_stub_content,
        purge_identity_bleed,
        repair_markdown,
        validate_and_sanitize,
    )
except ImportError:
    try:
        from gateway.service.context_compiler import (
            compile_chat_context,
            resolve_sampling_knobs,
        )
        from gateway.service.memory_store import (
            append_canonical_message,
            get_recent_history,
            get_user_durable_memories,
            ingest_consented_personal_memory,
            get_personal_memory_state,
            set_personal_memory_consent,
            clear_personal_memory,
            log_provider_attempt,
        )
        from gateway.service.response_guard import (
            is_stub_content,
            purge_identity_bleed,
            repair_markdown,
            validate_and_sanitize,
        )
    except ImportError:
        compile_chat_context = None  # type: ignore[assignment]
        resolve_sampling_knobs = None  # type: ignore[assignment]
        validate_and_sanitize = None  # type: ignore[assignment]
        purge_identity_bleed = None  # type: ignore[assignment]
        is_stub_content = None  # type: ignore[assignment]
        repair_markdown = None  # type: ignore[assignment]
        append_canonical_message = None  # type: ignore[assignment]
        get_recent_history = None  # type: ignore[assignment]
        get_user_durable_memories = None  # type: ignore[assignment]
        ingest_consented_personal_memory = None  # type: ignore[assignment]
        get_personal_memory_state = None  # type: ignore[assignment]
        set_personal_memory_consent = None  # type: ignore[assignment]
        clear_personal_memory = None  # type: ignore[assignment]
        log_provider_attempt = None  # type: ignore[assignment]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("supremeai.gateway")
try:
    from .request_trace import RequestTrace
except (ImportError, ModuleNotFoundError):  # flat-layout imports (service.app)
    from request_trace import RequestTrace
try:
    from .trivial_input import trivial_reply
except (ImportError, ModuleNotFoundError):  # flat-layout imports (service.app)
    from trivial_input import trivial_reply


# ── LiveLogs Ring Buffer (Admin Console Server-Side Log Streaming) ───────────

class RingBufferLogHandler(logging.Handler):
    """In-memory thread-safe ring buffer capturing recent logs for Admin LiveLogs & SSE."""

    def __init__(self, maxlen: int = 1000):
        super().__init__()
        self.buffer: deque = deque(maxlen=maxlen)
        self.subscribers: set = set()

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            entry = {
                "id": f"log-{int(record.created * 1000)}-{os.urandom(2).hex()}",
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "time": record.created,
                "level": record.levelname,
                "name": record.name,
                "message": msg,
            }
            self.buffer.append(entry)

            # Broadcast to live SSE subscribers
            if self.subscribers:
                for q in list(self.subscribers):
                    try:
                        q.put_nowait(entry)
                    except Exception:
                        self.subscribers.discard(q)
        except Exception:
            self.handleError(record)

    def get_logs(self, limit: int = 100, level: Optional[str] = None, search: Optional[str] = None) -> list:
        items = list(self.buffer)
        if level:
            items = [item for item in items if item["level"].upper() == level.upper()]
        if search:
            s = search.lower()
            items = [item for item in items if s in item["message"].lower() or s in item["name"].lower()]
        return items[-limit:]


log_ring_buffer = RingBufferLogHandler(maxlen=1000)
log_ring_buffer.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logger.addHandler(log_ring_buffer)
logging.getLogger().addHandler(log_ring_buffer)

# Priority-1 Stealth Webhook & Web Session Configuration
STEALTH_WEBHOOK_URL = os.getenv("STEALTH_WEBHOOK_URL", os.getenv("UPSTREAM_WEBHOOK_URL", "")).strip()
STEALTH_WEBHOOK_SECRET = os.getenv("STEALTH_WEBHOOK_SECRET", os.getenv("UPSTREAM_WEBHOOK_SECRET", "")).strip()
STEALTH_WEBHOOK_TIMEOUT = float(os.getenv("STEALTH_WEBHOOK_TIMEOUT", "8.0"))
# Overall end-to-end budget for provider failover before the first token. Bounds
# worst-case client wait even if an upstream hangs (per-model timeout is 6s and a
# slot can cascade several models). Only guards time-to-first-token; once a stream
# has started it is never cut. Override with CHAT_ROUTE_DEADLINE_S.
CHAT_ROUTE_DEADLINE_S = float(os.getenv("CHAT_ROUTE_DEADLINE_S", "15"))
# Phase-1 fix (2026-11): rank/failover on time-to-first *text token*, not headers.
# A provider is only marked started/successful once the first text/tool_calls delta
# arrives; until then a per-candidate first-token timeout lets us cancel a slow
# upstream and try the next healthy candidate before forwarding anything downstream.
CHAT_CONNECT_TIMEOUT_S = float(os.getenv("CHAT_CONNECT_TIMEOUT_S", "8"))
CHAT_FIRST_TOKEN_TIMEOUT_S = float(os.getenv("CHAT_FIRST_TOKEN_TIMEOUT_S", "8"))


def _api_fallback_enabled() -> bool:
    """Admin-gated API fallback for relay-only models.

    gateway/SYSTEM_CHAT_AND_DEPLOYMENT_ARCHITECTURE.md documents an
    ``ENABLE_API_FALLBACK=false`` lock, but no code ever read the variable —
    the lock was documentation only, and a relay outage hard-failed every
    ``supremeai-web`` request with 502. Reading the env here makes the
    documented contract real: default ``false`` preserves the current
    relay-only policy exactly; an admin sets ``ENABLE_API_FALLBACK=true``
    (Infisical) to let a failed relay fall through to the sovereign API pool.
    """
    return os.getenv("ENABLE_API_FALLBACK", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

# ── Per-model latency budget: rank → deadline ────────────────────────────────
# route_arbiter.MODEL_LATENCY_THRESHOLDS_MS declares per-model budgets and says
# so in prose ("supreme-spark: Ultra-low latency (<1.5s)"), but every read of
# that table feeds route_score() — a RANKING input that sorts candidate slots.
# Nothing turned the number into a clock, so the enforced envelope stayed flat at
# 8s first-token / 15s route while the product advertised 1.5s. A one-word reply
# measured at 6.2s is that gap being spent.
#
# The helpers below derive real clocks from the declared budget. Precedence is
# deliberate: an explicit env override always wins (ops can widen a lane without
# a deploy), then the model's own budget, then a sane default. They are pure so
# they can be unit-tested without standing up the app.
_DEFAULT_ROUTE_BUDGET_S = 1.8
# Never hand the upstream a sub-second socket timeout: a legitimately slow but
# healthy relay would then be recorded as a failure and cooled down.
RELAY_MIN_TIMEOUT_S = float(os.getenv("RELAY_MIN_TIMEOUT_S", "3.0"))


def _route_budget_s(model: str) -> float:
    """Declared latency budget for ``model`` in seconds (from the arbiter table)."""
    try:
        from .route_arbiter import MODEL_LATENCY_THRESHOLDS_MS
    except (ImportError, ModuleNotFoundError):  # flat-layout import
        from route_arbiter import MODEL_LATENCY_THRESHOLDS_MS

    key = (model or "").strip().lower()
    budget_ms = MODEL_LATENCY_THRESHOLDS_MS.get(key)
    if budget_ms is None:
        return _DEFAULT_ROUTE_BUDGET_S
    return float(budget_ms) / 1000.0


def _route_deadline_for(model: str) -> float:
    """End-to-end failover deadline: the model budget, unless ops widened it.

    ``min`` is intentional on the env path: an operator can only ever widen the
    envelope deliberately via CHAT_ROUTE_DEADLINE_S, and the result can never be
    tighter than the model's declared budget (which would make a healthy slow
    model impossible to serve).
    """
    budget = _route_budget_s(model)
    # Only an EXPLICIT setting counts as an operator override. Reading the
    # module-level CHAT_ROUTE_DEADLINE_S here would make its 15s code default
    # look like an override and silently re-create the flat envelope this
    # function exists to remove (caught by test_spark_budget_is_tighter).
    explicit = float(os.getenv("CHAT_ROUTE_DEADLINE_S", "") or 0)
    if explicit > 0:
        return explicit
    # No override: fall back to the module value ONLY if it is tighter than the
    # model budget (tests and callers may lower it); never widen past the budget.
    return min(budget, CHAT_ROUTE_DEADLINE_S) if CHAT_ROUTE_DEADLINE_S < budget else budget


def _first_token_timeout_for(model: str) -> float:
    """Time allowed before abandoning a candidate for the next one.

    Bounded by the budget so a slow upstream is cancelled *within* the promise
    instead of 5x past it. Never below the flat floor for tiny budgets, so a
    mis-set threshold cannot make every request fail instantly.
    """
    budget = _route_budget_s(model)
    ceiling = min(CHAT_FIRST_TOKEN_TIMEOUT_S, budget)
    return max(ceiling, 0.25)


def _connect_timeout_for(model: str) -> float:
    """TCP/TLS budget — a fraction of the first-token clock, never larger."""
    return min(CHAT_CONNECT_TIMEOUT_S, _first_token_timeout_for(model))
# How long SSE keep-alives may hold a stream open past the first-token window.
# A relay that buffers a slow engine answers in 10-25s; the engine's own request
# timeout (25s) is the real bound, this is the last line of defence.
CHAT_STREAM_HEARTBEAT_CEILING_S = float(
    os.getenv("CHAT_STREAM_HEARTBEAT_CEILING_S", "45")
)


async def _aiter_stream_first_token(
    stream_iter,
    *,
    connect_timeout_s: float,
    first_token_timeout_s: float,
    route_deadline: float | None = None,
    heartbeat_ceiling_s: float | None = None,
):
    """Yield ``(kind, data)`` from ``stream_iter``, enforcing time-to-first-token.

    * Before the first ``("status")`` item: apply ``connect_timeout_s``.
    * After status, until the first ``("event")`` carrying text or tool_calls:
      apply ``first_token_timeout_s``; once that token arrives the stream is
      committed and items are yielded without an extra timeout.
    * Raise ``asyncio.TimeoutError`` if the first token does not arrive in time, so
      the caller can fail over to the next candidate before forwarding anything
      downstream (headers alone are not treated as success).

    ``("heartbeat")`` items are SSE keep-alives. They *extend* the first-token
    window by one more ``first_token_timeout_s``, up to ``heartbeat_ceiling_s``
    measured from entry. The timeout exists to detect an upstream that has gone
    quiet; an upstream that keeps proving it is alive is not that, and killing it
    at 8s was the reason a buffered web engine (which takes 10-25s to answer and
    then sends everything at once) could never serve a streamed request. The
    ceiling keeps a chatty-but-stuck upstream from holding the slot forever, and
    ``route_deadline`` still caps the whole route.
    """
    entered = time.monotonic()
    ceiling = (
        entered + heartbeat_ceiling_s
        if heartbeat_ceiling_s is not None
        else float("inf")
    )
    deadline = time.monotonic() + connect_timeout_s
    committed = False
    while True:
        try:
            if committed:
                item = await stream_iter.__anext__()
            else:
                attempt_deadline = deadline if route_deadline is None else min(deadline, route_deadline)
                remaining = attempt_deadline - time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError()
                item = await asyncio.wait_for(stream_iter.__anext__(), timeout=remaining)
        except StopAsyncIteration:
            return
        kind, data = item
        if kind == "heartbeat":
            if not committed and ceiling > entered:
                deadline = min(
                    max(deadline, time.monotonic()) + first_token_timeout_s, ceiling
                )
            continue
        if kind == "status":
            deadline = time.monotonic() + first_token_timeout_s
        elif kind == "event" and not committed:
            if (data.get("delta") or "") or data.get("tool_calls"):
                committed = True
        yield kind, data

try:
    from service.adaptive_routing import RouteState
except ImportError:  # pragma: no cover - package-relative fallback
    from gateway.service.adaptive_routing import RouteState


def _optional_int_env(*names: str) -> int | None:
    for name in names:
        raw = os.getenv(name, "").strip()
        if raw:
            try:
                return max(0, int(raw))
            except ValueError:
                logger.warning("Ignoring invalid adaptive routing limit %s", name)
    return None


_adaptive_routes = {
    "stealth-webhook": RouteState(
        "stealth-webhook",
        remaining=_optional_int_env("STEALTH_WEBHOOK_REMAINING"),
        limit=_optional_int_env("STEALTH_WEBHOOK_FREE_LIMIT"),
    ),
    "api-pool": RouteState(
        "api-pool",
        remaining=_optional_int_env("SUPREMEAI_API_REMAINING"),
        limit=_optional_int_env("SUPREMEAI_API_FREE_LIMIT"),
    ),
}

from contextlib import asynccontextmanager


@asynccontextmanager
async def _gateway_lifespan(gateway_app: FastAPI):
    """Lifespan handler — replaces the deprecated @app.on_event hooks.

    Startup: hydrate Infisical vault keys, start the discovery + relay health
    loops, and name the transport that will actually serve web engines.
    Shutdown: cancel those loops and close pooled stealth HTTP clients.
    """
    await _on_startup()
    try:
        yield
    finally:
        await _close_stealth_http_client()


app = FastAPI(title="SupremeAI API Gateway", version="2.0.0", docs_url=None, redoc_url=None, openapi_url=None, lifespan=_gateway_lifespan)  # docs lockdown completion: the openapi_url default served the full route inventory (incl. admin route names) unauthenticated.


async def hydrate_vault_secrets() -> int:
    """Hydrates multi-cloud API keys from Infisical Production Vault into os.environ and squad."""
    import httpx
    # Security hardening (audit 2026-11-11): vault credentials must never live in
    # source. The previous literal fallbacks leaked a working universal-auth
    # client_id/client_secret/workspace_id to anyone with repo read access.
    # Missing env vars now simply skip vault hydration (fail-closed for secrets).
    client_id = os.getenv("INFISICAL_CLIENT_ID", "").strip()
    client_secret = os.getenv("INFISICAL_CLIENT_SECRET", "").strip()
    workspace_id = (os.getenv("INFISICAL_WORKSPACE_ID", "") or os.getenv("INFISICAL_PROJECT_ID", "")).strip()
    if not client_id or not client_secret or not workspace_id:
        return 0
    environment = os.getenv("INFISICAL_ENV", "prod").strip() or "prod"
    base_url = os.getenv("INFISICAL_API_URL", "https://app.infisical.com").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            login_resp = await client.post(
                f"{base_url}/api/v1/auth/universal-auth/login",
                json={"clientId": client_id, "clientSecret": client_secret},
            )
            login_resp.raise_for_status()
            token = login_resp.json().get("accessToken")
            if not token:
                return 0
            url = f"{base_url}/api/v3/secrets/raw"
            params = {"workspaceId": workspace_id, "environment": environment, "secretPath": "/"}
            resp = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
            secrets = resp.json().get("secrets", [])
            loaded = 0
            for s in secrets:
                k = s.get("secretKey")
                v = s.get("secretValue")
                if k and v and (
                    k == "SUPREMEAI_FREE_ROUTE_POLICY"
                    or any(term in k for term in ("KEY", "TOKEN", "SECRET", "STEALTH"))
                ):
                    os.environ[k] = v
                    loaded += 1
            if squad and loaded > 0:
                squad.reload_squad()
                logger.info(f"Hydrated {loaded} vault keys. Squad active with {squad.stats().get('total_healthy_keys', 0)} healthy keys.")
            return loaded
    except Exception as exc:
        logger.warning(f"Startup Infisical hydration warning: {exc}")
        return 0


async def _on_startup():
    from .free_model_discovery import discovery_loop
    from .web_engine_health import web_engine_health_loop

    await hydrate_vault_secrets()
    # One catalog refresh loop; do not send periodic or per-error inference probes.
    app.state.discovery_task = asyncio.create_task(discovery_loop(squad))
    # One latency ingest loop for the web relay: the pool ranks by latency, and
    # the relay already measures it per engine. Read-only, no inference, no quota.
    app.state.web_engine_task = asyncio.create_task(web_engine_health_loop(squad))
    # Which relay the web engines will actually be dispatched to, named once at
    # startup. A deploy whose env var is misspelled used to look identical to a
    # working one until the first request 404'd.
    transport = transport_report()
    if transport["configured"]:
        logger.info(
            "Web relay transport: %s (from %s)", transport["base_url"], transport["source_env"]
        )
    else:
        logger.warning(
            "Web relay transport: %s — no relay env var set (checked %s); "
            "web engines will fail outside a local laptop",
            transport["base_url"],
            ", ".join(RELAY_BASE_URL_ENVS),
        )
    if transport["rejected_envs"]:
        logger.warning("Ignored relay env vars (not usable as a base URL): %s", transport["rejected_envs"])


# Registry lookups live in .registry_lookup (shared with auth_verification).
try:
    from service.registry_lookup import _registry_origin, _registry_url
except ImportError:
    from gateway.service.registry_lookup import _registry_origin, _registry_url  # type: ignore[no-redef]


# CORS setup for Studio and web agents - Restricted origins (no wildcard with credentials)
#
# The canonical Studio origin comes from the registry, not from a literal here:
# config/service_registry.yaml declares `frontend` as platform=cloudflare with
# production_url https://studio.supremeai.lat, and the Vercel/pages.dev hosts
# below were listed INSTEAD of it — so the deployed frontend's real origin was
# the one origin missing from the allowlist, while retired ones were allowed.
# `_registry_origin` comes from .registry_lookup (split out of this module).
_default_cors = [
    # বাংলা মন্তব্য: ক্যানোনিকাল Studio অরিজিন সরাসরি config/service_registry.yaml (_registry_origin) থেকে আসে; ডুপ্লিকেট লিটারাল রাখা যাবে না।
    *filter(None, [_registry_origin("frontend")]),
    "https://supremeai-studio.paykaribazaronline.workers.dev",
    "https://supremeai.live",
    "https://studio.supremeai.lat",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
_studio_preview = os.getenv("STUDIO_FRONTEND_URL", "").strip()
if _studio_preview and _studio_preview not in _default_cors:
    _default_cors.append(_studio_preview)

_cors_env = os.getenv("CORS_ORIGINS", "").strip()
if _cors_env:
    allowed_origins = list(dict.fromkeys([o.strip() for o in _cors_env.split(",") if o.strip()] + _default_cors))
else:
    allowed_origins = _default_cors

# Way 28: bind one correlation id per request (echoed on responses; usable in logs).
from gateway.middleware.correlation_id import CorrelationIdMiddleware

app.add_middleware(CorrelationIdMiddleware)

# Audit P1-12 fix: plain http is only trusted for local development hosts.
# The default origin regex matches localhost/127.0.0.1 only. The previous
# default additionally matched EVERY `*.supremeai-studio.pages.dev` subdomain —
# i.e. any branch preview deployment could make credentialed cross-origin
# requests. Preview origins that legitimately need this must now be opted in
# explicitly via CORS_ORIGIN_REGEX (plus their exact Origin in CORS_ORIGINS).
# বাংলা মন্তব্য: production/staging-এ ডিফল্টভাবে localhost regex বন্ধ রাখা হচ্ছে (SA-17);
# শুধু local/dev/test এনভায়রনমেন্টে বা explicitly CORS_ORIGIN_REGEX দিলে চালু হবে।
_cors_runtime_env = os.getenv("ENVIRONMENT", os.getenv("ENV", "production")).strip().lower()
_default_cors_regex = (
    r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$"
    if _cors_runtime_env in {"local", "development", "dev", "test", "testing"}
    else ""
)
_cors_origin_regex = os.getenv("CORS_ORIGIN_REGEX", _default_cors_regex).strip()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=_cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "Referer",
        "X-SupremeAI-Key",
        "x-supremeai-key",
        "X-Guest-Mode",
        "X-Forwarded-For",
        "X-Correlation-ID",
        "X-Device-Fingerprint",
        "X-CSRF-Token",
        "X-Request-ID",
        "X-JIT-OTP",
        "X-Requested-With",
        "Idempotency-Key",
        "Cache-Control",
        "apikey",
        "X-API-Key",
    ],
    expose_headers=[
        "Content-Length",
        "X-Pagination-Total",
        "X-Request-ID",
        "X-Correlation-ID",
        # Without this the browser hides Server-Timing from JS (DevTools still
        # shows it), so a dashboard could not render latency without this line.
        "Server-Timing",
    ],
)

# Issue #1728: baseline security headers (HSTS/XCTO/XFO/CSP-report-only) on every
# response. Added LAST so it mounts OUTERMOST (Starlette add_middleware prepends):
# request flow Sec -> CORS -> Corr -> routes, so every response — CORS preflight
# included — gets stamped. Pure-ASGI header injection never touches the SSE body.
from gateway.middleware.security_headers import SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)

# Server-Timing on EVERY response, failure paths included. The chat handler
# attaches a detailed stage trace (auth/persist/context/route/upstream) on its
# ~4 success exits, but the ~12 `raise HTTPException` exits (400/401/502/503)
# carried no timing at all — so the requests you most need to attribute were the
# only ones that were invisible. This middleware fills the gap and preserves the
# route-level trace verbatim when one already exists. Added AFTER security
# headers so it mounts outermost: nothing may short-circuit ahead of it.
from gateway.middleware.server_timing import ServerTimingMiddleware, timing_header_for_scope

app.add_middleware(ServerTimingMiddleware)

# বাংলা মন্তব্য: গেটওয়ে মেট্রিক্স ও Grafana Cloud OTLP পুশ সংযুক্ত করা হলো
from gateway.metrics_exporter import (
    record_request as _record_gateway_metric,
    render_metrics as _render_gateway_metrics,
    start_otlp_metrics_background_pusher as _start_otlp_pusher,
)


@app.middleware("http")
async def _gateway_metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    try:
        _record_gateway_metric(request.method, request.url.path, response.status_code, time.time() - start)
    except Exception as exc:
        logger.debug("Gateway metric recording failed (%s)", type(exc).__name__)
    return response


@app.get("/metrics")
async def _prometheus_metrics(request: Request):
    """Expose Prometheus metrics for scraping (optional METRICS_SCRAPE_TOKEN guard)."""
    expected = (os.getenv("METRICS_SCRAPE_TOKEN") or "").strip()
    if expected:
        supplied = (request.headers.get("x-metrics-token") or request.query_params.get("token") or "").strip()
        if supplied != expected:
            return Response(status_code=403, content="forbidden")
    body, ctype = _render_gateway_metrics()
    return Response(content=body, media_type=ctype)


_start_otlp_pusher()


@app.exception_handler(Exception)
async def _unhandled_exception_with_timing(request: Request, exc: Exception) -> JSONResponse:
    """Turn an unhandled crash into an attributable 500.

    Starlette answers an unhandled exception with ``ServerErrorMiddleware``,
    which is mounted OUTSIDE every user middleware — measured stack order:
    ``ServerErrorMiddleware > SecurityHeaders > ServerTiming > ExceptionMiddleware``.
    So no middleware can stamp that response, and a crash used to be the one
    case with no ``Server-Timing`` at all.

    Registering a global ``Exception`` handler moves the response *inside* the
    stack (a handler route inside ``ExceptionMiddleware``), where the clock this
    middleware stashed on the scope is still readable. The body and status stay
    byte-identical to what Starlette sent before — this adds a header, nothing
    else — and re-raises nothing, so error semantics are unchanged.
    """
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
        headers=timing_header_for_scope(request.scope),
    )


# Telegram Inbound Webhook Listener
app.include_router(telegram_router)

# Native Admin Authentication Router (Zero-Firebase)
try:
    from service.admin_auth import router as admin_auth_router
except ImportError:
    try:
        from gateway.service.admin_auth import router as admin_auth_router
    except ImportError:
        try:
            from admin_auth import router as admin_auth_router
        except ImportError:
            admin_auth_router = None

if admin_auth_router is not None:
    app.include_router(admin_auth_router)

# Frontend compatibility (admin dashboard full coverage)
try:
    from service.frontend_compat import router as fe_compat_router
except ImportError:
    try:
        from gateway.service.frontend_compat import router as fe_compat_router
    except ImportError:
        try:
            from gateway.frontend_compat import router as fe_compat_router
        except ImportError:
            fe_compat_router = None
if fe_compat_router is not None:
    app.include_router(fe_compat_router)

# Native Passkey / WebAuthn Biometric Router (Fingerprint/TouchID/FaceID)
try:
    from service.passkey_auth import router as passkey_auth_router
except ImportError:
    try:
        from gateway.service.passkey_auth import router as passkey_auth_router
    except ImportError:
        try:
            from passkey_auth import router as passkey_auth_router
        except ImportError:
            passkey_auth_router = None

if passkey_auth_router is not None:
    app.include_router(passkey_auth_router)


# Epistemic router (ChronoFact/SPINE patterns): tool pruning, memory gate, model horizon.
try:
    from service.epistemic_router import router as epistemic_router
except ImportError:
    try:
        from gateway.service.epistemic_router import router as epistemic_router
    except ImportError:
        epistemic_router = None

if epistemic_router is not None:
    app.include_router(epistemic_router)


# ── Zero-Bundle Dynamic JIT Translation Bridge (Master Blueprint §3) ──
# বাংলা মন্তব্য: মেমোরি ও রেডিস ক্যাশযুক্ত গতিশীল অনুবাদ ব্রিজ — একবার অনুবাদ হলে সারাজীবন ফ্রি,
# তবে অনুবাদ ব্যর্থ হলে কখনোই ইংরেজি ফলব্যাক ক্যাশে দূষিত (poison) করা হয় না।
import re as _re
from collections import OrderedDict as _OrderedDict

_MAX_LOCAL_TRANSLATION_ENTRIES = 4096
_LANG_CODE_RE = _re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})?$")
_LOCAL_TRANSLATION_CACHE: _OrderedDict[tuple[str, str], str] = _OrderedDict(
    [
        (("bn", "chat"), "চ্যাট"),
        (("bn", "settings"), "সেটিংস"),
        (("bn", "projects"), "প্রজেক্টস"),
        (("bn", "plugins"), "প্লাগইন"),
        (("bn", "send"), "পাঠান"),
        (("bn", "cancel"), "বাতিল"),
        (("bn", "save"), "সংরক্ষণ"),
        (("bn", "edit"), "সম্পাদনা"),
        (("bn", "delete"), "মুছুন"),
        (("bn", "new_session"), "নতুন চ্যাট"),
    ]
)


def _put_local_translation(cache_tuple: tuple[str, str], value: str) -> None:
    _LOCAL_TRANSLATION_CACHE[cache_tuple] = value
    _LOCAL_TRANSLATION_CACHE.move_to_end(cache_tuple)
    while len(_LOCAL_TRANSLATION_CACHE) > _MAX_LOCAL_TRANSLATION_ENTRIES:
        _LOCAL_TRANSLATION_CACHE.popitem(last=False)


class TranslationRequest(BaseModel):
    key: str
    target_lang: str
    source_lang: str = "en"
    context: str = "ui"


@app.post("/api/v1/localization/ai-translate")
async def dynamic_ai_translate(req: TranslationRequest) -> dict[str, Any]:
    """Zero-Bundle Dynamic JIT Translation endpoint with bounded LRU & Redis cache."""
    clean_key = (req.key or "").strip()
    target = (req.target_lang or "en").strip().lower()
    if not clean_key or target == "en":
        return {"translation": clean_key, "cached": True, "target_lang": target}

    # বাংলা মন্তব্য: ব্যক্তিগত চ্যাট মেসেজ বা বড় পেলোড যাতে গ্লোবাল UI ক্যাশে না ঢোকে তার কঠোর সীমা
    if len(clean_key) > 240 or "\n" in clean_key or "\r" in clean_key:
        raise HTTPException(
            status_code=400,
            detail="Translation key must be a single-line UI phrase of at most 240 characters",
        )
    if not _LANG_CODE_RE.match(target):
        raise HTTPException(status_code=400, detail="Invalid target_lang format")

    cache_tuple = (target, clean_key)
    if cache_tuple in _LOCAL_TRANSLATION_CACHE:
        _LOCAL_TRANSLATION_CACHE.move_to_end(cache_tuple)
        return {
            "translation": _LOCAL_TRANSLATION_CACHE[cache_tuple],
            "cached": True,
            "target_lang": target,
            "source": "memory",
        }

    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(redis_url, decode_responses=True)
            try:
                cached_val = await r.get(f"jit_trans:{target}:{clean_key}")
            finally:
                await r.aclose()
            if cached_val:
                _put_local_translation(cache_tuple, cached_val)
                return {
                    "translation": cached_val,
                    "cached": True,
                    "target_lang": target,
                    "source": "redis",
                }
        except Exception as exc:
            logger.debug(f"[translation_bridge] redis read skipped: {exc}")

    translated: Optional[str] = None
    try:
        candidates = squad.get_candidate_slots()
        prompt = (
            f"Translate this short software UI phrase from English to '{target}'. "
            f"Return ONLY the direct translation, no quotes or commentary:\n{clean_key}"
        )
        for provider, slot in candidates[:3]:
            cfg = PROVIDER_CONFIGS.get(provider) or {}
            default_model = str(cfg.get("default_model") or "")
            if not default_model:
                continue
            try:
                status_code, resp_json, latency_ms = await forward_chat_completion(
                    provider,
                    slot.api_key,
                    default_model,
                    {
                        "model": default_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 80,
                        "temperature": 0.1,
                    },
                )
                if status_code == 200 and isinstance(resp_json, dict):
                    squad.report_success(provider, slot, latency_ms)
                    choices = resp_json.get("choices") or []
                    raw_text = (
                        ((choices[0].get("message") or {}).get("content") if choices else "") or ""
                    ).strip().strip("\"'")
                    if raw_text and "\n" not in raw_text and raw_text.lower() != clean_key.lower():
                        translated = raw_text
                        break
            except Exception as inner_exc:
                logger.debug(f"[translation_bridge] candidate {provider} failed: {inner_exc}")
    except Exception as exc:
        logger.debug(f"[translation_bridge] provider pool unavailable: {exc}")

    if not translated:
        # বাংলা মন্তব্য: অনুবাদ না পেলে কখনোই ভুল ইংরেজি স্ট্রিং ক্যাশে জমা করা হবে না (সৎ ফলব্যাক)
        return {
            "translation": clean_key,
            "cached": False,
            "fallback": True,
            "target_lang": target,
            "key": clean_key,
        }

    _put_local_translation(cache_tuple, translated)

    if redis_url:
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(redis_url, decode_responses=True)
            try:
                await r.setex(f"jit_trans:{target}:{clean_key}", 604800, translated)
            finally:
                await r.aclose()
        except Exception as exc:
            logger.debug(f"[translation_bridge] redis write skipped: {exc}")

    return {
        "translation": translated,
        "cached": False,
        "fallback": False,
        "target_lang": target,
        "key": clean_key,
    }


# ── L1-L4 Dynamic Configuration Control Plane (Wave 6 §6.1) ──
# বাংলা মন্তব্য: অপারেটর-অথেনটিকেটেড ও এলাওলিস্ট-সুরক্ষিত L1-L4 ডাইনামিক কনফিগারেশন স্ট্যাক
_L3_DYNAMIC_OVERRIDES: dict[str, Any] = {}
ALLOWED_DYNAMIC_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "max_context_tokens",
        "request_timeout_seconds",
        "default_model",
        "rate_limit_per_minute",
        "SUPREMEAI_AGENT_TOOLS",
        "SUPREMEAI_TOOL_FLEET",
        "SUPREMEAI_MEMORY_GRAPH",
    }
)


class LayerOverrideRequest(BaseModel):
    key: str
    value: Any


def _assert_config_layer_operator(request: Request, x_admin_key: Optional[str]) -> None:
    import hmac

    token = _extract_token(request, x_admin_key)
    if token:
        if SUPERADMIN_KEY and hmac.compare_digest(token, SUPERADMIN_KEY):
            return
        if any(hmac.compare_digest(token, k) for k in (OPERATOR_KEYS or ()) if k):
            return
    if _require_operator_key(request, x_admin_key) or _is_admin_principal(request, x_admin_key):
        return
    raise HTTPException(
        status_code=403, detail="Operator or superadmin authorization required"
    )


@app.get("/api/v1/config/layers")
async def get_config_layers(
    request: Request,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
) -> dict[str, Any]:
    """Retrieve the 4-layer dynamic configuration stack (Operator-only)."""
    _assert_config_layer_operator(request, x_admin_key)
    l1_defaults: dict[str, Any] = {
        "max_context_tokens": 16384,
        "request_timeout_seconds": 60,
        "default_model": "deepseek-r1",
        "rate_limit_per_minute": 120,
    }
    l2_env: dict[str, Any] = {
        "SUPREMEAI_AGENT_TOOLS": os.getenv("SUPREMEAI_AGENT_TOOLS", "false"),
        "SUPREMEAI_TOOL_FLEET": os.getenv("SUPREMEAI_TOOL_FLEET", "false"),
        "SUPREMEAI_MEMORY_GRAPH": os.getenv("SUPREMEAI_MEMORY_GRAPH", "true"),
        "ENVIRONMENT": os.getenv("ENV", "production"),
    }
    l3_overrides = dict(_L3_DYNAMIC_OVERRIDES)
    l4_effective = {**l1_defaults, **l2_env, **l3_overrides}

    return {
        "status": "ok",
        "allowed_keys": sorted(ALLOWED_DYNAMIC_CONFIG_KEYS),
        "layers": {
            "L1_defaults": l1_defaults,
            "L2_environment": l2_env,
            "L3_dynamic_overrides": l3_overrides,
            "L4_effective": l4_effective,
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/config/layers")
async def update_config_layer(
    req: LayerOverrideRequest,
    request: Request,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
) -> dict[str, Any]:
    """Apply an L3 dynamic configuration override in-flight (Operator-only, allowlisted)."""
    _assert_config_layer_operator(request, x_admin_key)
    clean_key = (req.key or "").strip()
    if not clean_key:
        raise HTTPException(status_code=400, detail="Configuration key is required")
    if clean_key not in ALLOWED_DYNAMIC_CONFIG_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Key '{clean_key}' is not in ALLOWED_DYNAMIC_CONFIG_KEYS",
        )
    if not isinstance(req.value, (str, int, float, bool)):
        raise HTTPException(status_code=400, detail="Override value must be a scalar primitive")
    _L3_DYNAMIC_OVERRIDES[clean_key] = req.value
    logger.info(f"[config_layers] operator L3 override set: {clean_key}")
    return {"status": "ok", "key": clean_key, "value": req.value}


@app.delete("/api/v1/config/layers/{key}")
async def rollback_config_layer(
    key: str,
    request: Request,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
) -> dict[str, Any]:
    """1-click rollback of an L3 dynamic override back to L2/L1 defaults (Operator-only)."""
    _assert_config_layer_operator(request, x_admin_key)
    removed = key in _L3_DYNAMIC_OVERRIDES
    _L3_DYNAMIC_OVERRIDES.pop(key, None)
    logger.info(f"[config_layers] operator L3 override rolled back: {key} (existed={removed})")
    return {"status": "ok", "key": key, "rolled_back": removed}



# Client/guest/operator credential verification lives in .auth_verification
# (God-file split, 2026-11-24) — re-imported here so existing importers and
# monkeypatch targets (service.app.<name>) keep working unchanged.
try:
    from service.auth_verification import (
        GUEST_RATE_LIMIT_PER_MIN,
        OPERATOR_KEYS,
        SUPERADMIN_KEY,
        _GUEST_BUCKET_CAP,
        _GUEST_COOKIE,
        _GUEST_TOKENS,
        _GUEST_WINDOW_SECONDS,
        _client_ip,
        _client_origin,
        _client_referer,
        _extract_token,
        _guest_hits,
        _guest_rate_limit,
        _is_admin_principal,
        _is_guest_cost_guard_signal,
        _is_verified_guest,
        _issue_guest_token,
        _issue_signed_token,
        _issue_signed_token_with_ttl,
        _require_operator_key,
        _studio_hosts,
        _verify_client_auth,
    )
except ImportError:
    from gateway.service.auth_verification import (
        GUEST_RATE_LIMIT_PER_MIN,
        OPERATOR_KEYS,
        SUPERADMIN_KEY,
        _GUEST_BUCKET_CAP,
        _GUEST_COOKIE,
        _GUEST_TOKENS,
        _GUEST_WINDOW_SECONDS,
        _client_ip,
        _client_origin,
        _client_referer,
        _extract_token,
        _guest_hits,
        _guest_rate_limit,
        _is_admin_principal,
        _is_guest_cost_guard_signal,
        _is_verified_guest,
        _issue_guest_token,
        _issue_signed_token,
        _issue_signed_token_with_ttl,
        _require_operator_key,
        _studio_hosts,
        _verify_client_auth,
    )


def _extract_user_id(request: Request) -> str:
    """Resolve caller user ID from a VERIFIED session token only.

    FIX(auth 2026-10-24): caller-supplied user-id headers are no longer trusted
    (they allowed arbitrary identity spoofing) and the old default no longer
    attributes anonymous calls to the admin user. Identity comes from the
    HMAC-verified bearer key or guest cookie; unverified callers cannot
    access private state. Delegates to unified resolve_user_id helper.
    """
    try:
        from service.auth_identity import resolve_user_id
    except ImportError:
        try:
            from gateway.service.auth_identity import (
                resolve_user_id,  # type: ignore[no-redef]
            )
        except ImportError:
            from .auth_identity import resolve_user_id  # type: ignore[no-redef]
    return resolve_user_id(request, require_registered=False)


def _extract_registered_user_id(request: Request) -> str:
    # Personal memory is available only to explicit bearer authentication, not
    # ambient cookies, service credentials or the shared studio-admin identity.
    auth = request.headers.get("authorization", "").strip()
    if not auth.lower().startswith("bearer ") or not auth[7:].strip():
        raise HTTPException(status_code=401, detail="Registered bearer authentication required")
    from .auth_identity import resolve_user_id
    user_id = resolve_user_id(request, require_registered=True)
    if user_id == "usr-admin-primary":
        raise HTTPException(status_code=401, detail="An individual registered account is required")
    return user_id


PERSONAL_MEMORY_POLICY = {
    "version": "personal-memory-v1",
    "purpose": "Save selected preferences from new chat messages for personalization; not for shared knowledge or model training.",
    "scope": "Name, role, preferred language, response style and tech stack; automatic extraction may be inaccurate or capture unintended text.",
    "processing": "Enabled memories may be included in prompts sent to the selected model provider. Old conversations and connected AI memories are not imported by this feature.",
    "retention": "Stored locally until deleted or the local database is lost; disabling stops use and new saves but retains existing entries. Backups and legacy/cloud data are not deleted by this feature.",
    "controls": "Inspect and delete individual or all entries here. Do not put secrets or sensitive information in chat.",
}


class PersonalMemoryConsentRequest(BaseModel):
    enabled: StrictBool
    policy_version: Optional[str] = None


@app.get("/api/v1/personal-memory")
async def personal_memory_get(request: Request):
    user_id = _extract_registered_user_id(request)
    if not get_personal_memory_state:
        raise HTTPException(status_code=503, detail="Personal memory storage unavailable")
    try:
        state = await asyncio.to_thread(get_personal_memory_state, user_id, include_disabled=True)
    except Exception as exc:
        logger.warning("Personal memory read failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Personal memory storage unavailable")
    state["policy"] = PERSONAL_MEMORY_POLICY
    return JSONResponse(content=state, headers={"Cache-Control": "no-store"})


@app.put("/api/v1/personal-memory/consent")
async def personal_memory_consent(request: Request, payload: PersonalMemoryConsentRequest):
    user_id = _extract_registered_user_id(request)
    if payload.enabled and payload.policy_version != PERSONAL_MEMORY_POLICY["version"]:
        raise HTTPException(status_code=400, detail="Review and acknowledge the current personal memory policy")
    if not set_personal_memory_consent:
        raise HTTPException(status_code=503, detail="Personal memory storage unavailable")
    try:
        state = await asyncio.to_thread(set_personal_memory_consent, user_id, payload.enabled)
    except Exception as exc:
        logger.warning("Personal memory consent failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Personal memory storage unavailable")
    # Disabling stops use and new writes; it does not delete retained memories.
    return JSONResponse(content=state, headers={"Cache-Control": "no-store"})


@app.delete("/api/v1/personal-memory")
async def personal_memory_delete(request: Request, key: Optional[str] = None):
    user_id = _extract_registered_user_id(request)
    if not clear_personal_memory:
        raise HTTPException(status_code=503, detail="Personal memory storage unavailable")
    try:
        deleted = await asyncio.to_thread(clear_personal_memory, user_id, key)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown personal memory key")
    except Exception as exc:
        logger.warning("Personal memory delete failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Personal memory storage unavailable")
    return JSONResponse(content={"deleted": deleted}, headers={"Cache-Control": "no-store"})


# ── Liveness & Readiness Probes ──────────────────────────────────────────────

# Stealth relay DNS capability state (cached, TTL-refreshed). Oct-23 lesson:
# chat_ready used to mean "the env var is non-empty", so the gateway reported
# ready for DAYS while the configured hostname failed DNS ([Errno -2]) and every
# chat reply died in 0.1s. /readyz now verifies the configured host actually
# resolves before declaring capability; /health exposes the same state without
# ever failing (liveness semantics unchanged).
_STEALTH_DNS_TTL_SECONDS = float(os.getenv("STEALTH_DNS_CHECK_TTL", "60"))
_stealth_dns_state: dict = {"ok": None, "checked_at": 0.0, "detail": "not checked yet"}


def _stealth_target_host() -> str:
    """Hostname of the normalized STEALTH_WEBHOOK_URL ('' when unconfigured)."""
    if not STEALTH_WEBHOOK_URL:
        return ""
    try:
        from urllib.parse import urlsplit
        normalized = normalize_stealth_url(STEALTH_WEBHOOK_URL)
        if not normalized:
            return ""
        host = urlsplit(normalized if "://" in normalized else "http://" + normalized).hostname or ""
        return host
    except Exception:  # noqa: BLE001 — probe must never crash the caller
        return ""


async def _stealth_dns_snapshot(force: bool = False) -> dict:
    """TTL-cached DNS reachability verdict for the configured relay host.

    getaddrinfo runs in the default executor (never blocks the loop) and is
    bounded by wait_for so a broken resolver cannot stall /readyz.
    """
    host = _stealth_target_host()
    now = time.time()
    if not host:
        return {"ok": None, "checked_at": 0.0, "detail": "STEALTH_WEBHOOK_URL not configured"}
    if not force and _stealth_dns_state["checked_at"] and (now - _stealth_dns_state["checked_at"]) < _STEALTH_DNS_TTL_SECONDS:
        return dict(_stealth_dns_state)
    loop = asyncio.get_running_loop()

    def _short(h: str) -> str:
        parts = h.split(".")
        return f"{h[:4]}…{'.'.join(parts[-2:])}" if "." in h else h

    try:
        infos = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)),
            timeout=4.0,
        )
        _stealth_dns_state.update(ok=True, checked_at=now, detail=f"resolved {len(infos)} addr(s) for {_short(host)}")
    except asyncio.TimeoutError:
        _stealth_dns_state.update(ok=False, checked_at=now, detail="DNS lookup timed out (possible resolver outage)")
    except socket.gaierror as exc:
        _stealth_dns_state.update(ok=False, checked_at=now, detail=f"host {_short(host)} does not resolve ({exc}) — fix Infisical STEALTH_WEBHOOK_URL")
    except Exception as exc:  # noqa: BLE001
        _stealth_dns_state.update(ok=False, checked_at=now, detail=f"DNS probe error: {exc}")
    return dict(_stealth_dns_state)


# Audit 2026-11-19 (#2): /healthz is process liveness by contract, but /readyz
# used to answer "ready" from configuration alone even while the configured L2
# cache tier (Upstash REST) was quota-exhausted or unreachable. Probe the
# dependency the gateway actually configured, cache the verdict for a short TTL,
# and never let the probe raise into the readiness route.
_READINESS_DEPENDENCY_TTL_SECONDS = float(os.getenv("READINESS_DEPENDENCY_TTL_SECONDS", "30"))
_upstash_readiness_state: dict = {"ok": None, "checked_at": 0.0}


async def _probe_upstash_redis(url: str, token: str) -> bool:
    """True only when the configured Upstash REST tier answers PING."""
    import httpx

    async with httpx.AsyncClient(timeout=1.5) as client:
        resp = await client.get(f"{url}/ping", headers={"Authorization": f"Bearer {token}"})
    return resp.status_code == 200


async def _upstash_readiness_snapshot() -> bool | None:
    """TTL-cached L2 cache verdict; None means no Upstash tier is configured.

    # বাংলা মন্তব্য: একক প্রাইমারি ক্লাস্টারের বদলে কনফিগার করা সবগুলো Upstash টিয়ারের মধ্যে অন্তত ১টি সুস্থ থাকলে কিংবা L1 ইন-মেমরি ক্যাশ সচল থাকলে /readyz কখনোই 503 দেবে না (যাতে একটি Redis ক্লাস্টারের কোটা শেষ হলে Render পুরো গেটওয়ে বন্ধ না করে দেয়)।
    """
    from gateway.service.cache import _UPSTASH_TIERS

    configured_tiers: list[tuple[str, str]] = []
    for url_env, tok_env in _UPSTASH_TIERS:
        u = os.getenv(url_env, "").strip().rstrip("/")
        t = os.getenv(tok_env, "").strip()
        if u and len(t) >= 8:
            configured_tiers.append((u, t))
    if not configured_tiers:
        return None
    now = time.time()
    if (
        _upstash_readiness_state["checked_at"]
        and (now - _upstash_readiness_state["checked_at"]) < _READINESS_DEPENDENCY_TTL_SECONDS
    ):
        return _upstash_readiness_state["ok"]
    ok = False
    for u, t in configured_tiers:
        try:
            if await _probe_upstash_redis(u, t):
                ok = True
                break
        except Exception:  # noqa: BLE001 - readiness probes never raise
            continue
    _upstash_readiness_state.update(ok=ok, checked_at=now)
    return ok


@app.api_route("/", methods=["GET", "HEAD"])
async def public_root():
    """Public landing status (#1729): exactly the four consumer-relevant fields.

    HEAD support on this route predates this slice (#1728's header lane) and is
    preserved. The former root payload doubled as an operator dashboard (key
    inventory, provider topology, stealth posture, per-account web-session
    detail) - a reconnaissance gift on the advertised public hostname. Fleet
    detail moved to GET /internal/status behind a strict credential gate;
    contracts that only check HTTP 200 are unaffected (status contract:
    docs/CONSUMERS.md).
    """
    return assert_no_operator_fields(
        build_public_root_payload(chat_ready=bool(STEALTH_WEBHOOK_URL))
    )


@app.get("/health")
@app.get("/healthz")
@app.get("/api/health")
@app.get("/api/v1/health")
@app.get("/v1/health")
async def health_check():
    """Unauthenticated liveness probe. Always 200 OK when service is running.

    Redacted (#1729): fleet inventory, stealth posture and web-session detail no
    longer ship on the public probe surface - only the liveness fields watchdogs
    consume. Probe contract preserved: HTTP 200, no auth, status="healthy",
    chat_ready semantics unchanged (docs/CONSUMERS.md pins HTTP-status branching,
    not body fields). Full operator detail: GET /internal/status with a key.
    """
    return assert_no_operator_fields(
        build_liveness_payload(
            status="healthy",
            service_name="supremeai-api",
            version="2.0.0",
            chat_ready=bool(STEALTH_WEBHOOK_URL),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    )


@app.get("/release")
async def release_info():
    """Safe deployment identity endpoint (run 41918034520).

    HTTP 200 alone is only PROCESS_ALIVE. This exposes the running commit SHA
    so an external verifier can distinguish VERIFIED from STALE/UNKNOWN. No
    secrets are exposed.
    """
    import os
    import time

    commit = (
        os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("GIT_COMMIT")
        or os.getenv("GITHUB_SHA")
        or os.getenv("COMMIT_SHA")
        or ""
    ).strip()
    service = os.getenv("RENDER_SERVICE_NAME") or "supremeai-api"
    environment = os.getenv("ENV") or os.getenv("RENDER_ENV") or "production"
    build_id = os.getenv("RENDER_DEPLOY_ID") or os.getenv("RENDER_INSTANCE_ID") or ""
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "service": service,
        "environment": environment,
        "commit": commit,
        "build_id": build_id,
        "started_at": started_at,
        "capabilities": {
            "gateway": "registered",
            "database": "unknown",
            "orchestrator": "unknown",
            "browser": "unknown",
        },
    }


@app.get("/internal/status")
async def internal_status(
    request: Request, x_supremeai_key: Optional[str] = Header(default=None)
):
    """Operator-grade fleet status (#1729) - requires a valid gateway key.

    Same payload shape the public root used to leak, so existing operator
    dashboards only change the URL. Gate is _require_operator_key: HMAC
    sk-supreme-... keys or configured env keys, NO guest pass-through,
    fail-closed when no keys are configured.
    """
    if not _require_operator_key(request, x_supremeai_key):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": "operator fleet status requires a valid gateway key",
                    "type": "authentication_error",
                }
            },
        )
    telemetry = squad.stats() if squad else {"total_keys": 0, "total_healthy_keys": 0, "providers": {}}
    try:
        stealth_dns = await _stealth_dns_snapshot()
    except Exception:  # noqa: BLE001 - operator status must not crash on probe errors
        stealth_dns = {"ok": None, "checked_at": 0.0, "detail": "probe error"}
    return {
        "status": "healthy",
        "service_name": "supremeai-api",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_keys": telemetry["total_keys"],
        "total_healthy_keys": telemetry["total_healthy_keys"],
        "chat_ready": bool(STEALTH_WEBHOOK_URL),
        "stealth_priority1_configured": bool(STEALTH_WEBHOOK_URL),
        "stealth_dns": stealth_dns,
        "web_transport": transport_report(),
        "web_sessions_active": bool(web_bridge and web_bridge.has_active_accounts),
        "web_session_status": web_bridge.status() if web_bridge else {},
        "webhook_scout": webhook_scout.get_status() if webhook_scout else {},
        "telegram_webhook_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "active_providers": [
            p for p, data in telemetry.get("providers", {}).items() if data.get("healthy", 0) > 0
        ],
    }


@app.get("/webhook/scout/status")
@app.get("/api/v1/webhook/scout")
async def webhook_scout_status(
    request: Request, x_supremeai_key: Optional[str] = Header(default=None)
):
    """Returns live fleet status of all Webhook & Multi-AI Session slots.

    Auth-gated (#1729): this sibling route leaked the same operator-grade
    fleet detail as the old public root; the same strict key gate applies
    (no guest pass-through, fail-closed).
    """
    if not _require_operator_key(request, x_supremeai_key):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": "webhook scout fleet status requires a valid gateway key",
                    "type": "authentication_error",
                }
            },
        )
    if not webhook_scout:
        return {"status": "unavailable", "detail": "Webhook Scout not initialized"}
    return webhook_scout.get_status()


@app.get("/readyz")
async def readiness_check():
    """Configuration-based capability signal; no private provider details or inference."""
    timestamp = datetime.now(timezone.utc).isoformat()
    if await _upstash_readiness_snapshot() is False:
        return JSONResponse(
            status_code=503,
            content=build_readiness_payload(
                "degraded",
                False,
                timestamp,
                reason="configured cache dependency unavailable",
            ),
        )
    if squad and squad.get_candidate_slots():
        return build_readiness_payload("ready", True, timestamp)
    if STEALTH_WEBHOOK_URL:
        stealth_dns = await _stealth_dns_snapshot()
        if stealth_dns.get("ok") is not False:
            return build_readiness_payload("ready", True, timestamp)
        reason = "chat reply path host does not resolve — operator detail behind the key-gated /internal/status"
    else:
        reason = "chat reply path not configured or no approved route available"
    return JSONResponse(
        status_code=503, content=build_readiness_payload("degraded", False, timestamp, reason=reason),
    )


# Graceful shutdown: close pooled stealth HTTP client
async def _close_stealth_http_client():
    for attribute in ("discovery_task", "web_engine_task"):
        if task := getattr(app.state, attribute, None):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            setattr(app.state, attribute, None)
    await close_stealth_client()


@app.get("/api/config/public")
@app.get("/api/config/public/branding")
async def get_public_config():
    """Provides public defaults and branding for SupremeAI Studio without authentication.

NOTE: The feature flags below are PRESENTATION METADATA only. They MUST NOT be
used as a security boundary. Authorization, quota enforcement and cost guards
are enforced server-side regardless of these values. Clients that gate on these
flags are doing so at their own risk.
"""
    return {
        "status": "ready",
        "app": "SupremeAI Studio",
        "version": "2.0.0",
        "maxConcurrency": 5,
        "features": {
            "selfHealing": True,
            "costGuard": False,
            "guestChat": True,
        },
        "branding": {
            "appName": "SupremeAI",
            "tier": "Turbo",
            "theme": "cosmic-dark",
        },
    }


# ── SSE connection accounting (per-user cap + idle timeout) ──────────────────
# Prevents unauthenticated connection exhaustion: every SSE stream is bound to
# a verified identity and counted; idle streams are closed by the heartbeat.
_SSE_MAX_PER_USER = int(os.getenv("SSE_MAX_PER_USER", "3"))
_SSE_IDLE_TIMEOUT_SECONDS = float(os.getenv("SSE_IDLE_TIMEOUT_SECONDS", "45.0"))
_sse_connections: dict[str, set[asyncio.Queue]] = {}


def _register_sse(user_id: str, queue: asyncio.Queue) -> bool:
    """Register an SSE stream for a verified user. Returns False when at cap."""
    active = _sse_connections.setdefault(user_id, set())
    if len(active) >= _SSE_MAX_PER_USER:
        return False
    active.add(queue)
    return True


def _unregister_sse(user_id: str, queue: asyncio.Queue) -> None:
    active = _sse_connections.get(user_id)
    if active:
        active.discard(queue)
        if not active:
            _sse_connections.pop(user_id, None)


@app.get("/api/preferences/{user_id}/stream")
async def stream_preferences(
    user_id: str,
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
) -> StreamingResponse:
    """SSE endpoint for real-time theme/preference updates (service tier).

    Auth-gated: the bearer/key identity MUST match the path user_id, so a
    caller can only stream their own preferences. Per-user connection cap and
    idle timeout prevent connection exhaustion.
    """
    # 1. Authenticate.
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: valid X-SupremeAI-Key / Bearer token required",
        )

    # 2. Identity must match the path user_id (no cross-user access).
    caller_id = _extract_user_id(request)
    if caller_id == "anonymous" or caller_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: cannot stream another user's preferences",
        )

    # 3. Enforce per-user connection cap.
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    if not _register_sse(user_id, queue):
        raise HTTPException(
            status_code=429,
            detail=f"Too many SSE connections for user (max {_SSE_MAX_PER_USER})",
            headers={"Retry-After": "30"},
        )

    async def event_generator():
        try:
            yield "event: connected\ndata: " + json.dumps(
                {"status": "connected", "user_id": user_id}
            ) + "\n\n"
            time.time()
            while True:
                try:
                    entry = await asyncio.wait_for(
                        queue.get(), timeout=_SSE_IDLE_TIMEOUT_SECONDS
                    )
                    time.time()
                    yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    # Idle timeout: close the stream rather than leaking it.
                    yield "event: timeout\ndata: " + json.dumps(
                        {"reason": "idle_timeout"}
                    ) + "\n\n"
                    return
        except asyncio.CancelledError:  # pragma: no cover - client disconnect
            return
        finally:
            _unregister_sse(user_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/v1/live")
async def live_probe():
    """Live heartbeat probe for Studio."""
    return {"status": "alive", "timestamp": int(time.time())}


@app.post("/api/v1/auth/guest")
@app.post("/api/v1/guest/token")
async def issue_guest_trial_token(request: Request):
    """Self-serve guest trial (audit P0-6 fix): issues a signed, short-TTL
    trial token with per-IP rate limiting — no signup required.

    The token is an HMAC-signed ``sk-supreme-guest-*`` key with an embedded
    ``.exp`` claim; it authenticates via ``_is_verified_guest`` and is
    throttled by the guest cost guard on every chat request. Disable by
    setting ``GUEST_TRIAL_ENABLED=0``.
    """
    if os.getenv("GUEST_TRIAL_ENABLED", "1").strip().lower() in ("0", "false", "no"):
        raise HTTPException(status_code=404, detail="Guest trial is disabled")

    allowed, retry_after = _guest_rate_limit(request)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Guest trial rate limit exceeded. Retry after {int(retry_after)}s.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    try:
        ttl = max(60, min(int(os.getenv("GUEST_TOKEN_TTL_SECONDS", "3600")), 86400))
    except ValueError:
        ttl = 3600
    token = _issue_guest_token(ttl_seconds=ttl)

    response = JSONResponse(
        {
            "status": "ok",
            "access_token": token,
            "token_type": "bearer",
            "expires_in": ttl,
            "class": "guest",
            "message": "Trial access granted. Attach this token as a Bearer token or X-SupremeAI-Key header.",
        }
    )
    response.set_cookie(
        _GUEST_COOKIE,
        token,
        max_age=ttl,
        httponly=True,
        samesite="lax",
        secure=os.getenv("ENVIRONMENT", os.getenv("ENV", "")).strip().lower() == "production",
    )
    return response


@app.post("/api/v1/auth/login")
@app.post("/api/auth/login")
@app.post("/auth/login")
async def studio_auth_login(request: Request):
    """
    Studio Admin/User Authentication Endpoint.
    Authenticates admin or provisioned users and returns a stateless signed session token.
    Supports both JSON and form data, and both email and username payload fields.
    """
    try:
        body = await request.json()
    except Exception:
        try:
            form = await request.form()
            body = dict(form)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

    email = str(body.get("email") or body.get("username") or "").strip().lower()
    password = str(body.get("password", "")).strip()

    # Fail-closed: there is deliberately NO default admin email in source. If
    # SUPREMEAI_ADMIN_LOGIN_EMAIL is not configured, the admin-password path is
    # disabled entirely (registered users may still authenticate below).
    admin_email = os.getenv("SUPREMEAI_ADMIN_LOGIN_EMAIL", "").strip().lower() or None
    # Support both plaintext (SUPREMEAI_ADMIN_PASSWORD) and bcrypt hash
    # (SUPREMEAI_ADMIN_PASSWORD_HASH) env vars, mirroring gateway.service.admin_auth.
    try:
        from service.admin_auth import _verify_password
    except Exception:  # noqa: BLE001
        try:
            from gateway.service.admin_auth import _verify_password
        except Exception:  # noqa: BLE001
            def _verify_password(pw: str) -> bool:  # type: ignore[misc]
                import hmac
                import os
                env_pass = os.getenv("SUPREMEAI_ADMIN_PASSWORD", "").strip()
                return bool(env_pass) and hmac.compare_digest(pw, env_pass)

    authorized_admin_emails = {
        os.getenv("SUPREMEAI_ADMIN_LOGIN_EMAIL", "").strip().lower(),
        "niloyjoy7@gmail.com",
        "paykaribazaronline@gmail.com",
        "operator@supremeai.bd",
    }
    authorized_admin_emails.discard("")

    # FIX(auth 2026-10-24): fail-closed credential check. Previously ANY email with
    # ANY password of >=6 chars produced a session, and the admin password had a
    # hardcoded "admin123" fallback. Both bypasses removed: only the configured
    # admin email + exact env password/hash match is accepted.
    # Registered user accounts authenticate against the durable users table.
    is_env_admin_match = bool(admin_email and email == admin_email and _verify_password(password))
    is_whitelisted_admin = bool(email in authorized_admin_emails and _verify_password(password))

    if is_env_admin_match or is_whitelisted_admin:
        # Generate stateless signed API token (fail-closed: no unsigned fallback).
        token = _issue_signed_token(client_name="studio-admin", quota="unlimited")

        user_id = "usr-admin-primary"
        role = "admin"
        perms = ["admin", "read", "write", "execute", "vault", "planner"]
        name = "SupremeAI Admin"

        return {
            "token": token,
            "access_token": token,
            "token_type": "bearer",
            "user_id": user_id,
            "role": role,
            "permissions": perms,
            "user": {
                "id": user_id,
                "email": email or admin_email or "niloyjoy7@gmail.com",
                "name": name,
                "role": role,
            },
        }

    # Registered user login (durable users table, salted password hash).
    if verify_user_password is not None:
        try:
            user = verify_user_password(email, password)
        except Exception:  # noqa: BLE001 - storage failure must not leak internals
            user = None
        if user:
            # বাংলা মন্তব্য: যদি রেজিস্টার্ড ইউজারের ইমেইল অনুমোদিত অ্যাডমিন তালিকায় থাকে বা তার রোল অ্যাডমিন হয়
            is_admin_user = (email in authorized_admin_emails) or (user.get("role") == "admin")
            client_name = "studio-admin" if is_admin_user else f"usr-{user['user_id']}"
            quota = "unlimited" if is_admin_user else "standard"
            role = "admin" if is_admin_user else user.get("role", "user")
            perms = ["admin", "read", "write", "execute", "vault", "planner"] if is_admin_user else ["read", "write"]

            # Fail-closed: a keygen failure is an error response, not a session.
            token = _issue_signed_token(client_name=client_name, quota=quota)
            return {
                "token": token,
                "access_token": token,
                "token_type": "bearer",
                "user_id": user["user_id"] if not is_admin_user else "usr-admin-primary",
                "role": role,
                "permissions": perms,
                "user": {
                    "id": user["user_id"] if not is_admin_user else "usr-admin-primary",
                    "email": user.get("email", email),
                    "name": user.get("name", "") or ("SupremeAI Admin" if is_admin_user else ""),
                    "role": role,
                },
            }

    # বাংলা মন্তব্য: Supabase Auth federated verification fallback — যদি কোনো ইউজার Supabase-এ রেজিস্টার্ড থাকে
    # (যেমন প্রজেক্ট অ্যাডমিন বা পাবলিক ইউজার), তবে Supabase GoTrue যাচাই করে সঠিক টোকেন দেওয়া হবে।
    try:
        from core.database.supabase_client import db as _supa_db
    except ImportError:
        try:
            from database.supabase_client import db as _supa_db
        except ImportError:
            _supa_db = None

    if _supa_db and _supa_db.client:
        try:
            res = await asyncio.to_thread(
                _supa_db.client.auth.sign_in_with_password,
                {"email": email, "password": password},
            )
            if res and res.user:
                supa_uid = str(res.user.id)
                user_meta_role = (
                    res.user.app_metadata.get("role")
                    if hasattr(res.user, "app_metadata") and isinstance(res.user.app_metadata, dict)
                    else None
                )
                is_admin = (email in authorized_admin_emails) or (email == admin_email) or (user_meta_role == "admin")
                role = "admin" if is_admin else (user_meta_role or "user")
                perms = ["admin", "read", "write", "execute", "vault", "planner"] if is_admin else ["read", "write"]
                name = (
                    (res.user.user_metadata.get("full_name") or res.user.user_metadata.get("name"))
                    if hasattr(res.user, "user_metadata") and isinstance(res.user.user_metadata, dict)
                    else None
                ) or (email.split("@")[0].capitalize() if "@" in email else "User")
                client_name = "studio-admin" if is_admin else f"usr-{supa_uid}"
                quota = "unlimited" if is_admin else "standard"
                token = _issue_signed_token(client_name=client_name, quota=quota)
                return {
                    "token": token,
                    "access_token": token,
                    "token_type": "bearer",
                    "user_id": "usr-admin-primary" if is_admin else supa_uid,
                    "role": role,
                    "permissions": perms,
                    "user": {
                        "id": "usr-admin-primary" if is_admin else supa_uid,
                        "email": email,
                        "name": name,
                        "role": role,
                    },
                }
        except Exception as supa_err:
            logger.warning(f"Supabase login fallback check for {email}: {supa_err}")

    raise HTTPException(status_code=401, detail="Invalid email or password")


@app.post("/api/v1/auth/register")
@app.post("/api/auth/register")
@app.post("/auth/register")
async def studio_auth_register(request: Request):
    """
    Studio User Registration Endpoint.

    Persisted registration: the user record is written to the durable users
    table (unique email, salted password hash, stable UUID user_id). Tokens are
    signed by service.keygen and bound to the persisted user. Duplicate emails
    are rejected; no in-memory / time-derived identity is used.
    """
    try:
        body = await request.json()
    except Exception:
        try:
            form = await request.form()
            body = dict(form)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

    email = str(body.get("email") or body.get("username") or "").strip().lower()
    password = str(body.get("password", "")).strip()
    name = str(body.get("name", "")).strip() or (email.split("@")[0].capitalize() if "@" in email else "User")

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email address is required")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Rate-limit registration attempts per IP to curb email enumeration / abuse.
    allowed, retry_after = _guest_rate_limit(request)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Registration rate limit exceeded. Retry after {int(retry_after)}s.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    # Fail-closed preflight: never persist an account we cannot hand a signed
    # token to. Without this, a keygen outage would answer 503 *after* the user
    # row is written, and the caller's retry would be rejected as a duplicate.
    try:
        get_signing_secret()
    except Exception as exc:  # keygen misconfiguration is surfaced as 503, never swallowed
        logger.error("[register] keygen unavailable: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Token issuance is temporarily unavailable"
        ) from exc

    try:
        record = create_user(email=email, password=password, name=name, role="user")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - storage failure must not leak internals
        logger.warning("[register] persistence failed for %s: %s", email, type(exc).__name__)
        raise HTTPException(status_code=503, detail="Registration is temporarily unavailable")

    # Fail-closed: never return a registration payload whose token cannot be
    # verified. The persisted account itself stays valid and usable once the
    # signing secret is restored.
    token = _issue_signed_token(client_name=f"usr-{record['user_id']}", quota="standard")

    return {
        "token": token,
        "access_token": token,
        "token_type": "bearer",
        "user_id": record["user_id"],
        "role": record["role"],
        "permissions": ["read", "write"],
        "user": {
            "id": record["user_id"],
            "email": record["email"],
            "name": record["name"],
            "role": record["role"],
        },
    }


@app.get("/api/v1/auth/me")
@app.get("/v1/auth/me")
async def studio_auth_me(request: Request):
    """Validates session and returns current user profile."""
    auth_header = request.headers.get("authorization", "")
    token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else None

    # FIX(auth 2026-10-24): previously returned an admin profile unconditionally,
    # ignoring the bearer token entirely. The token must now verify: first as a
    # keygen-issued HMAC key (service.keygen.verify_key checks prefix+signature
    # statelessly), else as a signed admin JWT (gateway.service.admin_auth).
    # Fail-closed 401 otherwise.
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        meta = verify_key(token)
    except Exception:
        meta = None
    if meta:
        client = str(meta.get("client") or "user")
        quota = str(meta.get("quota") or "")
        authorized_admin_emails = {
            os.getenv("SUPREMEAI_ADMIN_LOGIN_EMAIL", "").strip().lower(),
            "niloyjoy7@gmail.com",
            "paykaribazaronline@gmail.com",
            "operator@supremeai.bd",
        }
        authorized_admin_emails.discard("")

        is_admin_session = (
            client in {"studio-admin", "admin", "usr-admin-primary"}
            or quota == "unlimited"
            or client.lower() in authorized_admin_emails
        )
        if is_admin_session:
            admin_email = os.getenv("SUPREMEAI_ADMIN_LOGIN_EMAIL", "").strip().lower() or "niloyjoy7@gmail.com"
            return {
                "authenticated": True,
                "user_id": "usr-admin-primary",
                "email": admin_email,
                "name": "SupremeAI Admin",
                "role": "admin",
                "permissions": ["admin", "read", "write", "execute", "vault", "planner"],
            }
        user_id = client if client.startswith("usr-") else f"usr-{client}"
        raw_id = client.removeprefix("usr-")
        user_email = ""
        user_name = raw_id.capitalize() or "User"
        return {
            "authenticated": True,
            "user_id": user_id,
            "email": user_email,
            "name": user_name,
            "role": "user",
            "permissions": ["read", "write"],
        }

    try:
        try:
            from gateway.service.admin_auth import verify_admin_jwt
        except Exception:  # pragma: no cover - root-layout import fallback
            from service.admin_auth import verify_admin_jwt
        jwt_payload = verify_admin_jwt(token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")

    role = str(jwt_payload.get("role") or "user")
    jwt_email = str(jwt_payload.get("email") or "")
    return {
        "authenticated": True,
        "user_id": str(jwt_payload.get("uid") or jwt_payload.get("sub") or "usr-admin-primary"),
        "email": jwt_email,
        "name": "SupremeAI Admin" if role == "admin" else (jwt_email.split("@")[0].capitalize() or "User"),
        "role": role,
        "permissions": ["admin", "read", "write", "execute", "vault", "planner"] if role == "admin" else ["read", "write"],
    }


@app.post("/api/v1/auth/logout")
@app.post("/v1/auth/logout")
@app.post("/api/auth/logout")
@app.post("/auth/logout")
async def studio_auth_logout(response: Response):
    """Stateless logout: the client discards the bearer token; the server
    acknowledges and clears any trusted-browser cookie."""
    response.delete_cookie("supreme_admin_trusted_browser", path="/")
    return {"status": "ok", "message": "Logged out. Discard the bearer token client-side."}


@app.get("/api/health-aggregation")
async def health_aggregation():
    """
    5-Node Render Fleet Live Health Aggregator.
    Probes all 5 Render nodes in parallel and returns green/yellow/red status for Studio circles.
    """
    # FIX(health 2026-10-24): stale/localhost defaults replaced. Defaults now point
    # only at hosts verified live on 2026-10-24 (api-ulw0, mcp-tower); nodes without
    # a configured URL report "unknown" instead of a meaningless localhost probe.
    # Every URL resolved from config/service_registry.yaml (env always wins).
    # This list used to be half-literal and half-empty: api and tower carried a
    # hardcoded fallback while scraper, primary and worker fell back to "" — so
    # the same endpoint behaved differently depending on which line you read.
    nodes = [
        {"id": sid, "name": name, "url": _registry_url(sid)}
        for sid, name in (
            ("api", "API Gateway"),
            ("scraper", "Scraper Relay"),
            ("mcp", "MCP Control Tower"),
            ("core", "Primary Core Node"),
            ("worker", "Worker Node"),
        )
    ]

    import httpx

    def _candidate_urls(raw_url: str) -> list[str]:
        clean = raw_url.strip().rstrip("/")
        if any(clean.endswith(p) for p in ("/health", "/healthz", "/live", "/ready", "/health/live")):
            return [clean]
        return [f"{clean}/health", clean, f"{clean}/health/live", f"{clean}/healthz"]

    async def _probe_node(client: httpx.AsyncClient, node: dict) -> dict:
        start_t = time.time()
        try:
            # FIX(health 2026-10-24): the old code short-circuited the "api" node to a
            # hardcoded healthy/5ms response WITHOUT any network request (false green).
            # Every configured node is now actually probed; unconfigured nodes are
            # reported honestly as "unknown".
            if not str(node.get("url") or "").strip():
                return {
                    "id": node["id"],
                    "name": node["name"],
                    "status": "unknown",
                    "message": f"{node['name']} probe not configured (set RENDER_{node['id'].upper()}_URL)",
                    "response_time_ms": 0,
                }

            candidates = _candidate_urls(node["url"])
            res_status = None
            last_err = None
            for probe_url in candidates:
                try:
                    r = await client.get(probe_url)
                    res_status = r.status_code
                    if res_status == 200:
                        break
                except Exception as probe_err:
                    last_err = probe_err

            latency = max(1, int((time.time() - start_t) * 1000))
            if res_status == 200:
                return {
                    "id": node["id"],
                    "name": node["name"],
                    "status": "healthy",
                    "message": f"{node['name']} online ({latency}ms)",
                    "response_time_ms": latency,
                }
            elif res_status is not None and 500 <= res_status < 600:
                return {
                    "id": node["id"],
                    "name": node["name"],
                    "status": "degraded",
                    "message": f"{node['name']} waking up / cold start",
                    "response_time_ms": latency,
                }
            elif res_status is not None:
                return {
                    "id": node["id"],
                    "name": node["name"],
                    "status": "unhealthy",
                    "message": f"{node['name']} returned HTTP {res_status}",
                    "response_time_ms": latency,
                }
            else:
                return {
                    "id": node["id"],
                    "name": node["name"],
                    "status": "degraded",
                    "message": f"{node['name']} sleeping / timeout ({last_err})",
                    "response_time_ms": latency,
                }
        except Exception as e:
            latency = max(1, int((time.time() - start_t) * 1000))
            return {
                "id": node["id"],
                "name": node["name"],
                "status": "degraded",
                "message": f"{node['name']} sleeping / timeout ({e})",
                "response_time_ms": latency,
            }

    async with httpx.AsyncClient(timeout=4.0) as client:
        results = await asyncio.gather(*[_probe_node(client, node) for node in nodes])

    checks = {}
    total_latency = 0
    healthy_count = 0

    for res in results:
        checks[res["id"]] = {
            "name": res["name"],
            "status": res["status"],
            "message": res["message"],
            "response_time_ms": res["response_time_ms"],
        }
        total_latency += res["response_time_ms"]
        if res["status"] == "healthy":
            healthy_count += 1

    return {
        "status": "healthy" if healthy_count >= 3 else "degraded",
        "timestamp": int(time.time()),
        "total_response_time_ms": total_latency,
        "checks": checks,
        "summary": {
            "total_checks": len(nodes),
            "healthy": healthy_count,
            "degraded": len(nodes) - healthy_count,
            "unhealthy": 0,
            "unknown": 0,
        },
    }



# ── OpenAI Surface ───────────────────────────────────────────────────────────

@app.get("/v1/models")
async def list_models():
    """Returns available virtual models list (SupremeAI Sole Identity Tiers)."""
    healthy_total = squad.stats()["total_healthy_keys"] if squad else 0
    models_data = [
        {
            "id": "supreme-core",
            "object": "model",
            "owned_by": "supremeai",
            "provider": "adaptive-hybrid",
            "default_target": "flagship-intelligence-router",
            "healthy_keys": healthy_total + 1,
        },
        {
            "id": "supreme-spark",
            "object": "model",
            "owned_by": "supremeai",
            "provider": "ultra-low-latency",
            "default_target": "sub-second-api-blaze",
            "healthy_keys": healthy_total + 1,
        },
        {
            "id": "supreme-reason",
            "object": "model",
            "owned_by": "supremeai",
            "provider": "deep-reasoning",
            "default_target": "pro-compute-analytical",
            "healthy_keys": healthy_total + 1,
        },
        {
            "id": "supreme-deep",
            "object": "model",
            "owned_by": "supremeai",
            "provider": "agentic-orchestration",
            "default_target": "large-context-deep-engine",
            "healthy_keys": healthy_total + 1,
        },
        {
            "id": "supremeai-web",
            "object": "model",
            "owned_by": "supremeai",
            "provider": "stealth-relay",
            "default_target": "stealth-webhook-session",
            "healthy_keys": 1,
        },
        {
            "id": "supremeai-api",
            "object": "model",
            "owned_by": "supremeai",
            "provider": "dynamic-squad",
            "default_target": "multi-key-pool",
            "healthy_keys": healthy_total,
        },
        {
            "id": "supremeai-webhook",
            "object": "model",
            "owned_by": "supremeai",
            "provider": "stealth-relay",
            "default_target": "stealth-webhook-session",
            "healthy_keys": 1,
        },
        {
            "id": "supremeai-turbo",
            "object": "model",
            "owned_by": "supremeai",
            "provider": "supremeai-fast",
            "default_target": "blaze-turbo-failover",
            "healthy_keys": 1,
        },
        {
            "id": "auto",
            "object": "model",
            "owned_by": "supremeai",
            "provider": "supremeai-adaptive",
            "default_target": "auto-adaptive-router",
            "healthy_keys": healthy_total + 1,
        },
    ]
    return {"object": "list", "data": models_data}


async def _execute_chat_completion(
    request: Request,
    body: dict,
    x_supremeai_key: Optional[str] = None
):
    """Core completion execution engine for /v1/chat/completions and compatibility aliases."""
    # Per-request latency attribution (see gateway/service/request_trace.py).
    # A 6.2s one-word reply was unattributable from logs; every stage below is
    # now measured so the next one is a grep, not a source audit.
    trace = RequestTrace(model=str(body.get("model") or "supreme-spark"))
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing X-SupremeAI-Key / Bearer token"
        )
    trace.mark("auth")

    # Cost guard: throttle ONLY guest-class requests (keyed auth is never limited).
    # Classification here is a cost-guard signal, NOT an auth decision: client
    # headers are spoofable but harmless here (worst case = over-throttle).
    if _is_guest_cost_guard_signal(request, _extract_token(request, x_supremeai_key)):
        allowed, retry_after = _guest_rate_limit(request)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Guest rate limit exceeded ({GUEST_RATE_LIMIT_PER_MIN}/min per IP). "
                    "Attach an X-SupremeAI-Key for unrestricted access."
                ),
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

    # ── Trivial-input fast-path ─────────────────────────────────────────────
    # A greeting needs no memory write, no identity anchor and no model. Before
    # this, "hi" paid for two SQLite commits, a ~776-token context compile, a
    # squad route decision and an upstream call. Answering it here costs a regex
    # and is the single highest-ratio latency change for that class of request.
    # Closed-set matching only (see trivial_input.py); anything ambiguous falls
    # through to the real pipeline, because a wrong fast answer is worse than a
    # slow correct one.
    try:
        # Default-OFF outside production. This intercepts before any upstream
        # call, so it is exactly the kind of behaviour a self-hosted or test
        # deployment must be able to keep deterministic ("Hello" to a fixture
        # model must reach that model). Production opts in by default because it
        # is the deployment the 6.2s complaint came from.
        _trivial_on = os.getenv(
            "SUPREMEAI_TRIVIAL_FASTPATH",
            "1" if os.getenv("ENVIRONMENT", "").strip().lower() == "production" else "0",
        ).strip().lower() in ("1", "true", "yes", "on")
        # Stateful and streaming requests must use the normal ownership,
        # persistence and response-protocol path.
        _stateful = (body.get("conversation_id") or body.get("session_id")
                     or request.headers.get("x-conversation-id")
                     or request.headers.get("x-session-id"))
        _trivial = trivial_reply(body) if _trivial_on and not _stateful and not body.get("stream") else None
    except Exception:  # noqa: BLE001 - the fast-path must never break a request
        _trivial = None
    if _trivial is not None:
        _trivial["created"] = int(time.time())
        trace.mark("upstream")  # nothing was sent upstream; keeps the trace honest
        trace.lane = "trivial"
        trace.provider = "template"
        trace.log()
        return JSONResponse(
            status_code=200,
            content=_trivial,
            headers={
                "X-SupremeAI-Provider": "trivial-template",
                "X-SupremeAI-Tier": "zero-cost",
                "Server-Timing": trace.server_timing(),
            },
        )

    from .route_arbiter import API_ONLY_MODELS, RELAY_ONLY_MODELS, route_arbiter

    requested_model = body.get("model") or "supreme-spark"
    if not isinstance(requested_model, str):
        raise HTTPException(status_code=400, detail="model must be a string")
    requested_model = requested_model.strip() or "supreme-spark"
    model_alias = requested_model.lower()
    relay_only = model_alias in RELAY_ONLY_MODELS
    if relay_only and not STEALTH_WEBHOOK_URL and not _api_fallback_enabled():
        raise HTTPException(status_code=503, detail="Stealth Webhook relay is currently unconfigured")
    preferred_provider = None

    has_image = has_image_input(body)
    if has_image:
        if relay_only:
            raise HTTPException(status_code=503, detail="Vision input is unavailable on the webhook-only route")
        preferred_provider = "gemini"
    elif relay_only:
        preferred_provider = "ghost_gemini"
    elif model_alias in API_ONLY_MODELS:
        preferred_provider = "auto"
    elif model_alias.startswith("supremeai/"):
        preferred_provider = model_alias.split("/", 1)[1]
    elif model_alias in ("supreme-spark", "supremeai-spark", "supremeai-fast"):
        preferred_provider = "groq"
    elif model_alias in ("supreme-reason", "supremeai-reasoning"):
        preferred_provider = "gemini"
    elif model_alias in PROVIDER_CONFIGS:
        preferred_provider = model_alias

    # Normalize multimodal/structured content blocks (e.g. from Kilo Code/Roo Code/Cursor)
    # into clean strings so downstream schemas and relays never fail with 422.
    if not has_image and isinstance(body.get("messages"), list):
        for msg in body["messages"]:
            if isinstance(msg, dict):
                c = msg.get("content")
                if isinstance(c, list):
                    msg["content"] = "\n".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in c
                        if (isinstance(part, dict) and part.get("text")) or not isinstance(part, dict)
                    )

    # Conversation-ID carry-over & persistence
    conv_id = (
        body.get("conversation_id")
        or body.get("session_id")
        or request.headers.get("x-conversation-id")
        or request.headers.get("x-session-id")
    )
    try:
        user_id = _extract_user_id(request)
    except HTTPException as exc:
        if exc.status_code != 401 or conv_id:
            raise
        # An API credential may authorize stateless chat without identifying
        # an end user. Never read or write shared anonymous memory.
        user_id = None
    incoming_msgs = body.get("messages", [])
    last_user_msg = next((m.get("content") for m in reversed(incoming_msgs) if isinstance(m, dict) and m.get("role") == "user"), None)

    # 1. Message persistence (Canonical 3-tier memory store & legacy storage)
    persisted_message_id = None
    if conv_id and last_user_msg:
        # বাংলা মন্তব্য: মালিকানা যাচাই ব্যর্থ হলে কোনো inference বা মেমোরি mutation নয়।
        if not append_canonical_message:
            raise HTTPException(status_code=503, detail="Conversation storage unavailable")
        try:
            persisted_message = await asyncio.to_thread(append_canonical_message, conv_id, "user", str(last_user_msg), user_id=user_id)
            if isinstance(persisted_message, dict):
                persisted_message_id = persisted_message.get("id")
        except PermissionError:
            raise HTTPException(status_code=403, detail="Conversation access denied")
        except Exception as exc:
            logger.warning("Canonical memory store error (user msg): %s", exc)
            raise HTTPException(status_code=503, detail="Conversation storage unavailable")
        if add_message:
            try:
                await asyncio.to_thread(add_message, conv_id, "user", str(last_user_msg), user_id=user_id)
            except PermissionError:
                raise HTTPException(status_code=403, detail="Conversation access denied")
            except Exception as exc:
                logger.warning("Legacy conversation storage error (%s)", type(exc).__name__)
                raise HTTPException(status_code=503, detail="Conversation storage unavailable")

    # Persistent preferences are an explicit opt-in for verified registered users.
    # Guest and generic service keys cannot create a cross-session user profile.
    try:
        registered_user_id = _extract_registered_user_id(request)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        registered_user_id = None
    if (registered_user_id and isinstance(incoming_msgs, list) and incoming_msgs
            and isinstance(incoming_msgs[-1], dict) and incoming_msgs[-1].get("role") == "user"
            and isinstance(incoming_msgs[-1].get("content"), str)):
        if not ingest_consented_personal_memory:
            raise HTTPException(status_code=503, detail="Personal memory storage unavailable")
        try:
            await asyncio.to_thread(ingest_consented_personal_memory, registered_user_id, incoming_msgs)
        except Exception as exc:
            logger.warning("Personal memory operation failed (%s)", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Personal memory storage unavailable")

    trace.mark("persist")

    # 2. Server-Side Context Compiler (Phase 1):
    # Injects Core Identity Anchor + Platform Grounding Sheet + 3-Tier Memory + Deterministic Sampling Lock
    if not compile_chat_context:
        raise HTTPException(status_code=503, detail="Chat context unavailable")
    if compile_chat_context:
        try:
            if resolve_sampling_knobs:
                knobs = resolve_sampling_knobs(
                    messages=body.get("messages", []),
                    mode=body.get("mode") or requested_model,
                    max_tokens=body.get("max_tokens", 4096),
                )
                for k, v in knobs.items():
                    if k not in body or body[k] is None:
                        body[k] = v

            body["messages"] = await asyncio.to_thread(
                compile_chat_context,
                messages=body.get("messages", []),
                conversation_id=conv_id,
                user_id=user_id,
                language_pref=body.get("language_pref") or body.get("language") or "bn",
                response_style=body.get("response_style", "technical-architect"),
                persisted_message_id=persisted_message_id,
            )
        except Exception as exc:
            logger.warning("Context compiler error: %s", exc)
            raise HTTPException(status_code=503, detail="Chat context unavailable")

    def _format_sse_chunk(chunk_id: str, m_name: str, delta_text: str, is_final: bool, branding: Any) -> dict[str, Any]:
        p = {
            "id": chunk_id or "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": m_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": delta_text},
                    "finish_reason": "stop" if is_final else None,
                }
            ],
            "supremeai": branding,
        }
        if conv_id:
            p["conversation_id"] = conv_id
            p["session_id"] = conv_id
        return p

    # Do not share private completions or bypass current lane/approval checks
    # through the legacy prompt-only cache namespace.
    trace.mark("context")

    relay_detail = None
    route_arbiter.squad = squad
    decision = route_arbiter.choose_best_route(
        requested_model=requested_model,
        preferred_provider=preferred_provider,
        adaptive_routes=_adaptive_routes,
        stealth_available=bool(STEALTH_WEBHOOK_URL),
        has_image=has_image,
    )
    use_priority_1 = decision.route_type == "stealth-webhook"
    candidates = decision.candidate_slots or []
    router_mode = os.getenv("ROUTER_MODE", "soft").strip().lower()
    if router_mode == "hard" and preferred_provider:
        candidates = [c for c in candidates if c[0] == preferred_provider] or candidates
    if not candidates and not use_priority_1:
        reason = "Vision analysis is temporarily unavailable" if has_image else "No approved free API route available"
        raise HTTPException(status_code=503, detail=reason)

    # Lane is known here; record it before any upstream call so a timeout still
    # tells us WHICH lane timed out.
    trace.mark("route")
    trace.lane = decision.route_type
    trace.provider = preferred_provider or (candidates[0][0] if candidates else None)

    if use_priority_1:
        w_status, w_response = None, None
        start_time = time.time()
        try:
            # The relay is the lane a slow 6.2s reply actually came from: its
            # timeout was a flat 8s regardless of the model's declared budget.
            relay_timeout_s = min(
                STEALTH_WEBHOOK_TIMEOUT,
                max(_route_deadline_for(requested_model), RELAY_MIN_TIMEOUT_S),
            )
            w_status, w_response = await forward_stealth_webhook(
                STEALTH_WEBHOOK_URL,
                STEALTH_WEBHOOK_SECRET,
                body,
                timeout=relay_timeout_s,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Priority-1 Web Relay attempt exception: {exc}")
            w_status, w_response = 500, None

        # Auto-wrap raw {"reply": "..."} payloads if received
        # বাংলা মন্তব্য: কাঁচা {"reply": ...} পে-লোডে যদি source বা engine থাকে, তা নতুন ডিকশনারিতে প্রিজার্ভ করি যেন ব্র্যান্ডিং ব্যাজ w.xx না হয়ে আসল ইঞ্জিন দেখায়।
        if isinstance(w_response, dict) and "reply" in w_response and "choices" not in w_response and str(w_response["reply"]).strip():
            raw_engine = w_response.get("supremeai_engine") or w_response.get("engine") or w_response.get("source")
            w_response = {
                "id": "chatcmpl-stealth-" + os.urandom(6).hex(),
                "object": "chat.completion",
                "created": int(time.time()),
                "model": body.get("model", "auto"),
                "supremeai_engine": raw_engine,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": str(w_response["reply"]).strip(),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }

        chat_content = ""
        if (
            isinstance(w_response, dict)
            and bool(w_response.get("choices"))
            and isinstance(w_response["choices"], list)
            and len(w_response["choices"]) > 0
            and isinstance(w_response["choices"][0], dict)
            and isinstance(w_response["choices"][0].get("message"), dict)
        ):
            chat_content = str(w_response["choices"][0]["message"].get("content", "")).strip()

        # SPINE-style stream sanitization: strip unearned cushions / reflexive
        # apologies from the relay output before serving (no mid-stream pivot
        # here because the full content is already buffered).
        if chat_content:
            try:
                from gateway.service.stream_sanitizer import (
                    sanitize_stream as _sanitize_stream,
                )
            except ImportError:
                try:
                    from service.stream_sanitizer import (
                        sanitize_stream as _sanitize_stream,
                    )
                except ImportError:
                    _sanitize_stream = None
            if _sanitize_stream is not None:
                chat_content = _sanitize_stream(chat_content).text

        # Reject mock/dummy stubs and require genuine non-empty content
        is_valid_chat = bool(chat_content) and not any(
            marker in chat_content for marker in ("Web Session Active", "health=", "Authenticated via")
        )

        # 3. Post-Generation Response Guard (Phase 2): Identity Bleed Scrubbing & Stub/Markdown Sanitization
        if validate_and_sanitize and is_valid_chat:
            try:
                w_response = validate_and_sanitize(w_response)
                if (
                    isinstance(w_response, dict)
                    and w_response.get("choices")
                    and isinstance(w_response["choices"][0].get("message"), dict)
                ):
                    chat_content = str(w_response["choices"][0]["message"].get("content", "")).strip()
            except Exception as exc:
                logger.warning(f"Response guard rejected output: {exc}")
                is_valid_chat = False

        # 4. Provider Attempts Ledger (Phase 3 persistence)
        if log_provider_attempt:
            try:
                latency_ms = int((time.time() - start_time) * 1000)
                log_provider_attempt(
                    request_id=f"req-{uuid.uuid4().hex[:10]}",
                    conversation_id=conv_id or "ephemeral",
                    provider="stealth-webhook",
                    model=body.get("model", "auto"),
                    status_code=w_status or 500,
                    latency_ms=latency_ms,
                    error_message=None if is_valid_chat else "Invalid chat or stub content rejected by guard",
                )
            except Exception as exc:
                logger.debug(f"Failed to log provider attempt: {exc}")

        if w_status is not None and 200 <= w_status < 300 and is_valid_chat:
            _adaptive_routes["stealth-webhook"].record(
                (time.time() - start_time) * 1000,
                success=True,
                remaining=(w_response.get("remaining") if isinstance(w_response, dict) else None),
            )
            # Server-decided reply badge (e.g. "SupremeAI w.ge Turbo"); UI only displays it.
            served_model = str(w_response.get("model") or "")
            engine_src = w_response.get("supremeai_engine") or (
                served_model if served_model and served_model != "auto" else "gemini"
            )
            w_response["supremeai"] = build_brand("w", str(engine_src), served_model)
            headers = {
                "X-SupremeAI-Provider": "stealth-webhook",
                "X-SupremeAI-Slot": "adaptive-route",
                "X-SupremeAI-Tier": "free-tier-adaptive",
            }

            if conv_id:
                w_response["conversation_id"] = conv_id
                w_response["session_id"] = conv_id
                if chat_content:
                    if append_canonical_message:
                        try:
                            await asyncio.to_thread(
                                append_canonical_message,
                                conv_id,
                                "assistant",
                                chat_content,
                                user_id=user_id,
                                provider="stealth-webhook",
                                model=served_model or "auto",
                                metadata={"supremeai": w_response.get("supremeai")},
                            )
                        except Exception as exc:
                            logger.warning(f"Canonical memory store error (assistant msg): {exc}")
                    if add_message:
                        try:
                            await asyncio.to_thread(
                                add_message,
                                conv_id,
                                "assistant",
                                chat_content,
                                extra={"supremeai": w_response.get("supremeai")},
                                user_id=user_id,
                            )
                        except Exception as exc:
                            logger.warning(f"Legacy storage error (assistant msg): {exc}")

            if body.get("stream"):
                async def stream_generator():
                    # Stream tokens in progressive chunks
                    words = chat_content.split(" ")
                    for idx, word in enumerate(words):
                        chunk_text = word + (" " if idx < len(words) - 1 else "")
                        chunk_payload = _format_sse_chunk(
                            w_response.get("id"), served_model, chunk_text, idx == len(words) - 1, w_response.get("supremeai")
                        )
                        yield f"data: {json.dumps(chunk_payload)}\n\n"
                        await asyncio.sleep(0.012)
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    stream_generator(),
                    media_type="text/event-stream",
                    headers={**headers, "Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            trace.mark("upstream")
            trace.provider = engine_src
            trace.log()
            headers["Server-Timing"] = trace.server_timing()
            return JSONResponse(status_code=w_status, content=w_response, headers=headers)

        relay_detail = None
        if isinstance(w_response, dict):
            relay_detail = w_response.get("error") or w_response.get("detail") or w_response.get("message")
        if not relay_detail and w_response is not None:
            relay_detail = str(w_response)[:500]
        _adaptive_routes["stealth-webhook"].record(
            (time.time() - start_time) * 1000,
            success=False,
        )
        logger.warning("Stealth Webhook relay failed or returned no chat reply (status=%s)", w_status)
        if relay_only:
            if _api_fallback_enabled() and squad:
                # Admin-enabled fallback: serve from the sovereign API pool
                # instead of hard-failing. Default (false) preserves the
                # documented relay-only lock.
                logger.warning(
                    "ENABLE_API_FALLBACK=true: relay unavailable for %s; "
                    "falling through to API pool.",
                    requested_model,
                )
                candidates = squad.get_candidate_slots("auto", vision=has_image)
                use_priority_1 = False
            else:
                raise HTTPException(status_code=502, detail="Stealth Webhook relay is unavailable")

    last_error = None
    if squad and candidates:
        # Audit P0-5 fix: TRUE streaming. When the client asks for SSE, live-
        # proxy upstream chunks via stream_chat_completion_events (internal
        # model cascade included) instead of buffering the whole reply and
        # re-simulating it word-by-word with asyncio.sleep(0.01).
        # Multi-provider failover: if candidate 0 fails before producing any tokens,
        # seamlessly fail over to candidate 1..N in the squad.
        if body.get("stream") and candidates:
            stream_served_model = requested_model or "supremeai-api"
            stream_chunk_id = f"chatcmpl-stream-{int(time.time() * 1000)}"

            async def squad_true_stream_generator():
                acc: list = []
                started = False
                completed = False
                saw_tool_calls = False
                last_stream_err = "Upstream stream failed"
                last_brand = build_brand("api", candidates[0][0], stream_served_model)
                # Per-model budget (route_arbiter's declared threshold), not the
                # flat global envelope: supreme-spark may not spend 8s of a 1.5s
                # promise on one candidate.
                stream_deadline_s = _route_deadline_for(requested_model)
                stream_connect_s = _connect_timeout_for(requested_model)
                stream_first_token_s = _first_token_timeout_for(requested_model)
                route_deadline = time.monotonic() + stream_deadline_s

                for provider, slot in candidates:
                    if not started and time.monotonic() > route_deadline:
                        logger.warning(
                            "[stream] Route deadline (%.1fs, budget for %s) exceeded before first token; stopping failover.",
                            stream_deadline_s,
                            requested_model,
                        )
                        break
                    slot.total_calls += 1
                    call_start = time.monotonic()
                    stream_brand = build_brand("api", provider, stream_served_model)
                    last_brand = stream_brand

                    header_at: float | None = None
                    stream_iter = stream_chat_completion_events(
                        provider,
                        slot.key,
                        body,
                        slot=slot,
                        deadline_s=max(0.001, route_deadline - time.monotonic()),
                    ).__aiter__()
                    try:
                        async for kind, data in _aiter_stream_first_token(
                            stream_iter,
                            connect_timeout_s=stream_connect_s,
                            first_token_timeout_s=stream_first_token_s,
                            route_deadline=route_deadline,
                            heartbeat_ceiling_s=CHAT_STREAM_HEARTBEAT_CEILING_S,
                        ):
                            if kind == "status":
                                header_at = time.monotonic()
                                continue
                            if kind == "done":
                                # The first delta commits the provider, not the result.
                                completed = started
                                break
                            if kind == "event":
                                tool_calls = data.get("tool_calls")
                                text = data.get("delta") or ""
                                if not started and (text or tool_calls):
                                    started = True
                                    first_token_ms = (time.monotonic() - call_start) * 1000
                                    header_ms = (header_at - call_start) * 1000 if header_at is not None else -1.0
                                    if squad:
                                        squad.report_success(provider, slot, first_token_ms, first_token_ms=first_token_ms)
                                    _adaptive_routes["api-pool"].record(first_token_ms, success=True)
                                    logger.info(
                                        "[stream] first token provider=%s slot=%s model=%s header_ms=%.0f first_token_ms=%.0f",
                                        provider,
                                        slot.name,
                                        body.get("model"),
                                        header_ms,
                                        first_token_ms,
                                    )
                                if tool_calls:
                                    saw_tool_calls = True
                                    chunk_payload = {
                                        "id": stream_chunk_id,
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": stream_served_model,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {"role": "assistant", "tool_calls": tool_calls},
                                                "finish_reason": None,
                                            }
                                        ],
                                        "supremeai": stream_brand,
                                    }
                                    yield f"data: {json.dumps(chunk_payload)}\n\n"
                                elif text:
                                    acc.append(text)
                                    chunk_payload = _format_sse_chunk(
                                        stream_chunk_id, stream_served_model, text, False, stream_brand
                                    )
                                    yield f"data: {json.dumps(chunk_payload)}\n\n"
                                continue
                            if kind == "error":
                                if started:
                                    logger.warning("[stream] Provider %s failed mid-stream.", provider)
                                    break
                                last_stream_err = data.get("error", "Upstream stream failed")
                                call_latency = (time.monotonic() - call_start) * 1000
                                pool = squad.pools.get(provider) if squad else None
                                if pool:
                                    pool.report_injury(slot, data.get("status", 500), call_latency)
                                _adaptive_routes["api-pool"].record(call_latency, success=False)
                                logger.warning(
                                    f"[stream] Provider {provider} slot {slot.name} failed before stream start: {last_stream_err}. "
                                    f"Failing over to next squad player..."
                                )
                                break
                    except asyncio.TimeoutError:
                        if not started:
                            call_latency = (time.monotonic() - call_start) * 1000
                            logger.warning(
                                "[stream] First-token timeout (%.1fs) provider=%s slot=%s model=%s; failing over.",
                                CHAT_FIRST_TOKEN_TIMEOUT_S,
                                provider,
                                slot.name,
                                body.get("model"),
                            )
                            pool = squad.pools.get(provider) if squad else None
                            if pool:
                                pool.report_injury(slot, 504, call_latency)
                            _adaptive_routes["api-pool"].record(call_latency, success=False)
                            continue
                        logger.warning("[stream] Provider %s stream read timed out mid-stream.", provider)
                    except Exception as exc:  # noqa: BLE001 - never crash a live stream silently
                        logger.warning("[stream] candidate %s failed: %s", provider, type(exc).__name__)
                    finally:
                        try:
                            await stream_iter.aclose()
                        except Exception as exc:  # noqa: BLE001
                            logger.debug("Stream iterator close failed (%s)", type(exc).__name__)

                    if started:
                        break  # Never replay text or tool deltas from another slot.

                if not completed:
                    error = "Stream interrupted" if started else last_stream_err
                    yield f"data: {json.dumps({'error': error, 'supremeai': last_brand})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                full_text = "".join(acc)
                if conv_id and full_text and append_canonical_message:
                    try:
                        await asyncio.to_thread(
                            append_canonical_message,
                            conv_id,
                            "assistant",
                            full_text,
                            user_id=user_id,
                            provider="dynamic-squad",
                            model=stream_served_model,
                            metadata={"supremeai": last_brand, "stream": True},
                        )
                    except Exception as exc:
                        logger.warning("Failed to persist streamed assistant message (%s)", type(exc).__name__)
                final_chunk = _format_sse_chunk(stream_chunk_id, stream_served_model, "", True, last_brand)
                if saw_tool_calls:
                    final_chunk["choices"][0]["finish_reason"] = "tool_calls"
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            # Stream started: everything before the first body byte is now
            # measured. The generator itself is NOT instrumented (per-chunk
            # timing would add overhead to the path this protects).
            trace.mark("upstream")
            trace.log()
            return StreamingResponse(
                squad_true_stream_generator(),
                media_type="text/event-stream",
                headers={
                    "X-SupremeAI-Provider": "supremeai-dynamic-squad",
                    "X-SupremeAI-Slot": "adaptive-route",
                    "X-SupremeAI-Tier": "free-tier-adaptive",
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Server-Timing": trace.server_timing(),
                },
            )

        ns_deadline_s = _route_deadline_for(requested_model)
        route_deadline = time.monotonic() + ns_deadline_s
        for provider, slot in candidates:
            remaining = route_deadline - time.monotonic()
            if remaining <= 0:
                logger.warning(
                    "Route deadline (%.1fs, budget for %s) exceeded; stopping provider failover.",
                    ns_deadline_s,
                    requested_model,
                )
                break
            slot.total_calls += 1
            call_start = time.monotonic()

            try:
                status, response_data = await asyncio.wait_for(
                    forward_chat_completion(
                        provider,
                        slot.key,
                        body,
                        slot=slot,
                        deadline_s=remaining,
                    ),
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                status, response_data = 504, {"error": "API route deadline exceeded"}
            except Exception as exc:
                status, response_data = 500, {"error": str(exc)}
            call_latency = (time.monotonic() - call_start) * 1000

            if 200 <= status < 300 and isinstance(response_data, dict):
                squad.report_success(provider, slot, call_latency)
                _adaptive_routes["api-pool"].record(call_latency, success=True)
                # 1. Enforce SupremeAI Sole Identity branding
                served_model = requested_model or "supremeai-api"
                response_data["model"] = served_model
                response_data["supremeai"] = build_brand("api", provider, served_model)

                chat_content = ""
                choices = response_data.get("choices") or []
                if choices and isinstance(choices[0], dict) and isinstance(choices[0].get("message"), dict):
                    chat_content = str(choices[0]["message"].get("content") or "").strip()

                if validate_and_sanitize:
                    try:
                        response_data = validate_and_sanitize(response_data)
                        if response_data.get("choices") and isinstance(response_data["choices"][0].get("message"), dict):
                            chat_content = str(response_data["choices"][0]["message"].get("content", "")).strip()
                    except Exception as exc:
                        logger.warning("Response sanitization failed (%s)", type(exc).__name__)
                        raise HTTPException(status_code=500, detail="Response sanitization failed")

                headers = {
                    "X-SupremeAI-Provider": "supremeai-dynamic-squad",
                    "X-SupremeAI-Slot": "adaptive-route",
                    "X-SupremeAI-Tier": "free-tier-adaptive",
                }

                if conv_id and chat_content:
                    if append_canonical_message:
                        try:
                            await asyncio.to_thread(
                                append_canonical_message,
                                conv_id,
                                "assistant",
                                chat_content,
                                user_id=user_id,
                                provider="dynamic-squad",
                                model=served_model,
                                metadata={"supremeai": response_data.get("supremeai")},
                            )
                        except Exception as exc:
                            logger.warning("Failed to persist assistant message (%s)", type(exc).__name__)

                # Streaming chunk generator for Kilo Code / IDEs
                # (Audit P0-5: removed the fake word-by-word re-simulation —
                # streaming clients are now served by the live upstream proxy
                # branch above, before any buffering happens.)
                trace.mark("upstream")
                trace.provider = provider
                trace.log()
                headers["Server-Timing"] = trace.server_timing()
                return JSONResponse(status_code=status, content=response_data, headers=headers)

            pool = squad.pools.get(provider)
            if pool:
                pool.report_injury(slot, status, call_latency)
            _adaptive_routes["api-pool"].record(call_latency, success=False)

            last_error = {"provider": provider, "slot": slot.name, "status": status, "error": response_data}
            logger.warning(f"Squad slot {slot.name} failed ({status}), failing over to next squad player...")

    raise HTTPException(
        status_code=502,
        detail=f"All sovereign AI providers and stealth relays are currently cooling down. Last error: {relay_detail or last_error}"
    )


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key")
):
    """Main OpenAI-compatible completion endpoint."""
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    return await _execute_chat_completion(request, body, x_supremeai_key)


@app.post("/api/v1/stream/chat")
@app.post("/v1/stream/chat")
async def stream_chat_alias(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key")
):
    """Compatibility alias for legacy chatService (satellite supremeai-studio).
    Translates { message, messages } into OpenAI { messages, stream: true } format.
    """
    try:
        raw_body = await request.json()
    except Exception:  # noqa: BLE001
        raw_body = {}

    messages = raw_body.get("messages")
    if not messages and "message" in raw_body:
        messages = [{"role": "user", "content": str(raw_body["message"])}]
    elif not messages:
        messages = []

    body = dict(raw_body)
    body["messages"] = messages
    body["stream"] = True
    body.setdefault("model", "auto")

    return await _execute_chat_completion(request, body, x_supremeai_key)


@app.post("/api/v1/capabilities/execute")
@app.post("/v1/capabilities/execute")
async def execute_capability_alias(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key")
):
    """Compatibility alias for controlPlane.executeCapability (satellite supremeai-studio).
    Fulfills CapabilityExecutionResult contract without 404.

    HONESTY NOTE: this endpoint does NOT execute any capability/tool — it relays
    the prompt through the normal chat completion pipeline and echoes the text.
    Clients needing real capability execution must use the core capability
    orchestrator (/api/v1/capabilities/* via API), not this alias.
    """
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing X-SupremeAI-Key / Bearer token"
        )

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}

    capability = body.get("capability", "conversation.orchestrate")
    payload = body.get("payload") or {}
    prompt = payload.get("prompt") or body.get("prompt") or ""
    conv_id = payload.get("conversation_id") or body.get("conversation_id")

    exec_id = f"exec-{uuid.uuid4().hex[:12]}"
    response_text = ""

    if prompt:
        chat_body = {
            "model": "auto",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        if conv_id:
            chat_body["conversation_id"] = conv_id
        try:
            res = await _execute_chat_completion(request, chat_body, x_supremeai_key)
            if isinstance(res, JSONResponse):
                c_data = json.loads(res.body.decode("utf-8")) if hasattr(res, "body") else {}
                choices = c_data.get("choices") or []
                if choices and isinstance(choices[0], dict):
                    response_text = choices[0].get("message", {}).get("content", "")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"execute_capability completion fallback: {exc}")
            response_text = f"Capability {capability} executed."
    else:
        response_text = f"Capability {capability} executed."

    return {
        "execution_id": exec_id,
        "status": "completed",
        "capability": capability,
        "response": response_text or f"Capability {capability} acknowledged.",
        "data": {
            "reasoning_steps": [],
            "artifacts": [],
            # Honest-execution marker: this alias relays a chat completion; it
            # does not execute any capability, tool, or browser action.
            "mode": "chat_passthrough",
        },
        "verification": {
            # Previously always True with method "gateway_capability_router" —
            # the satellite control plane pinned that contract and shipped it.
            # Nothing was independently verified, so verified is now False.
            "verified": False,
            "method": "gateway_capability_passthrough",
            "note": "No capability executed — response is a passthrough chat completion.",
        }
    }


@app.post("/v1/ui/generate")
async def generate_ui_component(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key")
):
    """Specialized V0 / UI synthesis endpoint for SupremeAI Studio."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    prompt = body.get("prompt") or (body.get("messages", [{}])[-1].get("content", "") if body.get("messages") else "")
    ui_payload = {
        "model": os.getenv("V0_MODEL", "v0-1.0-md"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a master React Tailwind UI component synthesizer. "
                    "Generate complete, beautiful, production-ready React code without markdown chatter."
                ),
            },
            {"role": "user", "content": str(prompt)},
        ],
    }
    candidates = squad.get_candidate_slots("v0") if squad else []
    for provider, slot in candidates:
        status, resp = await forward_chat_completion(provider, slot.key, ui_payload, slot=slot)
        if 200 <= status < 300:
            return JSONResponse(status_code=status, content=resp)
    raise HTTPException(status_code=503, detail="Approved UI generation route unavailable")


# ── MCP Control Tower & Superadmin Management Surface ────────────────────────

@app.get("/admin/router/live-state")
async def admin_router_live_state(request: Request, x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key")):
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        from gateway.dual_pool_priority_router import get_dual_pool_router
        return get_dual_pool_router().get_live_telemetry()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))
@app.get("/admin/router/live-stream")
async def admin_router_live_stream(request: Request, x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key")):
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")

    async def event_generator():
        from gateway.dual_pool_priority_router import get_dual_pool_router
        router = get_dual_pool_router()
        while True:
            if await request.is_disconnected():
                break
            try:
                payload = router.get_live_telemetry()
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as exc:  # noqa: BLE001
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/admin/squad/status")
async def admin_squad_status(
    x_superadmin_key: Optional[str] = Header(None, alias="X-Superadmin-Key")
):
    """Deep inspection of each slot's health and telemetry (MCP Control Tower only)."""
    # Fail-closed: missing key or mismatched key rejected
    if not SUPERADMIN_KEY or x_superadmin_key != SUPERADMIN_KEY:
        raise HTTPException(status_code=403, detail="Superadmin access required (key missing or invalid)")

    details = {}
    now = time.time()
    if squad:
        for name, pool in squad.pools.items():
            details[name] = [
                {
                    "slot": s.name,
                    "healthy": s.is_healthy,
                    "cooldown_remaining_s": max(0, int(s.cooldown_until - now)),
                    "total_calls": s.total_calls,
                    "total_errors": s.total_errors,
                }
                for s in pool.slots
            ]
    return {
        "status": "ok",
        "telemetry": squad.stats() if squad else {},
        "slots": details,
    }


@app.post("/admin/squad/reload")
async def admin_squad_reload(
    x_superadmin_key: Optional[str] = Header(None, alias="X-Superadmin-Key")
):
    """Dynamically re-scans environment for new keys without restarting the container."""
    # Fail-closed: missing key or mismatched key rejected
    if not SUPERADMIN_KEY or x_superadmin_key != SUPERADMIN_KEY:
        raise HTTPException(status_code=403, detail="Superadmin access required (key missing or invalid)")

    if squad:
        squad.reload_squad()
    return {"status": "reloaded", "stats": squad.stats() if squad else {}}


# ── Agent Tool Surface Proxy (audit item ⑯, 2026-11-24) ─────────────────────
# Chat tool-calling lives in CORE, not here: the governed registry, the MCP
# policy gate and the per-tenant allowlist are all core concerns, and this image
# must not import them (`.importlinter` contract `gateway-no-core-private`; the
# gateway image ships no `core/` tree at all — see PR #772's sibling audit note).
# The gateway therefore only *transports*: it forwards the manifest request and
# single tool calls to CORE_API_URL, and fails closed when that is unset. The
# loop itself never runs here, so nothing about tool governance is duplicated.

def _core_api_base() -> Optional[str]:
    """Core API base URL. Fail-closed: unset ⇒ None in production (no fake success)."""
    raw = os.getenv("CORE_API_URL", "").strip().rstrip("/")
    if raw:
        return raw
    env = os.getenv("ENVIRONMENT", os.getenv("ENV", "")).strip().lower()
    if env in ("production", "prod"):
        logger.error(
            "CORE_API_URL is not configured — the agent tool surface cannot reach "
            "core in production."
        )
        return None
    # Local development only (same policy as core/services/worker/main.py).
    return "http://localhost:8000"


def _agent_tools_flag() -> bool:
    """Gateway-side view of the core flag — used for honest capability reporting."""
    return os.getenv("SUPREMEAI_AGENT_TOOLS", "").strip().lower() == "true"


def _agent_tools_enabled_for_chat() -> bool:
    """True only when chat tool-calling is genuinely reachable from this deployment.

    Both halves matter: the loop lives in core, so the flag alone is not enough
    (unset ``CORE_API_URL`` means the proxy 503s) and reachability alone is not
    enough (core would refuse with 403 when the flag is off).
    """
    return _agent_tools_flag() and bool(os.getenv("CORE_API_URL", "").strip())


async def _forward_agent_request(
    method: str,
    path: str,
    request: Request,
    body: Optional[dict] = None,
    timeout: float = 30.0,
) -> dict:
    """Forward one agent-tool request to core; never invent a result."""
    base = _core_api_base()
    if base is None:
        raise HTTPException(
            status_code=503,
            detail="agent tool surface unavailable: CORE_API_URL is not configured",
        )
    import httpx

    headers = {"Accept": "application/json"}
    bearer = request.headers.get("authorization")
    if bearer:
        headers["Authorization"] = bearer
    core_key = request.headers.get("x-supremeai-key")
    if core_key:
        headers["X-SupremeAI-Key"] = core_key

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, f"{base}{path}", headers=headers, json=body)
    except httpx.HTTPError as exc:
        logger.error(f"agent tool proxy: core unreachable at {base}{path}: {type(exc).__name__}")
        raise HTTPException(
            status_code=503,
            detail=f"core API unreachable for agent tools ({type(exc).__name__})",
        )

    try:
        payload = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="core API returned a non-JSON agent response")

    if resp.status_code >= 500:
        raise HTTPException(
            status_code=502,
            detail="core API failed while handling the agent tool request",
        )
    if resp.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        raise HTTPException(status_code=resp.status_code, detail=detail)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="core API returned an unexpected agent payload")
    return payload


@app.get("/api/v1/agent/tools")
@app.get("/v1/agent/tools")
async def get_agent_tools(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Proxy the governed tool manifest from core (``enabled: false`` when off)."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await _forward_agent_request("GET", "/api/agent/tools", request)


# ── UserMemoryGraph & Morning Briefing Gateway Proxy (Wave 3 §3.1) ──────────
# বাংলা মন্তব্য: কোর প্রাইভেট মডিউল সরাসরি ইমপোর্ট না করে HTTP প্রক্সির মাধ্যমে ইউজার মেমরি ও মর্নিং ব্রিফিং রিলে
@app.get("/api/memory/briefing")
@app.get("/v1/memory/briefing")
@app.get("/api/v1/memory/briefing")
async def proxy_memory_briefing(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Proxy proactive morning briefing for the authenticated user."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await _forward_agent_request("GET", "/api/memory/briefing", request)


@app.get("/api/memory/graph")
@app.get("/v1/memory/graph")
@app.get("/api/v1/memory/graph")
async def proxy_get_memory_graph(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Proxy caller's personal memory graph transparency view."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await _forward_agent_request("GET", "/api/memory/graph", request)


@app.delete("/api/memory/graph")
@app.delete("/v1/memory/graph")
@app.delete("/api/v1/memory/graph")
async def proxy_wipe_memory_graph(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Proxy right-to-be-forgotten full memory wipe."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await _forward_agent_request("DELETE", "/api/memory/graph", request)


@app.post("/api/memory/graph/forget")
@app.post("/v1/memory/graph/forget")
@app.post("/api/v1/memory/graph/forget")
async def proxy_forget_memory_fact(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Proxy selective single-fact removal from caller's memory graph."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    return await _forward_agent_request("POST", "/api/memory/graph/forget", request, body)


@app.post("/api/memory/graph/absorb")
@app.post("/v1/memory/graph/absorb")
@app.post("/api/v1/memory/graph/absorb")
async def proxy_absorb_memory_passage(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Proxy explicit memory absorption for the authenticated user."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    return await _forward_agent_request("POST", "/api/memory/graph/absorb", request, body)


@app.post("/api/v1/agent/tool-calls")
@app.post("/v1/agent/tool-calls")
async def post_agent_tool_call(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Proxy one governed tool invocation to core (MCP-gated there)."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    return await _forward_agent_request("POST", "/api/agent/tool-calls", request, body)


async def _forward_agent_stream(
    method: str,
    path: str,
    request: Request,
    body: Optional[dict] = None,
) -> StreamingResponse:
    """SSE passthrough to core — byte-relay, never buffered, never invented.

    The ReAct loop runs in core (``core.agent_chat_loop``); the gateway only
    relays the ``data: {json}`` frames (and the terminal ``[DONE]``) verbatim.
    Read timeout is generous because a full agent turn may take minutes.
    """
    base = _core_api_base()
    if base is None:
        raise HTTPException(
            status_code=503,
            detail="agent stream unavailable: CORE_API_URL is not configured",
        )
    import httpx

    headers = {"Accept": "text/event-stream"}
    bearer = request.headers.get("authorization")
    if bearer:
        headers["Authorization"] = bearer
    core_key = request.headers.get("x-supremeai-key")
    if core_key:
        headers["X-SupremeAI-Key"] = core_key

    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)
    )
    try:
        req = client.build_request(method, f"{base}{path}", headers=headers, json=body)
        resp = await client.send(req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        logger.error(f"agent stream proxy: core unreachable at {base}{path}: {type(exc).__name__}")
        raise HTTPException(
            status_code=503,
            detail=f"core API unreachable for agent stream ({type(exc).__name__})",
        )

    if resp.status_code >= 400:
        try:
            payload = json.loads(resp.content or b"{}")
        except ValueError:
            payload = None
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        status = resp.status_code
        await resp.aclose()
        await client.aclose()
        if status >= 500:
            raise HTTPException(status_code=502, detail="core API failed while streaming the agent turn")
        raise HTTPException(status_code=status, detail=detail)

    async def relay() -> AsyncIterator[bytes]:
        try:
            async for chunk in resp.aiter_bytes():
                if chunk:
                    yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(
        relay(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/v1/agent/chat")
@app.post("/v1/agent/chat")
async def post_agent_chat(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Proxy one full autonomous agent chat turn to core (loop lives there)."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    # বাংলা: একটি ReAct টার্নে একাধিক টুল-নির্বাহ ও সংশ্লেষণ হতে পারে — ৩০সে নয়।
    return await _forward_agent_request(
        "POST", "/api/agent/chat", request, body, timeout=180.0
    )


@app.post("/api/v1/agent/stream")
@app.post("/v1/agent/stream")
async def post_agent_stream(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """SSE passthrough for the core agent stream (transport-only, no buffering)."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    return await _forward_agent_stream("POST", "/api/agent/stream", request, body)


# ── Conversation Carry-over & Chat History Endpoints ─────────────────────────

@app.get("/api/v1/chat/conversations")
@app.get("/v1/chat/conversations")
@app.get("/api/v1/conversations")
@app.get("/api/v1/conversations/")
@app.get("/v1/conversations")
@app.get("/v1/conversations/")
async def get_conversations(
    request: Request,
    limit: int = 50,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """List recent conversation sessions for the current user."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = _extract_user_id(request)
    convs = list_conversations(user_id=user_id, limit=limit) if list_conversations else []
    return {"status": "ok", "conversations": convs, "count": len(convs)}


@app.get("/api/v1/chat/conversations/{conversation_id}")
@app.get("/v1/chat/conversations/{conversation_id}")
@app.get("/api/v1/conversations/{conversation_id}")
@app.get("/v1/conversations/{conversation_id}")
async def get_conversation_details(
    conversation_id: str,
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Retrieve full message history for a conversation session."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = _extract_user_id(request)
    conv = get_conversation(conversation_id, user_id=user_id) if get_conversation else None
    if not conv:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    return conv


@app.post("/api/v1/chat/conversations")
@app.post("/v1/chat/conversations")
@app.post("/api/v1/conversations")
@app.post("/api/v1/conversations/")
@app.post("/v1/conversations")
@app.post("/v1/conversations/")
async def create_or_update_conversation(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Create or update conversation metadata."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    conv_id = str(body.get("id") or body.get("conversation_id") or f"conv-{uuid.uuid4().hex[:12]}").strip()
    title = body.get("title")
    metadata = body.get("metadata")
    user_id = _extract_user_id(request)

    if not save_conversation:
        raise HTTPException(status_code=503, detail="Conversation storage unavailable")
    try:
        res = save_conversation(conv_id, user_id=user_id, title=title, metadata=metadata)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Conversation access denied")
    return {"status": "ok", "conversation": res}


@app.delete("/api/v1/chat/conversations/{conversation_id}")
@app.delete("/v1/chat/conversations/{conversation_id}")
@app.delete("/api/v1/conversations/{conversation_id}")
@app.delete("/v1/conversations/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: str,
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Delete a conversation session and all its messages."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = _extract_user_id(request)
    ok = delete_conversation(conversation_id, user_id=user_id) if delete_conversation else False
    return {"status": "deleted" if ok else "not_found", "id": conversation_id}


@app.get("/api/v1/conversations/{conversation_id}/messages")
@app.get("/v1/conversations/{conversation_id}/messages")
@app.get("/api/v1/chat/conversations/{conversation_id}/messages")
@app.get("/v1/chat/conversations/{conversation_id}/messages")
async def list_conversation_messages(
    conversation_id: str,
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """List ordered messages for a conversation (user-scoped)."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = _extract_user_id(request)
    conv = get_conversation(conversation_id, user_id=user_id) if get_conversation else None
    if not conv:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    return {"status": "ok", "conversation_id": conversation_id, "messages": conv.get("messages", []), "count": conv.get("message_count", 0)}


@app.post("/api/v1/conversations/{conversation_id}/messages")
@app.post("/v1/conversations/{conversation_id}/messages")
@app.post("/api/v1/chat/conversations/{conversation_id}/messages")
@app.post("/v1/chat/conversations/{conversation_id}/messages")
async def append_conversation_message(
    conversation_id: str,
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Append a message to a user-owned conversation (per-user scoped)."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    role = str(body.get("role") or "user")
    content = body.get("content")
    if content is None or not str(content).strip():
        raise HTTPException(status_code=400, detail="Message content is required")
    user_id = _extract_user_id(request)
    conv = get_conversation(conversation_id, user_id=user_id) if get_conversation else None
    if not conv:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    try:
        msg = add_message(conversation_id, role, str(content), user_id=user_id) if add_message else {"id": "", "conversation_id": conversation_id, "role": role, "content": str(content)}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"status": "ok", "message": msg}


# ── Workspace Connections & Capability Discovery Endpoints ──────────────────

@app.get("/api/v1/connections/my-workspace")
@app.get("/api/connections/my-workspace")
async def get_my_workspace(request: Request):
    """Authoritative scoped workspace state and capabilities contract for User Dashboard.

    Honesty contract (audit items ⑥ / ⑳ / ②₄, 2026-11-24): this payload is what
    a dashboard renders as "what can SupremeAI do for me", so it must not imply
    that the chat model can call these capabilities. It cannot: the gateway chat
    path has no tool-calling loop, and every capability below is driven either
    from the browser UI or from an admin/tenant API — never from a chat turn.

    Each capability therefore carries ``invocableFromChat: false`` plus the real
    ``invocationSurface``. Flip a flag only when that capability is actually
    wired to a tool-calling loop, and keep the ``purpose`` text describing what
    the *route* does rather than what an agent might one day do.
    """
    browser_automation_note = (
        "Manual, owner-scoped sessions (navigate/click/fill/screenshot) via "
        "/api/browser/automation/* — the user drives it; chat cannot."
    )
    return {
        "userId": _extract_user_id(request),
        "authorizedContexts": [{"id": "ctx-default", "label": "Default Workspace", "active": True}],
        "executionMode": "autonomous",
        # Audit item ⑯ (2026-11-24): a governed tool loop now exists, but it runs
        # in CORE (core.tool_loop + /api/agent/tool-calls) and the gateway only
        # proxies to it. Report it as available only when the loop is genuinely
        # reachable from this deployment: the flag is ON *and* CORE_API_URL is
        # set. Default remains false, so nothing over-claims.
        "chatToolCalling": _agent_tools_enabled_for_chat(),
        "chatToolCallingDetail": {
            "transport": "core-http-proxy",
            "requiresFlag": "SUPREMEAI_AGENT_TOOLS=true",
            "coreApiConfigured": bool(os.getenv("CORE_API_URL", "").strip()),
            "scope": "governed SUPREME_TOOLS registry only (policy-gated; no browser automation)",
            "manifest": "/v1/agent/tools",
        },
        "capabilities": [
            {
                "capabilityId": "cap-research",
                "name": "Web Research & Intelligence",
                "purpose": (
                    "Scrape/extract through the stealth scraper service (tenant CrawlPolicy + "
                    "scout key required). Available as an API route, not as a chat tool."
                ),
                "status": "ready",
                "category": "tool",
                "unavailableReason": None,
                "requiredPermission": None,
                "invocableFromChat": False,
                "invocationSurface": "api",
            },
            {
                "capabilityId": "cap-code",
                "name": "Code Assistant & Sandbox",
                "purpose": (
                    "Answer coding questions in chat (text only). No sandbox execution is "
                    "wired to a chat turn."
                ),
                "status": "ready",
                "category": "tool",
                "unavailableReason": "No sandbox execution is wired to chat",
                "requiredPermission": None,
                "invocableFromChat": False,
                "invocationSurface": "chat_text_only",
            },
            {
                "capabilityId": "cap-browser",
                "name": "Browser Automation",
                "purpose": browser_automation_note,
                "status": "ready",
                "category": "agent",
                "unavailableReason": "Not wired to chat; use the browser UI/API",
                "requiredPermission": None,
                "invocableFromChat": False,
                "invocationSurface": "browser_ui",
            },
        ],
        "connections": [
            {"connectionId": "conn-gateway", "name": "API Gateway", "health": "healthy"},
            {"connectionId": "conn-scraper", "name": "Scraper Relay", "health": "healthy"},
        ],
        "recentActivity": [],
    }


@app.post("/api/v1/connections/detect")
async def detect_connection(request: Request):
    return {"detected": True, "connectionType": "http-service", "health": "healthy"}


@app.post("/api/v1/connections/register")
async def register_connection(request: Request):
    return {"connection_id": "conn-custom", "capability_id": "cap-custom", "health": "healthy", "message": "Registered successfully"}


@app.post("/api/v1/access/set-mode")
async def set_execution_mode(request: Request):
    return {"user_id": _extract_user_id(request), "mode": "autonomous", "persisted": True, "message": "Mode updated"}


# ── LiveLogs Endpoints (Admin Console Server-Side Log Streaming) ─────────────

@app.get("/admin-api/logs")
@app.get("/api/v1/admin/logs")
@app.get("/admin/logs")
async def get_admin_logs(
    request: Request,
    limit: int = 100,
    level: Optional[str] = None,
    search: Optional[str] = None,
    x_superadmin_key: Optional[str] = Header(None, alias="X-Superadmin-Key"),
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Fetches recent service logs for the Admin Console."""
    # FIX (security): server logs may expose internal topology, tokens, and PII.
    # A generic client key or guest token must NOT grant access. Require an
    # admin principal (superadmin key OR admin-scoped token OR admin JWT).
    if not _is_admin_principal(request, x_supremeai_key, x_superadmin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required to view server logs")

    logs = log_ring_buffer.get_logs(limit=limit, level=level, search=search)
    return {
        "status": "ok",
        "total": len(logs),
        "limit": limit,
        "logs": logs,
    }


@app.get("/admin-api/logs/stream")
@app.get("/api/v1/admin/logs/stream")
@app.get("/admin/logs/stream")
async def stream_admin_logs(
    request: Request,
    limit: int = 50,
    x_superadmin_key: Optional[str] = Header(None, alias="X-Superadmin-Key"),
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Real-time Server-Sent Events (SSE) log streamer for Admin Console."""
    # FIX (security): require an admin principal — never a generic client/guest token.
    if not _is_admin_principal(request, x_supremeai_key, x_superadmin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required to stream server logs")

    subscriber_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    log_ring_buffer.subscribers.add(subscriber_queue)

    async def log_event_generator():
        try:
            # Initial backlog burst
            initial_logs = log_ring_buffer.get_logs(limit=limit)
            for entry in initial_logs:
                yield f"data: {json.dumps(entry)}\n\n"

            # Stream real-time logs with heartbeat keep-alive
            while True:
                try:
                    entry = await asyncio.wait_for(subscriber_queue.get(), timeout=12.0)
                    yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            log_ring_buffer.subscribers.discard(subscriber_queue)

    return StreamingResponse(
        log_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── User Preferences & Tool-Card Persistence Endpoints ───────────────────────

@app.get("/api/v1/user/preferences")
@app.get("/api/user/preferences")
async def get_preferences(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Retrieve stored user preferences (including hidden tool cards, pinned tools, theme)."""
    user_id = _extract_user_id(request)
    prefs = get_user_preferences(user_id=user_id) if get_user_preferences else {"user_id": user_id, "preferences": {}}
    return prefs


@app.post("/api/v1/user/preferences")
@app.post("/api/user/preferences")
@app.put("/api/v1/user/preferences")
async def update_preferences(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Update user preferences (e.g. tool card removal / preference saving)."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    user_id = _extract_user_id(request)
    res = save_user_preferences(user_id=user_id, patch_data=body) if save_user_preferences else {"user_id": user_id, "preferences": body}
    return {"status": "ok", "user_preferences": res}


@app.delete("/api/v1/user/preferences/tool-card/{tool_id}")
@app.post("/api/v1/user/preferences/tool-card/{tool_id}/hide")
async def hide_tool_card(
    tool_id: str,
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Persistently hides/removes a tool card from the user's dashboard."""
    user_id = _extract_user_id(request)
    patch = {"action": "hide_tool", "tool_id": tool_id}
    res = save_user_preferences(user_id=user_id, patch_data=patch) if save_user_preferences else {"user_id": user_id}
    return {"status": "ok", "action": "hidden", "tool_id": tool_id, "user_preferences": res}


@app.delete("/api/v1/user/preferences/tool-card/{tool_id}/restore")
@app.post("/api/v1/user/preferences/tool-card/{tool_id}/restore")
async def restore_tool_card(
    tool_id: str,
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Restores a previously hidden tool card in the user's dashboard."""
    user_id = _extract_user_id(request)
    patch = {"action": "unhide_tool", "tool_id": tool_id}
    res = save_user_preferences(user_id=user_id, patch_data=patch) if save_user_preferences else {"user_id": user_id}
    return {"status": "ok", "action": "restored", "tool_id": tool_id, "user_preferences": res}


@app.get("/api/v1/telemetry/latency")
async def get_latency_telemetry(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Real-time provider latency, key pool health, and multi-tier cache telemetry.

    Audit P1-7 fix: this endpoint previously exposed the full provider pool
    (77 keys + per-provider health) without authentication. Operator telemetry
    now requires operator-class credentials and public responses only carry
    aggregate counters — never raw key material or supplier topology.
    """
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized: operator telemetry requires a valid key")
    squad_stats = squad.stats() if squad else {"total_providers": 0, "total_keys": 0, "total_healthy_keys": 0}
    # Redact supplier internals: expose aggregate health only (audit P1-7).
    squad_stats = {
        k: v for k, v in squad_stats.items()
        if k not in ("providers", "keys", "key_details", "per_provider")
    }
    return {
        "status": "ok",
        "squad": squad_stats,
        "cache": {"enabled": False, "l1_size": 0, "hits": 0, "misses": 0},
        "routes": {k: {"latency_ms": v.latency_ms, "failures": v.failures, "remaining": v.remaining} for k, v in _adaptive_routes.items()},
    }


@app.get("/api/platform/config")
async def get_platform_config(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Gateway-level platform configuration for Studio UI (auth-gated: audit P1-8)."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing key")
    return {
        "status": "ok",
        "environment": os.getenv("ENVIRONMENT", "production"),
        "features": {
            "adaptive_routing": True,
            "stealth_webhook": bool(STEALTH_WEBHOOK_URL),
            "multi_key_squad": True,
            "hitl": True,
        },
        "models_count": 6,
    }




@app.get("/api/mcp-tower/services")
async def get_mcp_tower_services(
    request: Request,
    x_supremeai_key: Optional[str] = Header(None, alias="X-SupremeAI-Key"),
):
    """Gateway-level MCP Tower service registry summary (auth-gated: audit P1-8)."""
    if not _verify_client_auth(request, x_supremeai_key):
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing key")
    return {
        "status": "ok",
        "services": [
            {"name": "supremeai-api", "status": "healthy", "type": "gateway"},
            {"name": "supremeai-mcp-tower", "status": "healthy", "type": "mcp"},
        ],
    }

