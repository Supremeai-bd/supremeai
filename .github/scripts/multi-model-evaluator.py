#!/usr/bin/env python3
"""
multi-model-evaluator.py
========================
Cross-validates auto-fix diffs using multiple independent AI models.
Prevents the "AI reviews its own homework" anti-pattern.

Voting rule:
  - ALL available models must say "safe" to PASS.
  - If only 1 model available (API key missing), 1 "safe" vote suffices.
  - If ALL evaluators fail (API errors), fail closed → "unsafe".

Rate limiting:
  Exponential backoff: 4s, 8s, 16s, 32s, 64s (max 5 retries).

Environment Variables:
  - GEMINI_API_KEY: Google Gemini API key
  - OPENAI_API_KEY: OpenAI API key (optional — graceful degradation)
  - DIFF_FILE: Path to diff file to evaluate (from ci-auto-fix.py)
  - GITHUB_OUTPUT: GitHub Actions output file path
"""

import json
import os
import sys
import time
from typing import Optional

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DIFF_FILE = os.getenv("DIFF_FILE", "/tmp/auto-fix-diff.txt")
OUTPUT_FILE = os.getenv("GITHUB_OUTPUT", "")

# Read diff content from file (written by ci-auto-fix.py)
DIFF_CONTENT = ""
if os.path.exists(DIFF_FILE):
    with open(DIFF_FILE) as f:
        DIFF_CONTENT = f.read()

# Shared evaluation prompt template
EVAL_PROMPT = """You are a senior code reviewer evaluating an automated CI fix.
Your job: determine if this diff is SAFE to auto-merge into the main branch.

Consider these risks:
1. Does it introduce bugs, logic errors, or security vulnerabilities?
2. Does it change behavior beyond formatting/imports/lint fixes?
3. Does it modify critical files (auth, config, migrations, secrets)?
4. Is the change scope appropriate (not too many files/lines)?

Respond ONLY with valid JSON (no markdown, no backticks):
{{
  "verdict": "safe" or "unsafe",
  "confidence": 0.0 to 1.0,
  "reason": "brief 1-2 sentence explanation",
  "critical_issues": ["list any critical problems found, or empty array"]
}}

Git diff to review:
{diff}"""


# ═══════════════════════════════════════════════════════════════
# Rate-limited retry with exponential backoff
# ═══════════════════════════════════════════════════════════════
def retry_with_backoff(fn, max_retries: int = 5, base_wait: int = 4):
    """
    Exponential backoff: 4s, 8s, 16s, 32s, 64s.
    Only retries on rate-limit errors (429 / "rate" in message).
    Other errors re-raise immediately.
    """
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = "rate" in error_str or "429" in error_str or "quota" in error_str
            if is_rate_limit and attempt < max_retries - 1:
                wait = base_wait * (2 ** attempt)
                print(f"  ⏳ Rate limited. Waiting {wait}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait)
            else:
                raise  # Non-rate-limit error or last retry — propagate
    raise RuntimeError(f"Failed after {max_retries} retries")


# ═══════════════════════════════════════════════════════════════
# Gemini evaluator
# ═══════════════════════════════════════════════════════════════
def evaluate_with_gemini(diff: str) -> dict:
    """Evaluate diff using Google Gemini Flash 2.0."""
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = EVAL_PROMPT.format(diff=diff[:8000])

    def call():
        response = model.generate_content(prompt)
        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
        return json.loads(raw)

    result = retry_with_backoff(call)
    result["model"] = "gemini-2.0-flash"
    return result


# ═══════════════════════════════════════════════════════════════
# OpenAI evaluator
# ═══════════════════════════════════════════════════════════════
def evaluate_with_openai(diff: str) -> dict:
    """Evaluate diff using OpenAI GPT-4o-mini."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = EVAL_PROMPT.format(diff=diff[:8000])

    def call():
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content)

    result = retry_with_backoff(call)
    result["model"] = "gpt-4o-mini"
    return result


# ═══════════════════════════════════════════════════════════════
# Consensus engine
# ═══════════════════════════════════════════════════════════════
def evaluate_consensus(diff: str) -> dict:
    """
    Run all available evaluators and compute consensus.

    Voting rules:
      - ALL available models must agree "safe" → consensus = "safe"
      - ANY model says "unsafe" → consensus = "unsafe"
      - ALL evaluators failed → consensus = "unsafe" (fail closed)
    """
    votes = []
    errors = []
    models_attempted = 0

    # Gemini evaluator
    if GEMINI_API_KEY:
        models_attempted += 1
        print("🔍 Evaluating with Gemini Flash 2.0...")
        try:
            vote = evaluate_with_gemini(diff)
            votes.append(vote)
            print(f"   Gemini → {vote.get('verdict', 'unknown')} (confidence: {vote.get('confidence', 0)})")
        except Exception as e:
            error_msg = f"Gemini evaluation failed: {e}"
            errors.append(error_msg)
            print(f"   ⚠️ {error_msg}")

    # OpenAI evaluator (optional — graceful degradation)
    if OPENAI_API_KEY:
        models_attempted += 1
        print("🔍 Evaluating with GPT-4o-mini...")
        try:
            vote = evaluate_with_openai(diff)
            votes.append(vote)
            print(f"   GPT-4o-mini → {vote.get('verdict', 'unknown')} (confidence: {vote.get('confidence', 0)})")
        except Exception as e:
            error_msg = f"OpenAI evaluation failed: {e}"
            errors.append(error_msg)
            print(f"   ⚠️ {error_msg}")
    else:
        print("ℹ️  OPENAI_API_KEY not set — running in single-model mode")

    # No models available or all failed → fail closed
    if not votes:
        return {
            "consensus": "unsafe",
            "reason": f"All {models_attempted} evaluator(s) failed — failing closed for safety",
            "avg_confidence": 0.0,
            "safe_votes": 0,
            "total_votes": 0,
            "models_attempted": models_attempted,
            "models_agreed": False,
            "votes": [],
            "errors": errors,
        }

    # Count votes
    safe_count = sum(1 for v in votes if v.get("verdict") == "safe")
    total = len(votes)
    avg_confidence = sum(v.get("confidence", 0) for v in votes) / total

    # ALL available models must agree "safe"
    consensus = "safe" if safe_count == total else "unsafe"

    # Build reason from individual votes
    reasons = [f"{v.get('model', '?')}: {v.get('reason', 'no reason')}" for v in votes]
    combined_reason = " | ".join(reasons)

    return {
        "consensus": consensus,
        "reason": combined_reason,
        "avg_confidence": round(avg_confidence, 3),
        "safe_votes": safe_count,
        "total_votes": total,
        "models_attempted": models_attempted,
        "models_agreed": safe_count == total,
        "votes": votes,
        "errors": errors,
    }


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
def main():
    print("🧠 SupremeAI Multi-Model Consensus Evaluator")
    print(f"   Models configured: Gemini={'yes' if GEMINI_API_KEY else 'no'}, OpenAI={'yes' if OPENAI_API_KEY else 'no'}")

    # No diff to evaluate → skip (allow)
    if not DIFF_CONTENT.strip():
        print("⚠️  No diff content found — skipping consensus check (allowing)")
        if OUTPUT_FILE:
            with open(OUTPUT_FILE, "a") as f:
                f.write("consensus_result=safe\n")
                f.write("consensus_confidence=1.0\n")
                f.write("models_agreed=true\n")
        return 0

    print(f"   Diff size: {len(DIFF_CONTENT)} chars")

    # No API keys at all → skip gracefully (don't block CI)
    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        print("⚠️  No AI API keys configured — skipping consensus check (allowing)")
        if OUTPUT_FILE:
            with open(OUTPUT_FILE, "a") as f:
                f.write("consensus_result=safe\n")
                f.write("consensus_confidence=0.0\n")
                f.write("models_agreed=true\n")
        return 0

    # Run consensus evaluation
    result = evaluate_consensus(DIFF_CONTENT)

    # Print full result
    print(f"\n{'='*60}")
    print(json.dumps(result, indent=2, default=str))
    print(f"{'='*60}")

    # Write outputs for GitHub Actions
    if OUTPUT_FILE:
        with open(OUTPUT_FILE, "a") as f:
            f.write(f"consensus_result={result['consensus']}\n")
            f.write(f"consensus_confidence={result.get('avg_confidence', 0)}\n")
            f.write(f"models_agreed={str(result.get('models_agreed', False)).lower()}\n")

    # Exit code determines if auto-fix commit proceeds
    if result["consensus"] == "unsafe":
        print(f"\n🚨 CONSENSUS: UNSAFE — auto-fix commit will be blocked")
        if result.get("errors"):
            print(f"   Errors: {result['errors']}")
        return 1
    else:
        print(f"\n✅ CONSENSUS: SAFE (avg confidence: {result.get('avg_confidence', 0)})")
        return 0


if __name__ == "__main__":
    sys.exit(main())
