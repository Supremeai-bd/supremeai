#!/usr/bin/env python3
"""Shared zero-credential MCP client for the watchdog fleet.

Why this module exists
----------------------
Four watchers (`bridge_intake_gate_watchdog`, `bridge_landing_watchdog`,
`open_core_sync_staleness_watchdog`, `pr_landing_age_guard`) each carried their
own copy of `_rpc` — a ~50-line JSON-RPC-over-HTTP client with SSE handling,
retry backoff and session negotiation. The copies had drifted: `attempts`
defaulted to 3 in three of them and 4 in another, and the docstrings referred to
each other ("bridge_landing_watchdog `_rpc` shape") as the canonical source,
which none of them actually was.

The drift only became visible when the hardcoded host literals were removed and
the files became byte-identical over that span; the repo's anti-duplication gate
then reported 9 new clones. Extracting is the fix the gate asks for — the clones
were real, they just used to be masked by one differing line.

Contract
--------
`rpc(method, params=None, session_id=None, notify=False, attempts=3)`
    -> (payload: dict, session_id: str | None)

* Sends JSON-RPC 2.0 over streamable HTTP.
* Carries `MCP-Protocol-Version` on every post-initialize request (spec
  revision >= 2025-06-18).
* Reads the WHOLE body: the tower's runs surface can exceed 100 KB on one line,
  and line-iterating clients truncate it mid-line (documented live 2026-10-30).
* Retries with linear backoff (3s, 6s, 9s...), then re-raises.
* Parses `text/event-stream` payloads by scanning `data:` lines; a malformed
  line is skipped rather than failing the call, which is the behaviour every
  caller already depended on.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repo_paths import svc  # noqa: E402

#: Protocol revision negotiated with the tower.
PROTOCOL_VERSION = "2025-11-25"

#: Monotonic JSON-RPC request id, shared across calls in a process.
_id = [0]


def tower_url() -> str:
    """The MCP tower endpoint (env `RENDER_MCP_URL` wins, then the registry)."""
    return svc("mcp", "/mcp")


def rpc(
    method: str,
    params: dict | None = None,
    session_id: str | None = None,
    notify: bool = False,
    attempts: int = 3,
    url: str | None = None,
    timeout: float = 30.0,
):
    """One JSON-RPC call. Returns ``(payload, session_id)``.

    ``attempts`` is the retry count INCLUDING the first try, matching the
    watchers' original semantics (worst case 3+6+9s at the default).
    """
    payload: dict = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        payload["params"] = params
    if not notify:
        _id[0] += 1
        payload["id"] = _id[0]

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    endpoint = url or tower_url()
    if not endpoint:
        raise RuntimeError(
            "no MCP tower URL configured: set RENDER_MCP_URL or add `mcp` to "
            "config/service_registry.yaml"
        )

    last = None
    sid = session_id
    body = ctype = ""
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id") or sid
                body = resp.read().decode("utf-8", errors="replace")
                ctype = resp.headers.get("Content-Type") or ""
                break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(3 * (attempt + 1))
    else:
        raise last  # type: ignore[misc]

    if "text/event-stream" in ctype:
        for line in body.splitlines():
            if line.startswith("data:"):
                try:
                    return json.loads(line[5:].strip()), sid
                except ValueError:
                    # SSE lines are individually skippable by design: the
                    # stream interleaves keep-alives with payloads.
                    continue
    if not body.strip():
        return {"accepted": True}, sid
    return json.loads(body), sid


#: Pagination ladder for tower.bridge.work_queue. The deployed tower may still
#: be running the pre-r2 single-page handler while a redeploy lags, so ask for
#: 200 first (an r2 tower paginates fully), then 50 (the pre-r2 cap), then the
#: tower default. A rung that answers is served as-is, never retried.
QUEUE_LIMIT_LADDER: tuple = (200, 50, None)


def fetch_work_orders(fetch_text):
    """Open work orders across the queue-fidelity deploy window.

    Shared by the bridge landing watchdog and the verdict-plane gap probe.
    See QUEUE_LIMIT_LADDER for why the ladder exists.
    """
    last_err: Exception = RuntimeError("queue ladder exhausted")
    for limit in QUEUE_LIMIT_LADDER:
        arguments = {} if limit is None else {"limit": limit}
        try:
            payload = json.loads(fetch_text("bridge.work_queue", arguments))
        except json.JSONDecodeError as err:  # error-envelope text, not JSON
            last_err = err
            continue
        if not isinstance(payload, dict) or payload.get("isError"):
            last_err = TypeError(f"queue rung {limit} answered a non-payload")
            continue
        return (payload.get("workOrders", []) or [], limit)
    raise last_err


def text_of(res) -> str:
    """Concatenate the `text` parts of a tool-call result."""
    content = res.get("result", {}).get("content", []) if isinstance(res, dict) else []
    return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))


def tower_text(name: str, arguments: dict, *, client: str = "watchdog") -> str:
    """Initialize, acknowledge, then call one tool and return its text."""
    _, sid = rpc(
        "initialize",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": client, "version": "1.0"},
        },
    )
    rpc("notifications/initialized", {}, session_id=sid, notify=True)
    res, _ = rpc("tools/call", {"name": name, "arguments": arguments}, session_id=sid)
    return text_of(res)


if __name__ == "__main__":  # pragma: no cover - manual probe
    print("tower:", tower_url() or "(unconfigured)")
