"""Local approval for zero-cost Gateway API routes. Defaults and keys are not approval."""

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from functools import lru_cache
from urllib.parse import urlsplit

logger = logging.getLogger("supremeai.free_route_policy")
POLICY_ENV = "SUPREMEAI_FREE_ROUTE_POLICY"
VISION_PROVIDERS = frozenset({"gemini", "openai", "openrouter"})
CATALOG_REQUIRED = frozenset({"openrouter", "kilo"})
EXCLUDED_MODELS = frozenset({"auto", "default", "kilo-auto/free", "kilo-auto/efficient", "openrouter/free"})


def _https_base(url: str) -> str:
    target = urlsplit(url)
    if target.scheme != "https" or not target.hostname or target.username is not None or target.query or target.fragment:
        raise ValueError("invalid HTTPS base URL")
    return url.rstrip("/")


@lru_cache(maxsize=1)
def _policy(raw: str) -> dict[tuple[str, str, str], tuple[float, tuple[str, ...], tuple[str, ...]]]:
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            raise ValueError("expected a list")
        policy = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("expected an entry")
            provider = entry["provider"]
            digest = entry["key_sha256"]
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
            policy[identity] = (expires.timestamp(), tuple(dict.fromkeys(models)), tuple(dict.fromkeys(vision)))
        return policy
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
        logger.warning("Invalid SUPREMEAI_FREE_ROUTE_POLICY; no API routes approved")
        return {}


def approved_models(provider: str, base_url: str, api_key: str, *, vision: bool = False) -> tuple[str, ...]:
    if not api_key:
        return ()
    try:
        identity = (provider, _https_base(base_url), hashlib.sha256(api_key.encode()).hexdigest())
    except (ValueError, TypeError, AttributeError):
        return ()
    expiry, models, vision_models = _policy(os.getenv(POLICY_ENV, "[]")).get(identity, (0.0, (), ()))
    if time.time() >= expiry:
        return ()
    return vision_models if vision else models
