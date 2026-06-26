#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 🩺 SupremeAI CI Health Check — Phase 0
# ═══════════════════════════════════════════════════════════════════════════════
# এই স্ক্রিপ্ট CI শুরু হওয়ার আগে চলে
# চেক করে:
#   • SupremeAI live API reachable কিনা
#   • Backup Cloud Run server healthy কিনা
#   • কোন AI provider ব্যবহার করা যাবে
#   • API down থাকলে external AI fallback
# ═══════════════════════════════════════════════════════════════════════════════

import json
import os
import sys
import time
import urllib.request
from typing import Dict, Optional, Tuple

# ═══════════════════════════════════════════════════════════════
# কনফিগারেশন
# ═══════════════════════════════════════════════════════════════
SUPREMEAI_API_URL = os.environ.get("SUPREMEAI_API_URL", "")
SUPREMEAI_API_KEY = os.environ.get("SUPREMEAI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

BACKUP_SERVICE_NAME = os.environ.get("BACKUP_SERVICE_NAME", "supremeai-api-backup")
BACKUP_REGION = os.environ.get("BACKUP_REGION", "us-east1")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
GCP_SA_KEY = os.environ.get("GCP_SA_KEY", "")
SKIP_BACKUP = os.environ.get("SKIP_BACKUP", "false").lower() == "true"

# Health check timeout (seconds)
HEALTH_TIMEOUT = 30
RETRY_ATTEMPTS = 3


def set_output(name: str, value: str):
    """GitHub Actions output সেট করে"""
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"{name}={value}\n")
    print(f"OUTPUT: {name}={value}")


def check_supremeai_api() -> Tuple[bool, str]:
    """
    SupremeAI live API চেক করে
    রিটার্ন: (available, provider_to_use)
    """
    if not SUPREMEAI_API_URL:
        print("⚠️ SUPREMEAI_API_URL সেট নেই")
        return False, "openai"

    # Health endpoint ট্রাই করুন (যদি থাকে)
    health_url = f"{SUPREMEAI_API_URL}/health"

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            print(f"🩺 SupremeAI API health check (attempt {attempt}/{RETRY_ATTEMPTS}): {health_url}")

            req = urllib.request.Request(
                health_url,
                headers={
                    "Authorization": f"Bearer {SUPREMEAI_API_KEY}" if SUPREMEAI_API_KEY else "",
                    "Accept": "application/json"
                },
                method="GET"
            )

            with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8")
                    print(f"✅ SupremeAI API UP — Response: {body[:200]}")
                    return True, "supremeai"
                else:
                    print(f"⚠️ SupremeAI API returned status {resp.status}")

        except urllib.error.HTTPError as e:
            # 401/403 মানে API আছে কিন্তু auth issue — এটা acceptable
            if e.code in (401, 403):
                print(f"✅ SupremeAI API reachable (auth required — expected)")
                return True, "supremeai"
            print(f"⚠️ SupremeAI API HTTP error: {e.code}")

        except Exception as e:
            print(f"⚠️ SupremeAI API error: {e}")

        if attempt < RETRY_ATTEMPTS:
            print(f"⏳ অপেক্ষা... (retry in 3s)")
            time.sleep(3)

    print("❌ SupremeAI API DOWN — fallback to external AI")
    return False, "openai"


def check_openai_api() -> bool:
    """OpenAI API available কিনা চেক করে"""
    if not OPENAI_API_KEY:
        return False

    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Accept": "application/json"
            },
            method="GET"
        )

        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
            if resp.status == 200:
                print("✅ OpenAI API available")
                return True
    except Exception as e:
        print(f"⚠️ OpenAI API error: {e}")

    return False


def check_gemini_api() -> bool:
    """Gemini API available কিনা চেক করে"""
    if not GEMINI_API_KEY:
        return False

    try:
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models?key=" + GEMINI_API_KEY,
            headers={"Accept": "application/json"},
            method="GET"
        )

        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
            if resp.status == 200:
                print("✅ Gemini API available")
                return True
    except Exception as e:
        print(f"⚠️ Gemini API error: {e}")

    return False


def check_backup_server() -> Tuple[bool, str]:
    """
    Backup Cloud Run server health check
    রিটার্ন: (healthy, last_deploy_info)
    """
    if SKIP_BACKUP:
        print("⏭️ Backup check skipped (manual override)")
        return True, "skipped"

    if not GCP_SA_KEY or not GCP_PROJECT_ID:
        print("⚠️ GCP credentials নেই — backup check skip")
        return True, "no-credentials"

    # gcloud CLI দিয়ে backup service describe করুন
    import subprocess

    try:
        # gcloud auth activate
        result = subprocess.run(
            ["gcloud", "auth", "activate-service-account", "--key-file", "-"],
            input=GCP_SA_KEY.encode(),
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            print(f"⚠️ gcloud auth failed: {result.stderr}")
            return True, "auth-failed"

        # Backup service describe
        result = subprocess.run(
            ["gcloud", "run", "services", "describe", BACKUP_SERVICE_NAME,
             "--region", BACKUP_REGION,
             "--project", GCP_PROJECT_ID,
             "--format", "json"],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            print(f"⚠️ Backup service not found: {result.stderr}")
            return False, "not-found"

        service_info = json.loads(result.stdout)

        # সর্বশেষ revision এর তথ্য
        traffic = service_info.get("status", {}).get("traffic", [])
        if traffic:
            latest_revision = traffic[0].get("revisionName", "unknown")
            latest_url = traffic[0].get("url", "")

            # URL দিয়ে health check
            if latest_url:
                health_url = f"{latest_url}/health"
                try:
                    req = urllib.request.Request(health_url, method="GET", timeout=HEALTH_TIMEOUT)
                    with urllib.request.urlopen(req) as resp:
                        if resp.status == 200:
                            print(f"✅ Backup server healthy — revision: {latest_revision}")
                            return True, latest_revision
                except Exception as e:
                    print(f"⚠️ Backup health check failed: {e}")
                    return False, latest_revision

        return True, "unknown"

    except Exception as e:
        print(f"⚠️ Backup check error: {e}")
        return True, "error"


def determine_active_provider(supremeai_available: bool, openai_available: bool, gemini_available: bool) -> str:
    """
    কোন AI provider active হবে তা ঠিক করে
    Priority: supremeai > openai > gemini > local
    """
    if supremeai_available:
        return "supremeai"
    elif openai_available:
        return "openai"
    elif gemini_available:
        return "gemini"
    else:
        return "local"


def main():
    print("=" * 60)
    print("🩺 SupremeAI CI Health Check — Phase 0")
    print("=" * 60)

    # ১. SupremeAI API check
    supremeai_available, _ = check_supremeai_api()

    # ২. OpenAI API check (fallback)
    openai_available = check_openai_api() if not supremeai_available else False

    # ৩. Gemini API check (fallback)
    gemini_available = check_gemini_api() if not supremeai_available and not openai_available else False

    # ৪. Active provider ঠিক করুন
    active_provider = determine_active_provider(supremeai_available, openai_available, gemini_available)

    # ৫. Backup server check
    backup_healthy, backup_info = check_backup_server()

    # ৬. রিপোর্ট
    print("\n" + "=" * 60)
    print("📊 Health Check Summary")
    print("=" * 60)
    print(f"  SupremeAI API: {'✅ UP' if supremeai_available else '❌ DOWN'}")
    print(f"  OpenAI API:    {'✅ UP' if openai_available else '❌ DOWN'}")
    print(f"  Gemini API:    {'✅ UP' if gemini_available else '❌ DOWN'}")
    print(f"  Active Provider: {active_provider}")
    print(f"  Backup Server: {'✅ Healthy' if backup_healthy else '❌ Unhealthy'} ({backup_info})")
    print("=" * 60)

    # Output set করুন
    set_output("supremeai_available", "true" if supremeai_available else "false")
    set_output("backup_available", "true" if backup_healthy else "false")
    set_output("active_provider", active_provider)
    set_output("main_health_url", f"{SUPREMEAI_API_URL}/health" if SUPREMEAI_API_URL else "")
    set_output("backup_health_url", f"https://{BACKUP_SERVICE_NAME}-{BACKUP_REGION}-a.run.app/health" if backup_healthy else "")
    set_output("backup_last_deploy", backup_info)

    # Warning দিন যদি SupremeAI down থাকে
    if not supremeai_available:
        print("\n⚠️ WARNING: SupremeAI API is DOWN — using external AI fallback")
        print("   CI will continue but with reduced confidence in auto-fixes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
