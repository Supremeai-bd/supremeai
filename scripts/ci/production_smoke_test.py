#!/usr/bin/env python3
"""Critical-path production smoke test for SupremeAI (stdlib-only).

Verifies the critical user path against a deployed environment using ONLY the
Python standard library (urllib.request) — no pip dependencies required.

Usage
-----
    SMOKE_BASE_URL=https://api.example.com \
    SMOKE_EMAIL=you@example.com \
    SMOKE_PASSWORD='...' \
    python scripts/ci/production_smoke_test.py

Health-only (unauthenticated) probe, e.g. right after an infra rollout:

    SMOKE_BASE_URL=https://api.example.com SMOKE_SKIP_AUTH=true \
    python scripts/ci/production_smoke_test.py

Offline logic check (embedded fixture HTTP server, no network):

    python scripts/ci/production_smoke_test.py --self-test

Configuration (environment variables)
------------------------------------
    SMOKE_BASE_URL     Base URL of the deployed backend (falls back to BASE_URL).
                       Required unless --self-test is used.
    SMOKE_EMAIL        Login email for the authenticated steps.
    SMOKE_PASSWORD     Login password for the authenticated steps.
    SMOKE_TIMEOUT      Per-request timeout in seconds (default: 30).
    SMOKE_SKIP_AUTH    When truthy ("1"/"true"/"yes"/"on"), run health checks only.
    SMOKE_CHAT_PROMPT  Prompt text sent to the chat endpoint (default: "smoke test ping").

CLI flags (override env where applicable): --base-url, --timeout, --skip-auth,
--self-test. Credentials are intentionally env-only so they never appear in a
process listing.

Steps (endpoint paths verified against source, not guessed)
-----------------------------------------------------------
 1. GET  /health/live        — liveness (backend/core/app_builder.py:511 mounts
                               the canonical /health router; backend/core/
                               health_routes.py:192 defines /live)
 2. GET  /health/ready       — readiness (backend/core/health_routes.py:174)
 3. POST /api/v1/auth/login  — JSON {"username": <email>, "password": ...}
                               (matches frontend/src/store/authStore.ts:131 which
                               sends `username: email`; backend
                               api/routes/auth.py:205 LoginRequest accepts
                               username OR email and reconciles them). Response:
                               {access_token, refresh_token, token_type,
                               user_id, role} (api/routes/auth.py:231)
 4. GET  /api/v1/auth/me     — Bearer token → {user_id, role, scopes, email}
                               (api/routes/auth.py:567)
 5. POST /api/v1/stream/chat — JSON {"prompt": "..."} with Bearer token; SSE.
                               Only HTTP 200 + "text/event-stream" content type
                               is asserted, then the connection is closed
                               (api/routes/stream_chat_sse.py:413; primary
                               frontend path per
                               frontend/src/services/chatService.ts:43).
                               OPTIONAL step: any failure here is a WARN, not a
                               failure (LLM downstream issues must not block
                               the pipeline gate).
 6. POST /api/v1/auth/logout — Bearer token → {"status": "logged_out"}
                               (api/routes/auth.py:581); afterwards the same
                               access token must be rejected with 401 on
                               /api/v1/auth/me. NOTE: for non-admin users the
                               revocation check is fail-open if Redis is down
                               (api/routes/auth.py:170) — a FAIL here with
                               logout=200 usually means the Redis-backed jti
                               blacklist is unreachable.

Steps 3-6 are marked SKIPPED (not failures) when SMOKE_SKIP_AUTH is truthy or
when SMOKE_EMAIL/SMOKE_PASSWORD are missing.

Exit codes
----------
    0  all required steps passed (skips and warnings don't fail)
    1  configuration error, or at least one required step failed
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

USER_AGENT = "supremeai-production-smoke/1.0"
DEFAULT_TIMEOUT = 30.0
MAX_JSON_BODY_BYTES = 1_048_576  # 1 MiB cap for JSON responses
SSE_SNIFF_BYTES = 1024

# Real endpoint map (see module docstring for source references).
HEALTH_LIVE_PATH = "/health/live"
HEALTH_READY_PATH = "/health/ready"
LOGIN_PATH = "/api/v1/auth/login"
ME_PATH = "/api/v1/auth/me"
CHAT_STREAM_PATH = "/api/v1/stream/chat"
LOGOUT_PATH = "/api/v1/auth/logout"

TRUTHY = {"1", "true", "yes", "on"}


class ConfigError(Exception):
    """Invalid configuration; main() turns this into a clean exit 1."""


@dataclass
class SmokeConfig:
    base_url: str
    email: str | None = None
    password: str | None = None
    timeout: float = DEFAULT_TIMEOUT
    skip_auth: bool = False
    chat_prompt: str = "smoke test ping"


@dataclass
class HttpResponse:
    status: int | None
    headers: dict[str, str]
    body: bytes
    error: str | None = None

    @property
    def content_type(self) -> str:
        return self.headers.get("Content-Type", "") or self.headers.get("content-type", "")

    @property
    def is_stream(self) -> bool:
        return "text/event-stream" in self.content_type.lower()

    def body_text(self, limit: int = 300) -> str:
        return self.body[:limit].decode("utf-8", errors="replace").strip()


@dataclass
class StepResult:
    name: str
    outcome: str  # PASS | FAIL | SKIP | WARN
    detail: str
    seconds: float


def _is_truthy(value: str | None) -> bool:
    return isinstance(value, str) and value.strip().lower() in TRUTHY


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _http(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    stream: bool = False,
) -> HttpResponse:
    """Perform an HTTP request without ever raising.

    With ``stream=True`` only the first bytes of the body are sniffed (so an
    SSE endpoint that keeps the connection open cannot stall the run); the
    response is closed immediately afterwards.
    """
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/event-stream"}
    if headers:
        request_headers.update(headers)
    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            resp_headers = dict(response.headers.items())
            if stream:
                chunk = b""
                try:
                    if hasattr(response, "read1"):
                        chunk = response.read1(SSE_SNIFF_BYTES)
                    else:  # pragma: no cover - urllib always exposes read1 on http(s)
                        chunk = response.read(SSE_SNIFF_BYTES)
                except OSError:
                    # headers already validated; body sniffing is best-effort
                    chunk = b""
                body = chunk
            else:
                body = response.read(MAX_JSON_BODY_BYTES)
            return HttpResponse(status=status, headers=resp_headers, body=body)
    except urllib.error.HTTPError as exc:  # HTTP-level errors still carry a response
        try:
            body = exc.read(MAX_JSON_BODY_BYTES)
        except OSError:
            body = b""
        return HttpResponse(status=int(exc.code), headers=dict(exc.headers.items()), body=body)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", None) or exc
        return HttpResponse(status=None, headers={}, body=b"", error=f"{type(reason).__name__}: {reason}")
    except Exception as exc:  # noqa: BLE001 -- defensive net for exotic transports
        return HttpResponse(status=None, headers={}, body=b"", error=f"{type(exc).__name__}: {exc}")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _config_from_env_and_args(args: argparse.Namespace) -> SmokeConfig:
    base_url = args.base_url or os.getenv("SMOKE_BASE_URL") or os.getenv("BASE_URL")
    if not base_url:
        raise ConfigError(
            "SMOKE_BASE_URL (or BASE_URL) is required. "
            "Usage: SMOKE_BASE_URL=https://api.example.com SMOKE_EMAIL=... "
            "SMOKE_PASSWORD=... python scripts/ci/production_smoke_test.py"
        )
    base_url = base_url.strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise ConfigError(f"SMOKE_BASE_URL must start with http:// or https:// (got: {base_url!r})")

    raw_timeout = args.timeout if args.timeout is not None else os.getenv("SMOKE_TIMEOUT")
    if raw_timeout is None or raw_timeout == "":
        timeout = DEFAULT_TIMEOUT
    else:
        try:
            timeout = float(raw_timeout)
        except (TypeError, ValueError):
            raise ConfigError(f"SMOKE_TIMEOUT must be a number of seconds (got: {raw_timeout!r})")
        if timeout <= 0:
            raise ConfigError(f"SMOKE_TIMEOUT must be > 0 (got: {timeout})")

    email = os.getenv("SMOKE_EMAIL")
    password = os.getenv("SMOKE_PASSWORD")
    skip_auth = args.skip_auth or _is_truthy(os.getenv("SMOKE_SKIP_AUTH"))
    chat_prompt = os.getenv("SMOKE_CHAT_PROMPT") or "smoke test ping"

    return SmokeConfig(
        base_url=base_url,
        email=email.strip() if email else None,
        password=password if password else None,
        timeout=timeout,
        skip_auth=skip_auth,
        chat_prompt=chat_prompt,
    )


def _print_header(cfg: SmokeConfig, auth_mode: str) -> None:
    print("=== SupremeAI Production Smoke Test ===")
    print(f"Base URL : {cfg.base_url}")
    print(f"Timeout  : {cfg.timeout:g}s per request")
    print(f"Auth     : {auth_mode}")
    print("-" * 72)


def run_smoke(cfg: SmokeConfig, echo: Callable[[str], None] = print) -> tuple[list[StepResult], int]:
    """Execute the smoke steps; returns (results, exit_code). Never raises."""

    class StepFailure(Exception):
        """Required check violated — FAIL."""

    class StepSkip(Exception):
        """Step not applicable — SKIPPED (never fails the run)."""

    class StepWarn(Exception):
        """Optional check degraded — WARN (never fails the run)."""

    results: list[StepResult] = []

    def run_step(name: str, required: bool, fn: Callable[[], str]) -> None:
        started = time.monotonic()
        try:
            detail = fn()
            outcome = "PASS"
        except StepSkip as exc:
            detail = str(exc)
            outcome = "SKIP"
        except StepWarn as exc:
            detail = f"{exc} — optional, not blocking"
            outcome = "WARN"
        except StepFailure as exc:
            detail = str(exc)
            outcome = "FAIL"
        except Exception as exc:  # noqa: BLE001 -- unexpected; treat as failure, keep running
            detail = f"unexpected error: {type(exc).__name__}: {exc}"
            outcome = "FAIL"
        seconds = time.monotonic() - started
        results.append(StepResult(name=name, outcome=outcome, detail=detail, seconds=seconds))
        suffix = "" if required else " (optional)"
        echo(f"[{len(results)}/6] {name:<24} {outcome}{suffix:<12} {seconds:6.2f}s  {detail}")

    def expect(response: HttpResponse, want: int, what: str) -> None:
        if response.error is not None:
            raise StepFailure(f"{what}: network error — {response.error}")
        if response.status != want:
            raise StepFailure(f"{what}: expected HTTP {want}, got {response.status} — {response.body_text()}")

    creds_present = bool(cfg.email and cfg.password)
    auth_mode = "enabled"
    if cfg.skip_auth:
        auth_mode = "skipped (SMOKE_SKIP_AUTH=true)"
    elif not creds_present:
        auth_mode = "skipped (SMOKE_EMAIL/SMOKE_PASSWORD missing)"

    _print_header(cfg, auth_mode)

    token: str | None = None

    def guard_auth() -> None:
        """Raise StepSkip when steps 3-6 do not apply."""
        if cfg.skip_auth:
            raise StepSkip("SMOKE_SKIP_AUTH=true")
        if not creds_present:
            raise StepSkip("SMOKE_EMAIL/SMOKE_PASSWORD missing")
        if not token:
            raise StepSkip("no token available (login step failed)")

    # -- 1. Liveness ----------------------------------------------------------
    def step_health_live() -> str:
        resp = _http("GET", _join_url(cfg.base_url, HEALTH_LIVE_PATH), timeout=cfg.timeout)
        expect(resp, 200, "liveness probe")
        return "HTTP 200"

    run_step("health/liveness", True, step_health_live)

    # -- 2. Readiness ---------------------------------------------------------
    def step_health_ready() -> str:
        resp = _http("GET", _join_url(cfg.base_url, HEALTH_READY_PATH), timeout=cfg.timeout)
        expect(resp, 200, "readiness probe")
        return "HTTP 200"

    run_step("health/readiness", True, step_health_ready)

    # -- 3. Login -------------------------------------------------------------
    def step_login() -> str:
        if cfg.skip_auth:
            raise StepSkip("SMOKE_SKIP_AUTH=true")
        if not creds_present:
            raise StepSkip("SMOKE_EMAIL/SMOKE_PASSWORD missing")
        nonlocal token
        resp = _http(
            "POST",
            _join_url(cfg.base_url, LOGIN_PATH),
            headers={"Content-Type": "application/json"},
            json_body={"username": cfg.email, "password": cfg.password},
            timeout=cfg.timeout,
        )
        expect(resp, 200, "login")
        try:
            payload = json.loads(resp.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise StepFailure("login: 200 but body is not valid JSON")
        token = payload.get("access_token")
        if not token or not isinstance(token, str):
            raise StepFailure("login: 200 but no access_token in response")
        role = payload.get("role", "?")
        return f"HTTP 200, access_token received (role={role})"

    run_step("auth/login", True, step_login)

    # -- 4. Identity ----------------------------------------------------------
    def step_me() -> str:
        guard_auth()
        resp = _http(
            "GET",
            _join_url(cfg.base_url, ME_PATH),
            headers=_bearer(token),
            timeout=cfg.timeout,
        )
        expect(resp, 200, "identity (/auth/me)")
        try:
            payload = json.loads(resp.body.decode("utf-8"))
            user_id = payload.get("user_id")
        except (ValueError, UnicodeDecodeError):
            user_id = None
        return f"HTTP 200, user_id={user_id or '?'}"

    run_step("auth/me", True, step_me)

    # -- 5. Chat stream (OPTIONAL — warnings never fail the run) --------------
    def step_chat() -> str:
        guard_auth()
        resp = _http(
            "POST",
            _join_url(cfg.base_url, CHAT_STREAM_PATH),
            headers=_bearer(token),
            json_body={"prompt": cfg.chat_prompt},
            timeout=cfg.timeout,
            stream=True,
        )
        if resp.error is not None:
            raise StepWarn(f"chat stream: network error — {resp.error}")
        if resp.status != 200:
            raise StepWarn(f"chat stream: expected HTTP 200, got {resp.status} — {resp.body_text()}")
        if not resp.is_stream:
            raise StepWarn(f"chat stream: expected text/event-stream, got {resp.content_type!r}")
        return f"HTTP 200 + text/event-stream ({len(resp.body)}B sniffed, connection closed)"

    run_step("chat/stream", False, step_chat)

    # -- 6. Logout + token revocation ----------------------------------------
    def step_logout() -> str:
        guard_auth()
        resp = _http(
            "POST",
            _join_url(cfg.base_url, LOGOUT_PATH),
            headers=_bearer(token),
            timeout=cfg.timeout,
        )
        expect(resp, 200, "logout")
        # The access token must now be rejected on /auth/me.
        me_after = _http("GET", _join_url(cfg.base_url, ME_PATH), headers=_bearer(token), timeout=cfg.timeout)
        if me_after.error is not None:
            raise StepFailure(f"post-logout /auth/me: network error — {me_after.error}")
        if me_after.status == 200:
            raise StepFailure(
                "post-logout /auth/me still returns 200 — token was NOT revoked "
                "(if logout was 200, this usually means the Redis-backed jti "
                "blacklist is unreachable: revocation is fail-open for "
                "non-admin users, see api/routes/auth.py:170)"
            )
        if me_after.status != 401:
            raise StepFailure(f"post-logout /auth/me: expected 401, got {me_after.status}")
        return "logout 200, token rejected afterwards (401 on /auth/me)"

    run_step("auth/logout+revoke", True, step_logout)

    # -- Summary --------------------------------------------------------------
    failed = [r for r in results if r.outcome == "FAIL"]
    code = 1 if failed else 0
    counts = {k: sum(1 for r in results if r.outcome == k) for k in ("PASS", "FAIL", "SKIP", "WARN")}
    total = sum(r.seconds for r in results)
    print("-" * 72)
    print(
        f"Summary: PASS {counts['PASS']} | FAIL {counts['FAIL']} | "
        f"SKIP {counts['SKIP']} | WARN {counts['WARN']} | total {total:.2f}s"
    )
    for r in failed:
        print(f"  FAILED: {r.name} — {r.detail}")
    print(f"RESULT: {'FAIL' if failed else 'PASS'} (exit {code})")
    return results, code


# ---------------------------------------------------------------------------
# Self-test: exercises the full run_smoke() logic against an embedded fixture
# HTTP server on localhost. No external network access, stdlib only.
# ---------------------------------------------------------------------------

FIXTURE_TOKEN = "fixture-token-123"
FIXTURE_EMAIL = "smoke@fixture.test"
FIXTURE_PASSWORD = "fixture-pass"


class _FixtureState:
    def __init__(self, *, login_ok: bool = True, chat_ok: bool = True) -> None:
        self.login_ok = login_ok
        self.chat_ok = chat_ok
        self.revoked: set[str] = set()

    def authorized(self, handler: BaseHTTPRequestHandler) -> bool:
        header = handler.headers.get("Authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else ""
        return bool(token) and token not in self.revoked


def _make_fixture_handler(state: _FixtureState) -> type[BaseHTTPRequestHandler]:
    class FixtureHandler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # silence request logging
            pass

        def _send(self, code: int, payload: Any, content_type: str = "application/json") -> None:
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return {}

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == HEALTH_LIVE_PATH:
                self._send(200, {"status": "ok"})
            elif path == HEALTH_READY_PATH:
                self._send(200, {"status": "ready"})
            elif path == ME_PATH:
                if state.authorized(self):
                    self._send(200, {"user_id": "user-1", "role": "user", "scopes": [], "email": FIXTURE_EMAIL})
                else:
                    self._send(401, {"detail": "Not authenticated"})
            else:
                self._send(404, {"detail": "not found"})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == LOGIN_PATH:
                body = self._json_body()
                creds_ok = (
                    state.login_ok
                    and (body.get("username") or body.get("email")) == FIXTURE_EMAIL
                    and body.get("password") == FIXTURE_PASSWORD
                )
                if creds_ok:
                    self._send(
                        200,
                        {
                            "access_token": FIXTURE_TOKEN,
                            "refresh_token": "fixture-refresh",
                            "token_type": "bearer",
                            "user_id": "user-1",
                            "role": "user",
                        },
                    )
                else:
                    self._send(401, {"detail": "Invalid credentials"})
            elif path == ME_PATH:
                if state.authorized(self):
                    self._send(200, {"user_id": "user-1", "role": "user", "scopes": []})
                else:
                    self._send(401, {"detail": "Not authenticated"})
            elif path == CHAT_STREAM_PATH:
                if not state.chat_ok:
                    self._send(404, {"detail": "chat disabled in fixture"})
                elif not state.authorized(self):
                    self._send(401, {"detail": "Authorization required"})
                else:
                    sse = b'event: delta\ndata: {"text": "pong"}\n\nevent: done\ndata: [DONE]\n\n'
                    self._send(200, sse, content_type="text/event-stream")
            elif path == LOGOUT_PATH:
                if not state.authorized(self):
                    self._send(401, {"detail": "Not authenticated"})
                else:
                    header = self.headers.get("Authorization", "")
                    state.revoked.add(header[7:].strip())
                    self._send(200, {"status": "logged_out"})
            else:
                self._send(404, {"detail": "not found"})

    return FixtureHandler


class _FixtureServer:
    """Context manager running a fixture HTTP server on an ephemeral port."""

    def __init__(self, state: _FixtureState) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _make_fixture_handler(state))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self._thread.start()
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()


def self_test() -> int:
    """Run embedded-fixture scenarios against the real run_smoke() logic."""
    failures: list[str] = []

    def check(label: str, condition: bool) -> None:
        print(f"  {'PASS' if condition else 'FAIL'}: {label}")
        if not condition:
            failures.append(label)

    def make_cfg(base_url: str, **overrides: Any) -> SmokeConfig:
        defaults: dict[str, Any] = {
            "email": FIXTURE_EMAIL,
            "password": FIXTURE_PASSWORD,
            "timeout": 5.0,
            "skip_auth": False,
            "chat_prompt": "ping",
        }
        defaults.update(overrides)
        return SmokeConfig(base_url=base_url, **defaults)

    # Scenario 1: happy path — everything passes, exit 0.
    print("Scenario 1: full critical path (auth enabled)")
    with _FixtureServer(_FixtureState()) as base_url:
        results, code = run_smoke(make_cfg(base_url), echo=lambda _line: None)
    by_name = {r.name: r for r in results}
    check("exit code is 0", code == 0)
    check("all six steps present", len(results) == 6)
    check("all steps PASS", all(r.outcome == "PASS" for r in results))
    check("login captured token", by_name["auth/login"].outcome == "PASS")
    check("chat stream PASS", by_name["chat/stream"].outcome == "PASS")
    check("logout+revoke validated", by_name["auth/logout+revoke"].outcome == "PASS")

    # Scenario 2: skip-auth — health only, auth steps SKIPPED, exit 0.
    print("Scenario 2: SMOKE_SKIP_AUTH=true (health-only)")
    with _FixtureServer(_FixtureState()) as base_url:
        results, code = run_smoke(make_cfg(base_url, skip_auth=True), echo=lambda _line: None)
    check("exit code is 0", code == 0)
    check("health steps PASS", all(r.outcome == "PASS" for r in results[:2]))
    check("steps 3-6 SKIPPED", all(r.outcome == "SKIP" for r in results[2:]))

    # Scenario 3: bad credentials — login FAIL, exit 1.
    print("Scenario 3: invalid credentials")
    with _FixtureServer(_FixtureState(login_ok=False)) as base_url:
        results, code = run_smoke(make_cfg(base_url), echo=lambda _line: None)
    check("exit code is 1", code == 1)
    check("login FAIL", any(r.name == "auth/login" and r.outcome == "FAIL" for r in results))

    # Scenario 4: chat endpoint unavailable — WARN only, exit 0.
    print("Scenario 4: chat endpoint unavailable (must be WARN, not FAIL)")
    with _FixtureServer(_FixtureState(chat_ok=False)) as base_url:
        results, code = run_smoke(make_cfg(base_url), echo=lambda _line: None)
    check("exit code is 0", code == 0)
    check("chat step WARN", any(r.name == "chat/stream" and r.outcome == "WARN" for r in results))
    check("required steps still PASS", all(r.outcome != "FAIL" for r in results))

    # Scenario 5: missing credentials — auth steps SKIPPED, exit 0.
    print("Scenario 5: credentials missing")
    with _FixtureServer(_FixtureState()) as base_url:
        results, code = run_smoke(make_cfg(base_url, email=None, password=None), echo=lambda _line: None)
    check("exit code is 0", code == 0)
    check("steps 3-6 SKIPPED", all(r.outcome == "SKIP" for r in results[2:]))

    # Scenario 6: config handling — helpers and env parsing.
    print("Scenario 6: config parsing")
    check("_join_url strips slashes", _join_url("https://x/", "/health/live") == "https://x/health/live")
    check("_is_truthy accepts true/1/YES", _is_truthy("true") and _is_truthy("1") and _is_truthy("YES"))
    check("_is_truthy rejects false/0/none", not _is_truthy("false") and not _is_truthy("0") and not _is_truthy(None))

    env_keys = ("SMOKE_BASE_URL", "BASE_URL", "SMOKE_TIMEOUT", "SMOKE_SKIP_AUTH")
    old_env = {k: os.environ.get(k) for k in env_keys}
    try:
        ns = argparse.Namespace(base_url=None, timeout=None, skip_auth=False)
        for key in env_keys:
            os.environ.pop(key, None)
        try:
            _config_from_env_and_args(ns)
            check("missing base URL raises ConfigError", False)
        except ConfigError as exc:
            check("missing base URL raises ConfigError", "SMOKE_BASE_URL" in str(exc))

        os.environ["SMOKE_BASE_URL"] = "https://api.example.com/"
        os.environ["SMOKE_TIMEOUT"] = "12.5"
        os.environ["SMOKE_SKIP_AUTH"] = "true"
        cfg = _config_from_env_and_args(ns)
        check("base URL normalised", cfg.base_url == "https://api.example.com")
        check("timeout from env", cfg.timeout == 12.5)
        check("skip_auth from env", cfg.skip_auth is True)

        os.environ["SMOKE_TIMEOUT"] = "not-a-number"
        try:
            _config_from_env_and_args(ns)
            check("bad SMOKE_TIMEOUT raises ConfigError", False)
        except ConfigError:
            check("bad SMOKE_TIMEOUT raises ConfigError", True)
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    print("-" * 72)
    if failures:
        print(f"SELF-TEST RESULT: FAIL ({len(failures)} failing check(s))")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("SELF-TEST RESULT: PASS (all scenarios)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Critical-path production smoke test (stdlib-only). See module docstring for usage.",
    )
    parser.add_argument("--base-url", default=None, help="Override SMOKE_BASE_URL/BASE_URL")
    parser.add_argument("--timeout", type=float, default=None, help="Per-request timeout in seconds (default 30)")
    parser.add_argument("--skip-auth", action="store_true", help="Run health checks only (skip steps 3-6)")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the embedded fixture-based self-test (no network, no env config needed)",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    try:
        cfg = _config_from_env_and_args(args)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    _results, code = run_smoke(cfg)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
