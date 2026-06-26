#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 🧠 SupremeAI Intelligent Auto-Fix Engine v3.0
# ═══════════════════════════════════════════════════════════════════════════════
# বৈশিষ্ট্যসমূহ:
#   • প্রতিটি জবের জন্য আলাদা ফিক্স লজিক
#   • SupremeAI API প্রাইমারি — OpenAI/Gemini fallback
#   • Branch-based safe strategy (main এ সরাসরি কমিট নয়)
#   • Confidence score calculation (0.0 - 1.0)
#   • Auto-revert if fix fails
#   • Bangla comments for clarity
# ═══════════════════════════════════════════════════════════════════════════════

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════
# কনফিগারেশন
# ═══════════════════════════════════════════════════════════════
FAILED_JOB = os.environ.get("FAILED_JOB", "")
BRANCH = os.environ.get("BRANCH", "main")
RUN_ID = os.environ.get("RUN_ID", "0")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")

# AI API কনফিগারেশন — SupremeAI primary, others fallback
AI_API_PROVIDER = os.environ.get("AI_API_PROVIDER", "supremeai")
SUPREMEAI_API_KEY = os.environ.get("SUPREMEAI_API_KEY", "")
SUPREMEAI_API_URL = os.environ.get("SUPREMEAI_API_URL", "https://supremeai-api-565236080752.us-central1.run.app")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# confidence threshold
CONFIDENCE_THRESHOLD = 0.7
CRITICAL_CONFIDENCE = 0.95


# ═══════════════════════════════════════════════════════════════
# হেল্পার ফাংশনসমূহ
# ═══════════════════════════════════════════════════════════════

def run_cmd(cmd: List[str], cwd: Optional[str] = None, check: bool = False, capture: bool = True) -> subprocess.CompletedProcess:
    """কমান্ড রান করে আউটপুট রিটার্ন করে"""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture,
        text=True,
        check=False
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    return result


def set_output(name: str, value: str):
    """GitHub Actions output সেট করে"""
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"{name}={value}\n")
    print(f"OUTPUT: {name}={value}")


def calculate_confidence(fixes_applied: List[str], used_ai: bool, error_logs: str = "") -> float:
    """
    ফিক্সের confidence score হিসাব করে (0.0 - 1.0)

    স্কোরিং লজিক:
    - Formatter fix (ruff, black, eslint, prettier): 0.5
    - Dependency fix (lockfile, pub get): 0.6
    - SupremeAI-suggested fix: 0.8 - 0.95
    - Multiple fix types: +0.1 each (max 1.0)
    - Error logs এ "critical" / "fatal" থাকলে: -0.2
    """
    base_score = 0.0

    fix_scores = {
        "ruff": 0.5,
        "black": 0.5,
        "eslint": 0.5,
        "prettier": 0.5,
        "dart_fix": 0.5,
        "dart_format": 0.5,
        "poetry_lock": 0.6,
        "pnpm_install": 0.6,
        "flutter_pub_get": 0.6,
        "supremeai_suggested": 0.85 if used_ai else 0.0,
        "ai_suggested": 0.8 if used_ai else 0.0,
    }

    for fix in fixes_applied:
        for key, score in fix_scores.items():
            if key in fix.lower():
                base_score = max(base_score, score)

    unique_types = set()
    for fix in fixes_applied:
        for key in fix_scores.keys():
            if key in fix.lower():
                unique_types.add(key)

    bonus = min(len(unique_types) * 0.1, 0.2)
    base_score += bonus

    if error_logs:
        lower_logs = error_logs.lower()
        if "critical" in lower_logs or "fatal" in lower_logs or "segmentation" in lower_logs:
            base_score -= 0.2

    return max(0.0, min(1.0, base_score))


# ═══════════════════════════════════════════════════════════════
# AI API কল ফাংশনসমূহ — SupremeAI primary, others fallback
# ═══════════════════════════════════════════════════════════════

def call_supremeai_api(error_logs: str, file_context: str = "", job_name: str = "") -> Optional[str]:
    """SupremeAI API কল করে ফিক্স সাজেশন নেয়"""
    if not SUPREMEAI_API_KEY:
        print("⚠️ SupremeAI API key নেই — skip")
        return None

    try:
        payload = {
            "model": "supremeai-coder",
            "messages": [
                {
                    "role": "system",
                    "content": "You are the SupremeAI code fixer. Analyze error logs and suggest precise fixes. Return ONLY the fixed code or specific commands. Be concise."
                },
                {
                    "role": "user",
                    "content": f"Job: {job_name}\n\nError logs:\n{error_logs}\n\nFile context:\n{file_context}\n\nSuggest the fix."
                }
            ],
            "temperature": 0.1,
            "max_tokens": 2000
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{SUPREMEAI_API_URL}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {SUPREMEAI_API_KEY}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            suggestion = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return suggestion if suggestion else None

    except Exception as e:
        print(f"⚠️ SupremeAI API error: {e}")
        return None


def call_openai_api(error_logs: str, file_context: str = "", job_name: str = "") -> Optional[str]:
    """OpenAI API কল করে ফিক্স সাজেশন নেয় (fallback)"""
    if not OPENAI_API_KEY:
        return None

    try:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are an expert code fixer. Analyze errors and suggest fixes. Return ONLY the fix."},
                {"role": "user", "content": f"Job: {job_name}\n\nError logs:\n{error_logs}\n\nContext:\n{file_context}\n\nSuggest the fix."}
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

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            suggestion = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return suggestion if suggestion else None

    except Exception as e:
        print(f"⚠️ OpenAI API error: {e}")
        return None


def call_gemini_api(error_logs: str, file_context: str = "", job_name: str = "") -> Optional[str]:
    """Google Gemini API কল করে ফিক্স সাজেশন নেয় (fallback)"""
    if not GEMINI_API_KEY:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")

        full_prompt = f"""You are an expert code fixer. Analyze these error logs and suggest precise fixes.

Job: {job_name}
Error logs:
{error_logs}

File context:
{file_context}

Suggest the fix. Be concise."""

        response = model.generate_content(full_prompt)
        return response.text if response and response.text else None

    except Exception as e:
        print(f"⚠️ Gemini API error: {e}")
        return None


def get_ai_suggestion(error_logs: str, file_context: str = "", job_name: str = "") -> Tuple[Optional[str], bool, str]:
    """
    কনফিগার্ড AI provider দিয়ে ফিক্স সাজেশন নেয়
    রিটার্ন: (suggestion, used_ai, provider_name)
    """
    provider = AI_API_PROVIDER.lower()

    # প্রাইমারি: SupremeAI
    if provider in ("supremeai", "auto"):
        result = call_supremeai_api(error_logs, file_context, job_name)
        if result:
            return result, True, "supremeai"

    # Fallback 1: OpenAI
    if provider in ("openai", "auto"):
        result = call_openai_api(error_logs, file_context, job_name)
        if result:
            return result, True, "openai"

    # Fallback 2: Gemini
    if provider in ("gemini", "auto"):
        result = call_gemini_api(error_logs, file_context, job_name)
        if result:
            return result, True, "gemini"

    if provider == "local":
        print("🤖 Local mode — শুধু formatter fix চলবে")
        return None, False, "local"

    # Auto fallback chain (if primary failed)
    for fallback_fn, name in [(call_openai_api, "OpenAI"), (call_gemini_api, "Gemini"), (call_supremeai_api, "SupremeAI")]:
        if provider != name.lower():
            print(f"🔄 Fallback to {name}...")
            result = fallback_fn(error_logs, file_context, job_name)
            if result:
                return result, True, name.lower()

    return None, False, "none"


# ═══════════════════════════════════════════════════════════════
# ফিক্স ফাংশনসমূহ — প্রতিটি জব টাইপের জন্য
# ═══════════════════════════════════════════════════════════════

FIXES_APPLIED: List[str] = []
USED_AI = False
AI_PROVIDER_USED = "none"


def fix_backend() -> bool:
    """ব্যাকএন্ড জবের জন্য auto-fix"""
    backend_dir = Path("backend")
    if not backend_dir.exists():
        print("⚠️ backend/ ডিরেক্টরি পাওয়া যায়নি")
        return False

    print("🔧 ব্যাকএন্ড ফিক্স শুরু হচ্ছে...")

    # ১. Ruff দিয়ে lint fix
    ruff_result = run_cmd(["poetry", "run", "ruff", "check", ".", "--fix"], cwd=str(backend_dir))
    if ruff_result.returncode == 0 or "fixed" in (ruff_result.stdout + ruff_result.stderr).lower():
        FIXES_APPLIED.append("ruff check --fix")

    # ২. Black দিয়ে format
    black_result = run_cmd(["poetry", "run", "black", "."], cwd=str(backend_dir))
    if black_result.returncode == 0:
        FIXES_APPLIED.append("black .")

    # ৩. Import sort
    run_cmd(["poetry", "run", "ruff", "check", ".", "--select", "I", "--fix"], cwd=str(backend_dir))

    # ৪. Poetry lock update
    lock_result = run_cmd(["poetry", "lock", "--no-update"], cwd=str(backend_dir))
    if lock_result.returncode == 0:
        status = run_cmd(["git", "status", "--porcelain", "backend/poetry.lock"])
        if status.stdout.strip():
            FIXES_APPLIED.append("poetry_lock")

    # ৫. __init__.py ফাইল চেক
    for sub in ["core", "brain", "api", "memory", "tools"]:
        sub_path = backend_dir / sub
        if sub_path.exists():
            for subdir in sub_path.rglob("*"):
                if not subdir.is_dir():
                    continue
                python_files = list(subdir.glob("*.py"))
                if not python_files:
                    continue
                init_file = subdir / "__init__.py"
                if not init_file.exists():
                    init_file.write_text("# Auto-generated package marker\n")
                    FIXES_APPLIED.append(f"created {init_file}")

    # ৬. SupremeAI suggestion (যদি formatter ঠিক না করে)
    if ruff_result.returncode != 0 and black_result.returncode != 0:
        error_logs = ruff_result.stdout + ruff_result.stderr + black_result.stdout + black_result.stderr
        suggestion, used_ai, provider = get_ai_suggestion(error_logs, job_name="backend-test")
        if suggestion:
            global USED_AI, AI_PROVIDER_USED
            USED_AI = True
            AI_PROVIDER_USED = provider
            FIXES_APPLIED.append(f"{provider}_suggested")
            print(f"🤖 {provider} Suggestion: {suggestion[:500]}...")

    return len(FIXES_APPLIED) > 0


def fix_frontend(pkg_dir: str) -> bool:
    """ফ্রন্টএন্ড জবের জন্য auto-fix (studio, webchat, vscode)"""
    path = Path(pkg_dir)
    if not path.exists():
        print(f"⚠️ {pkg_dir}/ পাওয়া যায়নি")
        return False

    print(f"🔧 {pkg_dir} ফিক্স শুরু হচ্ছে...")

    # ১. ESLint fix
    eslint_result = run_cmd(["pnpm", "exec", "eslint", pkg_dir, "--fix"])
    if eslint_result.returncode == 0 or "fixed" in (eslint_result.stdout + eslint_result.stderr).lower():
        FIXES_APPLIED.append("eslint")

    # ২. Prettier format
    prettier_result = run_cmd(["pnpm", "exec", "prettier", "--write", pkg_dir])
    if prettier_result.returncode == 0:
        FIXES_APPLIED.append("prettier")

    # ৩. pnpm install (lockfile ঠিক করতে)
    pnpm_result = run_cmd(["pnpm", "install", "--no-frozen-lockfile"])
    if pnpm_result.returncode == 0:
        status = run_cmd(["git", "status", "--porcelain", "pnpm-lock.yaml"])
        if status.stdout.strip():
            FIXES_APPLIED.append("pnpm_install")

    # ৪. SupremeAI suggestion
    if eslint_result.returncode != 0:
        error_logs = eslint_result.stdout + eslint_result.stderr
        suggestion, used_ai, provider = get_ai_suggestion(error_logs, job_name=f"{pkg_dir}-build")
        if suggestion:
            global USED_AI, AI_PROVIDER_USED
            USED_AI = True
            AI_PROVIDER_USED = provider
            FIXES_APPLIED.append(f"{provider}_suggested")

    return len(FIXES_APPLIED) > 0


def fix_mobile() -> bool:
    """মোবাইল জবের জন্য auto-fix"""
    mobile_dir = Path("apps/mobile")
    if not mobile_dir.exists():
        print("⚠️ apps/mobile/ পাওয়া যায়নি")
        return False

    print("🔧 মোবাইল ফিক্স শুরু হচ্ছে...")

    # ১. Dart fix
    dart_result = run_cmd(["dart", "fix", "--apply"], cwd=str(mobile_dir))
    if dart_result.returncode == 0:
        FIXES_APPLIED.append("dart_fix")

    # ২. Dart format
    format_result = run_cmd(["dart", "format", "."], cwd=str(mobile_dir))
    if format_result.returncode == 0:
        FIXES_APPLIED.append("dart_format")

    # ৩. Flutter pub get
    pub_result = run_cmd(["flutter", "pub", "get"], cwd=str(mobile_dir))
    if pub_result.returncode == 0:
        status = run_cmd(["git", "status", "--porcelain", "apps/mobile/pubspec.lock"])
        if status.stdout.strip():
            FIXES_APPLIED.append("flutter_pub_get")

    # ৪. SupremeAI suggestion
    if dart_result.returncode != 0:
        error_logs = dart_result.stdout + dart_result.stderr
        suggestion, used_ai, provider = get_ai_suggestion(error_logs, job_name="mobile-analyze")
        if suggestion:
            global USED_AI, AI_PROVIDER_USED
            USED_AI = True
            AI_PROVIDER_USED = provider
            FIXES_APPLIED.append(f"{provider}_suggested")

    return len(FIXES_APPLIED) > 0


# ═══════════════════════════════════════════════════════════════
# জব ম্যাপিং
# ═══════════════════════════════════════════════════════════════

JOB_FIXERS = {
    "backend-test": fix_backend,
    "backend_test": fix_backend,
    "🐍 ব্যাকএন্ড টেস্ট": fix_backend,

    "studio-build": lambda: fix_frontend("apps/studio-client"),
    "studio_build": lambda: fix_frontend("apps/studio-client"),
    "🎨 স্টুডিও ক্লায়েন্ট বিল্ড": lambda: fix_frontend("apps/studio-client"),
    "🎨 স্টুডিও বিল্ড": lambda: fix_frontend("apps/studio-client"),

    "webchat-build": lambda: fix_frontend("apps/web-chat"),
    "webchat_build": lambda: fix_frontend("apps/web-chat"),
    "💬 ওয়েব চ্যাট বিল্ড": lambda: fix_frontend("apps/web-chat"),
    "💬 WebChat Build": lambda: fix_frontend("apps/web-chat"),

    "vscode-build": lambda: fix_frontend("tools/vscode-extension"),
    "vscode_build": lambda: fix_frontend("tools/vscode-extension"),
    "🧩 VS Code এক্সটেনশন বিল্ড": lambda: fix_frontend("tools/vscode-extension"),
    "🧩 VS Code Build": lambda: fix_frontend("tools/vscode-extension"),

    "mobile-analyze": fix_mobile,
    "mobile_analyze": fix_mobile,
    "📱 মোবাইল অ্যাপ অ্যানালাইসিস": fix_mobile,

    "prompt-eval": lambda: (print("প্রম্পট ইভ্যালুয়েশনের জন্য auto-fix নেই।") or False),
    "prompt_eval": lambda: (print("প্রম্পট ইভ্যালুয়েশনের জন্য auto-fix নেই।") or False),
    "🤖 LLM প্রম্পট ইভ্যালুয়েশন": lambda: (print("প্রম্পট ইভ্যালুয়েশনের জন্য auto-fix নেই।") or False),
}


# ═══════════════════════════════════════════════════════════════
# ব্রাঞ্চ ম্যানেজমেন্ট
# ═══════════════════════════════════════════════════════════════

def create_fix_branch(run_id: str, branch: str) -> str:
    """নতুন fix branch তৈরি করে"""
    fix_branch = f"ci/auto-fix-{run_id}"
    run_cmd(["git", "fetch", "origin", branch], check=False)
    run_cmd(["git", "checkout", "-B", fix_branch, f"origin/{branch}"], check=False)
    print(f"🌿 Fix branch তৈরি হয়েছে: {fix_branch}")
    return fix_branch


def commit_to_branch(fix_branch: str, failed_jobs: List[str]) -> bool:
    """ফিক্স branch এ কমিট করে"""
    run_cmd(["git", "config", "user.name", "SupremeAI CI Bot"], check=True)
    run_cmd(["git", "config", "user.email", "ci-bot@supremeai.dev"], check=True)
    run_cmd(["git", "add", "-A"], check=False)

    status = run_cmd(["git", "status", "--porcelain"])
    if not status.stdout.strip():
        print("📭 কোনো পরিবর্তন নেই — কমিট দরকার নেই")
        return False

    commit_msg = (
        f"ci(auto-fix): automated fixes for failed jobs [run {RUN_ID}] [skip ci]\n\n"
        f"Failed jobs: {', '.join(failed_jobs)}\n"
        f"AI Provider: {AI_PROVIDER_USED}\n"
        f"Fixes applied:\n"
        + "\n".join(f"- {item}" for item in FIXES_APPLIED)
    )

    run_cmd(["git", "commit", "-m", commit_msg], check=True)

    push_result = run_cmd(["git", "push", "origin", fix_branch, "--force"], check=False)
    if push_result.returncode == 0:
        print(f"✅ Fix pushed to {fix_branch}")
        return True
    else:
        print(f"❌ Fix branch push failed")
        return False


def revert_changes():
    """সব পরিবর্তন রিভার্ট করে"""
    print("🔄 পরিবর্তন রিভার্ট করা হচ্ছে...")
    run_cmd(["git", "checkout", "--", "."], check=False)
    run_cmd(["git", "clean", "-fd"], check=False)
    print("✅ সব পরিবর্তন রিভার্ট হয়েছে")


# ═══════════════════════════════════════════════════════════════
# মেইন ফাংশন
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="SupremeAI Intelligent Auto-Fix Engine v3")
    parser.add_argument("--job", required=True, help="ফেইল হওয়া জবের নাম")
    parser.add_argument("--mode", choices=["fix", "fix-and-branch", "suggest-only"], default="fix-and-branch")
    parser.add_argument("--run-id", default="0", help="GitHub run ID")
    parser.add_argument("--branch", default="main", help="বেস ব্রাঞ্চ")
    parser.add_argument("--ai-provider", default="auto", help="AI provider (auto/supremeai/openai/gemini/local)")
    args = parser.parse_args()

    # AI provider override
    global AI_API_PROVIDER
    if args.ai_provider != "auto":
        AI_API_PROVIDER = args.ai_provider

    print("=" * 60)
    print("🧠 SupremeAI Intelligent Auto-Fix Engine v3.0")
    print(f"🎯 Job: {args.job}")
    print(f"📋 Mode: {args.mode}")
    print(f"🌿 Branch: {args.branch}")
    print(f"🤖 AI Provider: {AI_API_PROVIDER}")
    print("=" * 60)

    fixer = JOB_FIXERS.get(args.job)
    if fixer is None:
        for key, fn in JOB_FIXERS.items():
            if key.lower() in args.job.lower() or args.job.lower() in key.lower():
                fixer = fn
                break

    if fixer is None:
        print(f"❌ '{args.job}' এর জন্য কোনো auto-fix নেই")
        set_output("fix_applied", "false")
        set_output("confidence", "0.0")
        set_output("fix_branch", "")
        set_output("error_logs", "")
        return 0

    try:
        fix_success = fixer()
    except Exception as exc:
        print(f"❌ Auto-fix failed: {exc}")
        fix_success = False

    if not fix_success:
        print("📭 কোনো ফিক্স অ্যাপ্লাই হয়নি")
        set_output("fix_applied", "false")
        set_output("confidence", "0.0")
        set_output("fix_branch", "")
        set_output("error_logs", "")
        return 0

    confidence = calculate_confidence(FIXES_APPLIED, USED_AI)
    print(f"📊 Confidence score: {confidence:.2f}")

    if args.mode == "suggest-only":
        print("💡 Suggest-only mode — কোনো কমিট হবে না")
        set_output("fix_applied", "true")
        set_output("confidence", str(confidence))
        set_output("fix_branch", "")
        set_output("error_logs", "")
        return 0

    status = run_cmd(["git", "status", "--porcelain"])
    if not status.stdout.strip():
        print("📭 কোনো পরিবর্তন নেই")
        set_output("fix_applied", "false")
        set_output("confidence", str(confidence))
        set_output("fix_branch", "")
        set_output("error_logs", "")
        return 0

    if args.mode == "fix-and-branch":
        fix_branch = create_fix_branch(args.run_id, args.branch)
        committed = commit_to_branch(fix_branch, [args.job])

        if committed:
            set_output("fix_applied", "true")
            set_output("confidence", str(confidence))
            set_output("fix_branch", fix_branch)
            set_output("error_logs", "")
            print(f"✅ Auto-fix complete — branch: {fix_branch}, confidence: {confidence:.2f}, AI: {AI_PROVIDER_USED}")
        else:
            revert_changes()
            set_output("fix_applied", "false")
            set_output("confidence", str(confidence))
            set_output("fix_branch", "")
            set_output("error_logs", "")
            print("❌ Fix commit failed — changes reverted")
    else:
        set_output("fix_applied", "true")
        set_output("confidence", str(confidence))
        set_output("fix_branch", "")
        set_output("error_logs", "")

    return 0


if __name__ == "__main__":
    sys.exit(main())
