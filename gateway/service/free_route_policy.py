"""Local approval for zero-cost Gateway API routes. Defaults and keys are not approval.

Two kinds of surface need two kinds of proof
--------------------------------------------
A catalog provider proves it is free by listing a `:free` model
(`CATALOG_REQUIRED`). A *web slot* (`claude_web`, `chatgpt_web`, `gemini_v0_web`
…) has no catalog: it is a browser session on a consumer product, and the only
thing that can say "this is live and free right now" is the relay that is
holding the session. Until now such a slot was approved on the operator's word
alone — the single place in this policy where nothing was checked.

So a web-slot entry must carry `evidence`: which relay engine was observed, in
which state, and when. Approval then has two clocks — the operator's `expires_at`
and the evidence's own age — and the shorter one wins. Evidence is recorded from
a real relay `/health` read (`observed_at` is the relay's timestamp, not the
mint time), so an approval cannot outlive the cookie it was approving.

Why only the entry is dropped, never the whole policy
----------------------------------------------------
Structural errors still reject the entire policy (an unparseable entry means the
operator does not know what is in there). Stale evidence is different: the relay
cookie expired overnight and the provider routes that never depended on it
should keep serving. Dropping the policy as a whole would turn one dead cookie
into a total outage.
"""

import hmac
import json
import logging
import os
import re
import time
from datetime import datetime
from functools import lru_cache
from typing import NamedTuple
from urllib.parse import urlsplit

logger = logging.getLogger("supremeai.free_route_policy")
from .providers.web_engines import WEB_ENGINES_BY_PROVIDER

POLICY_ENV = "SUPREMEAI_FREE_ROUTE_POLICY"
HMAC_KEY_ENV = "SUPREMEAI_FREE_ROUTE_HMAC_KEY"
VISION_PROVIDERS = frozenset({"gemini", "openai", "openrouter"})
CATALOG_REQUIRED = frozenset({"openrouter", "kilo"})
EXCLUDED_MODELS = frozenset({"auto", "default", "kilo-auto/free", "kilo-auto/efficient", "openrouter/free"})
# Providers served by the browser relay: approval needs live session evidence,
# because no catalog can prove a consumer web session is free.
WEB_SLOT_PROVIDERS = frozenset(WEB_ENGINES_BY_PROVIDER)
EVIDENCE_KIND = "session"
# One cookie lifetime. Longer and the approval would outlive the thing it was
# approving; shorter and every operator re-mints several times a shift for
# nothing, which in practice means they stop running `--from-relay`.
EVIDENCE_MAX_AGE_S = 6 * 3600.0
EVIDENCE_STATES = frozenset({"OK", "EXPIRED", "CHALLENGED", "UNKNOWN"})

RouteIdentity = tuple[str, str, str]


class Evidence(NamedTuple):
    """What the relay said about this engine, as recorded in the approval."""

    engine: str
    state: str
    observed_at: float

    def age_s(self, now: float | None = None) -> float:
        return max(0.0, (time.time() if now is None else now) - self.observed_at)


class ApprovedRoute(NamedTuple):
    identity: RouteIdentity
    models: tuple[str, ...]
    evidence: Evidence | None = None


def _parse_evidence(provider: str, entry: object) -> tuple[bool, Evidence | None]:
    """`(usable, evidence)` for one entry's `evidence` field.

    `usable` is False only for a web slot whose evidence is missing, malformed,
    not `OK`, or for the wrong engine — the caller drops that entry and keeps
    the rest. Non-web providers return `(True, None)` unchanged, so existing
    openrouter/kilo approvals keep working exactly as before.
    """
    if provider not in WEB_SLOT_PROVIDERS:
        return True, None
    expected = WEB_ENGINES_BY_PROVIDER[provider].engine
    if not isinstance(entry, dict):
        logger.warning(
            "Free-route approval for web slot `%s` has no relay evidence; entry dropped", provider
        )
        return False, None
    engine = entry.get("engine")
    if engine != expected:
        logger.warning(
            "Free-route approval for `%s` cites engine `%r`, but that provider routes to `%s`; "
            "entry dropped — one engine's health cannot approve another's slot",
            provider, engine, expected,
        )
        return False, None
    state = entry.get("state")
    if state not in EVIDENCE_STATES or state != "OK":
        logger.warning(
            "Free-route approval for `%s` was recorded in state `%r`; only a live OK surface "
            "may be approved (entry dropped)", provider, state,
        )
        return False, None
    observed = entry.get("observed_at")
    try:
        stamp = datetime.fromisoformat(str(observed))
        if stamp.tzinfo is None:
            raise ValueError("naive timestamp")
        observed_at = stamp.timestamp()
    except (TypeError, ValueError):
        logger.warning(
            "Free-route approval for `%s` has an unusable evidence timestamp %r; entry dropped",
            provider, observed,
        )
        return False, None
    return True, Evidence(engine, state, observed_at)


def _https_base(url: str) -> str:
    target = urlsplit(url)
    if target.scheme != "https" or not target.hostname or target.username is not None or target.query or target.fragment:
        raise ValueError("invalid HTTPS base URL")
    return url.rstrip("/")


def credential_identity(provider: str, base_url: str, api_key: str) -> RouteIdentity | None:
    key_hex = os.getenv(HMAC_KEY_ENV, "")
    if not api_key or not re.fullmatch(r"[a-fA-F0-9]{64}", key_hex):
        return None
    try:
        base_url = _https_base(base_url)
        payload = json.dumps([provider, base_url, api_key], separators=(",", ":")).encode("utf-8")
        # A leaked approval tag must not enable guessing the provider secret
        # offline. The HMAC key is independent of provider and client keys.
        tag = hmac.digest(bytes.fromhex(key_hex), b"supremeai:free-route:v1\x00" + payload, "sha256")
        return provider, base_url, tag.hex()
    except (ValueError, TypeError, AttributeError):
        return None


@lru_cache(maxsize=1)
def _policy(
    raw: str,
) -> dict[RouteIdentity, tuple[float, tuple[str, ...], tuple[str, ...], Evidence | None]]:
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            raise ValueError("expected a list")
        policy = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("expected an entry")
            provider = entry["provider"]
            digest = entry["key_hmac_sha256"]
            if not isinstance(provider, str) or not re.fullmatch(r"[a-z0-9_]+", provider):
                raise ValueError("invalid provider")
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("invalid credential fingerprint")
            identity = (provider, _https_base(entry["base_url"]), digest)
            expires = datetime.fromisoformat(entry["expires_at"])
            if expires.tzinfo is None or identity in policy:
                raise ValueError("missing timezone or duplicate approval")
            models = entry["models"]
            if not isinstance(models, list) or not models or not all(
                isinstance(model, str) and model and model == model.strip()
                and model.lower() not in EXCLUDED_MODELS
                and (provider not in CATALOG_REQUIRED or model.endswith(":free"))
                for model in models
            ):
                raise ValueError("invalid concrete model list")
            vision = entry.get("vision_models", [])
            if not isinstance(vision, list) or any(model not in models for model in vision):
                raise ValueError("vision_models must be a subset of models")
            if vision and provider not in VISION_PROVIDERS:
                raise ValueError("vision provider unsupported")
            usable, evidence = _parse_evidence(provider, entry.get("evidence"))
            if not usable:
                continue
            policy[identity] = (
                expires.timestamp(),
                tuple(dict.fromkeys(models)),
                tuple(dict.fromkeys(vision)),
                evidence,
            )
        return policy
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
        logger.warning("Invalid SUPREMEAI_FREE_ROUTE_POLICY; no API routes approved")
        return {}


def approved_route(provider: str, base_url: str, api_key: str, *, vision: bool = False) -> ApprovedRoute | None:
    raw_policy = os.getenv(POLICY_ENV)
    if not raw_policy or (identity := credential_identity(provider, base_url, api_key)) is None:
        return None
    entry = _policy(raw_policy).get(identity)
    if entry is None:
        return None
    expiry, models, vision_models, evidence = entry
    now = time.time()
    allowed_models = vision_models if vision else models
    if not allowed_models or now >= expiry:
        return None
    if evidence is not None:
        age = evidence.age_s(now)
        if age > EVIDENCE_MAX_AGE_S:
            # Evaluated per call, not in the cached parse: the cache is keyed by
            # the env string, so a decision made there would never age.
            logger.warning(
                "Free-route approval for `%s` cites %.1fh-old relay evidence (limit %.0fh); "
                "re-mint with --from-relay", identity[0], age / 3600, EVIDENCE_MAX_AGE_S / 3600,
            )
            return None
    return ApprovedRoute(identity, allowed_models, evidence)
