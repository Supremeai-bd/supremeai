#!/usr/bin/env python3
"""zero_cost_capacity_probe.py — how much free capacity does one account
actually give us, per SURFACE?

The question this answers
-------------------------
"One Google account = one API key, but the web session gives me another ~2.5
keys' worth, so I can get 3–5 keys' benefit from one account." That arithmetic
is structurally right and operationally misleading, because quota is not
counted per account — it is counted **per surface**:

* a keyed free tier bucket (RPM + RPD per project/key, rotated by
  `core/llm/llm_gateway/registry.py::_ProviderKeyPool`, which already splits a
  comma-joined `GEMINI_API_KEY="k1,k2,k3"` into separately-cooled keys);
* a web/UI bucket that belongs to the browser session, not to the key
  (`AI_FLEET_COOKIES_GZIP_B64`, `BLAZE_SESSION_JWT`, `CHATGPT_SESSION_TOKEN` —
  the same names `gateway/dual_pool_priority_router.py` already reads for its
  `supremeai-web` pool).

Multiplying buckets multiplies**quota**, not **throughput**: keyed surfaces run
in parallel under an RPM budget, while a web session is ~one concurrent
operation, serialized, and loses streaming first-token latency. So before any
routing is built on top of this, the carry question is measurable: which
surfaces are configured, are they alive, and what does the provider say about
the remaining budget?

What this does
--------------
* `--check` (default): no network. Counts configured keys per keyed surface
  (comma-joined values and `_N` numbered variants), reports web-session
  presence as a boolean, and prints the zero-cost ladder with the gaps named.
  **Never prints a secret value** — only how many keys exist and where they
  were found.
* `--live`: still spends no tokens. Each keyed surface is probed with a GET on
  its models endpoint (OpenRouter additionally reads `/api/v1/key`, which
  reports the account's own limit/usage). Classified as
  `ALIVE` / `EXPIRED` / `CHALLENGED` / `UNKNOWN` with latency.
* `--json`: machine-readable report (for an admin dashboard later).
* `--strict`: exit 2 when no keyed surface is configured at all. Without it a
  missing surface is informational, not a failure.

Exit codes: 0 ok · 1 unexpected error · 2 `--strict` and nothing configured.

Usage:
    python scripts/ops/zero_cost_capacity_probe.py
    python scripts/ops/zero_cost_capacity_probe.py --live
    python scripts/ops/zero_cost_capacity_probe.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Keyed surfaces: (surface name, env names in priority order, models endpoint).
# The endpoint is used only for liveness — a GET on a models listing costs no
# tokens, so `--live` can be run as often as an operator likes.
KEYED_SURFACES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("gemini", ("GEMINI_API_KEY",), "https://generativelanguage.googleapis.com/v1beta/models"),
    ("openrouter", ("OPENROUTER_API_KEY",), "https://openrouter.ai/api/v1/models"),
    ("groq", ("GROQ_API_KEY",), "https://api.groq.com/openai/v1/models"),
    ("nvidia", ("NVIDIA_API_KEY",), "https://integrate.api.nvidia.com/v1/models"),
    ("kilo", ("KILO_API_KEY", "KILOCODE_API_KEY"), "https://ai-gateway.kilo.ai/api/v1/models"),
)

# Web/session surfaces: quota that belongs to a browser session, not a key.
# Presence only — this probe never claims a session is usable, because liveness
# for these needs a real request against the site (see the bridge plan).
WEB_SURFACES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ai-fleet-cookie-bundle", ("AI_FLEET_COOKIES_GZIP_B64",)),
    ("chatgpt-web", ("CHATGPT_SESSION_TOKEN", "CHATGPT_WEB_TOKEN")),
    ("blaze-claude-web", ("BLAZE_SESSION_JWT",)),
    ("codegeex-web", ("CODEGEEX_TOKEN", "CODEGEEX_SESSION_KEY")),
    ("cline-web", ("CLINE_TOKEN", "CLINE_API_KEY")),
    ("codegpt-web", ("CODEGPT_TOKEN",)),
)

ALIVE = "ALIVE"
EXPIRED = "EXPIRED"
CHALLENGED = "CHALLENGED"
UNKNOWN = "UNKNOWN"

_SECRET_MARKER = "***"


def mask(_value: str) -> str:
    """Secrets never leave the process; counts do, values do not."""
    return _SECRET_MARKER


def split_keys(raw: str | None) -> list[str]:
    """Split a comma-joined multi-key value, dropping blanks.

    Matches `_ProviderKeyPool` (registry.py:94) so this probe reports the same
    key count the router will actually rotate over.
    """
    if not raw:
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def numbered_keys(env: dict[str, str], base: str) -> list[str]:
    """Collect `BASE_1..BASE_n` style keys (the verifier's fallback convention)."""
    found: list[str] = []
    index = 1
    while (value := env.get(f"{base}_{index}", "").strip()):
        found.append(value)
        index += 1
    return found


def keys_for(env: dict[str, str], names: tuple[str, ...]) -> list[str]:
    """All keys configured for a surface, in the order the router would use."""
    collected: list[str] = []
    for name in names:
        collected.extend(split_keys(env.get(name)))
        collected.extend(numbered_keys(env, name))
    return collected


def classify(status: int) -> str:
    """Map an HTTP status onto the three states an operator can act on."""
    if 200 <= status < 300:
        return ALIVE
    if status in (401, 403):
        return EXPIRED
    if status in (428, 429):
        return CHALLENGED
    return UNKNOWN


def keyed_report(env: dict[str, str], live: bool, timeout: float = 10.0) -> list[dict]:
    """Describe every keyed surface. `live=False` performs no network I/O."""
    rows: list[dict] = []
    for surface, names, endpoint in KEYED_SURFACES:
        keys = keys_for(env, names)
        row: dict = {
            "surface": surface,
            "kind": "keyed",
            "configured_keys": len(keys),
            "env_names": [n for n in names if env.get(n)],
            "status": "NOT_CONFIGURED" if not keys else "CONFIGURED",
            "latency_ms": None,
            "detail": "",
        }
        if live and keys:
            row.update(probe_endpoint(endpoint, keys[0], timeout=timeout))
        rows.append(row)
    return rows


def web_report(env: dict[str, str]) -> list[dict]:
    """Presence of session surfaces — never upgraded to `ALIVE` without a real call."""
    rows: list[dict] = []
    for surface, names in WEB_SURFACES:
        present = [n for n in names if env.get(n)]
        rows.append({
            "surface": surface,
            "kind": "web-session",
            "configured_keys": len(present),
            "env_names": present,
            "status": "PRESENT" if present else "NOT_CONFIGURED",
            "latency_ms": None,
            # A configured cookie is not a live session; saying otherwise is the
            # silent failure this probe exists to prevent.
            "detail": "presence only — liveness needs a site request",
        })
    return rows


def probe_endpoint(endpoint: str, key: str, timeout: float = 10.0) -> dict:
    """GET a models listing (no token spend) and classify the response."""
    request = urllib.request.Request(
        endpoint,
        headers={
            "Authorization": f"Bearer {key}",
            "x-api-key": key,
            "x-goog-api-key": key,
            "User-Agent": "supremeai-capacity-probe/1",
        },
        method="GET",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            elapsed = int((time.monotonic() - started) * 1000)
            return {"status": classify(response.status), "latency_ms": elapsed,
                    "detail": f"HTTP {response.status}"}
    except urllib.error.HTTPError as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return {"status": classify(exc.code), "latency_ms": elapsed,
                "detail": f"HTTP {exc.code}"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return {"status": UNKNOWN, "latency_ms": elapsed,
                "detail": f"{type(exc).__name__}"}


def ladder(rows: list[dict]) -> list[tuple[str, str, str]]:
    """The zero-cost order routes should be tried in, with the reason.

    Paid is not a rung: the policy is zero cost or nothing.
    """
    keyed_alive = [r["surface"] for r in rows if r["kind"] == "keyed" and r["configured_keys"]]
    web_present = [r["surface"] for r in rows if r["kind"] == "web-session" and r["configured_keys"]]
    return [
        ("L0 keyed free tier (parallel, RPM-budgeted)",
         ", ".join(keyed_alive) or "none configured",
         "rotate keys; a 429 cools one key, the pool moves on"),
        ("L1 free vision roster (keyed, no session)",
         ", ".join(keyed_alive) or "none configured",
         "images should stay on free keyed vision before any session is used"),
        ("L2 web/session bridge (serialized, fallback only)",
         ", ".join(web_present) or "none configured",
         "~one concurrent op, no streaming guarantee, session can die silently"),
        ("L3 paid", "blocked by policy", "never selected implicitly"),
    ]


def render(rows: list[dict], as_json: bool) -> str:
    if as_json:
        return json.dumps(
            {"surfaces": rows, "ladder": ladder(rows)},
            indent=2,
            ensure_ascii=False,
        )
    lines = ["| surface | kind | keys | status | latency | note |", "| --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        latency = f"{row['latency_ms']} ms" if row.get("latency_ms") is not None else "—"
        lines.append(
            f"| `{row['surface']}` | {row['kind']} | {row['configured_keys']} | "
            f"{row['status']} | {latency} | {row['detail'] or '—'} |"
        )
    lines.append("")
    lines.append("| rung | surfaces | rule |")
    lines.append("| --- | --- | --- |")
    for name, surfaces, rule in ladder(rows):
        lines.append(f"| {name} | {surfaces} | {rule} |")
    return "\n".join(lines)


def _self_test() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failures.append(name)

    check("split: blanks dropped", split_keys(" a , b ,, c ") == ["a", "b", "c"])
    check("split: empty is empty", split_keys("") == [] and split_keys(None) == [])
    check("numbered: stops at gap",
          numbered_keys({"K_1": "x", "K_2": "y", "K_4": "z"}, "K") == ["x", "y"])
    check("keys_for: merges value and numbered",
          len(keys_for({"GEMINI_API_KEY": "a,b", "GEMINI_API_KEY_1": "c"}, ("GEMINI_API_KEY",))) == 3)
    check("classify: 200 alive", classify(200) == ALIVE)
    check("classify: 401/403 expired", classify(401) == EXPIRED and classify(403) == EXPIRED)
    check("classify: 429 challenged", classify(429) == CHALLENGED)
    check("classify: 500 unknown", classify(500) == UNKNOWN)

    secret = "sk-do-not-print-123456"
    env = {"GEMINI_API_KEY": secret, "BLAZE_SESSION_JWT": secret}
    rows = keyed_report(env, live=False) + web_report(env)
    rendered = render(rows, as_json=False) + render(rows, as_json=True)
    check("secrets never rendered", secret not in rendered)
    check("mask never returns the value", secret not in mask(secret))
    check("web presence is not liveness",
          next(r for r in rows if r["surface"] == "blaze-claude-web")["status"] == "PRESENT")
    check("missing surface is informational",
          next(r for r in rows if r["surface"] == "groq")["status"] == "NOT_CONFIGURED")
    check("ladder keeps paid blocked",
          any("blocked by policy" in surfaces for _, surfaces, _ in ladder(rows)))

    if failures:
        print(f"self-test: {len(failures)} failed")
        for name in failures:
            print(f"  FAIL {name}")
        return 1
    print(f"self-test: {11} / 11 passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Zero-cost capacity probe (per surface)")
    parser.add_argument("--check", action="store_true", help="config only, no network (default)")
    parser.add_argument("--live", action="store_true", help="probe models endpoints (no token spend)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--strict", action="store_true", help="exit 2 when no keyed surface exists")
    parser.add_argument("--self-test", action="store_true", help="run built-in tests")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()

    env = dict(os.environ)
    rows = keyed_report(env, live=args.live) + web_report(env)
    print(render(rows, as_json=args.json))

    if args.strict and not any(r["kind"] == "keyed" and r["configured_keys"] for r in rows):
        print("strict: no keyed surface configured", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
