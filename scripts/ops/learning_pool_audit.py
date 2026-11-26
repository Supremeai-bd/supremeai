#!/usr/bin/env python3
"""learning_pool_audit.py — Reserve core keys, run parallel learning across all
remaining LLM API keys, and produce a full per-key audit report.

Usage:
    python scripts/ops/learning_pool_audit.py
    python scripts/ops/learning_pool_audit.py --reserve gemini:1,groq:1,openrouter:1
    python scripts/ops/learning_pool_audit.py --out audit_report.json
    python scripts/ops/learning_pool_audit.py --self-test
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# Reuse key discovery from zero_cost_capacity_probe if available
try:
    from scripts.ops.zero_cost_capacity_probe import keys_for
except ImportError:
    def keys_for(env: dict[str, str], names: tuple[str, ...]) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for base in names:
            candidates = [env.get(base, "")]
            for i in range(1, 100):
                val = env.get(f"{base}_{i}", "")
                if val:
                    candidates.append(val)
            for raw in candidates:
                for part in raw.split(","):
                    k = part.strip()
                    if k and k not in seen:
                        seen.add(k)
                        found.append(k)
        return found


DEFAULT_PROMPT = (
    "Give 1 practical, non-generic rule about human understanding, emotional subtext, "
    "or avoiding common AI mistakes. Keep it under 5 lines with 1 concrete example."
)

# (provider, env_names, default_model, endpoint_type)
PROVIDERS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("gemini", ("GEMINI_API_KEY",), "gemini-2.0-flash", "gemini"),
    ("groq", ("GROQ_API_KEY",), "llama-3.1-8b-instant", "openai"),
    ("openrouter", ("OPENROUTER_API_KEY",), "nvidia/nemotron-3.5-lightning:free", "openai"),
    ("nvidia", ("NVIDIA_API_KEY",), "meta/llama-3.1-8b-instruct", "openai"),
    ("kilo", ("KILO_API_KEY", "KILOCODE_API_KEY"), "nvidia/nemotron-3.5-lightning:free", "openai"),
)

OPENAI_ENDPOINTS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "nvidia": "https://integrate.api.nvidia.com/v1/chat/completions",
    "kilo": "https://ai-gateway.kilo.ai/api/v1/chat/completions",
}


def mask_key(key: str) -> str:
    return f"...{key[-4:]}" if len(key) >= 4 else "****"


def score_quality(text: str) -> int:
    """Simple 0-100 heuristic for output usefulness."""
    if not text or not text.strip():
        return 0
    length = len(text.strip())
    score = 30 if length >= 40 else 10
    if length >= 120:
        score += 30
    if "\n" in text or "-" in text or ":" in text:
        score += 20
    if "example" in text.lower() or "e.g." in text.lower() or "যেমন" in text:
        score += 20
    return min(score, 100)


def parse_reserve(spec: str) -> dict[str, int]:
    reserve: dict[str, int] = {}
    for item in spec.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        prov, count = item.split(":", 1)
        reserve[prov.strip().lower()] = max(0, int(count.strip()))
    return reserve


def build_pools(
    env: dict[str, str],
    reserve_spec: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split all discovered keys into (reserved, learning_pool)."""
    reserved: list[dict[str, Any]] = []
    learning: list[dict[str, Any]] = []

    for provider, env_names, model, kind in PROVIDERS:
        all_keys = keys_for(env, env_names)
        r_count = min(reserve_spec.get(provider, 0), len(all_keys))
        for idx, key in enumerate(all_keys):
            entry = {
                "provider": provider,
                "key_id": f"{provider}#{idx + 1}",
                "masked": mask_key(key),
                "key": key,
                "model": model,
                "kind": kind,
            }
            if idx < r_count:
                reserved.append({k: v for k, v in entry.items() if k != "key"})
            else:
                learning.append(entry)
    return reserved, learning


def call_one_key(entry: dict[str, Any], prompt: str, timeout: int = 20) -> dict[str, Any]:
    provider = entry["provider"]
    model = entry["model"]
    key = entry["key"]
    started = time.perf_counter()

    try:
        if entry["kind"] == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            headers = {"Content-Type": "application/json"}
        else:
            url = OPENAI_ENDPOINTS[provider]
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 250,
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            latency_ms = round((time.perf_counter() - started) * 1000)

        if entry["kind"] == "gemini":
            text = (
                raw.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
        else:
            text = raw.get("choices", [{}])[0].get("message", {}).get("content", "")

        return {
            "provider": provider,
            "key_id": entry["key_id"],
            "masked": entry["masked"],
            "model": model,
            "status": "active",
            "http_status": 200,
            "latency_ms": latency_ms,
            "output_chars": len(text),
            "quality_score": score_quality(text),
            "output": text.strip(),
        }
    except urllib.error.HTTPError as e:
        latency_ms = round((time.perf_counter() - started) * 1000)
        status = "rate_limited" if e.code == 429 else ("invalid" if e.code in (401, 403) else "error")
        return {
            "provider": provider,
            "key_id": entry["key_id"],
            "masked": entry["masked"],
            "model": model,
            "status": status,
            "http_status": e.code,
            "latency_ms": latency_ms,
            "output_chars": 0,
            "quality_score": 0,
            "error": str(e),
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - started) * 1000)
        return {
            "provider": provider,
            "key_id": entry["key_id"],
            "masked": entry["masked"],
            "model": model,
            "status": "error",
            "http_status": 0,
            "latency_ms": latency_ms,
            "output_chars": 0,
            "quality_score": 0,
            "error": str(e),
        }


def run_self_test() -> int:
    env = {
        "GEMINI_API_KEY": "g1,g2,g3",
        "GROQ_API_KEY": "q1,q2",
        "OPENROUTER_API_KEY": "o1",
    }
    reserve = parse_reserve("gemini:1,groq:1,openrouter:1")
    reserved, learning = build_pools(env, reserve)
    assert len(reserved) == 3, f"Expected 3 reserved, got {len(reserved)}"
    assert len(learning) == 3, f"Expected 3 learning, got {len(learning)}"
    assert score_quality("") == 0
    assert score_quality("Rule: Always check intent.\nExample: User says 'fine' when upset.") >= 70
    print("✅ learning_pool_audit.py self-test PASSED!")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Parallel LLM Learning Pool & Audit")
    parser.add_argument("--reserve", default="gemini:1,groq:1,openrouter:1", help="Keys to reserve per provider")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Learning prompt to send")
    parser.add_argument("--workers", type=int, default=20, help="Max parallel workers")
    parser.add_argument("--out", default="", help="Optional JSON file path to save full audit")
    parser.add_argument("--self-test", action="store_true", help="Run offline self-test")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    reserve_spec = parse_reserve(args.reserve)
    reserved, learning = build_pools(dict(os.environ), reserve_spec)

    print(f"Reserved keys: {len(reserved)} | Learning pool keys: {len(learning)}")
    if not learning:
        print("No learning keys found in environment.")
        return 0

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(call_one_key, entry, args.prompt) for entry in learning]
        for fut in concurrent.futures.as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda r: (r["provider"], r["key_id"]))
    active = [r for r in results if r["status"] == "active"]
    avg_latency = round(sum(r["latency_ms"] for r in active) / len(active)) if active else 0

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reserved_keys": reserved,
        "summary": {
            "total_learning_keys": len(results),
            "active_keys": len(active),
            "failed_or_limited": len(results) - len(active),
            "avg_active_latency_ms": avg_latency,
        },
        "results": results,
    }

    print(json.dumps(report["summary"], indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Full audit saved to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
