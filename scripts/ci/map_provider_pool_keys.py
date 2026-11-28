#!/usr/bin/env python3
"""Map Infisical-exported key aliases into LLM_PROVIDER_KEYS for the CI gate.

The semantic PR gate runs the verifier from the trusted base (main), whose
pool scan and model defaults may lag behind vault naming or model reality.
This workflow step (which runs the PR head's workflow file) reads every
documented vault alias for each provider family from the process env and
emits the unified `LLM_PROVIDER_KEYS` JSON the trusted-base verifier already
consumes - with an explicit, deployment-verified model per family so an
exhausted free-tier model (gemini-2.5-flash) is not retried forever.

Values are never printed; only names and counts are logged.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

MAX_NUMBERED = 12
MIN_KEY_LEN = 16
PLACEHOLDERS = {"", "changeme", "your-key-here", "xxx", "none", "null", "test"}

# family -> (env alias names in priority order, default model)
# Aliases mirror gateway/provider_chain.py and .env.example.
FAMILIES: dict[str, tuple[tuple[str, ...], str]] = {
    "gemini": (
        ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_AI_API_KEY", "GEMINI_TOKEN", "JULES_API_KEY", "SUPREMEAI_PROVIDER_KEY_GEMINI", "GEMINI_API_KEYS"),
        "gemini-flash-lite-latest",
    ),
    "groq": (("GROQ_API_KEY", "SUPREMEAI_PROVIDER_KEY_GROQ", "GROQ_API_KEYS"), "llama-3.3-70b-versatile"),
    "openai": (("OPENAI_API_KEY", "SUPREMEAI_PROVIDER_KEY_OPENAI", "OPENAI_API_KEYS"), "gpt-4o-mini"),
    "openrouter": (("OPENROUTER_API_KEY", "SUPREMEAI_PROVIDER_KEY_OPENROUTER", "OPENROUTER_API_KEYS"), "meta-llama/llama-3.3-70b-instruct:free"),
    "deepseek": (("DEEPSEEK_API_KEY", "SUPREMEAI_PROVIDER_KEY_DEEPSEEK", "DEEPSEEK_API_KEYS"), "deepseek-chat"),
    "mistral": (("MISTRAL_API_KEY", "SUPREMEAI_PROVIDER_KEY_MISTRAL", "MISTRAL_API_KEYS"), "mistral-small-latest"),
}

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
FAMILY_URLS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "mistral": "https://api.mistral.ai/v1/chat/completions",
}


def _model_for(family: str) -> str:
    overrides = {
        "gemini": ("EVALUATOR_GEMINI_MODEL", "GEMINI_MODEL"),
        "groq": ("EVALUATOR_GROQ_MODEL", "GROQ_MODEL"),
    }
    for name in overrides.get(family, ()):
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return FAMILIES[family][1]


def _url_for(family: str, model: str) -> str:
    if family == "gemini":
        return GEMINI_URL.format(model=model)
    return FAMILY_URLS[family]


def _usable(value: str) -> bool:
    v = value.strip().strip("'\"")
    return len(v) >= MIN_KEY_LEN and v.lower() not in PLACEHOLDERS


def _family_values(family: str) -> list[str]:
    aliases, _ = FAMILIES[family]
    values: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        for i in range(1, MAX_NUMBERED + 1):
            name = alias if i == 1 else f"{alias}_{i}"
            raw = os.environ.get(name, "").strip().strip("'\"")
            if not raw:
                continue
            for token in raw.split(","):
                token = token.strip().strip("'\"")
                if _usable(token) and token not in seen:
                    values.append(token)
                    seen.add(token)
            break  # numbered slots are alternatives, not additive
    return values


def build_pool() -> dict[str, list[dict[str, str]]]:
    pool: dict[str, list[dict[str, str]]] = {}
    for family in FAMILIES:
        model = _model_for(family)
        url = _url_for(family, model)
        entries = [{"key": v, "url": url, "model": model} for v in _family_values(family)]
        if entries:
            pool[family] = entries
    return pool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--append-env",
        nargs="?",
        const=os.environ.get("GITHUB_ENV", ""),
        default=None,
        help="Append LLM_PROVIDER_KEYS to this env file (defaults to $GITHUB_ENV)",
    )
    args = parser.parse_args(argv)

    pool = build_pool()
    total = sum(len(v) for v in pool.values())
    families = ", ".join(f"{k}:{len(v)}" for k, v in pool.items()) or "none"
    print(f"[POOL-MAP] mapped {total} key(s) across families: {families} (values never logged)")
    if not total:
        return 0

    if args.append_env:
        # Single-line JSON keeps GITHUB_ENV parsing simple; values are masked
        # by Actions because they originate from exported secrets.
        with open(args.append_env, "a", encoding="utf-8") as fh:
            fh.write(f"LLM_PROVIDER_KEYS={json.dumps(pool, separators=(',', ':'))}\n")
        print("[POOL-MAP] LLM_PROVIDER_KEYS written for the trusted-base gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
