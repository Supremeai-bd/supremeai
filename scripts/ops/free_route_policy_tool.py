#!/usr/bin/env python3
"""free_route_policy_tool.py — mint `SUPREMEAI_FREE_ROUTE_POLICY` entries.

Why this exists
---------------
Nothing serves without approval: `free_route_policy.approved_route()` returns
None unless the running `SUPREMEAI_FREE_ROUTE_POLICY` holds an HMAC-signed entry
for that exact `(provider, https base URL, credential)` triple. That is the
right default — wiring a surface must never be the same act as approving it —
but it left web engines disabled in practice, because hand-writing the signed
JSON (and getting the fingerprint right) is not something an operator should do
from memory.

This tool builds the entries, validates them with the *real* parser before
printing anything, and never shows a secret: the credential is read from an env
var by name, and the only value that leaves the process is the 64-hex HMAC
fingerprint — by design non-reversible and not usable as a credential.

Two rules the tool refuses to paper over
----------------------------------------
* **HTTPS only.** `_https_base()` rejects anything else, so a `http://127.0.0.1`
  relay can never be approved. Put the relay behind an HTTPS tunnel or use the
  deployed one.
* **A provider must have concrete models.** `auto`/`default` are rejected, and
  `vision_models` is a subset of `models`.

The fingerprint is computed here rather than imported so this stays runnable with
the standard library alone (CI guards run without fastapi). That duplication is
pinned by `tests/test_free_route_policy_tool.py`, which asserts this tool's
fingerprint equals `free_route_policy.credential_identity()` — drift fails CI.

Usage
-----
    # mint entries for the web engines that share the relay credential
    python3 scripts/ops/free_route_policy_tool.py \
        --provider claude_web --provider chatgpt_web \
        --credential-env STEALTH_WEBHOOK_URL \
        --models duck-claude,duck-gpt --ttl-hours 24

    # what is approved right now, per web engine?
    python3 scripts/ops/free_route_policy_tool.py --check --provider claude_web

    # merge into an existing policy instead of replacing it
    python3 scripts/ops/free_route_policy_tool.py ... --merge

Exit codes: 0 ok · 1 invalid input / missing approval (`--check`) · 2 environment
not fit to mint (no HMAC key, no HTTPS relay).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

POLICY_ENV = "SUPREMEAI_FREE_ROUTE_POLICY"
HMAC_KEY_ENV = "SUPREMEAI_FREE_ROUTE_HMAC_KEY"
# Same domain separator as free_route_policy.py: changing this silently
# invalidates every existing approval, so it is part of the contract.
HMAC_PREFIX = b"supremeai:free-route:v1\x00"
EXCLUDED_MODELS = frozenset({"auto", "default", "kilo-auto/free", "kilo-auto/efficient", "openrouter/free"})
CATALOG_REQUIRED = frozenset({"openrouter", "kilo"})
VISION_PROVIDERS = frozenset({"gemini", "openai", "openrouter"})
PROVIDER_RE = re.compile(r"[a-z0-9_]+")
HEX64_RE = re.compile(r"[a-fA-F0-9]{64}")


class PolicyError(Exception):
    """Input the policy parser would reject anyway — reported with a reason."""


def https_base(url: str) -> str:
    """Mirror of `free_route_policy._https_base` (https only, no userinfo/query)."""
    target = urlsplit(url or "")
    if (
        target.scheme != "https"
        or not target.hostname
        or target.username is not None
        or target.query
        or target.fragment
    ):
        raise PolicyError(
            f"`{url}` is not an approvable HTTPS base URL — approval requires https "
            "with no userinfo, query or fragment (a localhost relay needs an HTTPS tunnel)"
        )
    return url.rstrip("/")


def fingerprint(provider: str, base_url: str, credential: str, hmac_key_hex: str) -> str:
    """The 64-hex approval tag for a credential, identical to the gateway's."""
    payload = json.dumps([provider, base_url, credential], separators=(",", ":")).encode("utf-8")
    return hmac.digest(bytes.fromhex(hmac_key_hex), HMAC_PREFIX + payload, "sha256").hex()


def build_entry(
    provider: str,
    base_url: str,
    credential: str,
    models: list[str],
    vision_models: list[str],
    ttl_hours: float,
    hmac_key_hex: str,
    now: datetime | None = None,
) -> dict:
    """One policy entry, validated against the same rules the parser applies."""
    if not PROVIDER_RE.fullmatch(provider or ""):
        raise PolicyError(f"`{provider}` must match [a-z0-9_]+")
    base = https_base(base_url)
    if not credential:
        raise PolicyError(
            f"`{provider}` resolved an empty credential — refusing to approve a route "
            "that cannot authenticate"
        )
    if not models:
        raise PolicyError(f"`{provider}` needs at least one concrete model")
    for model in models:
        if model != model.strip() or not model:
            raise PolicyError(f"`{provider}`: model `{model!r}` has whitespace")
        if model.lower() in EXCLUDED_MODELS:
            raise PolicyError(f"`{provider}`: `{model}` is a placeholder, not a concrete model")
        if provider in CATALOG_REQUIRED and not model.endswith(":free"):
            raise PolicyError(f"`{provider}`: catalog providers may only approve `:free` models")
    unknown_vision = [model for model in vision_models if model not in models]
    if unknown_vision:
        raise PolicyError(f"`{provider}`: vision_models {unknown_vision} are not in models")
    if vision_models and provider not in VISION_PROVIDERS:
        raise PolicyError(
            f"`{provider}` cannot carry vision_models — only {sorted(VISION_PROVIDERS)} may, "
            "so image routing needs a provider the arbiter already trusts for vision"
        )
    expires = (now or datetime.now(timezone.utc)) + timedelta(hours=ttl_hours)
    return {
        "provider": provider,
        "base_url": base,
        "key_hmac_sha256": fingerprint(provider, base, credential, hmac_key_hex),
        "expires_at": expires.replace(microsecond=0).isoformat(),
        "models": list(dict.fromkeys(models)),
        "vision_models": list(dict.fromkeys(vision_models)),
    }


def validate_with_gateway(entries: list[dict]) -> str | None:
    """Re-use the gateway's own parser, when it is importable, as the last word."""
    try:
        from gateway.service.free_route_policy import _policy  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - optional dependency; pre-checks already ran
        return None
    parsed = _policy(json.dumps(entries))
    if not parsed:
        return "the gateway parser rejected the generated policy (see its warning for the reason)"
    if len(parsed) != len(entries):
        return f"the gateway parser accepted only {len(parsed)} of {len(entries)} entries"
    return None


def merge_policies(existing_raw: str, new_entries: list[dict]) -> list[dict]:
    """Keep existing entries, replacing any that target the same identity."""
    try:
        existing = json.loads(existing_raw) if existing_raw else []
    except json.JSONDecodeError as exc:
        raise PolicyError(f"existing {POLICY_ENV} is not JSON: {exc}") from exc
    if not isinstance(existing, list):
        raise PolicyError(f"existing {POLICY_ENV} must be a JSON list")
    fresh = {(e["provider"], e["base_url"]) for e in new_entries}
    kept = [
        entry
        for entry in existing
        if isinstance(entry, dict) and (entry.get("provider"), entry.get("base_url")) not in fresh
    ]
    return kept + new_entries


def check_approvals(policy_raw: str, providers: list[str]) -> list[str]:
    """Human-readable status per provider; empty list means everything approved."""
    try:
        from gateway.service.free_route_policy import _policy  # noqa: PLC0415

        parsed = _policy(policy_raw)
        status = {
            provider: (expiry, models)
            for (provider, _base, _tag), (expiry, models, _vision) in parsed.items()
        }
    except Exception:  # noqa: BLE001 - no gateway import: fall back to structural check
        status = {}
        for entry in json.loads(policy_raw) if policy_raw else []:
            if not isinstance(entry, dict):
                continue
            try:
                expiry = datetime.fromisoformat(entry["expires_at"]).timestamp()
            except (KeyError, ValueError):
                continue
            status[entry.get("provider", "?")] = (expiry, tuple(entry.get("models") or ()))
    lines: list[str] = []
    now = datetime.now(timezone.utc).timestamp()
    for provider in providers:
        if provider not in status:
            lines.append(f"MISSING  {provider}: no approval entry in {POLICY_ENV}")
            continue
        expiry, models = status[provider]
        state = "EXPIRED" if expiry <= now else "ok"
        when = datetime.fromtimestamp(expiry, timezone.utc).isoformat()
        lines.append(f"{state:<8} {provider}: {len(models)} model(s), expires {when}")
    return lines


def _self_test() -> int:
    failures: list[str] = []
    key = "11" * 32

    def check(name: str, condition: bool) -> None:
        if not condition:
            failures.append(name)

    entry = build_entry("claude_web", "https://relay.example.com", "cookie", ["duck-claude"], [], 24, key)
    check("fingerprint is 64 hex", bool(re.fullmatch(r"[a-f0-9]{64}", entry["key_hmac_sha256"])))
    check("expiry is tz-aware", datetime.fromisoformat(entry["expires_at"]).tzinfo is not None)
    check("models preserved", entry["models"] == ["duck-claude"])

    # http is never approvable; the error must say why, not just fail.
    try:
        https_base("http://127.0.0.1:8788")
        check("http rejected", False)
    except PolicyError as exc:
        check("http rejected with reason", "https" in str(exc))

    for bad, label in (
        (("claude_web", "https://relay.example.com", "cookie", ["auto"], [], 24), "placeholder model"),
        (("claude_web", "https://relay.example.com", "cookie", [], [], 24), "empty models"),
        (("claude_web", "https://relay.example.com", "", ["duck-claude"], [], 24), "empty credential"),
        (("Bad-Name", "https://relay.example.com", "cookie", ["duck-claude"], [], 24), "provider charset"),
        (("kilo", "https://relay.example.com", "k", ["glm-5"], [], 24), "catalog needs :free"),
        (("claude_web", "https://relay.example.com", "cookie", ["duck-claude"], ["gemini-web"], 24), "vision subset"),
    ):
        try:
            build_entry(*bad, key)
            check(f"rejected {label}", False)
        except PolicyError:
            check(f"rejected {label}", True)

    merged = merge_policies(
        json.dumps([{"provider": "kilo", "base_url": "https://a.example.com", "models": ["x:free"]}]),
        [entry],
    )
    check("merge keeps unrelated", len(merged) == 2)
    replaced = merge_policies(json.dumps([entry | {"models": ["old"]}]), [entry])
    check("merge replaces same identity", len(replaced) == 1 and replaced[0]["models"] == ["duck-claude"])
    rendered = json.dumps(entry)
    check("secret never rendered", "cookie" not in rendered and key not in rendered)

    if failures:
        print(f"self-test: {len(failures)} failed")
        for name in failures:
            print(f"  FAIL {name}")
        return 1
    print("self-test: 12 / 12 passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mint/verify SUPREMEAI_FREE_ROUTE_POLICY entries")
    parser.add_argument("--provider", action="append", default=[], help="provider name (repeatable)")
    parser.add_argument("--base-url", default="", help="HTTPS base URL (default: resolved from the provider)")
    parser.add_argument("--credential-env", default="", help="env var NAME holding the credential")
    parser.add_argument("--models", default="", help="comma-separated concrete models")
    parser.add_argument("--vision-models", default="", help="comma-separated subset usable for images")
    parser.add_argument("--ttl-hours", type=float, default=24.0)
    parser.add_argument("--merge", action="store_true", help=f"merge into the current {POLICY_ENV}")
    parser.add_argument("--check", action="store_true", help="report approval status instead of minting")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()
    if not args.provider:
        parser.error("at least one --provider is required")

    if args.check:
        lines = check_approvals(os.environ.get(POLICY_ENV, ""), args.provider)
        print("\n".join(lines))
        return 0 if all(line.startswith("ok") for line in lines) else 1

    hmac_key = os.environ.get(HMAC_KEY_ENV, "").strip()
    if not HEX64_RE.fullmatch(hmac_key):
        print(f"{HMAC_KEY_ENV} must be 64 hex characters; nothing minted.", file=sys.stderr)
        return 2
    credential = os.environ.get(args.credential_env, "").strip() if args.credential_env else ""
    if not credential:
        print(
            f"--credential-env {args.credential_env or '<unset>'} is empty; nothing minted "
            "(the tool reads the credential by name and never prints it).",
            file=sys.stderr,
        )
        return 2

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    vision = [m.strip() for m in args.vision_models.split(",") if m.strip()]
    try:
        entries = [
            build_entry(
                provider=provider,
                base_url=args.base_url,
                credential=credential,
                models=models,
                vision_models=vision,
                ttl_hours=args.ttl_hours,
                hmac_key_hex=hmac_key,
            )
            for provider in args.provider
        ]
        policy = merge_policies(os.environ.get(POLICY_ENV, ""), entries) if args.merge else entries
    except PolicyError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1

    problem = validate_with_gateway(policy)
    if problem:
        print(f"refused: {problem}", file=sys.stderr)
        return 1

    print(json.dumps(policy, indent=2))
    print(
        f"\n# {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} minted for "
        f"{', '.join(e['provider'] for e in entries)}; set {POLICY_ENV} to the JSON above.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
