#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 🧠 SupremeAI Evaluator — Phase 4
# ═══════════════════════════════════════════════════════════════════════════════
# এই স্ক্রিপ্ট CI রিপোর্টের পর চলে
# কাজ:
#   • সব error logs + fixed code → SupremeAI live API /v1/ci/evaluate
#   • SupremeAI returns: confidence, risk_level, deploy_recommendation
#   • Fallback: OpenAI/Gemini দিয়ে cross-validate
#   • Output: evaluator_result JSON
# ═══════════════════════════════════════════════════════════════════════════════

import json
import os
import sys
import urllib.request
from typing import Dict, Optional, Tuple

# ═══════════════════════════════════════════════════════════════
# কনফিগারেশন
# ═══════════════════════════════════════════════════════════════
SUPREMEAI_API_URL = os.environ.get("SUPREMEAI_API_URL", "")
SUPREMEAI_API_KEY = os.environ.get("SUPREMEAI_API_KEY", "")
SUPREMEAI_EVALUATOR_ENDPOINT = os.environ.get("SUPREMEAI_EVALUATOR_ENDPOINT", "/v1/ci/evaluate")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
AI_API_PROVIDER = os.environ.get("AI_API_PROVIDER", "supremeai")

FAILED_JOBS = os.environ.get("FAILED_JOBS", "[]")
FIX_BRANCHES = os.environ.get("FIX_BRANCHES", "")
OVERALL_CONFIDENCE = os.environ.get("OVERALL_CONFIDENCE", "0.0")

GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")
GITHUB_SHA = os.environ.get("GITHUB_SHA", "")
GITHUB_REF_NAME = os.environ.get("GITHUB_REF_NAME", "")
GITHUB_RUN_ID = os.environ.get("GITHUB_RUN_ID", "")


def set_output(name: str, value: str):
    """GitHub Actions output সেট করে"""
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"{name}={value}\n")
    print(f"OUTPUT: {name}={value}")


def call_supremeai_evaluator(error_logs: str, fixed_code: str, job_context: str) -> Optional[Dict]:
    """SupremeAI live API দিয়ে evaluate করে"""
    if not SUPREMEAI_API_URL or not SUPREMEAI_API_KEY:
        print("⚠️ SupremeAI API credentials নেই — evaluator skip")
        return None

    evaluate_url = f"{SUPREMEAI_API_URL}{SUPREMEAI_EVALUATOR_ENDPOINT}"

    try:
        payload = {
            "repository": GITHUB_REPOSITORY,
            "commit_sha": GITHUB_SHA,
            "branch": GITHUB_REF_NAME,
            "run_id": GITHUB_RUN_ID,
            "failed_jobs": json.loads(FAILED_JOBS) if FAILED_JOBS else [],
            "fix_branches": FIX_BRANCHES.split(",") if FIX_BRANCHES else [],
            "overall_confidence": float(OVERALL_CONFIDENCE),
            "error_logs": error_logs,
            "fixed_code_summary": fixed_code,
            "job_context": job_context
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            evaluate_url,
            data=data,
            headers={
                "Authorization": f"Bearer {SUPREMEAI_API_KEY}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"✅ SupremeAI Evaluator response received")
            return result

    except Exception as e:
        print(f"⚠️ SupremeAI Evaluator error: {e}")
        return None


def call_openai_evaluator(error_logs: str, fixed_code: str, job_context: str) -> Optional[Dict]:
    """OpenAI দিয়ে evaluate করে (fallback)"""
    if not OPENAI_API_KEY:
        return None

    try:
        prompt = f"""You are an expert CI/CD evaluator. Analyze the following CI failure and auto-fix attempt, then provide a structured evaluation.

Repository: {GITHUB_REPOSITORY}
Commit: {GITHUB_SHA}
Branch: {GITHUB_REF_NAME}
Run ID: {GITHUB_RUN_ID}

Failed Jobs: {FAILED_JOBS}
Fix Branches: {FIX_BRANCHES}
Overall Confidence (from auto-fix): {OVERALL_CONFIDENCE}

Error Logs:
{error_logs}

Fixed Code Summary:
{fixed_code}

Job Context:
{job_context}

Evaluate and return ONLY a JSON object with this exact structure:
{{
  "final_confidence": 0.0-1.0,
  "risk_assessment": "safe" | "caution" | "dangerous",
  "deploy_recommended": true | false,
  "human_review_required": true | false,
  "reasoning": "detailed explanation"
}}"""

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are an expert CI/CD evaluator. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 2000
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            # JSON extract from markdown code block if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            eval_result = json.loads(content)
            print(f"✅ OpenAI Evaluator response received")
            return eval_result

    except Exception as e:
        print(f"⚠️ OpenAI Evaluator error: {e}")
        return None


def call_gemini_evaluator(error_logs: str, fixed_code: str, job_context: str) -> Optional[Dict]:
    """Gemini দিয়ে evaluate করে (fallback)"""
    if not GEMINI_API_KEY:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt = f"""You are an expert CI/CD evaluator. Analyze the following CI failure and auto-fix attempt, then provide a structured evaluation.

Repository: {GITHUB_REPOSITORY}
Commit: {GITHUB_SHA}
Branch: {GITHUB_REF_NAME}
Run ID: {GITHUB_RUN_ID}

Failed Jobs: {FAILED_JOBS}
Fix Branches: {FIX_BRANCHES}
Overall Confidence (from auto-fix): {OVERALL_CONFIDENCE}

Error Logs:
{error_logs}

Fixed Code Summary:
{fixed_code}

Job Context:
{job_context}

Evaluate and return ONLY a JSON object with this exact structure:
{{
  "final_confidence": 0.0-1.0,
  "risk_assessment": "safe" | "caution" | "dangerous",
  "deploy_recommended": true | false,
  "human_review_required": true | false,
  "reasoning": "detailed explanation"
}}"""

        response = model.generate_content(prompt)
        content = response.text if response and response.text else ""

        # JSON extract
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        eval_result = json.loads(content)
        print(f"✅ Gemini Evaluator response received")
        return eval_result

    except Exception as e:
        print(f"⚠️ Gemini Evaluator error: {e}")
        return None


def get_evaluator_result(error_logs: str = "", fixed_code: str = "", job_context: str = "") -> Tuple[Dict, str]:
    """
    সব provider দিয়ে evaluate করে সবচেয়ে ভালো result রিটার্ন করে
    রিটার্ন: (result_dict, provider_name)
    """
    provider = AI_API_PROVIDER.lower()

    # প্রাইমারি: SupremeAI
    if provider in ("supremeai", "auto"):
        result = call_supremeai_evaluator(error_logs, fixed_code, job_context)
        if result:
            return result, "supremeai"

    # Fallback 1: OpenAI
    if provider in ("openai", "auto"):
        result = call_openai_evaluator(error_logs, fixed_code, job_context)
        if result:
            return result, "openai"

    # Fallback 2: Gemini
    if provider in ("gemini", "auto"):
        result = call_gemini_evaluator(error_logs, fixed_code, job_context)
        if result:
            return result, "gemini"

    # Auto fallback chain
    for fn, name in [(call_openai_evaluator, "openai"), (call_gemini_evaluator, "gemini"), (call_supremeai_evaluator, "supremeai")]:
        if provider != name:
            print(f"🔄 Fallback to {name} evaluator...")
            result = fn(error_logs, fixed_code, job_context)
            if result:
                return result, name

    # সব failed — default conservative result
    print("❌ সব evaluator failed — conservative default returning")
    return {
        "final_confidence": 0.3,
        "risk_assessment": "dangerous",
        "deploy_recommended": False,
        "human_review_required": True,
        "reasoning": "All AI evaluators failed. Manual review required."
    }, "none"


def main():
    print("=" * 60)
    print("🧠 SupremeAI Evaluator — Phase 4")
    print("=" * 60)

    # Error logs সংগ্রহ (CI report থেকে)
    error_logs = ""
    fixed_code = ""
    job_context = f"""
Repository: {GITHUB_REPOSITORY}
Branch: {GITHUB_REF_NAME}
Commit: {GITHUB_SHA}
Run ID: {GITHUB_RUN_ID}
Failed Jobs: {FAILED_JOBS}
Fix Branches: {FIX_BRANCHES}
Auto-fix Confidence: {OVERALL_CONFIDENCE}
"""

    # Evaluator চালান
    result, provider = get_evaluator_result(error_logs, fixed_code, job_context)

    # Result validate
    final_confidence = float(result.get("final_confidence", 0.0))
    risk_assessment = result.get("risk_assessment", "dangerous")
    deploy_recommended = result.get("deploy_recommended", False)
    human_review_required = result.get("human_review_required", True)
    reasoning = result.get("reasoning", "No reasoning provided")

    # Confidence cap
    final_confidence = max(0.0, min(1.0, final_confidence))

    # Risk level validate
    if risk_assessment not in ("safe", "caution", "dangerous"):
        risk_assessment = "dangerous"

    print("\n" + "=" * 60)
    print("📊 Evaluator Result")
    print("=" * 60)
    print(f"  Provider: {provider}")
    print(f"  Final Confidence: {final_confidence:.2f}")
    print(f"  Risk Assessment: {risk_assessment}")
    print(f"  Deploy Recommended: {deploy_recommended}")
    print(f"  Human Review Required: {human_review_required}")
    print(f"  Reasoning: {reasoning[:200]}...")
    print("=" * 60)

    # Output set
    set_output("final_confidence", str(final_confidence))
    set_output("risk_assessment", risk_assessment)
    set_output("deploy_recommended", "true" if deploy_recommended else "false")
    set_output("human_review_required", "true" if human_review_required else "false")
    set_output("reasoning", reasoning)

    return 0


if __name__ == "__main__":
    sys.exit(main())
